"""
Unit tests for the Indicator Library.
Tests known values, edge cases, and candle measurement functions.

Satisfies: Requirements 4.1, 4.2
"""

import math

import numpy as np
import pandas as pd
import pytest

from indicators.atr import ATR
from indicators.rsi import RSI
from indicators.ema import EMA
from indicators.adx import ADX
from indicators.bollinger import BollingerBands
from indicators.candle import (
    body_length, upper_wick, lower_wick, tail_length,
    candle_range, is_bullish, is_bearish, is_doji, is_marubozu, body_position,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ohlcv(closes, highs=None, lows=None, opens=None, volumes=None) -> pd.DataFrame:
    n = len(closes)
    closes = np.array(closes, dtype=float)
    if highs is None:
        highs = closes + 1.0
    if lows is None:
        lows = closes - 1.0
    if opens is None:
        opens = closes - 0.5
    if volumes is None:
        volumes = np.ones(n) * 1000.0
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes,
    })


# ---------------------------------------------------------------------------
# ATR tests
# ---------------------------------------------------------------------------

class TestATR:

    def test_returns_nan_for_insufficient_data(self):
        ohlcv = make_ohlcv([100, 101, 102])
        result = ATR().compute(ohlcv, period=14)
        assert result.isna().all()

    def test_first_valid_value_at_period_minus_1(self):
        closes = list(range(100, 120))  # 20 values
        ohlcv = make_ohlcv(closes)
        result = ATR().compute(ohlcv, period=14)
        # Indices 0..12 should be NaN, index 13 should be valid
        assert result.iloc[:13].isna().all()
        assert not math.isnan(result.iloc[13])

    def test_known_value_simple_case(self):
        # All candles: high=101, low=99, close=100 → TR=2 always
        # ATR(3) should converge to 2.0
        n = 20
        closes = [100.0] * n
        highs = [101.0] * n
        lows = [99.0] * n
        ohlcv = make_ohlcv(closes, highs=highs, lows=lows)
        result = ATR().compute(ohlcv, period=3)
        # After enough bars, ATR should be very close to 2.0
        assert abs(result.iloc[-1] - 2.0) < 0.01

    def test_positive_values_only(self):
        closes = [100 + i * 0.5 for i in range(30)]
        ohlcv = make_ohlcv(closes)
        result = ATR().compute(ohlcv, period=14)
        valid = result.dropna()
        assert (valid > 0).all()


# ---------------------------------------------------------------------------
# RSI tests
# ---------------------------------------------------------------------------

class TestRSI:

    def test_returns_nan_for_insufficient_data(self):
        ohlcv = make_ohlcv([100, 101, 102])
        result = RSI().compute(ohlcv, period=14)
        assert result.isna().all()

    def test_rsi_100_when_all_closes_rising(self):
        # All gains, no losses → RSI should be 100
        closes = [100 + i for i in range(20)]
        ohlcv = make_ohlcv(closes)
        result = RSI().compute(ohlcv, period=5)
        valid = result.dropna()
        assert (valid == 100.0).all()

    def test_rsi_0_when_all_closes_falling(self):
        # All losses, no gains → RSI should be 0
        closes = [100 - i for i in range(20)]
        ohlcv = make_ohlcv(closes)
        result = RSI().compute(ohlcv, period=5)
        valid = result.dropna()
        assert (valid == 0.0).all()

    def test_rsi_bounded_0_to_100(self):
        rng = np.random.default_rng(0)
        closes = 100 + np.cumsum(rng.normal(0, 2, 100))
        ohlcv = make_ohlcv(closes)
        result = RSI().compute(ohlcv, period=14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_near_50_for_random_walk(self):
        # Long random walk should average near 50
        rng = np.random.default_rng(42)
        closes = 100 + np.cumsum(rng.normal(0, 1, 500))
        ohlcv = make_ohlcv(closes)
        result = RSI().compute(ohlcv, period=14)
        mean_rsi = result.dropna().mean()
        assert 35 < mean_rsi < 65


# ---------------------------------------------------------------------------
# EMA tests
# ---------------------------------------------------------------------------

class TestEMA:

    def test_returns_nan_for_insufficient_data(self):
        ohlcv = make_ohlcv([100, 101])
        result = EMA().compute(ohlcv, period=5)
        assert result.isna().all()

    def test_first_value_equals_sma(self):
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        ohlcv = make_ohlcv(closes)
        result = EMA().compute(ohlcv, period=5)
        # First valid value at index 4 = SMA of all 5 = 30.0
        assert abs(result.iloc[4] - 30.0) < 1e-10

    def test_ema_tracks_constant_series(self):
        # EMA of constant series should equal the constant
        closes = [50.0] * 30
        ohlcv = make_ohlcv(closes)
        result = EMA().compute(ohlcv, period=10)
        valid = result.dropna()
        assert (abs(valid - 50.0) < 1e-10).all()

    def test_ema_responds_faster_than_sma(self):
        # After a price jump, EMA should be closer to new price than SMA
        closes = [100.0] * 20 + [200.0] * 10
        ohlcv = make_ohlcv(closes)
        ema = EMA().compute(ohlcv, period=10)
        # At the last bar, EMA should be > 150 (closer to 200 than SMA would be)
        assert ema.iloc[-1] > 150.0


# ---------------------------------------------------------------------------
# ADX tests
# ---------------------------------------------------------------------------

class TestADX:

    def test_returns_nan_for_insufficient_data(self):
        ohlcv = make_ohlcv([100] * 5)
        result = ADX().compute(ohlcv, period=14)
        assert result.isna().all()

    def test_adx_bounded_0_to_100(self):
        rng = np.random.default_rng(1)
        closes = 100 + np.cumsum(rng.normal(0, 1, 100))
        highs = closes + rng.uniform(0.5, 2, 100)
        lows = closes - rng.uniform(0.5, 2, 100)
        ohlcv = make_ohlcv(closes, highs=highs, lows=lows)
        result = ADX().compute(ohlcv, period=14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_adx_high_in_strong_trend(self):
        # Strong uptrend: each close 2 higher than previous
        n = 60
        closes = [100 + i * 2 for i in range(n)]
        highs = [c + 1 for c in closes]
        lows = [c - 0.5 for c in closes]
        ohlcv = make_ohlcv(closes, highs=highs, lows=lows)
        result = ADX().compute(ohlcv, period=14)
        # ADX should be > 25 in a strong trend
        assert result.dropna().iloc[-1] > 25

    def test_adx_full_returns_three_series(self):
        closes = [100 + i for i in range(50)]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        ohlcv = make_ohlcv(closes, highs=highs, lows=lows)
        result = ADX().compute_full(ohlcv, period=14)
        assert len(result.adx) == 50
        assert len(result.di_plus) == 50
        assert len(result.di_minus) == 50


# ---------------------------------------------------------------------------
# Bollinger Bands tests
# ---------------------------------------------------------------------------

class TestBollingerBands:

    def test_returns_nan_for_insufficient_data(self):
        ohlcv = make_ohlcv([100, 101, 102])
        result = BollingerBands().compute(ohlcv, period=20)
        assert result.isna().all()

    def test_upper_lower_symmetric_around_middle(self):
        closes = [100 + i * 0.1 for i in range(50)]
        ohlcv = make_ohlcv(closes)
        bb = BollingerBands().compute_full(ohlcv, period=20, k=2.0)
        valid_idx = bb.middle.dropna().index
        upper = bb.upper.loc[valid_idx]
        middle = bb.middle.loc[valid_idx]
        lower = bb.lower.loc[valid_idx]
        # upper - middle should equal middle - lower (symmetric)
        diff = (upper - middle) - (middle - lower)
        assert (abs(diff) < 1e-10).all()

    def test_constant_series_has_zero_bandwidth(self):
        closes = [100.0] * 30
        ohlcv = make_ohlcv(closes)
        bb = BollingerBands().compute_full(ohlcv, period=20, k=2.0)
        valid_idx = bb.middle.dropna().index
        # Std of constant series = 0, so upper = lower = middle
        assert (abs(bb.upper.loc[valid_idx] - bb.middle.loc[valid_idx]) < 1e-10).all()

    def test_middle_band_equals_sma(self):
        closes = [float(i) for i in range(1, 31)]
        ohlcv = make_ohlcv(closes)
        bb = BollingerBands().compute_full(ohlcv, period=5)
        # Middle at index 4 = SMA(1,2,3,4,5) = 3.0
        assert abs(bb.middle.iloc[4] - 3.0) < 1e-10


# ---------------------------------------------------------------------------
# Candle measurement tests
# ---------------------------------------------------------------------------

class TestCandleMeasurements:

    def _candle(self, o, h, l, c):
        return {"open": o, "high": h, "low": l, "close": c}

    def test_body_length_bullish(self):
        c = self._candle(100, 105, 98, 103)
        assert abs(body_length(c) - 3.0) < 1e-10

    def test_body_length_bearish(self):
        c = self._candle(103, 105, 98, 100)
        assert abs(body_length(c) - 3.0) < 1e-10

    def test_body_length_doji(self):
        c = self._candle(100, 105, 95, 100)
        assert body_length(c) == 0.0

    def test_upper_wick_bullish(self):
        # open=100, close=103, high=105 → upper wick = 105-103 = 2
        c = self._candle(100, 105, 98, 103)
        assert abs(upper_wick(c) - 2.0) < 1e-10

    def test_lower_wick_bullish(self):
        # open=100, close=103, low=98 → lower wick = 100-98 = 2
        c = self._candle(100, 105, 98, 103)
        assert abs(lower_wick(c) - 2.0) < 1e-10

    def test_tail_length_long_setup(self):
        # Long setup → lower wick
        c = self._candle(100, 105, 95, 103)
        assert tail_length(c, "long") == lower_wick(c)

    def test_tail_length_short_setup(self):
        # Short setup → upper wick
        c = self._candle(100, 108, 98, 103)
        assert tail_length(c, "short") == upper_wick(c)

    def test_tail_length_invalid_direction(self):
        c = self._candle(100, 105, 95, 103)
        with pytest.raises(ValueError):
            tail_length(c, "sideways")

    def test_is_bullish(self):
        assert is_bullish(self._candle(100, 105, 98, 103))
        assert not is_bullish(self._candle(103, 105, 98, 100))

    def test_is_bearish(self):
        assert is_bearish(self._candle(103, 105, 98, 100))
        assert not is_bearish(self._candle(100, 105, 98, 103))

    def test_is_doji(self):
        # Body = 0, range = 10 → doji
        assert is_doji(self._candle(100, 105, 95, 100))
        # Body = 5, range = 7 → not doji
        assert not is_doji(self._candle(100, 107, 100, 105))

    def test_is_marubozu(self):
        # No wicks: open=low, close=high
        assert is_marubozu(self._candle(95, 105, 95, 105))
        # Has wicks
        assert not is_marubozu(self._candle(100, 108, 98, 105))

    def test_candle_range(self):
        c = self._candle(100, 110, 90, 105)
        assert abs(candle_range(c) - 20.0) < 1e-10

    def test_body_position_top(self):
        # Body at top: open=close=high → position near 1.0
        c = self._candle(105, 105, 95, 105)
        assert body_position(c) > 0.9

    def test_body_position_bottom(self):
        # Body at bottom: open=close=low → position near 0.0
        c = self._candle(95, 105, 95, 95)
        assert body_position(c) < 0.1
