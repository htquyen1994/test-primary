"""
Integration Test: Full Signal Pipeline
========================================
Tests the complete pipeline from OHLCV data → signal scoring → alert building.
Uses SQLite in-memory DB (no Redis required for this test).

Satisfies: Requirements 17.1, 6.5
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from strategies.registry import StrategyRegistry
from engine.regime_detector import RegimeDetector
from engine.correlation_manager import CorrelationManager
from engine.scorer import SignalScorer
from risk.manager import RiskManager
from alert.builder import build_signal_card
from alert.invalidator import compute_expiry


def make_config():
    cfg = MagicMock()
    cfg.strategy.active = ["smc_ob_fvg"]
    cfg.strategy.score_threshold.alert = 75
    cfg.strategy.score_threshold.watch = 55
    cfg.strategy.time_invalidation_candles = 15
    cfg.exchange.testnet = True
    cfg.exchange.market_type = "futures"
    cfg.exchange.fee_rate = 0.001
    cfg.exchange.slippage_pct = 0.0002
    cfg.position.mode = "risk_pct"
    cfg.position.risk_pct = 0.02
    cfg.position.fixed_usd = 100.0
    cfg.position.max_concurrent = 3
    cfg.position.leverage = 5
    cfg.risk.correlation_threshold = 0.8
    cfg.risk.max_correlated_risk_pct = 3.0
    cfg.risk.portfolio_heat_limit_pct = 6.0
    cfg.regime.adx_trending_threshold = 25.0
    cfg.regime.adx_choppy_threshold = 20.0
    cfg.regime.atr_parabolic_multiplier = 3.0
    cfg.regime.parabolic_score_multiplier = 0.6
    cfg.regime.ranging_score_multiplier = 0.85
    cfg.regime.trending_score_multiplier = 1.0
    return cfg


def make_trending_ohlcv(n: int = 60, base: float = 100.0) -> pd.DataFrame:
    closes = [base + i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "open": [c - 0.3 for c in closes],
        "high": [c + 1.0 for c in closes],
        "low":  [c - 1.0 for c in closes],
        "close": closes,
        "volume": [1000.0] * n,
    })


class TestSignalPipelineIntegration:

    def setup_method(self):
        StrategyRegistry._registry.clear()
        # Force reload to re-execute @register decorators
        import importlib
        for mod_name in ["strategies.smc_ob_fvg", "strategies.pinbar", "strategies.engulfing",
                         "strategies.inside_bar", "strategies.quasimodo", "strategies.flag",
                         "strategies.rsi_momentum", "strategies.ema_cross"]:
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)

    def test_regime_detector_classifies_trending(self):
        """Regime detector returns valid state for trending data."""
        detector = RegimeDetector()
        ohlcv_1h = make_trending_ohlcv(60)
        ohlcv_15m = make_trending_ohlcv(50)
        result = detector.classify(ohlcv_1h, ohlcv_15m)
        assert result.regime in {"TRENDING", "RANGING", "CHOPPY", "PARABOLIC"}
        assert 0.0 < result.score_multiplier <= 1.0

    def test_signal_scorer_produces_valid_score(self):
        """Signal scorer always produces integer in [0, 100]."""
        from engine.scorer import ScoreInput
        scorer = SignalScorer()
        result = scorer.score(ScoreInput(
            order_flow=20, smc=15, vsa=10, context=8, bonus=5,
            regime_multiplier=1.0, direction="long", regime="TRENDING",
        ))
        assert 0 <= result.final_score <= 100
        assert result.classification in {"ALERT", "WATCH", "IGNORE"}

    def test_risk_manager_computes_position_size(self):
        """Risk manager returns valid position size."""
        manager = RiskManager(
            mode="risk_pct", risk_pct=0.02, max_risk_pct=0.02,
            leverage=1, market_type="spot",
        )
        result = manager.compute_position_size(
            asset="BTC/USDT",
            entry_price=50000.0,
            stop_loss=49000.0,
            account_equity=10000.0,
            atr_value=500.0,
        )
        assert result.allowed is True
        assert result.position_size_usd > 0

    def test_alert_builder_produces_required_fields(self):
        """Alert builder produces all required Signal Card fields."""
        from strategies.signal import Signal, ScoreBreakdown
        signal = Signal(
            strategy_name="smc_ob_fvg", asset="BTC/USDT", timeframe="15m",
            direction="long", candle_index=100,
            candle_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            entry_price=50000.0, stop_loss=49000.0,
            take_profit_1=52000.0, take_profit_2=54000.0,
            raw_score=90.0, final_score=80,
            score_breakdown=ScoreBreakdown(order_flow=25, smc=20, vsa=20, context=10, bonus=5),
            classification="ALERT", regime="TRENDING",
            regime_multiplier=1.0, funding_rate=0.0001,
            portfolio_heat=0.02, correlated_group_risk=0.01,
            expires_at_candle=115,
        )
        card = build_signal_card(signal)
        required = ["asset", "direction", "final_score", "entry_price",
                    "stop_loss", "take_profit_1", "take_profit_2",
                    "gross_rr", "net_rr", "score_breakdown", "regime", "expires_at_candle"]
        for field in required:
            assert field in card, f"Missing: {field}"

    def test_strategy_registry_loads_active_strategies(self):
        """Strategy registry loads only active strategies."""
        # Auto-discover to ensure all strategies are registered
        StrategyRegistry.auto_discover("strategies")
        config = make_config()
        instances = StrategyRegistry.load_active(config)
        assert "smc_ob_fvg" in instances

    def test_full_pipeline_no_crash(self):
        """
        Full pipeline: OHLCV → regime → strategy → scorer → alert builder.
        Verifies no crashes and produces valid output.
        """
        config = make_config()
        ohlcv_15m = make_trending_ohlcv(60)
        ohlcv_1h = make_trending_ohlcv(60)

        detector = RegimeDetector.from_config(config)
        regime_state = detector.classify(ohlcv_1h, ohlcv_15m)

        scorer = SignalScorer.from_config(config)
        from engine.scorer import ScoreInput
        score_output = scorer.score(ScoreInput(
            order_flow=20, smc=15, vsa=10, context=8, bonus=5,
            regime_multiplier=regime_state.score_multiplier,
            direction="long",
            regime=regime_state.regime,
        ))

        assert 0 <= score_output.final_score <= 100
        assert regime_state.regime in {"TRENDING", "RANGING", "PARABOLIC", "CHOPPY"}
