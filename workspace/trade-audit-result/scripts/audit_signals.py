"""
Signal Audit — SQL Server
==========================
Query signal_log, trade_journal, circuit_breaker_state.
Run: python audit_signals.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from _db import get_connection
from datetime import datetime, timezone
from sqlalchemy import text

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

def sep(title="", w=68):
    if title:
        print(f"\n=== {title} {'='*(w-len(title)-5)}")
    else:
        print("=" * w)

with get_connection() as conn:

    # ── Overview ──────────────────────────────────────────────────────────────
    sep("SIGNAL LOG OVERVIEW")
    r = conn.execute(text("""
        SELECT COUNT(*) as total,
               MIN(timestamp) as first_signal,
               MAX(timestamp) as last_signal,
               COUNT(DISTINCT asset) as assets,
               COUNT(DISTINCT strategy_name) as strategies
        FROM signal_log
    """)).fetchone()
    print(f"  Total signals:     {r.total:,}")
    print(f"  Date range:        {r.first_signal}  →  {r.last_signal}")
    print(f"  Unique assets:     {r.assets}")
    print(f"  Unique strategies: {r.strategies}")

    # ── By Classification ─────────────────────────────────────────────────────
    sep("ALL-TIME BY CLASSIFICATION")
    rows = conn.execute(text("""
        SELECT classification, COUNT(*) as cnt,
               AVG(CAST(final_score AS FLOAT)) as avg_score,
               MAX(final_score) as max_score
        FROM signal_log GROUP BY classification ORDER BY cnt DESC
    """)).fetchall()
    print(f"  {'Class':<10} {'Count':>8} {'Avg Score':>10} {'Max Score':>10}")
    print(f"  {'-'*10} {'-'*8} {'-'*10} {'-'*10}")
    for r in rows:
        print(f"  {r.classification:<10} {r.cnt:>8,} {r.avg_score:>10.1f} {r.max_score:>10}")

    # ── By Asset ──────────────────────────────────────────────────────────────
    sep("ALL-TIME BY ASSET")
    rows = conn.execute(text("""
        SELECT asset, COUNT(*) as cnt,
               SUM(CASE WHEN classification='ALERT' THEN 1 ELSE 0 END) as alerts,
               AVG(CAST(final_score AS FLOAT)) as avg_score,
               MAX(final_score) as max_score
        FROM signal_log GROUP BY asset ORDER BY cnt DESC
    """)).fetchall()
    print(f"  {'Asset':<14} {'Total':>8} {'ALERT':>7} {'Avg':>7} {'Max':>7}")
    print(f"  {'-'*14} {'-'*8} {'-'*7} {'-'*7} {'-'*7}")
    for r in rows:
        print(f"  {r.asset:<14} {r.cnt:>8,} {r.alerts:>7} {r.avg_score:>7.1f} {r.max_score:>7}")

    # ── By Strategy ───────────────────────────────────────────────────────────
    sep("ALL-TIME BY STRATEGY")
    rows = conn.execute(text("""
        SELECT strategy_name, COUNT(*) as cnt,
               SUM(CASE WHEN classification='ALERT' THEN 1 ELSE 0 END) as alerts,
               AVG(CAST(final_score AS FLOAT)) as avg_final,
               AVG(CAST(score_order_flow AS FLOAT)) as avg_of,
               AVG(CAST(score_smc AS FLOAT)) as avg_smc,
               AVG(CAST(score_vsa AS FLOAT)) as avg_vsa,
               AVG(CAST(score_context AS FLOAT)) as avg_ctx
        FROM signal_log GROUP BY strategy_name ORDER BY cnt DESC
    """)).fetchall()
    print(f"  {'Strategy':<22} {'Total':>7} {'ALERT':>6} {'Final':>6} {'OF':>5} {'SMC':>5} {'VSA':>5} {'CTX':>5}")
    print(f"  {'-'*22} {'-'*7} {'-'*6} {'-'*6} {'-'*5} {'-'*5} {'-'*5} {'-'*5}")
    for r in rows:
        print(f"  {r.strategy_name:<22} {r.cnt:>7,} {r.alerts:>6} {r.avg_final:>6.1f} {r.avg_of:>5.1f} {r.avg_smc:>5.1f} {r.avg_vsa:>5.1f} {r.avg_ctx:>5.1f}")

    # ── By Regime ─────────────────────────────────────────────────────────────
    sep("ALL-TIME BY REGIME")
    rows = conn.execute(text("""
        SELECT regime, COUNT(*) as cnt,
               SUM(CASE WHEN classification='ALERT' THEN 1 ELSE 0 END) as alerts,
               AVG(CAST(final_score AS FLOAT)) as avg_score
        FROM signal_log GROUP BY regime ORDER BY cnt DESC
    """)).fetchall()
    print(f"  {'Regime':<12} {'Total':>8} {'ALERT':>7} {'Avg Score':>10}")
    print(f"  {'-'*12} {'-'*8} {'-'*7} {'-'*10}")
    for r in rows:
        print(f"  {r.regime:<12} {r.cnt:>8,} {r.alerts:>7} {r.avg_score:>10.1f}")

    # ── Today's Signals ───────────────────────────────────────────────────────
    sep(f"TODAY'S SIGNALS ({TODAY})")
    rows = conn.execute(text("""
        SELECT timestamp, asset, timeframe, direction,
               raw_score, final_score,
               score_order_flow, score_smc, score_vsa, score_context, score_bonus,
               regime, regime_multiplier, funding_rate,
               portfolio_heat, correlated_group_risk,
               classification, user_action, expires_at_candle, strategy_name
        FROM signal_log
        WHERE CAST(timestamp AS DATE) = CAST(GETUTCDATE() AS DATE)
        ORDER BY timestamp DESC
    """)).fetchall()

    alerts  = [r for r in rows if r.classification == 'ALERT']
    watches = [r for r in rows if r.classification == 'WATCH']
    ignores = [r for r in rows if r.classification == 'IGNORE']
    print(f"  Total: {len(rows)} | ALERT: {len(alerts)} | WATCH: {len(watches)} | IGNORE: {len(ignores)}")

    if alerts:
        sep("TODAY — ALERT SIGNALS", w=50)
        for r in alerts:
            print(f"\n  [{r.timestamp}] {r.asset} {r.timeframe} {r.direction.upper()}")
            print(f"    Score: raw={r.raw_score:.1f} → final={r.final_score} | {r.classification}")
            print(f"    OF={r.score_order_flow:.0f} SMC={r.score_smc:.0f} VSA={r.score_vsa:.0f} CTX={r.score_context:.0f} Bonus={r.score_bonus:.0f}")
            print(f"    Regime: {r.regime} (×{r.regime_multiplier:.2f}) | Funding: {r.funding_rate:.4f}")
            print(f"    Action: {r.user_action or 'PENDING'}")
            # Validation
            if r.score_order_flow == 0 and r.final_score >= 75:
                print(f"    !! WARN: ALERT with Order Flow=0 (OB feed not running?)")
            if r.final_score > 60 and r.score_order_flow == 0:
                print(f"    !! WARN: Score > 60 but OB unavailable (data quality cap violated)")

    if rows:
        sep("TODAY — SCORE DISTRIBUTION", w=50)
        buckets = {"0-20": 0, "21-40": 0, "41-54": 0, "55-74 (WATCH)": 0, "75-100 (ALERT)": 0}
        for r in rows:
            s = r.final_score
            if s <= 20: buckets["0-20"] += 1
            elif s <= 40: buckets["21-40"] += 1
            elif s <= 54: buckets["41-54"] += 1
            elif s <= 74: buckets["55-74 (WATCH)"] += 1
            else: buckets["75-100 (ALERT)"] += 1
        for b, cnt in buckets.items():
            bar = "#" * (cnt * 25 // max(len(rows), 1))
            print(f"  {b:>18}: {cnt:>5} {bar}")

        sep("TODAY — AVG MODULE SCORES", w=50)
        avg_of  = sum(float(r.score_order_flow) for r in rows) / len(rows)
        avg_smc = sum(float(r.score_smc) for r in rows) / len(rows)
        avg_vsa = sum(float(r.score_vsa) for r in rows) / len(rows)
        avg_ctx = sum(float(r.score_context) for r in rows) / len(rows)
        avg_bon = sum(float(r.score_bonus) for r in rows) / len(rows)
        avg_fin = sum(float(r.final_score) for r in rows) / len(rows)
        print(f"  Order Flow:  {avg_of:>5.1f}/35  {'<< OB feed not running' if avg_of == 0 else ''}")
        print(f"  SMC:         {avg_smc:>5.1f}/30  {'<< LOW - check debug_smc.py' if avg_smc < 5 else ''}")
        print(f"  VSA:         {avg_vsa:>5.1f}/30")
        print(f"  Context:     {avg_ctx:>5.1f}/15")
        print(f"  Bonus:       {avg_bon:>5.1f}/15")
        print(f"  Final avg:   {avg_fin:>5.1f}/100")

        sep("TODAY — DATA QUALITY CHECK", w=50)
        of_zero = sum(1 for r in rows if r.score_order_flow == 0)
        cap_violated = sum(1 for r in rows if r.final_score > 60 and r.score_order_flow == 0)
        print(f"  Signals with Order Flow = 0:   {of_zero}/{len(rows)} ({of_zero/len(rows)*100:.0f}%)")
        print(f"  Score > 60 but OF = 0:         {cap_violated}  (should be 0)")
        if cap_violated > 0:
            print(f"  !! DATA QUALITY CAP NOT ENFORCED for {cap_violated} signals")
        else:
            print(f"  Data quality cap: OK")
    else:
        sep("NO SIGNALS TODAY — RECENT 20 SIGNALS", w=50)
        rows = conn.execute(text("""
            SELECT TOP 20 timestamp, asset, timeframe, direction,
                   final_score, classification, regime, strategy_name,
                   score_order_flow, score_smc, score_vsa, score_context
            FROM signal_log ORDER BY timestamp DESC
        """)).fetchall()
        for r in rows:
            print(f"  [{r.timestamp}] {r.asset} {r.timeframe} {r.direction.upper()} | score={r.final_score} | {r.classification} | {r.regime}")

    # ── Top 10 Highest Scoring ────────────────────────────────────────────────
    sep("TOP 10 HIGHEST SCORING SIGNALS (all time)")
    rows = conn.execute(text("""
        SELECT TOP 10 timestamp, asset, timeframe, direction,
               final_score, classification, regime, strategy_name, user_action,
               score_order_flow, score_smc, score_vsa, score_context, score_bonus
        FROM signal_log ORDER BY final_score DESC, timestamp DESC
    """)).fetchall()
    for r in rows:
        action = r.user_action or "PENDING"
        print(f"  [{r.timestamp}] {r.asset} {r.timeframe} {r.direction.upper()} | score={r.final_score} | {r.classification} | {r.regime} | {action}")
        print(f"    OF={r.score_order_flow:.0f} SMC={r.score_smc:.0f} VSA={r.score_vsa:.0f} CTX={r.score_context:.0f} Bonus={r.score_bonus:.0f}")

    # ── Circuit Breaker ───────────────────────────────────────────────────────
    sep("CIRCUIT BREAKER STATE")
    try:
        rows = conn.execute(text("""
            SELECT TOP 5 trigger_type, trigger_detail, triggered_at, unlock_at,
                   regime_at_trigger, is_locked, unlock_requires_review,
                   unlocked_at, unlocked_by
            FROM circuit_breaker_state ORDER BY triggered_at DESC
        """)).fetchall()
        if rows:
            for r in rows:
                status = "LOCKED" if r.is_locked else "UNLOCKED"
                print(f"  [{status}] {r.trigger_type} | triggered: {r.triggered_at} | unlock: {r.unlock_at}")
                if r.unlocked_at:
                    print(f"    Unlocked: {r.unlocked_at} by {r.unlocked_by}")
        else:
            print("  No circuit breaker events")
    except Exception as e:
        print(f"  circuit_breaker_state not found: {e}")

    # ── Trade Journal ─────────────────────────────────────────────────────────
    sep("TRADE JOURNAL SUMMARY")
    r = conn.execute(text("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) as losses,
               SUM(net_pnl) as total_pnl
        FROM trade_journal WHERE exit_timestamp IS NOT NULL
    """)).fetchone()
    if r and r.total > 0:
        win_rate = (r.wins or 0) / r.total * 100
        print(f"  Closed trades: {r.total} | Wins: {r.wins} | Losses: {r.losses} | Win rate: {win_rate:.1f}%")
        print(f"  Total Net PnL: {r.total_pnl:.4f}")
    else:
        print("  No closed trades yet")

print(f"\n{'='*68}")
print(f"  Audit completed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"{'='*68}")
