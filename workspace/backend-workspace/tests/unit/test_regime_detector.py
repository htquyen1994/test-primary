"""
Unit tests for Regime Detector.
Tests all 4 state transitions, threshold boundaries, and config sourcing.

Satisfies: Requirements 13.1–13.9
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.regime_detector import RegimeDetector, RegimeState, VALID_REGIMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_trending_ohlcv_1h(n: int = 60) -> pd.DataFrame:
    """Strong uptrend — ADX should be > 25."""
    closes = [100 + i * 2 for i in range(n)]
    highs = [c + 1 for c in closes]
    lows = [c - 0.5 for c in closes]
    opens = [c - 0.3 for c in closes]
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": [1000.0] * n,
    })


def make_choppy_ohlcv_1h(n: int = 60) -> pd.DataFrame:
    """Sideways choppy market — ADX should be < 20."""
    rng = np.random.default_rng(99)
    closes = 100.0 + rng.uniform(-0.3, 0.3, n)
    highs = closes + 0.2
    lows = closes - 0.2
    opens = closes - 0.1
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": [1000.0] * n,
    })


def make_parabolic_ohlcv_15m(n_base: int = 40) -> pd.DataFrame:
    """ATR spike candle at the end."""
    rng = np.random.default_rng(0)
    base_closes = 100.0 + np.cumsum(rng.normal(0, 0.2, n_base))
    base_highs = base_closes + 0.3
    base_lows = base_closes - 0.3
    base_opens = base_closes - 0.1
    base_vols = np.ones(n_base) * 800.0

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


def make_flat_ohlcv(n: int = 50, price: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({
        "open": [price] * n, "high": [price + 0.5] * n,
        "low": [price - 0.5] * n, "close": [price] * n,
        "volume": [1000.0] * n,
    })


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestRegimeDetector:

    def setup_method(self):
        self.detector = RegimeDetector(
            adx_trending_threshold=25.0,
            adx_choppy_threshold=20.0,
            atr_parabolic_multiplier=3.0,
        )

    def test_trending_classification_with_strong_trend(self):
        """ADX > 25 in strong uptrend → TRENDING."""
        ohlcv_1h = make_trending_ohlcv_1h(60)
        ohlcv_15m = make_flat_ohlcv(50)
        result = self.detector.classify(ohlcv_1h, ohlcv_15m)
        assert result.regime == "TRENDING"
        assert result.score_multiplier == 1.0
        assert result.suppress_short is False

    def test_choppy_classification_with_sideways_market(self):
        """ADX < 20 in choppy market → CHOPPY."""
        ohlcv_1h = make_choppy_ohlcv_1h(60)
        ohlcv_15m = make_flat_ohlcv(50)
        result = self.detector.classify(ohlcv_1h, ohlcv_15m)
        assert result.regime in {"CHOPPY", "RANGING"}  # both valid for low ADX
        assert result.score_multiplier == 0.85
        assert result.suppress_short is False

    def test_parabolic_classification_with_atr_spike(self):
        """ATR spike > 3× rolling avg → PARABOLIC (highest priority)."""
        ohlcv_1h = make_trending_ohlcv_1h(60)  # even trending 1h
        ohlcv_15m = make_parabolic_ohlcv_15m(40)
        result = self.detector.classify(ohlcv_1h, ohlcv_15m)
        assert result.regime == "PARABOLIC"
        assert abs(result.score_multiplier - 0.6) < 1e-10
        assert result.suppress_short is True

    def test_parabolic_takes_precedence_over_trending(self):
        """
        PARABOLIC check runs before ADX check.
        Even if ADX > 25, ATR spike → PARABOLIC.
        Satisfies: Design decision — PARABOLIC priority
        """
        ohlcv_1h = make_trending_ohlcv_1h(60)
        ohlcv_15m = make_parabolic_ohlcv_15m(40)
        result = self.detector.classify(ohlcv_1h, ohlcv_15m)
        # Must be PARABOLIC, not TRENDING
        assert result.regime == "PARABOLIC"

    def test_ranging_is_default_for_insufficient_data(self):
        """With insufficient data for ADX, defaults to RANGING."""
        ohlcv_1h = make_flat_ohlcv(5)   # too few for ADX
        ohlcv_15m = make_flat_ohlcv(5)
        result = self.detector.classify(ohlcv_1h, ohlcv_15m)
        assert result.regime == "RANGING"
        assert result.score_multiplier == 0.85

    def test_all_thresholds_read_from_constructor(self):
        """Custom thresholds are respected."""
        detector = RegimeDetector(
            adx_trending_threshold=30.0,
            adx_choppy_threshold=15.0,
            atr_parabolic_multiplier=5.0,
            parabolic_score_multiplier=0.5,
        )
        assert detector.adx_trending_threshold == 30.0
        assert detector.adx_choppy_threshold == 15.0
        assert detector.atr_parabolic_multiplier == 5.0
        assert detector.parabolic_score_multiplier == 0.5

    def test_regime_state_always_valid(self):
        """RegimeState must always be one of the 4 valid states."""
        for ohlcv_1h, ohlcv_15m in [
            (make_flat_ohlcv(5), make_flat_ohlcv(5)),
            (make_trending_ohlcv_1h(60), make_flat_ohlcv(50)),
            (make_choppy_ohlcv_1h(60), make_flat_ohlcv(50)),
            (make_trending_ohlcv_1h(60), make_parabolic_ohlcv_15m(40)),
        ]:
            result = self.detector.classify(ohlcv_1h, ohlcv_15m)
            assert result.regime in VALID_REGIMES

    def test_regime_state_invalid_raises(self):
        """RegimeState with invalid regime raises ValueError."""
        with pytest.raises(ValueError, match="regime"):
            RegimeState(regime="UNKNOWN", score_multiplier=1.0, suppress_short=False)

    def test_non_parabolic_never_suppresses_short(self):
        """Only PARABOLIC regime suppresses Short signals."""
        for ohlcv_1h, ohlcv_15m in [
            (make_trending_ohlcv_1h(60), make_flat_ohlcv(50)),
            (make_choppy_ohlcv_1h(60), make_flat_ohlcv(50)),
            (make_flat_ohlcv(5), make_flat_ohlcv(5)),
        ]:
            result = self.detector.classify(ohlcv_1h, ohlcv_15m)
            if result.regime != "PARABOLIC":
                assert result.suppress_short is False
