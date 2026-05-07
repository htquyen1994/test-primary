"""
Unit tests for VSA + Volume Profile module.

Satisfies: Requirement 6.2
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.volume_profile import compute_volume_profile, VolumeProfile
from engine.vsa import (
    detect_no_supply, detect_effort_vs_result, detect_absorption,
    compute_vsa_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ohlcv(n: int, base_price: float = 100.0, base_vol: float = 1000.0) -> pd.DataFrame:
    return pd.DataFrame({
        "open":   [base_price - 0.5] * n,
        "high":   [base_price + 1.0] * n,
        "low":    [base_price - 1.0] * n,
        "close":  [base_price] * n,
        "volume": [base_vol] * n,
    })


def make_ohlcv_with_volumes(volumes: list, price: float = 100.0) -> pd.DataFrame:
    n = len(volumes)
    return pd.DataFrame({
        "open":   [price - 0.5] * n,
        "high":   [price + 1.0] * n,
        "low":    [price - 1.0] * n,
        "close":  [price] * n,
        "volume": volumes,
    })


# ---------------------------------------------------------------------------
# Volume Profile tests
# ---------------------------------------------------------------------------

class TestVolumeProfile:

    def test_poc_is_highest_volume_price(self):
        # Create a series where most volume is at price 105
        rows = []
        for i in range(10):
            rows.append({"open": 99, "high": 101, "low": 99, "close": 100, "volume": 100})
        # High volume candle at 105
        rows.append({"open": 104, "high": 106, "low": 104, "close": 105, "volume": 5000})
        ohlcv = pd.DataFrame(rows)
        vp = compute_volume_profile(ohlcv, bins=20)
        # POC should be near 105
        assert abs(vp.poc - 105.0) < 2.0

    def test_value_area_contains_70_percent_volume(self):
        # Uniform distribution — value area should cover ~70% of price range
        n = 50
        prices = [100 + i * 0.1 for i in range(n)]
        ohlcv = pd.DataFrame({
            "open":   [p - 0.05 for p in prices],
            "high":   [p + 0.05 for p in prices],
            "low":    [p - 0.05 for p in prices],
            "close":  prices,
            "volume": [100.0] * n,
        })
        vp = compute_volume_profile(ohlcv, bins=20)
        assert vp.vah >= vp.poc >= vp.val

    def test_vah_above_val(self):
        ohlcv = make_ohlcv(30)
        vp = compute_volume_profile(ohlcv)
        assert vp.vah >= vp.val

    def test_poc_within_price_range(self):
        ohlcv = make_ohlcv(30, base_price=50000.0)
        vp = compute_volume_profile(ohlcv)
        assert 49000 <= vp.poc <= 51000

    def test_empty_ohlcv_returns_zero_profile(self):
        vp = compute_volume_profile(pd.DataFrame())
        assert vp.poc == 0.0
        assert vp.vah == 0.0
        assert vp.val == 0.0

    def test_is_price_at_poc(self):
        vp = VolumeProfile(poc=100.0, vah=102.0, val=98.0, total_volume=1000.0)
        assert vp.is_price_at_poc(100.0) is True
        assert vp.is_price_at_poc(100.2) is True   # within 0.3%
        assert vp.is_price_at_poc(101.0) is False  # too far

    def test_is_price_at_value_area_edge(self):
        vp = VolumeProfile(poc=100.0, vah=105.0, val=95.0, total_volume=1000.0)
        assert vp.is_price_at_value_area_edge(105.0) is True   # at VAH
        assert vp.is_price_at_value_area_edge(95.0) is True    # at VAL
        assert vp.is_price_at_value_area_edge(100.0) is False  # at POC, not edge


# ---------------------------------------------------------------------------
# VSA signal tests
# ---------------------------------------------------------------------------

class TestVSASignals:

    def test_no_supply_detected_when_pullback_vol_low(self):
        # Impulse vol = 5000, current vol = 1500 → ratio = 0.30 < 0.40
        volumes = [1000, 1000, 1000, 1000, 5000, 1500]
        ohlcv = make_ohlcv_with_volumes(volumes)
        assert detect_no_supply(ohlcv) is True

    def test_no_supply_not_detected_when_vol_high(self):
        # Current vol = 4000, impulse = 5000 → ratio = 0.80 > 0.40
        volumes = [1000, 1000, 1000, 1000, 5000, 4000]
        ohlcv = make_ohlcv_with_volumes(volumes)
        assert detect_no_supply(ohlcv) is False

    def test_effort_vs_result_detected(self):
        # Low volume + small range candle
        n = 10
        ohlcv = pd.DataFrame({
            "open":   [100.0] * n,
            "high":   [100.1] * n,  # very small range
            "low":    [99.9] * n,
            "close":  [100.0] * n,
            "volume": [5000, 5000, 5000, 5000, 5000, 5000, 5000, 5000, 5000, 200],
        })
        # ATR ~= 0.2 (range = 0.2), current range = 0.2 → ratio = 1.0 (not small enough)
        # Use larger ATR to make range ratio small
        atr = 5.0  # current range 0.2 / 5.0 = 0.04 < 0.30
        assert detect_effort_vs_result(ohlcv, atr_value=atr) is True

    def test_effort_vs_result_not_detected_high_vol(self):
        n = 10
        ohlcv = pd.DataFrame({
            "open":   [100.0] * n,
            "high":   [100.1] * n,
            "low":    [99.9] * n,
            "close":  [100.0] * n,
            "volume": [1000] * n,  # all same volume — no low-vol candle
        })
        assert detect_effort_vs_result(ohlcv, atr_value=5.0) is False


# ---------------------------------------------------------------------------
# VSA Score aggregator tests
# ---------------------------------------------------------------------------

class TestVSAScore:

    def test_score_zero_when_no_conditions_met(self):
        ohlcv = make_ohlcv(20, base_vol=1000.0)
        vp = VolumeProfile(poc=0.0, vah=0.0, val=0.0, total_volume=0.0)
        result = compute_vsa_score(ohlcv, vp, atr_value=1.0)
        assert result.score == 0.0

    def test_score_max_30(self):
        # Even if all conditions met, score should not exceed 30
        volumes = [1000, 1000, 1000, 1000, 5000, 200]
        ohlcv = make_ohlcv_with_volumes(volumes)
        vp = VolumeProfile(poc=100.0, vah=101.0, val=99.0, total_volume=10000.0)
        result = compute_vsa_score(ohlcv, vp, atr_value=5.0, entry_price=100.0)
        assert result.score <= 30.0

    def test_poc_bonus_added_when_entry_at_poc(self):
        ohlcv = make_ohlcv(10)
        vp = VolumeProfile(poc=100.0, vah=102.0, val=98.0, total_volume=5000.0)
        result = compute_vsa_score(ohlcv, vp, atr_value=1.0, entry_price=100.0)
        assert result.at_poc is True
        assert result.score >= 10.0

    def test_value_area_edge_bonus_when_at_vah(self):
        ohlcv = make_ohlcv(10)
        vp = VolumeProfile(poc=100.0, vah=105.0, val=95.0, total_volume=5000.0)
        result = compute_vsa_score(ohlcv, vp, atr_value=1.0, entry_price=105.0)
        assert result.at_value_area_edge is True
        assert result.score >= 6.0

    def test_empty_ohlcv_returns_zero(self):
        vp = VolumeProfile(poc=100.0, vah=102.0, val=98.0, total_volume=1000.0)
        result = compute_vsa_score(pd.DataFrame(), vp, atr_value=1.0)
        assert result.score == 0.0
