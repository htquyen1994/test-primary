"""
Property 12: Regime Output Validity
Property 13: PARABOLIC Short Suppression
=========================================

Property 12: For any valid OHLCV DataFrame, RegimeDetector must always
return exactly one of {TRENDING, RANGING, PARABOLIC, CHOPPY} — never null.

Property 13: When ATR(14) on 15m exceeds 3× rolling average ATR(14),
the regime must be PARABOLIC, score_multiplier must be 0.6, and
suppress_short must be True.

Satisfies: Requirements 13.1, 13.4, 13.5
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from engine.regime_detector import RegimeDetector, RegimeState, VALID_REGIMES


# ---------------------------------------------------------------------------
# OHLCV generation helpers
# ---------------------------------------------------------------------------

def make_ohlcv(n: int, base: float = 100.0, volatility: float = 1.0) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    closes = base + np.cumsum(rng.normal(0, volatility, n))
    closes = np.abs(closes) + 1.0
    highs = closes + rng.uniform(0.1, volatility * 2, n)
    lows = closes - rng.uniform(0.1, volatility * 2, n)
    lows = np.maximum(lows, 0.01)
    opens = lows + rng.uniform(0, highs - lows)
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": rng.uniform(100, 10000, n),
    })


def make_parabolic_ohlcv(n_base: int = 40) -> pd.DataFrame:
    """
    Creates 15m OHLCV where the last candle has an ATR spike > 3× rolling avg.
    """
    rng = np.random.default_rng(0)
    # Base candles with small, consistent ranges
    base_closes = 100.0 + np.cumsum(rng.normal(0, 0.2, n_base))
    base_highs = base_closes + 0.3
    base_lows = base_closes - 0.3
    base_opens = base_closes - 0.1
    base_vols = rng.uniform(500, 1000, n_base)

    # Spike candle: range = 20× normal range
    spike_close = base_closes[-1] + 15.0
    spike_high = spike_close + 10.0
    spike_low = base_closes[-1] - 5.0

    closes = np.append(base_closes, spike_close)
    highs = np.append(base_highs, spike_high)
    lows = np.append(base_lows, spike_low)
    opens = np.append(base_opens, base_closes[-1])
    vols = np.append(base_vols, 50000.0)

    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": vols,
    })


# ---------------------------------------------------------------------------
# Property 12: Regime Output Validity
# ---------------------------------------------------------------------------

@given(
    n_1h=st.integers(min_value=5, max_value=100),
    n_15m=st.integers(min_value=5, max_value=100),
    volatility=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property12_regime_output_always_valid(n_1h: int, n_15m: int, volatility: float):
    """
    Property 12: RegimeDetector.classify() always returns exactly one of
    {TRENDING, RANGING, PARABOLIC, CHOPPY} — never null, never undefined.

    Validates: Requirement 13.1
    """
    detector = RegimeDetector()
    ohlcv_1h = make_ohlcv(n_1h, volatility=volatility)
    ohlcv_15m = make_ohlcv(n_15m, volatility=volatility)

    result = detector.classify(ohlcv_1h, ohlcv_15m)

    assert result is not None, "RegimeDetector must never return None"
    assert result.regime in VALID_REGIMES, (
        f"Regime '{result.regime}' is not one of {VALID_REGIMES}"
    )
    assert isinstance(result.score_multiplier, float), "score_multiplier must be float"
    assert 0.0 < result.score_multiplier <= 1.0, (
        f"score_multiplier {result.score_multiplier} must be in (0, 1]"
    )
    assert isinstance(result.suppress_short, bool), "suppress_short must be bool"


# ---------------------------------------------------------------------------
# Property 13: PARABOLIC Short Suppression
# ---------------------------------------------------------------------------

def test_property13_parabolic_suppresses_short():
    """
    Property 13: When ATR(14) on 15m exceeds 3× rolling average ATR(14),
    regime must be PARABOLIC, multiplier must be 0.6, suppress_short must be True.

    Validates: Requirements 13.4, 13.5
    """
    detector = RegimeDetector(
        atr_parabolic_multiplier=3.0,
        parabolic_score_multiplier=0.6,
    )
    ohlcv_1h = make_ohlcv(50)
    ohlcv_15m = make_parabolic_ohlcv(n_base=40)

    result = detector.classify(ohlcv_1h, ohlcv_15m)

    assert result.regime == "PARABOLIC", (
        f"Expected PARABOLIC regime for ATR spike, got {result.regime}"
    )
    assert abs(result.score_multiplier - 0.6) < 1e-10, (
        f"PARABOLIC multiplier must be 0.6, got {result.score_multiplier}"
    )
    assert result.suppress_short is True, (
        "PARABOLIC regime must suppress Short signals"
    )


@given(
    n_base=st.integers(min_value=35, max_value=60),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property13_parabolic_always_suppresses_short(n_base: int):
    """
    Property 13 (generalized): For any OHLCV data where ATR spike is detected,
    suppress_short must always be True and multiplier must be 0.6.
    """
    detector = RegimeDetector(atr_parabolic_multiplier=3.0)
    ohlcv_1h = make_ohlcv(50)
    ohlcv_15m = make_parabolic_ohlcv(n_base=n_base)

    result = detector.classify(ohlcv_1h, ohlcv_15m)

    if result.regime == "PARABOLIC":
        assert result.suppress_short is True
        assert abs(result.score_multiplier - 0.6) < 1e-10
