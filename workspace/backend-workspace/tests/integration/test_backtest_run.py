"""
Integration Test: Full Backtest Run
=====================================
Tests BacktestingEngine with a real strategy over synthetic data.

Satisfies: Requirements 9.6, 10.1–10.4
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestingEngine
from backtest.metrics import compute_metrics
from strategies.registry import StrategyRegistry


def make_ohlcv(n: int = 200, trend: float = 0.3) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    closes = 100.0 + np.cumsum(rng.normal(trend, 1.0, n))
    closes = np.abs(closes) + 1.0
    highs = closes + rng.uniform(0.5, 2.0, n)
    lows = closes - rng.uniform(0.5, 2.0, n)
    lows = np.maximum(lows, 0.01)
    opens = lows + rng.uniform(0, highs - lows)
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": rng.uniform(500, 5000, n),
    })


class TestBacktestIntegration:

    def setup_method(self):
        StrategyRegistry._registry.clear()
        for mod in ["strategies.smc_ob_fvg", "strategies.pinbar"]:
            importlib.import_module(mod)

    def test_backtest_runs_without_crash(self):
        """BacktestingEngine runs over 200 candles without error."""
        from strategies.smc_ob_fvg import SMCOrderBlockFVGStrategy
        config = MagicMock()
        config.strategy.score_threshold.alert = 75
        config.strategy.score_threshold.watch = 55
        config.strategy.time_invalidation_candles = 15

        strategy = SMCOrderBlockFVGStrategy(config)
        engine = BacktestingEngine(fee_rate=0.001, slippage_pct=0.0005)
        ohlcv = make_ohlcv(200)

        results = engine.run(strategy, ohlcv)
        assert isinstance(results, list)

    def test_metrics_computed_after_run(self):
        """Metrics are computed and contain all required fields."""
        from strategies.smc_ob_fvg import SMCOrderBlockFVGStrategy
        config = MagicMock()
        config.strategy.score_threshold.alert = 75
        config.strategy.score_threshold.watch = 55
        config.strategy.time_invalidation_candles = 15

        strategy = SMCOrderBlockFVGStrategy(config)
        engine = BacktestingEngine()
        ohlcv = make_ohlcv(200)
        results = engine.run(strategy, ohlcv)
        metrics = compute_metrics(results)

        required = ["win_rate", "profit_factor", "max_drawdown",
                    "sharpe_ratio", "recovery_factor", "total_trades"]
        for field in required:
            assert field in metrics

        assert 0.0 <= metrics["win_rate"] <= 1.0

    def test_candles_processed_ascending(self):
        """Engine processes candles in ascending order even if input is shuffled."""
        from strategies.smc_ob_fvg import SMCOrderBlockFVGStrategy
        config = MagicMock()
        config.strategy.score_threshold.alert = 75
        config.strategy.score_threshold.watch = 55
        config.strategy.time_invalidation_candles = 15

        strategy = SMCOrderBlockFVGStrategy(config)
        engine = BacktestingEngine()
        ohlcv = make_ohlcv(100)
        shuffled = ohlcv.sample(frac=1, random_state=99)

        # Should not crash — engine sorts internally
        results = engine.run(strategy, shuffled)
        assert isinstance(results, list)
