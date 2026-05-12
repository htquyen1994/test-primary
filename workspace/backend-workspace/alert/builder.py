"""
Alert Builder
==============
Builds the Signal Card payload from a Signal object.
Computes gross R:R and net R:R after fees and slippage.

Satisfies: Requirements 18.1, 17.2
"""

from __future__ import annotations

import logging
from typing import Optional

from strategies.signal import Signal

logger = logging.getLogger(__name__)


def build_signal_card(
    signal: Signal,
    fee_rate: float = 0.001,
    slippage_pct: float = 0.0002,
) -> dict:
    """
    Build the Signal Card payload for the Dashboard.

    All required fields per Requirement 18.1:
    - asset, direction, final_score
    - entry_price, stop_loss, take_profit_1, take_profit_2
    - gross_rr, net_rr
    - score_breakdown (all five sub-scores)
    - regime, expires_at_candle

    Args:
        signal:       Signal object from strategy
        fee_rate:     Exchange fee rate (default 0.1%)
        slippage_pct: Estimated slippage (default 0.02%)

    Returns:
        Dict with all Signal Card fields

    Satisfies: Requirement 18.1
    """
    entry = signal.entry_price
    sl = signal.stop_loss
    tp1 = signal.take_profit_1
    tp2 = signal.take_profit_2

    sl_dist = abs(entry - sl)
    tp1_dist = abs(tp1 - entry)

    # Gross R:R
    gross_rr = tp1_dist / sl_dist if sl_dist > 0 else 0.0

    # Net R:R after fees and slippage (entry + exit round-trip)
    total_cost_pct = (fee_rate + slippage_pct) * 2
    fee_cost = entry * total_cost_pct
    net_tp1_dist = tp1_dist - fee_cost
    net_rr = net_tp1_dist / sl_dist if sl_dist > 0 else 0.0

    return {
        # Identity
        "signal_id": f"{signal.strategy_name}_{signal.asset}_{signal.candle_index}",
        "strategy_name": signal.strategy_name,
        "asset": signal.asset,
        "timeframe": signal.timeframe,
        "direction": signal.direction,
        "candle_index": signal.candle_index,
        "candle_timestamp": signal.candle_timestamp.isoformat(),

        # Score
        "final_score": signal.final_score,
        "raw_score": signal.raw_score,
        "classification": signal.classification,
        "score_breakdown": signal.score_breakdown.to_dict(),

        # Trade levels
        "entry_price": entry,
        "stop_loss": sl,
        "take_profit_1": tp1,
        "take_profit_2": tp2,

        # R:R
        "gross_rr": round(gross_rr, 3),
        "net_rr": round(net_rr, 3),

        # Market context
        "regime": signal.regime,
        "regime_multiplier": signal.regime_multiplier,
        "funding_rate": signal.funding_rate,
        "portfolio_heat": signal.portfolio_heat,

        # Time invalidation
        "expires_at_candle": signal.expires_at_candle,
        "created_at": signal.created_at.isoformat(),
    }
