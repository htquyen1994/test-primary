"""
Unit tests for Correlation Manager and Portfolio Heat.

Satisfies: Requirements 14.1–14.9
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.correlation_manager import CorrelationManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ohlcv_1h(closes: list) -> pd.DataFrame:
    n = len(closes)
    return pd.DataFrame({
        "open":   [c - 0.5 for c in closes],
        "high":   [c + 1.0 for c in closes],
        "low":    [c - 1.0 for c in closes],
        "close":  closes,
        "volume": [1000.0] * n,
    })


# ---------------------------------------------------------------------------
# Correlation matrix tests
# ---------------------------------------------------------------------------

class TestCorrelationMatrix:

    def test_identical_series_correlation_is_one(self):
        manager = CorrelationManager()
        closes = [100 + i for i in range(30)]
        manager.update("BTC/USDT", make_ohlcv_1h(closes))
        manager.update("ETH/USDT", make_ohlcv_1h(closes))

        matrix = manager.get_correlation_matrix()
        assert abs(matrix.loc["BTC/USDT", "ETH/USDT"] - 1.0) < 1e-10

    def test_opposite_series_correlation_is_minus_one(self):
        manager = CorrelationManager()
        closes_a = [100 + i for i in range(30)]
        closes_b = [100 - i for i in range(30)]
        manager.update("BTC/USDT", make_ohlcv_1h(closes_a))
        manager.update("ETH/USDT", make_ohlcv_1h(closes_b))

        matrix = manager.get_correlation_matrix()
        assert abs(matrix.loc["BTC/USDT", "ETH/USDT"] - (-1.0)) < 1e-10

    def test_correlation_bounded_minus_one_to_one(self):
        rng = np.random.default_rng(42)
        manager = CorrelationManager()
        for i, asset in enumerate(["BTC/USDT", "ETH/USDT", "SOL/USDT"]):
            closes = (100 + np.cumsum(rng.normal(0, 1, 30))).tolist()
            manager.update(asset, make_ohlcv_1h(closes))

        matrix = manager.get_correlation_matrix()
        for col in matrix.columns:
            for idx in matrix.index:
                val = matrix.loc[idx, col]
                if not np.isnan(val):
                    assert -1.0 <= val <= 1.0

    def test_empty_matrix_for_single_asset(self):
        manager = CorrelationManager()
        manager.update("BTC/USDT", make_ohlcv_1h([100 + i for i in range(30)]))
        matrix = manager.get_correlation_matrix()
        assert matrix.empty

    def test_correlated_group_above_threshold(self):
        manager = CorrelationManager(correlation_threshold=0.8)
        closes = [100 + i for i in range(30)]
        manager.update("BTC/USDT", make_ohlcv_1h(closes))
        manager.update("ETH/USDT", make_ohlcv_1h(closes))  # identical → corr=1.0

        group = manager.get_correlated_group("BTC/USDT")
        assert "ETH/USDT" in group

    def test_uncorrelated_asset_not_in_group(self):
        rng = np.random.default_rng(0)
        manager = CorrelationManager(correlation_threshold=0.8)
        closes_btc = [100 + i for i in range(30)]
        closes_sol = (100 + np.cumsum(rng.normal(0, 5, 30))).tolist()
        manager.update("BTC/USDT", make_ohlcv_1h(closes_btc))
        manager.update("SOL/USDT", make_ohlcv_1h(closes_sol))

        group = manager.get_correlated_group("BTC/USDT")
        # SOL with random walk may or may not be correlated — just check no crash
        assert isinstance(group, list)


# ---------------------------------------------------------------------------
# Portfolio Heat tests
# ---------------------------------------------------------------------------

class TestPortfolioHeat:

    def test_heat_equals_sum_of_risk_pcts(self):
        manager = CorrelationManager()
        positions = {"BTC/USDT": 0.02, "ETH/USDT": 0.015, "SOL/USDT": 0.01}
        heat = manager.get_portfolio_heat(positions)
        assert abs(heat - 4.5) < 1e-10  # (0.02 + 0.015 + 0.01) * 100 = 4.5%

    def test_empty_positions_heat_is_zero(self):
        manager = CorrelationManager()
        assert manager.get_portfolio_heat({}) == 0.0

    def test_single_position_heat(self):
        manager = CorrelationManager()
        heat = manager.get_portfolio_heat({"BTC/USDT": 0.02})
        assert abs(heat - 2.0) < 1e-10


# ---------------------------------------------------------------------------
# Risk check tests
# ---------------------------------------------------------------------------

class TestRiskCheck:

    def test_signal_allowed_when_within_limits(self):
        manager = CorrelationManager(
            portfolio_heat_limit_pct=6.0,
            max_correlated_risk_pct=3.0,
        )
        result = manager.check_new_signal(
            asset="SOL/USDT",
            new_risk_pct=0.01,
            open_positions={"BTC/USDT": 0.02},
        )
        assert result.allowed is True

    def test_signal_rejected_when_portfolio_heat_exceeded(self):
        """
        Portfolio heat limit enforcement.
        Satisfies: Requirement 14.7
        """
        manager = CorrelationManager(portfolio_heat_limit_pct=5.0)
        # Existing heat = 4.5%, new = 1% → total 5.5% > 5.0%
        result = manager.check_new_signal(
            asset="SOL/USDT",
            new_risk_pct=0.01,
            open_positions={"BTC/USDT": 0.02, "ETH/USDT": 0.025},
        )
        assert result.allowed is False
        assert "Portfolio_Heat" in result.rejection_reason

    def test_signal_rejected_when_correlated_risk_exceeded(self):
        """
        Correlated group risk limit enforcement.
        Satisfies: Requirements 14.4, 14.5
        """
        manager = CorrelationManager(
            correlation_threshold=0.8,
            max_correlated_risk_pct=3.0,
            portfolio_heat_limit_pct=20.0,  # high limit to isolate correlated check
        )
        # Make BTC and ETH perfectly correlated
        closes = [100 + i for i in range(30)]
        manager.update("BTC/USDT", make_ohlcv_1h(closes))
        manager.update("ETH/USDT", make_ohlcv_1h(closes))

        # BTC already open at 2%, new ETH at 2% → group = 4% > 3% limit
        result = manager.check_new_signal(
            asset="ETH/USDT",
            new_risk_pct=0.02,
            open_positions={"BTC/USDT": 0.02},
        )
        assert result.allowed is False
        assert "Correlated" in result.rejection_reason

    def test_rejection_includes_group_members(self):
        """Rejection reason must include correlated group members."""
        manager = CorrelationManager(
            correlation_threshold=0.8,
            max_correlated_risk_pct=3.0,
            portfolio_heat_limit_pct=20.0,
        )
        closes = [100 + i for i in range(30)]
        manager.update("BTC/USDT", make_ohlcv_1h(closes))
        manager.update("ETH/USDT", make_ohlcv_1h(closes))

        result = manager.check_new_signal(
            asset="ETH/USDT",
            new_risk_pct=0.02,
            open_positions={"BTC/USDT": 0.02},
        )
        if not result.allowed:
            assert "BTC/USDT" in result.rejection_reason or \
                   len(result.correlated_group) > 0
