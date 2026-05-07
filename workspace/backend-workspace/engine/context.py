"""
Context Filter Module
======================
Higher-timeframe context validation.

Scoring (max 15 pts):
  1H bias aligned with signal direction:  +8 pts
  Funding rate within ±0.05%:             +4 pts
  Price >= 0.5% from nearest S/R:         +3 pts

Satisfies: Requirement 6.2 (Context component), Requirement 1.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from engine.smc import detect_htf_bias

logger = logging.getLogger(__name__)

FUNDING_RATE_NEUTRAL_THRESHOLD = 0.0005   # ±0.05%
SR_DISTANCE_THRESHOLD = 0.005             # 0.5% from nearest S/R


@dataclass
class ContextResult:
    """Output of the Context Filter."""
    score: float = 0.0
    htf_bias_aligned: bool = False
    funding_rate_neutral: bool = False
    price_away_from_sr: bool = False
    htf_bias: str = "neutral"


def compute_context_score(
    ohlcv_1h: pd.DataFrame,
    signal_direction: str,
    funding_rate: float,
    nearest_sr_distance_pct: float = 0.0,
) -> ContextResult:
    """
    Compute the Context Filter module score (max 15 pts).

    Args:
        ohlcv_1h:               1-hour OHLCV DataFrame
        signal_direction:       "long" or "short"
        funding_rate:           Current funding rate (e.g. 0.0003 = 0.03%)
        nearest_sr_distance_pct: Distance to nearest S/R as fraction (e.g. 0.006 = 0.6%)

    Returns:
        ContextResult with score and individual flags

    Satisfies: Requirement 6.2 (Context component)
    """
    result = ContextResult()

    # 1. HTF bias alignment (+8 pts)
    if not ohlcv_1h.empty:
        result.htf_bias = detect_htf_bias(ohlcv_1h)
        if _bias_aligned(signal_direction, result.htf_bias):
            result.htf_bias_aligned = True
            result.score += 8.0

    # 2. Funding rate neutral (+4 pts)
    if abs(funding_rate) <= FUNDING_RATE_NEUTRAL_THRESHOLD:
        result.funding_rate_neutral = True
        result.score += 4.0

    # 3. Price away from S/R (+3 pts)
    if nearest_sr_distance_pct >= SR_DISTANCE_THRESHOLD:
        result.price_away_from_sr = True
        result.score += 3.0

    result.score = min(result.score, 15.0)
    return result


def _bias_aligned(direction: str, htf_bias: str) -> bool:
    """Returns True if signal direction aligns with HTF bias."""
    if htf_bias == "neutral":
        return False
    return (direction == "long" and htf_bias == "bullish") or \
           (direction == "short" and htf_bias == "bearish")
