"""
Synthetic data test — verifies full optimizer pipeline without DB or Binance.

Run: python -m tuning.test_with_synthetic
     (from workspace/trade-audit-result/scripts/)

Creates 200 fake labeled signals with known patterns:
  - HIGH score (80+): 65% WIN  → optimizer should raise/keep threshold
  - MID score (65-79): 50% WIN → borderline
  - LOW score (50-64): 38% WIN → optimizer should raise threshold above 64
  - SMC is the most predictive module (injected signal)
  - VSA is noise (random)
"""
from __future__ import annotations

import sys, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from tuning.threshold_analyzer import ThresholdAnalyzer
from tuning.weight_analyzer    import WeightAnalyzer
from tuning.regime_analyzer    import RegimeAnalyzer
from tuning.recommender        import Recommender
from tuning.report_writer      import ReportWriter


def make_synthetic(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # Component scores
    smc   = rng.uniform(0, 30, n)   # most predictive
    of    = rng.uniform(0, 35, n)   # somewhat predictive
    vsa   = rng.uniform(0, 30, n)   # noise
    ctx   = rng.uniform(0, 15, n)   # noise
    bonus = rng.uniform(0, 15, n)   # noise
    rm    = rng.choice([0.85, 1.0, 0.6], n, p=[0.4, 0.5, 0.1])  # regime multiplier

    # Final score (raw formula)
    raw   = smc + of + vsa + ctx + bonus
    final = np.clip(np.round(raw * rm / 125 * 100), 0, 100).astype(int)

    # WIN probability driven primarily by SMC + OF (realistic signal)
    p_win = 0.25 + 0.012 * smc + 0.005 * of + rng.uniform(-0.05, 0.05, n)
    p_win = np.clip(p_win, 0.1, 0.85)
    outcome = np.where(rng.uniform(size=n) < p_win, "WIN", "LOSS")

    regime_map = {0.85: "CHOPPY", 1.0: "TRENDING", 0.6: "PARABOLIC"}
    regimes = [regime_map[r] for r in rm]

    return pd.DataFrame({
        "log_id":            [f"fake-{i}" for i in range(n)],
        "final_score":       final,
        "raw_score":         raw,
        "score_order_flow":  of,
        "score_smc":         smc,
        "score_vsa":         vsa,
        "score_context":     ctx,
        "score_bonus":       bonus,
        "regime":            regimes,
        "regime_multiplier": rm,
        "entry_price":       rng.uniform(100, 200, n),
        "stop_loss":         rng.uniform(95,  195, n),
        "take_profit_1":     rng.uniform(105, 215, n),
        "rr_ratio":          rng.uniform(1.5, 3.0, n),
        "mae_pct":           rng.uniform(0.1, 0.5, n),
        "mfe_pct":           rng.uniform(0.3, 1.5, n),
        "outcome":           outcome,
    })


def main():
    print("=" * 60)
    print("  SYNTHETIC DATA TEST — Threshold Optimizer")
    print("=" * 60)

    df = make_synthetic(200)
    n = len(df)
    wins = int((df["outcome"] == "WIN").sum())
    print(f"\nGenerated N={n} signals: WIN={wins} ({wins/n:.1%}), LOSS={n-wins} ({(n-wins)/n:.1%})")
    print(f"Score range: {df['final_score'].min()}–{df['final_score'].max()}")

    # ── 1. Threshold analysis ───────────────────────────────────────────────
    print("\n[1] Threshold Analysis...")
    ta = ThresholdAnalyzer().analyze(df, current_threshold=75)
    cur = ta.current_stats
    opt = ta.optimal_stats
    print(f"  Current T=75: precision={cur.precision:.1%} recall={cur.recall:.1%} EV={cur.ev:+.3f}")
    if opt:
        print(f"  Optimal T={opt.threshold}: precision={opt.precision:.1%} EV={opt.ev:+.3f}")

    if ta.buckets:
        print("  Score buckets:")
        for b, v in sorted(ta.buckets.items()):
            print(f"    {b}: win_rate={v['win_rate']:.1%} n={v['n']} EV={v['ev']:+.3f}")

    # ── 2. Weight analysis ───────────────────────────────────────────────────
    print("\n[2] Weight Analysis...")
    wa = WeightAnalyzer().analyze(df)
    print("  Module importance:")
    for ms in wa.module_stats:
        sig = "SIG" if ms.is_significant else "ns"
        print(f"    {ms.importance_rank}. {ms.name.upper():<6} AUC={ms.auc_roc:.3f} r={ms.correlation:+.3f} [{sig}]")

    opt_w = wa.optimization
    print(f"  AUC: {opt_w.auc_baseline:.4f} → {opt_w.auc_optimized:.4f} (+{opt_w.auc_improvement:.4f})")
    print(f"  Weights: { {k: v for k, v in opt_w.weights.items()} }")

    # ── 3. Regime analysis ───────────────────────────────────────────────────
    print("\n[3] Regime Analysis...")
    ra = RegimeAnalyzer().analyze(df)
    for regime, rs in sorted(ra.regimes.items(), key=lambda x: -x[1].win_rate):
        print(f"  {regime:<12}: win_rate={rs.win_rate:.1%} n={rs.n} → {rs.recommendation}")

    # ── 4. Recommendations ───────────────────────────────────────────────────
    print("\n[4] Recommendations...")
    rec = Recommender({}).recommend(ta, wa, ra)
    print(f"  Summary: {rec.summary}")
    for r in rec.recommendations:
        print(f"  [{r.confidence}] {r.param_name}: {r.old_value} → {r.new_value} (effect={r.effect_size:+.4f})")

    # ── 5. Report ────────────────────────────────────────────────────────────
    print("\n[5] Writing report...")
    out = Path(__file__).parent.parent.parent / "temp" / "synthetic_test_report.md"
    out.parent.mkdir(exist_ok=True)
    ReportWriter().write(out, ta, wa, ra, rec)
    print(f"  Report: {out}")

    # ── Assertions ────────────────────────────────────────────────────────────
    print("\n[OK] Assertions:")
    assert ta.optimal_stats is not None, "Should find optimal threshold"
    assert len(wa.module_stats) == 5, "Should analyze 5 modules"
    # SMC should rank #1 or #2 (most predictive in synthetic data)
    smc_rank = next(ms.importance_rank for ms in wa.module_stats if ms.name == "smc")
    assert smc_rank <= 2, f"SMC should rank 1-2, got {smc_rank}"
    assert wa.optimization.auc_optimized >= wa.optimization.auc_baseline - 0.001, "AUC should not decrease"
    assert ra.regimes, "Should have regime breakdown"
    print(f"  SMC rank: {smc_rank} (expected 1-2) ✓")
    print(f"  AUC: {wa.optimization.auc_baseline:.4f} → {wa.optimization.auc_optimized:.4f} ✓")
    print(f"  Optimal threshold: {ta.optimal_threshold} ✓")
    print("\n  ALL ASSERTIONS PASSED ✓\n")


if __name__ == "__main__":
    main()
