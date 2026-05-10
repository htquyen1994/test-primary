"""
Log Publisher
==============
Publishes detailed scoring breakdown to Redis 'logs:channel' after every
candle close — regardless of whether the signal is ALERT, WATCH, or IGNORE.

This is separate from the alerts pipeline and does NOT affect performance:
- Published asynchronously after scoring is complete
- Only consumed by connected Dashboard log viewers
- If no viewer is connected, messages are simply dropped (no queue buildup)

Satisfies: Requirement 17 (Rich Logging) + Dashboard log view
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LOGS_CHANNEL = "logs:channel"


def build_log_entry(
    symbol: str,
    timeframe: str,
    candle_timestamp: str,
    regime: str,
    regime_multiplier: float,
    adx_value: float,
    atr_value: float,
    of_score: float,
    smc_score: float,
    vsa_score: float,
    ctx_score: float,
    bonus: float,
    raw_score: float,
    final_score: int,
    classification: str,
    # Detail breakdown
    delta: float = 0.0,
    delta_threshold: float = 1000.0,
    ob_retested: bool = False,
    fvg_touched: bool = False,
    choch_aligned: bool = False,
    htf_bias: str = "neutral",
    no_supply: bool = False,
    effort_vs_result: bool = False,
    at_poc: bool = False,
    funding_rate: float = 0.0,
    portfolio_heat: float = 0.0,
    rejection_reason: str = "",
    # Phase 9 extra fields (Task 31, 33, 34, 35)
    extra: dict = None,
) -> dict:
    """
    Build a detailed log entry explaining why a signal scored as it did.
    """
    reasons_met = []
    reasons_missed = []

    # Order Flow breakdown
    if delta > delta_threshold:
        reasons_met.append(f"Delta +{delta:.0f} BTC > threshold {delta_threshold:.0f} → +15 pts")
    else:
        reasons_missed.append(f"Delta {delta:.0f} BTC < threshold {delta_threshold:.0f} → 0/15 pts")

    # SMC breakdown
    if choch_aligned:
        reasons_met.append(f"CHoCH aligned with {htf_bias} 1H bias → +10 pts")
    else:
        reasons_missed.append(f"No CHoCH aligned with {htf_bias} bias → 0/10 pts")

    if ob_retested:
        reasons_met.append("Order Block retest ✓ → +10 pts")
    else:
        reasons_missed.append("No OB retest → 0/10 pts")

    if fvg_touched:
        reasons_met.append("FVG midpoint touched ✓ → +10 pts")
    else:
        reasons_missed.append("No FVG midpoint touch → 0/10 pts")

    # VSA breakdown
    if no_supply:
        reasons_met.append("No Supply (pullback vol < 40%) ✓ → +10 pts")
    else:
        reasons_missed.append("No Supply not detected → 0/10 pts")

    if effort_vs_result:
        reasons_met.append("Effort vs Result ✓ → +10 pts")
    else:
        reasons_missed.append("Effort vs Result not detected → 0/10 pts")

    if at_poc:
        reasons_met.append("Entry at POC ✓ → +10 pts")
    else:
        reasons_missed.append("Entry not at POC → 0/10 pts")

    # Context breakdown
    if htf_bias != "neutral":
        reasons_met.append(f"1H bias = {htf_bias} ✓ → +8 pts")
    else:
        reasons_missed.append("1H bias = neutral → 0/8 pts")

    if abs(funding_rate) <= 0.0005:
        reasons_met.append(f"Funding rate {funding_rate:.4%} neutral ✓ → +4 pts")
    else:
        reasons_missed.append(f"Funding rate {funding_rate:.4%} extreme → 0/4 pts")

    # Why not ALERT
    why_not_alert = ""
    if classification != "ALERT":
        needed = 75 - final_score
        why_not_alert = f"Need {needed} more points to reach ALERT threshold (75)"
        if rejection_reason:
            why_not_alert += f" | Rejected: {rejection_reason}"

    return {
        "type": "scoring_log",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe": timeframe,
        "candle_timestamp": candle_timestamp,
        # Regime
        "regime": regime,
        "regime_multiplier": regime_multiplier,
        "adx": round(adx_value, 2),
        "atr": round(atr_value, 4),
        # Scores
        "scores": {
            "order_flow": round(of_score, 1),
            "smc": round(smc_score, 1),
            "vsa": round(vsa_score, 1),
            "context": round(ctx_score, 1),
            "bonus": round(bonus, 1),
            "raw": round(raw_score, 1),
            "final": final_score,
        },
        "classification": classification,
        # Breakdown
        "conditions_met": reasons_met,
        "conditions_missed": reasons_missed,
        "why_not_alert": why_not_alert,
        # Market context
        "delta": round(delta, 0),
        "delta_threshold": round(delta_threshold, 0),
        "funding_rate": round(funding_rate, 6),
        "portfolio_heat": round(portfolio_heat, 2),
        "htf_bias": htf_bias,
        # Phase 9 extra fields (MTF, BTC Guard, Daily Bias)
        **(extra or {}),
    }


def publish_log(redis_client_sync, log_entry: dict) -> None:
    """
    Publish log entry to Redis logs:channel (sync version for Celery tasks).
    Fire-and-forget — if no subscriber, message is dropped silently.
    """
    try:
        redis_client_sync.publish(LOGS_CHANNEL, json.dumps(log_entry))
    except Exception as exc:
        logger.debug("Log publish failed (no subscribers): %s", exc)
