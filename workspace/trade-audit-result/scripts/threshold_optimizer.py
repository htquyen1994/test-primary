"""
Threshold Optimizer — Entry Point
====================================
Automated tuning of scoring weights and alert thresholds based on labeled outcomes.

Usage:
    python threshold_optimizer.py                       # analyze + recommend (dry-run)
    python threshold_optimizer.py --step=analyze        # step 1: stats only
    python threshold_optimizer.py --step=recommend      # step 1+2: add recommendations
    python threshold_optimizer.py --step=apply          # step 1+2+3: apply to DB (dry-run)
    python threshold_optimizer.py --step=apply --apply  # actually write to DB
    python threshold_optimizer.py --lookback=60         # use 60 days of history

What it does:
  1. Load labeled signals from DB + outcome cache (or simulate via Binance API)
  2. Sweep alert threshold 50–95 → find optimal EV point
  3. Analyze each module's predictive power (AUC-ROC, correlation)
  4. Optimize weight multipliers via coordinate descent
  5. Analyze per-regime win rates
  6. Generate recommendations with confidence levels
  7. Optionally apply to DB (creates new trading_params version)
  8. Write Markdown report

Output files:
    workspace/trade-audit-result/YYYY-MM-DD/tuning/
        tuning_report.md
        recommendation.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import io
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

# ── Path setup ────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).parent
_WORKSPACE  = _SCRIPT_DIR.parent.parent          # workspace/
sys.path.insert(0, str(_WORKSPACE / "backend-workspace"))
sys.path.insert(0, str(_WORKSPACE / "trading-core"))
sys.path.insert(0, str(_SCRIPT_DIR))

# Fix Windows console encoding
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("threshold_optimizer")

# ── DB connection ─────────────────────────────────────────────────────────────

def _connect():
    """Open a pyodbc connection using DATABASE_URL from .env"""
    import pyodbc

    env_path = _WORKSPACE / "backend-workspace" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    env_path2 = _WORKSPACE / "backend-workspace" / ".env"
    if env_path2.exists():
        for line in env_path2.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()   # force-set (not setdefault)

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not found in .env")
    url_part = db_url.replace("mssql+pyodbc://", "").split("?")[0]
    userinfo, hostdb = url_part.split("@", 1)
    username, password = userinfo.split(":", 1)
    password = unquote(password)
    hostport, database = hostdb.split("/", 1)
    server = hostport.replace(":", ",")

    for drv in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]:
        try:
            cs = (
                f"DRIVER={{{drv}}};SERVER={server};DATABASE={database};"
                f"UID={username};PWD={password};TrustServerCertificate=yes"
            )
            conn = pyodbc.connect(cs, timeout=10)
            logger.info("Connected to SQL Server (%s): %s/%s", drv, server, database)
            return conn
        except Exception:
            continue
    raise RuntimeError("Could not connect to SQL Server (tried ODBC 17 and 18)")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(step: str, lookback_days: int, apply: bool, out_dir: Path) -> None:
    from tuning.outcome_loader   import OutcomeLoader
    from tuning.threshold_analyzer import ThresholdAnalyzer
    from tuning.weight_analyzer    import WeightAnalyzer
    from tuning.regime_analyzer    import RegimeAnalyzer
    from tuning.recommender        import Recommender
    from tuning.config_applier     import ConfigApplier
    from tuning.report_writer      import ReportWriter

    temp_dir = _SCRIPT_DIR.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*64}")
    print(f"  THRESHOLD OPTIMIZER — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Step: {step.upper()} | Lookback: {lookback_days}d | Apply: {apply}")
    print(f"{'='*64}\n")

    # ── Connect to DB ─────────────────────────────────────────────────────────
    conn = _connect()

    # ── Step 1: Load labeled outcomes ─────────────────────────────────────────
    print("[1/5] Loading labeled outcomes...")
    loader = OutcomeLoader(conn, temp_dir, lookback_days=lookback_days)
    df_all = loader.load()
    df = OutcomeLoader.to_labeled(df_all)

    n_all     = len(df_all)
    n_labeled = len(df)
    n_pending = int((df_all.get("outcome", "") == "PENDING").sum()) if not df_all.empty else 0

    print(f"      Total signals (with SL/TP): {n_all}")
    print(f"      Labeled (WIN/LOSS): {n_labeled} | PENDING: {n_pending}")

    if n_labeled == 0:
        print("\n  [!] No labeled signals (WIN/LOSS) — cannot run optimization.")
        print("      System needs ALERT/WATCH signals with SL/TP that have resolved.")
        print("      Re-run after signals have had 8+ hours to hit TP or SL.\n")
        # Still show score distribution for near-threshold signals
        if not df_all.empty:
            _print_score_distribution(df_all, _get_current_threshold(conn))
        _write_stub_report(out_dir, n_all, n_pending)
        conn.close()
        return

    if n_labeled < 5:
        print(f"\n  [!] Only {n_labeled} labeled signal(s) — results will be unreliable.")
        print("      Need ≥ 20 for recommendations, ≥ 50 for HIGH confidence.\n")

    if step == "analyze":
        _print_sample_stats(df)
        _print_score_distribution(df_all, _get_current_threshold(conn))
        conn.close()
        return

    # ── Step 2: Analysis ──────────────────────────────────────────────────────
    print("[2/5] Running threshold analysis...")
    current_t = _get_current_threshold(conn)
    ta = ThresholdAnalyzer().analyze(df, current_threshold=current_t)
    _print_threshold_summary(ta)

    print("[3/5] Running weight analysis...")
    wa = WeightAnalyzer().analyze(df)
    _print_weight_summary(wa)

    print("[4/5] Running regime analysis...")
    ra = RegimeAnalyzer().analyze(df)
    _print_regime_summary(ra)

    if step == "analyze":
        conn.close()
        return

    # ── Step 3: Recommend ─────────────────────────────────────────────────────
    print("[5a/5] Generating recommendations...")
    current_params = _get_current_params(conn)
    recommender = Recommender(current_params)
    rec = recommender.recommend(ta, wa, ra)
    _print_recommendations(rec)

    # Save recommendation JSON
    rec_path = out_dir / "recommendation.json"
    rec.save(rec_path)

    apply_result = None
    if step in ("apply", "all"):
        # ── Step 4: Apply ─────────────────────────────────────────────────────
        print(f"\n[5b/5] {'Applying' if apply else 'Dry-run applying'} recommendations...")
        applier = ConfigApplier(conn, dry_run=not apply)
        apply_result = applier.apply(rec)
        _print_apply_result(apply_result)

    # ── Step 5: Write report ──────────────────────────────────────────────────
    print("\n[5/5] Writing report...")
    report_path = out_dir / "tuning_report.md"
    ReportWriter().write(report_path, ta, wa, ra, rec, apply_result)
    print(f"\n  Report: {report_path}")
    print(f"  Recommendation JSON: {rec_path}\n")

    conn.close()

    print(f"{'='*64}")
    print(f"  Done — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*64}\n")


# ── Print helpers ─────────────────────────────────────────────────────────────

def _print_score_distribution(df_all: "pd.DataFrame", current_t: int) -> None:
    """Show score distribution for near-threshold signals (no outcome needed)."""
    if df_all.empty or "final_score" not in df_all.columns:
        return
    print(f"\n  Score distribution (near-threshold signals, N={len(df_all)}):")
    print(f"  {'Range':<12} {'Count':>6}  bar")
    for lo, hi in [(50,54),(55,59),(60,64),(65,69),(70,74),(75,79),(80,84),(85,100)]:
        mask = (df_all["final_score"] >= lo) & (df_all["final_score"] <= hi)
        n = int(mask.sum())
        marker = " <-- ALERT threshold" if lo == current_t else ""
        bar = "█" * min(n, 40)
        print(f"  {lo}-{hi:<8}  {n:>6}  {bar}{marker}")
    print()


def _print_sample_stats(df):
    n = len(df)
    wins  = int((df["outcome"] == "WIN").sum())
    losses = int((df["outcome"] == "LOSS").sum())
    wr = wins / n if n > 0 else 0
    print(f"\n  Sample: N={n} | WIN={wins} ({wr:.1%}) | LOSS={losses}")
    if "regime" in df.columns:
        for regime, grp in df.groupby("regime"):
            w = int((grp["outcome"] == "WIN").sum())
            print(f"  {regime:<12}: N={len(grp)} | WIN={w} ({w/len(grp):.1%})")
    print()


def _print_threshold_summary(ta):
    cur = ta.current_stats
    opt = ta.optimal_stats
    if cur:
        print(f"  Current T={ta.current_threshold}: precision={cur.precision:.1%} "
              f"recall={cur.recall:.1%} EV={cur.ev:+.3f}")
    if opt and opt.threshold != ta.current_threshold:
        print(f"  Optimal T={ta.optimal_threshold}: precision={opt.precision:.1%} "
              f"recall={opt.recall:.1%} EV={opt.ev:+.3f} "
              f"[CI {opt.ev_ci_low:+.3f}~{opt.ev_ci_high:+.3f}]")
    else:
        print(f"  Current threshold appears near-optimal.")
    print()


def _print_weight_summary(wa):
    print(f"  AUC baseline: {wa.optimization.auc_baseline:.4f} "
          f"-> optimized: {wa.optimization.auc_optimized:.4f} "
          f"(+{wa.optimization.auc_improvement:.4f})")
    if wa.module_stats:
        print("  Module importance (by |correlation|):")
        for ms in wa.module_stats[:3]:
            sig = "sig" if ms.is_significant else "ns"
            print(f"    {ms.importance_rank}. {ms.name.upper():<6} "
                  f"AUC={ms.auc_roc:.3f} r={ms.correlation:+.3f} p={ms.p_value:.3f} [{sig}]")
    print()


def _print_regime_summary(ra):
    if ra.regimes:
        print("  Regime win rates:")
        for regime, rs in sorted(ra.regimes.items(), key=lambda x: -x[1].win_rate):
            flag = " <-- BLOCK?" if regime in ra.block_candidates else ""
            print(f"    {regime:<12}: {rs.win_rate:.1%} (N={rs.n}){flag}")
    print()


def _print_recommendations(rec):
    print(f"\n  {len(rec.recommendations)} recommendation(s):")
    if not rec.recommendations:
        print("    None — current params are near-optimal or sample too small.")
    for r in rec.recommendations:
        arrow = "+" if r.new_value > r.old_value else ""
        print(f"    [{r.confidence}] {r.param_name}: "
              f"{r.old_value} -> {r.new_value} (effect={arrow}{r.effect_size:.4f})")
    print()


def _print_apply_result(result):
    if result.get("dry_run"):
        print("  [DRY-RUN] No changes written.")
    elif result.get("applied"):
        print(f"  [APPLIED] New version: {result.get('new_version_tag')}")
    else:
        print(f"  [NOT APPLIED] {result.get('error', 'no changes')}")
    for c in result.get("changes", []):
        print(f"    {c['param']}: {c['old']} -> {c['new']}")
    for s in result.get("skipped", []):
        print(f"    SKIPPED {s.get('param','?')}: {s.get('reason','')}")
    print()


def _get_current_threshold(conn) -> int:
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT score_alert_threshold FROM dbo.trading_params "
            "WHERE is_active = 1 ORDER BY activated_at DESC"
        )
        row = cur.fetchone()
        return int(row[0]) if row else 75
    except Exception:
        return 75


def _get_current_params(conn) -> dict:
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM dbo.trading_params WHERE is_active = 1 "
            "ORDER BY activated_at DESC"
        )
        row = cur.fetchone()
        if not row:
            return {}
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    except Exception:
        return {}


def _write_stub_report(out_dir: Path, n_all: int, n_pending: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stub = out_dir / "tuning_report.md"
    stub.write_text(
        f"# Threshold Optimization Report — "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"## Status: INSUFFICIENT DATA\n\n"
        f"- Signals with SL/TP: {n_all}\n"
        f"- PENDING (< 8h old): {n_pending}\n"
        f"- Labeled WIN/LOSS: **0**\n\n"
        f"### What to do\n\n"
        f"1. Wait for ALERT/WATCH signals to resolve (TP or SL hit)\n"
        f"2. Run `validate_signals.py --step=2` to label outcomes\n"
        f"3. Re-run `threshold_optimizer.py`\n\n"
        f"*Minimum sample for recommendations: N ≥ 20 (WIN + LOSS)*\n",
        encoding="utf-8",
    )
    print(f"  Stub report written → {stub}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Automated threshold & weight optimizer for signal scoring",
    )
    parser.add_argument(
        "--step",
        choices=["analyze", "recommend", "apply", "all"],
        default="all",
        help="How far to run (default: all)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=30,
        help="Days of signal history to load (default: 30)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually write recommendations to DB (default: dry-run)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: trade-audit-result/YYYY-MM-DD/tuning/)",
    )
    args = parser.parse_args()

    out_dir = args.out_dir or (
        _SCRIPT_DIR.parent
        / datetime.now(timezone.utc).strftime("%Y-%m-%d")
        / "tuning"
    )

    run(
        step=args.step,
        lookback_days=args.lookback,
        apply=args.apply,
        out_dir=out_dir,
    )


if __name__ == "__main__":
    main()
