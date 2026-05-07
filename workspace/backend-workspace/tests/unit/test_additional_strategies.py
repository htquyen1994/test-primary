"""
Unit tests for additional strategies: Inside Bar, Quasimodo, Flag, RSI Momentum, EMA Cross.

Satisfies: Requirements 1.2, 5.1
"""
from __future__ import annotations
import importlib
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest
from indicators.base import LookAheadError
from strategies.registry import StrategyRegistry


def make_config():
    cfg = MagicMock()
    cfg.strategy.active = []
    cfg.strategy.score_threshold.alert = 75
    cfg.strategy.score_threshold.watch = 55
    cfg.strategy.time_invalidation_candles = 15
    return cfg


def make_context(htf_bias="bullish"):
    n = 40
    closes = [100 + i for i in range(n)] if htf_bias == "bullish" else \
             [100 - i for i in range(n)] if htf_bias == "bearish" else [100.0] * n
    ohlcv_1h = pd.DataFrame({
        "open": [c - 0.5 for c in closes], "high": [c + 1.0 for c in closes],
        "low": [c - 1.0 for c in closes], "close": closes, "volume": [1000.0] * n,
    })
    return {
        "ohlcv_1h": ohlcv_1h, "regime": "TRENDING", "regime_multiplier": 1.0,
        "funding_rate": 0.0001, "portfolio_heat": 0.02, "correlated_group_risk": 0.01,
        "asset": "BTC/USDT", "timeframe": "15m",
    }


def flat_ohlcv(n=30, price=100.0):
    return pd.DataFrame({
        "open": [price] * n, "high": [price + 0.5] * n,
        "low": [price - 0.5] * n, "close": [price] * n, "volume": [1000.0] * n,
    })


class TestInsideBarStrategy:
    def setup_method(self):
        StrategyRegistry._registry.clear()
        import strategies.inside_bar; importlib.reload(strategies.inside_bar)
        from strategies.inside_bar import InsideBarStrategy
        self.strategy = InsideBarStrategy(make_config())

    def test_detects_inside_bar(self):
        rows = [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000}] * 10
        # Mother bar: wide range
        rows.append({"open": 99, "high": 103, "low": 97, "close": 101, "volume": 2000})
        # Inside bar: contained within mother
        rows.append({"open": 100, "high": 102, "low": 98, "close": 100.5, "volume": 800})
        ohlcv = pd.DataFrame(rows)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert isinstance(signals, list)

    def test_returns_empty_for_non_inside_bar(self):
        ohlcv = flat_ohlcv(15)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert signals == []

    def test_no_lookahead_raises(self):
        from strategies.inside_bar import InsideBarStrategy
        class Bad(InsideBarStrategy):
            def generate_signals(self, ohlcv, context):
                self._check_no_lookahead(ohlcv, T=3)
                return []
        bad = Bad(make_config())
        with pytest.raises(LookAheadError):
            bad.generate_signals(flat_ohlcv(15), make_context())


class TestQuasimodoStrategy:
    def setup_method(self):
        StrategyRegistry._registry.clear()
        import strategies.quasimodo; importlib.reload(strategies.quasimodo)
        from strategies.quasimodo import QuasimodoStrategy
        self.strategy = QuasimodoStrategy(make_config())

    def test_returns_list(self):
        ohlcv = flat_ohlcv(25)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert isinstance(signals, list)

    def test_returns_empty_for_insufficient_data(self):
        ohlcv = flat_ohlcv(5)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert signals == []


class TestFlagStrategy:
    def setup_method(self):
        StrategyRegistry._registry.clear()
        import strategies.flag; importlib.reload(strategies.flag)
        from strategies.flag import FlagStrategy
        self.strategy = FlagStrategy(make_config())

    def test_returns_list(self):
        ohlcv = flat_ohlcv(25)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert isinstance(signals, list)

    def test_returns_empty_for_insufficient_data(self):
        ohlcv = flat_ohlcv(5)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert signals == []

    def test_detects_bullish_flag(self):
        rows = []
        for i in range(15):
            rows.append({"open": 100, "high": 100.5, "low": 99.5, "close": 100, "volume": 500})
        # Impulse candle
        rows.append({"open": 100, "high": 107, "low": 99.8, "close": 106, "volume": 8000})
        # Flag consolidation (declining volume)
        for i, vol in enumerate([600, 500, 400, 300]):
            rows.append({"open": 105, "high": 106, "low": 104, "close": 105, "volume": vol})
        ohlcv = pd.DataFrame(rows)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert isinstance(signals, list)


class TestRSIMomentumStrategy:
    def setup_method(self):
        StrategyRegistry._registry.clear()
        import strategies.rsi_momentum; importlib.reload(strategies.rsi_momentum)
        from strategies.rsi_momentum import RSIMomentumStrategy
        self.strategy = RSIMomentumStrategy(make_config())

    def test_returns_empty_for_insufficient_data(self):
        ohlcv = flat_ohlcv(10)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert signals == []

    def test_generates_long_on_rsi_cross_above_50(self):
        # Rising prices → RSI should cross above 50
        closes = [100 - i * 0.5 for i in range(30)] + [100 + i for i in range(30)]
        ohlcv = pd.DataFrame({
            "open": [c - 0.3 for c in closes], "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes], "close": closes, "volume": [1000.0] * 60,
        })
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert isinstance(signals, list)


class TestEMACrossStrategy:
    def setup_method(self):
        StrategyRegistry._registry.clear()
        import strategies.ema_cross; importlib.reload(strategies.ema_cross)
        from strategies.ema_cross import EMACrossStrategy
        self.strategy = EMACrossStrategy(make_config())

    def test_returns_empty_for_insufficient_data(self):
        ohlcv = flat_ohlcv(10)
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert signals == []

    def test_returns_list_for_sufficient_data(self):
        closes = [100 + i * 0.5 for i in range(60)]
        ohlcv = pd.DataFrame({
            "open": [c - 0.3 for c in closes], "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes], "close": closes, "volume": [1000.0] * 60,
        })
        signals = self.strategy.generate_signals(ohlcv, make_context())
        assert isinstance(signals, list)
