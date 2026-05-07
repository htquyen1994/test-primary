"""
Unit tests for Strategy Registry, BaseStrategy, and Signal dataclass.

Satisfies: Requirements 16.1–16.7, 5.4, 6.1
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from unittest.mock import MagicMock

import pandas as pd
import pytest

from indicators.base import LookAheadError
from strategies.base import BaseStrategy
from strategies.registry import StrategyRegistry, StrategyNotFoundError
from strategies.signal import Signal, ScoreBreakdown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(active_strategies=None):
    """Create a minimal mock config object."""
    cfg = MagicMock()
    cfg.strategy.active = active_strategies or []
    cfg.strategy.score_threshold.alert = 75
    cfg.strategy.score_threshold.watch = 55
    cfg.strategy.time_invalidation_candles = 15
    return cfg


def make_signal(**kwargs) -> Signal:
    """Create a valid Signal with sensible defaults."""
    defaults = dict(
        strategy_name="test_strategy",
        asset="BTC/USDT",
        timeframe="15m",
        direction="long",
        candle_index=100,
        candle_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit_1=52000.0,
        take_profit_2=54000.0,
        raw_score=80.0,
        final_score=80,
        score_breakdown=ScoreBreakdown(order_flow=20, smc=20, vsa=20, context=10, bonus=10),
        classification="ALERT",
        regime="TRENDING",
        regime_multiplier=1.0,
        funding_rate=0.0001,
        portfolio_heat=0.02,
        correlated_group_risk=0.01,
        expires_at_candle=115,
    )
    defaults.update(kwargs)
    return Signal(**defaults)


# ---------------------------------------------------------------------------
# Signal dataclass tests
# ---------------------------------------------------------------------------

class TestSignalDataclass:

    def test_valid_signal_creates_successfully(self):
        sig = make_signal()
        assert sig.direction == "long"
        assert sig.final_score == 80
        assert sig.classification == "ALERT"

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="direction"):
            make_signal(direction="sideways")

    def test_final_score_below_zero_raises(self):
        with pytest.raises(ValueError, match="final_score"):
            make_signal(final_score=-1)

    def test_final_score_above_100_raises(self):
        with pytest.raises(ValueError, match="final_score"):
            make_signal(final_score=101)

    def test_invalid_classification_raises(self):
        with pytest.raises(ValueError, match="classification"):
            make_signal(classification="MAYBE")

    def test_invalid_regime_raises(self):
        with pytest.raises(ValueError, match="regime"):
            make_signal(regime="VOLATILE")

    def test_score_boundary_values(self):
        # 0 and 100 are valid
        sig_min = make_signal(final_score=0, classification="IGNORE")
        sig_max = make_signal(final_score=100, classification="ALERT")
        assert sig_min.final_score == 0
        assert sig_max.final_score == 100

    def test_gross_rr_calculation(self):
        # entry=50000, sl=49000, tp1=52000
        # R:R = (52000-50000)/(50000-49000) = 2.0
        sig = make_signal(entry_price=50000, stop_loss=49000, take_profit_1=52000)
        assert abs(sig.gross_rr - 2.0) < 1e-10

    def test_to_dict_contains_all_required_fields(self):
        sig = make_signal()
        d = sig.to_dict()
        required = [
            "strategy_name", "asset", "timeframe", "direction",
            "entry_price", "stop_loss", "take_profit_1", "take_profit_2",
            "raw_score", "final_score", "score_breakdown",
            "classification", "regime", "regime_multiplier",
            "funding_rate", "portfolio_heat", "correlated_group_risk",
            "expires_at_candle", "created_at",
        ]
        for field_name in required:
            assert field_name in d, f"Missing field: {field_name}"

    def test_score_breakdown_to_dict(self):
        sb = ScoreBreakdown(order_flow=25, smc=20, vsa=15, context=10, bonus=5)
        d = sb.to_dict()
        assert d["order_flow"] == 25
        assert d["smc"] == 20
        assert d["vsa"] == 15
        assert d["context"] == 10
        assert d["bonus"] == 5


# ---------------------------------------------------------------------------
# Strategy Registry tests
# ---------------------------------------------------------------------------

class TestStrategyRegistry:

    def setup_method(self):
        """Clear registry before each test to avoid cross-test pollution."""
        StrategyRegistry._registry.clear()

    def test_register_decorator_adds_to_registry(self):
        @StrategyRegistry.register("test_strat_a")
        class StratA(BaseStrategy):
            @property
            def name(self): return "test_strat_a"
            def generate_signals(self, ohlcv, context): return []

        assert "test_strat_a" in StrategyRegistry.list_registered()

    def test_list_registered_returns_all_names(self):
        @StrategyRegistry.register("strat_x")
        class StratX(BaseStrategy):
            @property
            def name(self): return "strat_x"
            def generate_signals(self, ohlcv, context): return []

        @StrategyRegistry.register("strat_y")
        class StratY(BaseStrategy):
            @property
            def name(self): return "strat_y"
            def generate_signals(self, ohlcv, context): return []

        registered = StrategyRegistry.list_registered()
        assert "strat_x" in registered
        assert "strat_y" in registered

    def test_load_active_only_instantiates_active_strategies(self):
        @StrategyRegistry.register("active_one")
        class ActiveOne(BaseStrategy):
            @property
            def name(self): return "active_one"
            def generate_signals(self, ohlcv, context): return []

        @StrategyRegistry.register("inactive_one")
        class InactiveOne(BaseStrategy):
            @property
            def name(self): return "inactive_one"
            def generate_signals(self, ohlcv, context): return []

        config = make_config(active_strategies=["active_one"])
        instances = StrategyRegistry.load_active(config)

        assert "active_one" in instances
        assert "inactive_one" not in instances
        assert isinstance(instances["active_one"], ActiveOne)

    def test_load_active_raises_for_unknown_strategy(self):
        """
        Raises StrategyNotFoundError before any data is fetched.
        Satisfies: Requirement 16.4
        """
        config = make_config(active_strategies=["nonexistent_strategy"])
        with pytest.raises(StrategyNotFoundError) as exc_info:
            StrategyRegistry.load_active(config)
        assert "nonexistent_strategy" in str(exc_info.value)

    def test_load_active_passes_config_to_constructor(self):
        """
        Config object is passed to strategy constructor.
        Satisfies: Requirement 16.7
        """
        received_config = []

        @StrategyRegistry.register("config_test_strat")
        class ConfigTestStrat(BaseStrategy):
            def __init__(self, config):
                super().__init__(config)
                received_config.append(config)

            @property
            def name(self): return "config_test_strat"
            def generate_signals(self, ohlcv, context): return []

        config = make_config(active_strategies=["config_test_strat"])
        StrategyRegistry.load_active(config)

        assert len(received_config) == 1
        assert received_config[0] is config

    def test_register_non_basestrategy_raises_type_error(self):
        with pytest.raises(TypeError):
            @StrategyRegistry.register("bad_strat")
            class NotAStrategy:
                pass

    def test_empty_active_list_returns_empty_dict(self):
        config = make_config(active_strategies=[])
        instances = StrategyRegistry.load_active(config)
        assert instances == {}


# ---------------------------------------------------------------------------
# BaseStrategy no-look-ahead guard tests
# ---------------------------------------------------------------------------

class TestBaseStrategyNoLookahead:

    def setup_method(self):
        StrategyRegistry._registry.clear()

    def _make_strategy(self):
        @StrategyRegistry.register("lookahead_test")
        class TestStrat(BaseStrategy):
            @property
            def name(self): return "lookahead_test"

            def generate_signals(self, ohlcv, context) -> List[Signal]:
                T = len(ohlcv) - 1
                self._check_no_lookahead(ohlcv, T)
                return []

        config = make_config()
        return TestStrat(config)

    def test_no_lookahead_passes_with_correct_data(self):
        strat = self._make_strategy()
        ohlcv = pd.DataFrame(
            {"open": [1, 2, 3], "high": [2, 3, 4], "low": [0, 1, 2],
             "close": [1.5, 2.5, 3.5], "volume": [100, 200, 300]}
        )
        # Should not raise
        result = strat.generate_signals(ohlcv, {})
        assert result == []

    def test_lookahead_raises_when_extra_candles_present(self):
        """
        If a strategy is given ohlcv with more candles than T+1,
        _check_no_lookahead raises LookAheadError.
        Satisfies: Requirement 5.3
        """
        config = make_config()

        class BadStrat(BaseStrategy):
            @property
            def name(self): return "bad_strat"

            def generate_signals(self, ohlcv, context) -> List[Signal]:
                # Deliberately check at T=1 but ohlcv has 3 rows → look-ahead
                self._check_no_lookahead(ohlcv, T=1)
                return []

        strat = BadStrat(config)
        ohlcv = pd.DataFrame(
            {"open": [1, 2, 3], "high": [2, 3, 4], "low": [0, 1, 2],
             "close": [1.5, 2.5, 3.5], "volume": [100, 200, 300]}
        )
        with pytest.raises(LookAheadError):
            strat.generate_signals(ohlcv, {})

    def test_classify_score_alert(self):
        strat = self._make_strategy()
        assert strat.classify_score(75) == "ALERT"
        assert strat.classify_score(100) == "ALERT"

    def test_classify_score_watch(self):
        strat = self._make_strategy()
        assert strat.classify_score(55) == "WATCH"
        assert strat.classify_score(74) == "WATCH"

    def test_classify_score_ignore(self):
        strat = self._make_strategy()
        assert strat.classify_score(0) == "IGNORE"
        assert strat.classify_score(54) == "IGNORE"
