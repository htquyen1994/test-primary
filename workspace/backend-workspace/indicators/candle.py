"""
Candle Measurement Utilities
==============================
Pure functions for measuring candle body, wicks, and tails.
Used by strategy pattern detectors (Pinbar, Engulfing, etc.).

Satisfies: Requirement 4.2
"""

from __future__ import annotations

from typing import Union

import pandas as pd


# Type alias for a single candle row
Candle = Union[pd.Series, dict]


def body_length(candle: Candle) -> float:
    """
    Absolute distance between open and close.
    Zero for a doji.
    """
    return abs(float(candle["close"]) - float(candle["open"]))


def upper_wick(candle: Candle) -> float:
    """
    Distance from the top of the body to the high.
    Represents selling pressure above the body.
    """
    return float(candle["high"]) - max(float(candle["open"]), float(candle["close"]))


def lower_wick(candle: Candle) -> float:
    """
    Distance from the bottom of the body to the low.
    Represents buying pressure below the body.
    """
    return min(float(candle["open"]), float(candle["close"])) - float(candle["low"])


def tail_length(candle: Candle, direction: str) -> float:
    """
    The significant tail for a given trade direction.

    For long setups  → lower wick (rejection of lower prices = bullish)
    For short setups → upper wick (rejection of higher prices = bearish)

    Args:
        candle:    Single OHLCV candle
        direction: "long" or "short"

    Returns:
        Length of the relevant tail
    """
    if direction == "long":
        return lower_wick(candle)
    elif direction == "short":
        return upper_wick(candle)
    else:
        raise ValueError(f"direction must be 'long' or 'short', got '{direction}'")


def candle_range(candle: Candle) -> float:
    """Total range from low to high."""
    return float(candle["high"]) - float(candle["low"])


def is_bullish(candle: Candle) -> bool:
    """Close > Open (green candle)."""
    return float(candle["close"]) > float(candle["open"])


def is_bearish(candle: Candle) -> bool:
    """Close < Open (red candle)."""
    return float(candle["close"]) < float(candle["open"])


def is_doji(candle: Candle, threshold_pct: float = 0.05) -> bool:
    """
    Body is less than threshold_pct of the total range.
    Default: body < 5% of range.
    """
    rng = candle_range(candle)
    if rng == 0:
        return True
    return body_length(candle) / rng < threshold_pct


def is_marubozu(candle: Candle, wick_threshold_pct: float = 0.05) -> bool:
    """
    Both wicks are less than threshold_pct of the total range.
    Indicates strong directional momentum with no rejection.
    """
    rng = candle_range(candle)
    if rng == 0:
        return False
    return (
        upper_wick(candle) / rng < wick_threshold_pct
        and lower_wick(candle) / rng < wick_threshold_pct
    )


def body_position(candle: Candle) -> float:
    """
    Where the body sits within the total range, as a fraction [0, 1].
    0 = body at the bottom, 1 = body at the top.
    Used to classify pin bars.
    """
    rng = candle_range(candle)
    if rng == 0:
        return 0.5
    body_bottom = min(float(candle["open"]), float(candle["close"]))
    return (body_bottom - float(candle["low"])) / rng
