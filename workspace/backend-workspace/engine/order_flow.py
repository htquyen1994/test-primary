"""
Order Flow Analysis Module
===========================
Measures institutional order flow pressure using:
  - Cumulative Delta (buy vol - sell vol)
  - Bid/Ask stack imbalance at S/R zones
  - Absorption (high volume, price doesn't move)

Scoring (max 35 pts):
  Delta > threshold:           +15 pts
  Bid stack > Ask stack × 2:  +10 pts
  Absorption detected:         +10 pts

Satisfies: Requirement 6.2 (Order Flow component)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

# Default delta threshold (BTC-equivalent units)
DEFAULT_DELTA_THRESHOLD = 1000.0


@dataclass
class OrderFlowResult:
    """Output of the Order Flow analysis."""
    score: float = 0.0
    delta_bullish: bool = False
    bid_dominant: bool = False
    absorption: bool = False


def compute_order_flow_score(
    delta: float,
    bid_stack: float,
    ask_stack: float,
    absorption: bool,
    delta_threshold: float = DEFAULT_DELTA_THRESHOLD,
) -> OrderFlowResult:
    """
    Compute the Order Flow module score (max 35 pts).

    Args:
        delta:           Cumulative buy_vol - sell_vol over last 5 candles
        bid_stack:       Total bid size at S/R zone (from order book)
        ask_stack:       Total ask size at S/R zone
        absorption:      True if high volume but price did not move significantly
        delta_threshold: Minimum delta to score (configurable, default 1000)

    Returns:
        OrderFlowResult with score and individual signal flags

    Satisfies: Requirement 6.2 (Order Flow component)
    """
    result = OrderFlowResult()

    # Institutional buying pressure: large positive delta
    if delta > delta_threshold:
        result.delta_bullish = True
        result.score += 15.0

    # Bid dominance at key level: buyers stacking up
    if ask_stack > 0 and bid_stack > ask_stack * 2.0:
        result.bid_dominant = True
        result.score += 10.0

    # Absorption: large volume absorbed without price decline
    if absorption:
        result.absorption = True
        result.score += 10.0

    result.score = min(result.score, 35.0)
    return result
