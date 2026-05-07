"""
Unit tests for Risk Manager.

Satisfies: Requirements 7.1–7.5, 14.4, 14.5, 14.7
"""

from __future__ import annotations

import pytest

from risk.manager import RiskManager


class TestRiskManager:

    def test_risk_pct_mode_computes_correct_size(self):
        """
        position_size = (equity * risk_pct) / (sl_pct + fee_cost)
        Satisfies: Requirement 7.1
        """
        manager = RiskManager(mode="risk_pct", risk_pct=0.02, max_risk_pct=0.02,
                               leverage=1, market_type="spot")
        result = manager.compute_position_size(
            asset="BTC/USDT",
            entry_price=50000.0,
            stop_loss=49000.0,   # sl_pct = 1000/50000 = 2%
            account_equity=10000.0,
            atr_value=500.0,
        )
        assert result.allowed is True
        assert result.position_size_usd > 0
        # Max loss should be ~2% of 10000 = ~200 USD
        sl_dist = abs(50000 - 49000)
        max_loss = result.position_size_usd * (sl_dist / 50000)
        assert max_loss <= 10000 * 0.02 * 1.01  # within 1% tolerance

    def test_fixed_usd_mode_returns_configured_amount(self):
        """Satisfies: Requirement 7.1 (fixed_usd mode)"""
        manager = RiskManager(mode="fixed_usd", fixed_usd=100.0, max_risk_pct=0.10,
                               leverage=1, market_type="spot")
        result = manager.compute_position_size(
            asset="BTC/USDT",
            entry_price=50000.0,
            stop_loss=49000.0,
            account_equity=10000.0,
            atr_value=500.0,
        )
        assert result.allowed is True
        assert result.position_size_usd == 100.0

    def test_atr_zero_rejects_signal(self):
        """Satisfies: Requirement 7.4"""
        manager = RiskManager(mode="risk_pct", risk_pct=0.02, max_risk_pct=0.02)
        result = manager.compute_position_size(
            asset="BTC/USDT",
            entry_price=50000.0,
            stop_loss=49000.0,
            account_equity=10000.0,
            atr_value=0.0,  # ATR = 0
        )
        assert result.allowed is False
        assert "ATR" in result.rejection_reason

    def test_leverage_applied_for_futures(self):
        """Futures position size = spot size × leverage. Satisfies: Req 7.5"""
        spot_manager = RiskManager(mode="fixed_usd", fixed_usd=100.0, max_risk_pct=0.10,
                                    leverage=1, market_type="spot")
        futures_manager = RiskManager(mode="fixed_usd", fixed_usd=100.0, max_risk_pct=0.10,
                                       leverage=5, market_type="futures")

        spot_result = spot_manager.compute_position_size(
            "BTC/USDT", 50000.0, 49000.0, 10000.0, 500.0)
        futures_result = futures_manager.compute_position_size(
            "BTC/USDT", 50000.0, 49000.0, 10000.0, 500.0)

        assert futures_result.position_size_usd == spot_result.position_size_usd * 5

    def test_leverage_not_applied_for_spot(self):
        """Spot positions do not use leverage. Satisfies: Req 7.5"""
        manager = RiskManager(mode="fixed_usd", fixed_usd=100.0, max_risk_pct=0.10,
                               leverage=10, market_type="spot")
        result = manager.compute_position_size(
            "BTC/USDT", 50000.0, 49000.0, 10000.0, 500.0)
        assert result.position_size_usd == 100.0  # leverage not applied

    def test_max_risk_cap_enforced(self):
        """Max loss must not exceed equity × max_risk_pct. Satisfies: Req 7.3"""
        manager = RiskManager(mode="risk_pct", risk_pct=0.02, max_risk_pct=0.02,
                               leverage=1, market_type="spot")
        result = manager.compute_position_size(
            asset="BTC/USDT",
            entry_price=50000.0,
            stop_loss=49000.0,
            account_equity=10000.0,
            atr_value=500.0,
        )
        assert result.allowed is True
        sl_dist = abs(50000 - 49000)
        max_loss = result.position_size_usd * (sl_dist / 50000)
        assert max_loss <= 10000 * 0.02 * 1.01

    def test_zero_sl_distance_rejects(self):
        manager = RiskManager(mode="risk_pct", risk_pct=0.02, max_risk_pct=0.02)
        result = manager.compute_position_size(
            "BTC/USDT", 50000.0, 50000.0, 10000.0, 500.0)  # SL = entry
        assert result.allowed is False
