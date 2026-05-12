"""
Unit tests for SMC Analysis module.
Tests Order Block, FVG, CHoCH detection and score aggregation.

Satisfies: Requirements 1.2, 6.2
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.smc import (
    find_order_block, find_fvg, detect_choch, detect_htf_bias,
    compute_smc_score, OrderBlock, FairValueGap, CHoCH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ohlcv(rows: list[dict]) -> pd.DataFrame:
    """Build OHLCV DataFrame from list of dicts."""
    return pd.DataFrame(rows)


def flat_ohlcv(n: int, price: float = 100.0) -> pd.DataFrame:
    """Flat market — no patterns."""
    return pd.DataFrame({
        "open":   [price] * n,
        "high":   [price + 0.5] * n,
        "low":    [price - 0.5] * n,
        "close":  [price] * n,
        "volume": [1000.0] * n,
    })


def bullish_impulse_ohlcv(n_base: int = 20) -> pd.DataFrame:
    """
    Creates a series with a clear bullish OB setup:
    - n_base flat candles
    - 1 bearish candle (the OB)
    - 1 large bullish impulse candle (body >= 1.5 * ATR)
    """
    rows = []
    base_price = 100.0
    for i in range(n_base):
        rows.append({"open": base_price, "high": base_price + 0.5,
                     "low": base_price - 0.5, "close": base_price, "volume": 500.0})
    # Bearish OB candle
    rows.append({"open": 101.0, "high": 101.5, "low": 99.5, "close": 99.8, "volume": 800.0})
    # Large bullish impulse (body = 5.0, well above ATR ~1.0)
    rows.append({"open": 99.8, "high": 106.0, "low": 99.5, "close": 105.0, "volume": 5000.0})
    return pd.DataFrame(rows)


def bearish_impulse_ohlcv(n_base: int = 20) -> pd.DataFrame:
    """Creates a series with a clear bearish OB setup."""
    rows = []
    base_price = 100.0
    for i in range(n_base):
        rows.append({"open": base_price, "high": base_price + 0.5,
                     "low": base_price - 0.5, "close": base_price, "volume": 500.0})
    # Bullish OB candle
    rows.append({"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.2, "volume": 800.0})
    # Large bearish impulse
    rows.append({"open": 100.2, "high": 100.5, "low": 94.0, "close": 95.0, "volume": 5000.0})
    return pd.DataFrame(rows)


def fvg_bullish_ohlcv() -> pd.DataFrame:
    """Creates a series with a clear bullish FVG."""
    # c1.high=100, c3.low=102 → gap [100, 102]
    return pd.DataFrame({
        "open":   [98, 99, 101],
        "high":   [100, 101, 104],
        "low":    [97, 98, 102],
        "close":  [99, 100, 103],
        "volume": [1000, 1000, 1000],
    })


def fvg_bearish_ohlcv() -> pd.DataFrame:
    """Creates a series with a clear bearish FVG."""
    # c1.low=100, c3.high=98 → gap [98, 100]
    return pd.DataFrame({
        "open":   [102, 101, 99],
        "high":   [103, 102, 98],
        "low":    [100, 99, 96],
        "close":  [101, 100, 97],
        "volume": [1000, 1000, 1000],
    })


# ---------------------------------------------------------------------------
# Order Block tests
# ---------------------------------------------------------------------------

class TestOrderBlock:

    def test_detects_bullish_ob(self):
        ohlcv = bullish_impulse_ohlcv()
        obs = find_order_block(ohlcv)
        assert obs  # non-empty list
        assert obs[0].type == "bullish"
        assert obs[0].valid is True

    def test_detects_bearish_ob(self):
        ohlcv = bearish_impulse_ohlcv()
        obs = find_order_block(ohlcv)
        assert obs
        assert obs[0].type == "bearish"
        assert obs[0].valid is True

    def test_returns_none_for_flat_market(self):
        ohlcv = flat_ohlcv(30)
        obs = find_order_block(ohlcv)
        assert not obs  # empty list

    def test_ob_mid_is_average_of_high_low(self):
        ohlcv = bullish_impulse_ohlcv()
        obs = find_order_block(ohlcv)
        assert obs
        ob = obs[0]
        assert abs(ob.mid - (ob.high + ob.low) / 2) < 1e-10

    def test_ob_invalidated_when_price_closes_below_low(self):
        ob = OrderBlock(type="bullish", high=101.5, low=99.5, mid=100.5, candle_index=5)
        # Candle that closes below OB low
        candle = pd.Series({"open": 100, "high": 100.5, "low": 98, "close": 98.5})
        ob.invalidate_if_broken(candle)
        assert ob.valid is False

    def test_ob_not_invalidated_when_price_stays_above_low(self):
        ob = OrderBlock(type="bullish", high=101.5, low=99.5, mid=100.5, candle_index=5)
        candle = pd.Series({"open": 100, "high": 101, "low": 99.6, "close": 100.5})
        ob.invalidate_if_broken(candle)
        assert ob.valid is True

    def test_ob_retest_detection(self):
        ob = OrderBlock(type="bullish", high=101.5, low=99.5, mid=100.5, candle_index=5)
        assert ob.is_price_retesting(100.5) is True   # at mid
        assert ob.is_price_retesting(99.5) is True    # at low
        assert ob.is_price_retesting(101.5) is True   # at high
        assert ob.is_price_retesting(98.0) is False   # below OB

    def test_returns_none_for_insufficient_data(self):
        ohlcv = flat_ohlcv(5)
        obs = find_order_block(ohlcv)
        assert not obs  # empty list


# ---------------------------------------------------------------------------
# Fair Value Gap tests
# ---------------------------------------------------------------------------

class TestFairValueGap:

    def test_detects_bullish_fvg(self):
        ohlcv = fvg_bullish_ohlcv()
        fvg = find_fvg(ohlcv)
        assert fvg is not None
        assert fvg.type == "bullish"
        assert fvg.bot == 100.0  # c1.high
        assert fvg.top == 102.0  # c3.low
        assert abs(fvg.mid - 101.0) < 1e-10

    def test_detects_bearish_fvg(self):
        ohlcv = fvg_bearish_ohlcv()
        fvg = find_fvg(ohlcv)
        assert fvg is not None
        assert fvg.type == "bearish"
        assert fvg.top == 100.0  # c1.low
        assert fvg.bot == 98.0   # c3.high

    def test_returns_none_for_no_gap(self):
        # Overlapping wicks — no FVG
        ohlcv = pd.DataFrame({
            "open":   [100, 101, 102],
            "high":   [102, 103, 104],
            "low":    [99, 100, 101],
            "close":  [101, 102, 103],
            "volume": [1000, 1000, 1000],
        })
        fvg = find_fvg(ohlcv)
        assert fvg is None

    def test_fvg_filled_when_price_trades_through(self):
        fvg = FairValueGap(type="bullish", top=102.0, bot=100.0, mid=101.0, candle_index=2)
        # Candle whose low goes below bot
        candle = pd.Series({"open": 101, "high": 103, "low": 99.5, "close": 102})
        fvg.check_if_filled(candle)
        assert fvg.filled is True

    def test_fvg_not_filled_when_price_stays_above(self):
        fvg = FairValueGap(type="bullish", top=102.0, bot=100.0, mid=101.0, candle_index=2)
        candle = pd.Series({"open": 101, "high": 103, "low": 100.5, "close": 102})
        fvg.check_if_filled(candle)
        assert fvg.filled is False

    def test_fvg_midpoint_detection(self):
        fvg = FairValueGap(type="bullish", top=102.0, bot=100.0, mid=101.0, candle_index=2)
        assert fvg.is_price_at_midpoint(101.0) is True
        assert fvg.is_price_at_midpoint(101.05) is True   # within tolerance
        assert fvg.is_price_at_midpoint(102.5) is False   # too far


# ---------------------------------------------------------------------------
# CHoCH tests
# ---------------------------------------------------------------------------

class TestCHoCH:

    def test_detects_bullish_choch(self):
        # Last close (104) must break ABOVE the highest high in reference window
        # Reference highs: [101, 102, 103, 102, 101] → max = 103
        # Last close = 104 > 103 → bullish CHoCH
        closes = [100, 101, 102, 101, 100, 104]
        ohlcv = pd.DataFrame({
            "open":   [c - 0.5 for c in closes],
            "high":   [c + 1.0 for c in closes],
            "low":    [c - 1.0 for c in closes],
            "close":  closes,
            "volume": [1000] * len(closes),
        })
        choch = detect_choch(ohlcv)
        assert choch is not None
        assert choch.direction == "bullish"

    def test_detects_bearish_choch(self):
        # Last close (96) must break BELOW the lowest low in reference window
        # Reference lows: [99, 98, 97, 98, 99] → min = 97
        # Last close = 96 < 97 → bearish CHoCH
        closes = [100, 99, 98, 99, 100, 96]
        ohlcv = pd.DataFrame({
            "open":   [c + 0.5 for c in closes],
            "high":   [c + 1.0 for c in closes],
            "low":    [c - 1.0 for c in closes],
            "close":  closes,
            "volume": [1000] * len(closes),
        })
        choch = detect_choch(ohlcv)
        assert choch is not None
        assert choch.direction == "bearish"

    def test_returns_none_for_flat_market(self):
        ohlcv = flat_ohlcv(20)
        choch = detect_choch(ohlcv)
        assert choch is None


# ---------------------------------------------------------------------------
# HTF Bias tests
# ---------------------------------------------------------------------------

class TestHTFBias:

    def test_bullish_bias_for_uptrend(self):
        # Clear uptrend: each close higher than previous
        closes = [100 + i for i in range(30)]
        ohlcv = pd.DataFrame({
            "open":   [c - 0.5 for c in closes],
            "high":   [c + 1.0 for c in closes],
            "low":    [c - 1.0 for c in closes],
            "close":  closes,
            "volume": [1000] * 30,
        })
        bias = detect_htf_bias(ohlcv)
        assert bias == "bullish"

    def test_bearish_bias_for_downtrend(self):
        closes = [100 - i for i in range(30)]
        ohlcv = pd.DataFrame({
            "open":   [c + 0.5 for c in closes],
            "high":   [c + 1.0 for c in closes],
            "low":    [c - 1.0 for c in closes],
            "close":  closes,
            "volume": [1000] * 30,
        })
        bias = detect_htf_bias(ohlcv)
        assert bias == "bearish"

    def test_neutral_for_insufficient_data(self):
        ohlcv = flat_ohlcv(2)
        bias = detect_htf_bias(ohlcv)
        assert bias == "neutral"


# ---------------------------------------------------------------------------
# SMC Score aggregator tests
# ---------------------------------------------------------------------------

class TestSMCScore:

    def test_score_zero_when_no_patterns(self):
        ohlcv = flat_ohlcv(30)
        result = compute_smc_score(ohlcv, flat_ohlcv(30))
        assert result.score == 0.0

    def test_score_max_30(self):
        # Even if all conditions met, score should not exceed 30
        ohlcv = bullish_impulse_ohlcv()
        result = compute_smc_score(ohlcv, ohlcv)
        assert result.score <= 30.0

    def test_score_non_negative(self):
        ohlcv = flat_ohlcv(30)
        result = compute_smc_score(ohlcv, flat_ohlcv(30))
        assert result.score >= 0.0

    def test_returns_smc_result_object(self):
        ohlcv = flat_ohlcv(30)
        result = compute_smc_score(ohlcv, flat_ohlcv(30))
        assert hasattr(result, "score")
        assert hasattr(result, "order_block")
        assert hasattr(result, "fvg")
        assert hasattr(result, "choch")
        assert hasattr(result, "htf_bias")

    def test_empty_ohlcv_returns_zero_score(self):
        result = compute_smc_score(pd.DataFrame(), pd.DataFrame())
        assert result.score == 0.0
