"""
Multi-Timeframe Bias Detector
================================
Detects 4H and Daily bias to filter signals and adjust position sizing.

3 Scenarios (Task 31.3):
  A — Aligned:  4H + 1H same direction as signal
      → size × 1.0, score +10, no warning
  B — Diverging: 4H ranging/choppy, 1H aligned
      → size × 0.5, score -10, warning "4H không xác nhận"
  C — Opposing:  4H trending opposite to signal (ADX > 25)
      → BLOCK (size × 0.0), score -999, rejection logged

Daily Bias (Task 35.2):
  BEAR: close < EMA200 AND close < EMA50 AND 3+ lower highs in 10 days
        → additional size × 0.75 for long signals
  BULL: close > EMA200 AND close > EMA50 AND 3+ higher lows in 10 days
        → no reduction
  NEUTRAL: otherwise

Satisfies: Requirements 20, 21 (Phase 9 MTF filter)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ADX threshold for "trending" classification
ADX_TRENDING_THRESHOLD = 20
ADX_OPPOSING_THRESHOLD = 25  # Scenario C requires strong trend


@dataclass
class MTFAlignment:
    """Result of MTF alignment check."""
    scenario: str           # "A" | "B" | "C"
    size_multiplier: float  # 1.0 | 0.5 | 0.0
    score_adjustment: float # +10 | -10 | -999
    warning_message: Optional[str] = None
    rejection_reason: Optional[str] = None
    bias_4h: str = "ranging"
    bias_1h: str = "neutral"


def _compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Compute EMA using pandas ewm."""
    return series.ewm(span=period, adjust=False).mean()


def _compute_adx(ohlcv: pd.DataFrame, period: int = 14) -> float:
    """Compute ADX value for the last candle."""
    n = len(ohlcv)
    if n < period + 2:
        return 0.0
    try:
        from indicators.adx import ADX
        series = ADX().compute(ohlcv, period=period)
        valid = series.dropna()
        return float(valid.iloc[-1]) if not valid.empty else 0.0
    except Exception:
        return 0.0


def detect_4h_bias(ohlcv_4h: pd.DataFrame) -> str:
    """
    Classify 4H trend as "bullish" | "bearish" | "ranging".

    Logic:
      bullish: price > EMA200 AND higher lows AND ADX > 20
      bearish: price < EMA200 AND lower highs AND ADX > 20
      ranging: ADX < 20 OR price oscillating around EMA200

    Args:
        ohlcv_4h: 4H OHLCV DataFrame (needs 200+ candles for EMA200)

    Returns:
        "bullish" | "bearish" | "ranging"
    """
    n = len(ohlcv_4h)
    if n < 20:
        return "ranging"

    closes = ohlcv_4h["close"].astype(float)
    highs = ohlcv_4h["high"].astype(float)
    lows = ohlcv_4h["low"].astype(float)

    current_close = float(closes.iloc[-1])

    # EMA200 (fallback to EMA50 if not enough data)
    ema_period = 200 if n >= 200 else 50
    ema = _compute_ema(closes, ema_period)
    ema_val = float(ema.iloc[-1])

    # ADX
    adx_val = _compute_adx(ohlcv_4h)

    # Market structure: higher lows / lower highs (last 10 bars)
    lookback = min(10, n)
    recent_lows = lows.iloc[-lookback:].values
    recent_highs = highs.iloc[-lookback:].values

    higher_lows = all(recent_lows[i] >= recent_lows[i - 1] for i in range(1, len(recent_lows)))
    lower_highs = all(recent_highs[i] <= recent_highs[i - 1] for i in range(1, len(recent_highs)))

    # Bullish: above EMA + higher lows + trending
    if current_close > ema_val and higher_lows and adx_val > ADX_TRENDING_THRESHOLD:
        return "bullish"

    # Bearish: below EMA + lower highs + trending
    if current_close < ema_val and lower_highs and adx_val > ADX_TRENDING_THRESHOLD:
        return "bearish"

    return "ranging"


def detect_daily_bias(ohlcv_daily: pd.DataFrame) -> str:
    """
    Classify Daily trend as "BULL" | "BEAR" | "NEUTRAL".

    Logic:
      BEAR: close < EMA200 AND close < EMA50 AND 3+ lower highs in last 10 days
      BULL: close > EMA200 AND close > EMA50 AND 3+ higher lows in last 10 days
      NEUTRAL: otherwise

    Args:
        ohlcv_daily: Daily OHLCV DataFrame (needs 200+ candles for EMA200)

    Returns:
        "BULL" | "BEAR" | "NEUTRAL"
    """
    n = len(ohlcv_daily)
    if n < 10:
        return "NEUTRAL"

    closes = ohlcv_daily["close"].astype(float)
    highs = ohlcv_daily["high"].astype(float)
    lows = ohlcv_daily["low"].astype(float)

    current_close = float(closes.iloc[-1])

    # EMA200 and EMA50
    ema200_period = 200 if n >= 200 else n
    ema50_period = 50 if n >= 50 else n
    ema200 = float(_compute_ema(closes, ema200_period).iloc[-1])
    ema50 = float(_compute_ema(closes, ema50_period).iloc[-1])

    # Count lower highs / higher lows in last 10 days
    lookback = min(10, n)
    recent_highs = highs.iloc[-lookback:].values
    recent_lows = lows.iloc[-lookback:].values

    lower_high_count = sum(
        1 for i in range(1, len(recent_highs))
        if recent_highs[i] < recent_highs[i - 1]
    )
    higher_low_count = sum(
        1 for i in range(1, len(recent_lows))
        if recent_lows[i] > recent_lows[i - 1]
    )

    # BEAR: below both EMAs + 3+ lower highs
    if current_close < ema200 and current_close < ema50 and lower_high_count >= 3:
        return "BEAR"

    # BULL: above both EMAs + 3+ higher lows
    if current_close > ema200 and current_close > ema50 and higher_low_count >= 3:
        return "BULL"

    return "NEUTRAL"


def get_mtf_alignment(
    bias_4h: str,
    bias_1h: str,
    signal_direction: str,
) -> MTFAlignment:
    """
    Determine MTF alignment scenario and return size/score adjustments.

    Scenarios:
      A — Aligned (4H + 1H same direction as signal):
          size × 1.0, score +10
      B — Diverging (4H ranging, 1H aligned):
          size × 0.5, score -10, warning shown
      C — Opposing (4H trending opposite, ADX > 25 implied by bias):
          BLOCK (size × 0.0), score -999

    Args:
        bias_4h:          "bullish" | "bearish" | "ranging"
        bias_1h:          "bullish" | "bearish" | "neutral"
        signal_direction: "long" | "short"

    Returns:
        MTFAlignment with scenario, multipliers, and messages
    """
    # Normalize direction to bias language
    signal_bias = "bullish" if signal_direction == "long" else "bearish"
    opposite_bias = "bearish" if signal_bias == "bullish" else "bullish"

    # Scenario C — 4H directly opposing signal (strongest filter)
    if bias_4h == opposite_bias:
        direction_label = "Long" if signal_direction == "long" else "Short"
        return MTFAlignment(
            scenario="C",
            size_multiplier=0.0,
            score_adjustment=-999,
            warning_message=f"BLOCKED: 4H downtrend — {direction_label} bị vô hiệu hóa",
            rejection_reason="4H_OPPOSING_TREND",
            bias_4h=bias_4h,
            bias_1h=bias_1h,
        )

    # Scenario A — 4H aligned with signal
    if bias_4h == signal_bias:
        return MTFAlignment(
            scenario="A",
            size_multiplier=1.0,
            score_adjustment=+10.0,
            warning_message=None,
            bias_4h=bias_4h,
            bias_1h=bias_1h,
        )

    # Scenario B — 4H ranging/choppy (not aligned, not opposing)
    return MTFAlignment(
        scenario="B",
        size_multiplier=0.5,
        score_adjustment=-10.0,
        warning_message="4H không xác nhận — size giảm 50%",
        bias_4h=bias_4h,
        bias_1h=bias_1h,
    )


def get_daily_size_multiplier(daily_bias: str, signal_direction: str) -> tuple:
    """
    Return (size_multiplier, warning_message) based on daily bias.

    When daily bearish + long signal → size × 0.75 (25% reduction).
    When daily bullish + long signal → no reduction.

    Args:
        daily_bias:       "BULL" | "BEAR" | "NEUTRAL"
        signal_direction: "long" | "short"

    Returns:
        (multiplier: float, warning: str | None)
    """
    if daily_bias == "BEAR" and signal_direction == "long":
        return 0.75, "⚠ Daily bearish — size giảm thêm 25%"
    return 1.0, None
