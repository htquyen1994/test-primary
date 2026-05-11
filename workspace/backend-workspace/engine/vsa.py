"""
VSA + Volume Profile Module
=============================
Volume Spread Analysis combined with Volume Profile confirmation.

Scoring (max 30 pts):
  VSA (max 20 pts):
    No Supply (pullback vol < 40% impulse vol):  +10 pts
    Effort vs Result (low vol, price holds):     +10 pts

  Volume Profile (max 10 pts):
    Entry within 0.3% of POC:                   +10 pts
    Entry at VAH or VAL:                         +6 pts

Satisfies: Requirement 6.2 (VSA+VolProfile component)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)

# Thresholds
NO_SUPPLY_RATIO = 0.40      # pullback vol < 40% of impulse vol
EFFORT_RESULT_RATIO = 0.50  # low vol but price holds
EFFORT_RANGE_RATIO = 0.30   # price range < 30% of ATR = "price holds"
POC_TOLERANCE_PCT = 0.003   # 0.3% from POC
VAH_VAL_TOLERANCE_PCT = 0.003


@dataclass
class VSAResult:
    """Output of the VSA + Volume Profile analysis."""
    score: float = 0.0
    no_supply: bool = False
    effort_vs_result: bool = False
    absorption: bool = False
    at_poc: bool = False
    at_value_area_edge: bool = False


def detect_no_supply(ohlcv: pd.DataFrame, lookback: int = 5) -> bool:
    """
    No Supply: pullback volume < 40% of prior impulse volume.

    Identifies a low-volume retracement after a strong move —
    indicates weak selling pressure (supply drying up).

    Args:
        ohlcv:    OHLCV DataFrame
        lookback: Number of candles to look back for impulse

    Returns:
        True if current candle shows No Supply pattern
    """
    n = len(ohlcv)
    if n < lookback + 1:
        return False

    current_vol = float(ohlcv.iloc[-1]["volume"])
    # Impulse volume = 75th percentile of lookback window — robust to outlier spikes
    _vols = ohlcv.iloc[-lookback - 1:-1]["volume"].values
    impulse_vol = float(np.percentile(_vols, 75))

    if impulse_vol == 0:
        return False

    ratio = current_vol / impulse_vol
    return ratio < NO_SUPPLY_RATIO


def detect_effort_vs_result(
    ohlcv: pd.DataFrame,
    atr_value: float,
    lookback: int = 5,
) -> bool:
    """
    Effort vs Result: low volume candle but price holds key level.

    Low effort (volume) with good result (price doesn't fall) =
    smart money absorbing supply quietly.

    Args:
        ohlcv:     OHLCV DataFrame
        atr_value: Current ATR value for range comparison
        lookback:  Lookback for impulse volume reference
    """
    n = len(ohlcv)
    if n < lookback + 1 or atr_value == 0:
        return False

    current = ohlcv.iloc[-1]
    current_vol = float(current["volume"])
    current_range = float(current["high"]) - float(current["low"])

    impulse_vol = float(ohlcv.iloc[-lookback - 1:-1]["volume"].max())
    if impulse_vol == 0:
        return False

    vol_ratio = current_vol / impulse_vol
    range_ratio = current_range / atr_value if atr_value > 0 else 1.0

    # Low volume AND small range (price "holds" — doesn't move much)
    return vol_ratio < EFFORT_RESULT_RATIO and range_ratio < EFFORT_RANGE_RATIO


def detect_absorption(
    ohlcv: pd.DataFrame,
    delta: float,
    atr_value: float,
) -> bool:
    """
    Absorption: high volume but price did not move significantly.

    Large volume absorbed without price decline = institutional buying.

    Args:
        ohlcv:     OHLCV DataFrame
        delta:     Cumulative buy-sell delta (positive = net buying)
        atr_value: Current ATR for range comparison
    """
    n = len(ohlcv)
    if n < 5 or atr_value == 0:
        return False

    current = ohlcv.iloc[-1]
    current_vol = float(current["volume"])
    current_range = float(current["high"]) - float(current["low"])

    avg_vol = float(ohlcv.iloc[-5:]["volume"].mean())
    if avg_vol == 0:
        return False

    # High volume (> 1.5x average) but small range (< 50% ATR)
    high_volume = current_vol > avg_vol * 1.5
    small_range = current_range < atr_value * 0.5

    return high_volume and small_range


def compute_vsa_score(
    ohlcv: pd.DataFrame,
    volume_profile: VolumeProfile,
    atr_value: float,
    delta: float = 0.0,
    entry_price: float = 0.0,
) -> VSAResult:
    """
    Compute the VSA + Volume Profile module score (max 30 pts).

    Args:
        ohlcv:          15m OHLCV DataFrame
        volume_profile: Pre-computed VolumeProfile (POC/VAH/VAL)
        atr_value:      Current ATR(14) value
        delta:          Cumulative order flow delta
        entry_price:    Proposed entry price (uses last close if 0)

    Returns:
        VSAResult with score and individual signal flags

    Satisfies: Requirement 6.2 (VSA+VolProfile component)
    """
    result = VSAResult()

    if ohlcv.empty or len(ohlcv) < 5:
        return result

    if entry_price == 0:
        entry_price = float(ohlcv.iloc[-1]["close"])

    # --- VSA signals (max 20 pts) ---

    # No Supply: +10 pts
    if detect_no_supply(ohlcv):
        result.no_supply = True
        result.score += 10.0

    # Effort vs Result: +10 pts
    if detect_effort_vs_result(ohlcv, atr_value):
        result.effort_vs_result = True
        result.score += 10.0

    # Absorption (used by Order Flow module, bonus here if present)
    if detect_absorption(ohlcv, delta, atr_value):
        result.absorption = True

    # --- Volume Profile bonus (max 10 pts) ---

    if volume_profile.poc > 0:
        if volume_profile.is_price_at_poc(entry_price, POC_TOLERANCE_PCT):
            result.at_poc = True
            result.score += 10.0
        elif volume_profile.is_price_at_value_area_edge(entry_price, VAH_VAL_TOLERANCE_PCT):
            result.at_value_area_edge = True
            result.score += 6.0

    result.score = min(result.score, 30.0)
    return result
