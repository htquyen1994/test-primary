"""
Order Flow Analysis Module
===========================
Measures institutional order flow pressure using:
  - Cumulative Delta (buy vol - sell vol)
  - Bid/Ask stack imbalance at S/R zones
  - Absorption (high volume, price doesn't move)

Scoring (max 35 pts):
  Delta > dynamic threshold:   +15 pts
  Bid stack > Ask stack × 2:  +10 pts
  Absorption detected:         +10 pts

Dynamic Threshold (Task 34.1):
  threshold = percentile_75(abs(delta_values_24h)) × 1.5
  Fallback to 1000.0 if fewer than 10 data points available

Satisfies: Requirement 6.2 (Order Flow component), Task 34
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Fallback delta threshold when insufficient history
FALLBACK_DELTA_THRESHOLD = 1000.0
MIN_HISTORY_POINTS = 10     # minimum data points for dynamic threshold
PERCENTILE_75 = 75
DYNAMIC_MULTIPLIER = 1.5    # percentile_75 × 1.5


@dataclass
class OrderFlowResult:
    """Output of the Order Flow analysis."""
    score: float = 0.0
    delta_bullish: bool = False
    bid_dominant: bool = False
    absorption: bool = False
    dynamic_threshold: float = FALLBACK_DELTA_THRESHOLD  # logged for transparency


def compute_dynamic_delta_threshold(delta_history: List[float]) -> float:
    """
    Compute dynamic delta threshold from 24h history.

    Logic: percentile_75(abs(delta_values_24h)) × 1.5
    Fallback to 1000.0 if fewer than 10 data points.

    Args:
        delta_history: List of delta values (last 96 = 24h of 15m candles)

    Returns:
        Dynamic threshold value

    Satisfies: Task 34.1
    """
    if len(delta_history) < MIN_HISTORY_POINTS:
        logger.debug(
            "Insufficient delta history (%d points) — using fallback threshold %.0f",
            len(delta_history), FALLBACK_DELTA_THRESHOLD,
        )
        return FALLBACK_DELTA_THRESHOLD

    abs_deltas = [abs(d) for d in delta_history if d != 0]
    if not abs_deltas:
        return FALLBACK_DELTA_THRESHOLD

    p75 = float(np.percentile(abs_deltas, PERCENTILE_75))
    threshold = p75 * DYNAMIC_MULTIPLIER

    # Sanity bounds: never below 100 or above 50000
    threshold = max(100.0, min(threshold, 50000.0))
    return threshold


def compute_order_flow_score(
    delta: float,
    bid_stack: float,
    ask_stack: float,
    absorption: bool,
    delta_threshold: float = FALLBACK_DELTA_THRESHOLD,
) -> OrderFlowResult:
    """
    Compute the Order Flow module score (max 35 pts).

    Args:
        delta:           Cumulative buy_vol - sell_vol over last 5 candles
        bid_stack:       Total bid size at S/R zone (from order book)
        ask_stack:       Total ask size at S/R zone
        absorption:      True if high volume but price did not move significantly
        delta_threshold: Dynamic threshold (use compute_dynamic_delta_threshold())

    Returns:
        OrderFlowResult with score and individual signal flags

    Satisfies: Requirement 6.2 (Order Flow component)
    """
    result = OrderFlowResult(dynamic_threshold=delta_threshold)

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
