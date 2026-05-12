"""
Property 1: Indicator No-Look-Ahead Invariant
Property 2: Indicator NaN for Insufficient Data
================================================
For any OHLCV array and index T:
  - compute(ohlcv[:T+1])[T] == compute(ohlcv)[T]  (no look-ahead)
  - All output values at indices 0..N-2 are NaN    (insufficient data)

Satisfies: Requirements 4.3, 4.5, 5.1
"""

import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from indicators.atr import ATR
from indicators.rsi import RSI
from indicators.ema import EMA
from indicators.adx import ADX
from indicators.bollinger import BollingerBands


# ---------------------------------------------------------------------------
# OHLCV generation strategy
# ---------------------------------------------------------------------------

def make_ohlcv(n: int, seed_close: float = 100.0) -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame of length n with realistic prices."""
    rng = np.random.default_rng(42)
    closes = seed_close + np.cumsum(rng.normal(0, 1, n))
    closes = np.abs(closes) + 1.0  # ensure positive

    highs = closes + rng.uniform(0.1, 2.0, n)
    lows = closes - rng.uniform(0.1, 2.0, n)
    lows = np.maximum(lows, 0.01)
    opens = lows + rng.uniform(0, highs - lows)
    volumes = rng.uniform(100, 10000, n)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


# Hypothesis strategy: generate (n_total, T) where T < n_total
@st.composite
def ohlcv_with_index(draw, min_n=5, max_n=100):
    n_total = draw(st.integers(min_value=min_n, max_value=max_n))
    T = draw(st.integers(min_value=0, max_value=n_total - 1))
    return n_total, T


# ---------------------------------------------------------------------------
# Property 1: No-Look-Ahead Invariant
# ---------------------------------------------------------------------------

INDICATORS_WITH_PERIOD = [
    (ATR(), 5),
    (RSI(), 5),
    (EMA(), 5),
    (ADX(), 5),
    (BollingerBands(), 5),
]


@given(params=ohlcv_with_index(min_n=20, max_n=80))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property1_atr_no_lookahead(params):
    """
    Property 1 (ATR): compute(ohlcv[:T+1])[T] == compute(ohlcv)[T]
    Extending the array with future candles must not change the value at T.
    """
    n_total, T = params
    period = 5
    assume(T >= period - 1)  # need enough data for a valid value

    ohlcv = make_ohlcv(n_total)
    indicator = ATR()

    val_full = indicator.compute(ohlcv, period).iloc[T]
    val_partial = indicator.compute(ohlcv.iloc[:T + 1], period).iloc[T]

    if math.isnan(val_full):
        assert math.isnan(val_partial)
    else:
        assert abs(val_full - val_partial) < 1e-10, (
            f"ATR look-ahead violation at T={T}: full={val_full}, partial={val_partial}"
        )


@given(params=ohlcv_with_index(min_n=20, max_n=80))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property1_rsi_no_lookahead(params):
    """Property 1 (RSI): no look-ahead invariant."""
    n_total, T = params
    period = 5
    assume(T >= period)

    ohlcv = make_ohlcv(n_total)
    indicator = RSI()

    val_full = indicator.compute(ohlcv, period).iloc[T]
    val_partial = indicator.compute(ohlcv.iloc[:T + 1], period).iloc[T]

    if math.isnan(val_full):
        assert math.isnan(val_partial)
    else:
        assert abs(val_full - val_partial) < 1e-10


@given(params=ohlcv_with_index(min_n=20, max_n=80))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property1_ema_no_lookahead(params):
    """Property 1 (EMA): no look-ahead invariant."""
    n_total, T = params
    period = 5
    assume(T >= period - 1)

    ohlcv = make_ohlcv(n_total)
    indicator = EMA()

    val_full = indicator.compute(ohlcv, period).iloc[T]
    val_partial = indicator.compute(ohlcv.iloc[:T + 1], period).iloc[T]

    if math.isnan(val_full):
        assert math.isnan(val_partial)
    else:
        assert abs(val_full - val_partial) < 1e-10


@given(params=ohlcv_with_index(min_n=40, max_n=80))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property1_adx_no_lookahead(params):
    """Property 1 (ADX): no look-ahead invariant."""
    n_total, T = params
    period = 5
    assume(T >= 2 * period - 1)  # ADX needs 2*period candles

    ohlcv = make_ohlcv(n_total)
    indicator = ADX()

    val_full = indicator.compute(ohlcv, period).iloc[T]
    val_partial = indicator.compute(ohlcv.iloc[:T + 1], period).iloc[T]

    if math.isnan(val_full):
        assert math.isnan(val_partial)
    else:
        assert abs(val_full - val_partial) < 1e-10


@given(params=ohlcv_with_index(min_n=20, max_n=80))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property1_bb_no_lookahead(params):
    """Property 1 (BollingerBands): no look-ahead invariant."""
    n_total, T = params
    period = 5
    assume(T >= period - 1)

    ohlcv = make_ohlcv(n_total)
    indicator = BollingerBands()

    val_full = indicator.compute(ohlcv, period).iloc[T]
    val_partial = indicator.compute(ohlcv.iloc[:T + 1], period).iloc[T]

    if math.isnan(val_full):
        assert math.isnan(val_partial)
    else:
        assert abs(val_full - val_partial) < 1e-10


# ---------------------------------------------------------------------------
# Property 2: NaN for Insufficient Data
# ---------------------------------------------------------------------------

@given(
    n=st.integers(min_value=1, max_value=30),
    period=st.integers(min_value=2, max_value=30),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property2_atr_nan_insufficient(n: int, period: int):
    """
    Property 2 (ATR): indices 0..period-2 must be NaN when n < period.
    """
    assume(n < period)
    ohlcv = make_ohlcv(n)
    result = ATR().compute(ohlcv, period)
    assert result.isna().all(), f"ATR should be all NaN when n={n} < period={period}"


@given(
    n=st.integers(min_value=1, max_value=30),
    period=st.integers(min_value=2, max_value=30),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property2_rsi_nan_insufficient(n: int, period: int):
    """Property 2 (RSI): all NaN when n <= period."""
    assume(n <= period)
    ohlcv = make_ohlcv(n)
    result = RSI().compute(ohlcv, period)
    assert result.isna().all()


@given(
    n=st.integers(min_value=1, max_value=30),
    period=st.integers(min_value=2, max_value=30),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property2_ema_nan_insufficient(n: int, period: int):
    """Property 2 (EMA): all NaN when n < period."""
    assume(n < period)
    ohlcv = make_ohlcv(n)
    result = EMA().compute(ohlcv, period)
    assert result.isna().all()


@given(
    n=st.integers(min_value=1, max_value=30),
    period=st.integers(min_value=2, max_value=30),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property2_adx_nan_insufficient(n: int, period: int):
    """Property 2 (ADX): all NaN when n < period+1."""
    assume(n < period + 1)
    ohlcv = make_ohlcv(n)
    result = ADX().compute(ohlcv, period)
    assert result.isna().all()


@given(
    n=st.integers(min_value=1, max_value=30),
    period=st.integers(min_value=2, max_value=30),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property2_bb_nan_insufficient(n: int, period: int):
    """Property 2 (BollingerBands): all NaN when n < period."""
    assume(n < period)
    ohlcv = make_ohlcv(n)
    result = BollingerBands().compute(ohlcv, period)
    assert result.isna().all()
