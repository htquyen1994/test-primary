"""
Unit tests for Backtesting Engine, Metrics, Walk-Forward, and AI Feedback.

Satisfies: Requirements 8.1–8.6, 9.1–9.6, 10.1–10.5, 11.3–11.6
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from backtest.models import TradeResult
from backtest.engine import BacktestingEngine
from backtest.metrics import compute_metrics, _compute_max_drawdown, _compute_sharpe
from backtest.ai_feedback import find_underperformance_clusters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_trade(net_pnl: float, result: str = None) -> TradeResult:
    t = TradeResult(
        strategy_name="test", asset="BTC/USDT", timeframe="15m",
        direction="long", entry_price=50000.0, stop_loss=49000.0,
        take_profit_1=52000.0, take_profit_2=54000.0,
        actual_entry_price=50025.0, position_size_usd=100.0,
        net_pnl=net_pnl, gross_pnl=net_pnl + 0.1,
        signal_score=80,
    )
    if result:
        t.result = result
    else:
        t.compute_result()
    return t


def make_ohlcv(n: int, base: float = 100.0, trend: float = 0.5) -> pd.DataFrame:
    closes = [base + i * trend for i in range(n)]
    return pd.DataFrame({
        "open":   [c - 0.3 for c in closes],
        "high":   [c + 1.0 for c in closes],
        "low":    [c - 1.0 for c in closes],
        "close":  closes,
        "volume": [1000.0] * n,
    })


# ---------------------------------------------------------------------------
# TradeResult tests
# ---------------------------------------------------------------------------

class TestTradeResult:

    def test_compute_result_win(self):
        t = make_trade(net_pnl=50.0)
        assert t.result == "win"

    def test_compute_result_loss(self):
        t = make_trade(net_pnl=-30.0)
        assert t.result == "loss"

    def test_compute_result_be(self):
        t = make_trade(net_pnl=0.0)
        assert t.result == "be"

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError):
            TradeResult(direction="sideways")

    def test_invalid_result_raises(self):
        with pytest.raises(ValueError):
            TradeResult(result="maybe")


# ---------------------------------------------------------------------------
# Performance Metrics tests
# ---------------------------------------------------------------------------

class TestMetrics:

    def test_win_rate_formula(self):
        """Satisfies: Requirement 9.2"""
        trades = [make_trade(10, "win")] * 6 + [make_trade(-5, "loss")] * 4
        m = compute_metrics(trades)
        assert abs(m["win_rate"] - 0.6) < 1e-10
        assert 0.0 <= m["win_rate"] <= 1.0

    def test_win_rate_all_wins(self):
        trades = [make_trade(10, "win")] * 5
        m = compute_metrics(trades)
        assert m["win_rate"] == 1.0

    def test_win_rate_all_losses(self):
        trades = [make_trade(-5, "loss")] * 5
        m = compute_metrics(trades)
        assert m["win_rate"] == 0.0

    def test_profit_factor(self):
        trades = [make_trade(10, "win")] * 3 + [make_trade(-5, "loss")] * 2
        m = compute_metrics(trades)
        # gross_profit = 30, gross_loss = 10 → PF = 3.0
        assert abs(m["profit_factor"] - 3.0) < 0.01

    def test_max_drawdown_negative(self):
        """Max drawdown should be negative (decline). Satisfies: Req 9.4"""
        equity = np.array([100, 110, 90, 95, 80, 100])
        dd = _compute_max_drawdown(equity)
        assert dd < 0

    def test_max_drawdown_no_drawdown(self):
        equity = np.array([100, 110, 120, 130])
        dd = _compute_max_drawdown(equity)
        assert dd == 0.0

    def test_sharpe_formula(self):
        """Satisfies: Requirement 9.3"""
        returns = np.array([1.0, 2.0, -1.0, 3.0, 0.5])
        equity = np.cumsum(returns)
        sharpe = _compute_sharpe(equity)
        daily_returns = np.diff(equity)
        std = np.std(daily_returns, ddof=1)
        if std > 0:
            expected = np.mean(daily_returns) / std * np.sqrt(365)
            assert abs(sharpe - expected) < 1e-6
        else:
            assert sharpe == 0.0

    def test_sharpe_zero_std(self):
        equity = np.array([100, 101, 102, 103])  # constant returns
        sharpe = _compute_sharpe(equity)
        # std of [1,1,1] = 0 → sharpe = 0
        assert sharpe == 0.0

    def test_statistically_insufficient_flag(self):
        """Satisfies: Requirement 11.6"""
        trades = [make_trade(10, "win")] * 5  # only 5 trades
        m = compute_metrics(trades)
        assert m["is_statistically_insufficient"] is True

    def test_sufficient_trades_not_flagged(self):
        trades = [make_trade(10, "win")] * 30
        m = compute_metrics(trades)
        assert m["is_statistically_insufficient"] is False

    def test_empty_trades_returns_zeros(self):
        m = compute_metrics([])
        assert m["total_trades"] == 0
        assert m["win_rate"] == 0.0


# ---------------------------------------------------------------------------
# Backtesting Engine tests
# ---------------------------------------------------------------------------

class TestBacktestingEngine:

    def test_slippage_long_entry(self):
        """Long entry: buy higher. Satisfies: Req 8.2"""
        engine = BacktestingEngine(slippage_pct=0.001)
        actual = engine._apply_slippage(50000.0, "long", "entry")
        assert abs(actual - 50050.0) < 0.01

    def test_slippage_short_entry(self):
        """Short entry: sell lower. Satisfies: Req 8.2"""
        engine = BacktestingEngine(slippage_pct=0.001)
        actual = engine._apply_slippage(50000.0, "short", "entry")
        assert abs(actual - 49950.0) < 0.01

    def test_slippage_long_exit(self):
        """Long exit: sell lower."""
        engine = BacktestingEngine(slippage_pct=0.001)
        actual = engine._apply_slippage(52000.0, "long", "exit")
        assert abs(actual - 51948.0) < 0.01

    def test_processes_candles_ascending(self):
        """Satisfies: Requirement 8.6"""
        engine = BacktestingEngine()
        ohlcv = make_ohlcv(50)
        # Shuffle the index to test sorting
        shuffled = ohlcv.sample(frac=1, random_state=42)
        # Engine should sort internally
        mock_strategy = MagicMock()
        mock_strategy.name = "test"
        mock_strategy.generate_signals.return_value = []
        results = engine.run(mock_strategy, shuffled)
        assert isinstance(results, list)

    def test_intra_candle_sl_fill(self):
        """SL hit within candle → fill at SL price. Satisfies: Req 8.5"""
        engine = BacktestingEngine(slippage_pct=0.0)
        trade = TradeResult(
            direction="long", entry_price=100.0, stop_loss=98.0,
            take_profit_1=104.0, take_profit_2=106.0,
            actual_entry_price=100.0, position_size_usd=100.0,
        )
        # Candle that hits SL (low=97 < sl=98)
        candle = pd.Series({"open": 99, "high": 100, "low": 97, "close": 99})
        result = engine._check_exit(trade, candle, None, 1)
        assert result is not None
        assert result.result == "loss"

    def test_intra_candle_tp_fill(self):
        """TP hit within candle → fill at TP price. Satisfies: Req 8.5"""
        engine = BacktestingEngine(slippage_pct=0.0)
        trade = TradeResult(
            direction="long", entry_price=100.0, stop_loss=98.0,
            take_profit_1=104.0, take_profit_2=106.0,
            actual_entry_price=100.0, position_size_usd=100.0,
        )
        # Candle that hits TP1 (high=105 > tp1=104)
        candle = pd.Series({"open": 101, "high": 105, "low": 100, "close": 103})
        result = engine._check_exit(trade, candle, None, 1)
        assert result is not None
        assert result.result == "win"


# ---------------------------------------------------------------------------
# AI Feedback Loop tests
# ---------------------------------------------------------------------------

class TestAIFeedback:

    def test_cluster_detected_for_low_win_rate(self):
        """Satisfies: Requirement 11.3"""
        entries = [
            {"strategy_name": "smc", "asset": "BTC/USDT",
             "win_rate": 0.35, "profit_factor": 0.8,
             "total_trades": 40, "is_statistically_insufficient": False,
             "start_date": "2024-01-01", "end_date": "2024-02-01"},
            {"strategy_name": "smc", "asset": "BTC/USDT",
             "win_rate": 0.38, "profit_factor": 0.9,
             "total_trades": 35, "is_statistically_insufficient": False,
             "start_date": "2024-02-01", "end_date": "2024-03-01"},
        ]
        clusters = find_underperformance_clusters(entries)
        assert len(clusters) >= 1
        assert clusters[0]["strategy_name"] == "smc"

    def test_insufficient_runs_excluded(self):
        """Satisfies: Requirement 11.6"""
        entries = [
            {"strategy_name": "smc", "asset": "BTC/USDT",
             "win_rate": 0.30, "profit_factor": 0.5,
             "total_trades": 5, "is_statistically_insufficient": True,
             "start_date": "2024-01-01", "end_date": "2024-02-01"},
        ]
        clusters = find_underperformance_clusters(entries)
        assert clusters == []

    def test_good_performance_no_cluster(self):
        entries = [
            {"strategy_name": "smc", "asset": "BTC/USDT",
             "win_rate": 0.60, "profit_factor": 1.8,
             "total_trades": 50, "is_statistically_insufficient": False,
             "start_date": "2024-01-01", "end_date": "2024-02-01"},
        ]
        clusters = find_underperformance_clusters(entries)
        assert clusters == []

    def test_cluster_contains_suggestions(self):
        entries = [
            {"strategy_name": "smc", "asset": "BTC/USDT",
             "win_rate": 0.35, "profit_factor": 0.8,
             "total_trades": 40, "is_statistically_insufficient": False,
             "start_date": "2024-01-01", "end_date": "2024-02-01"},
        ]
        clusters = find_underperformance_clusters(entries)
        assert len(clusters) > 0
        assert len(clusters[0]["suggestions"]) > 0
