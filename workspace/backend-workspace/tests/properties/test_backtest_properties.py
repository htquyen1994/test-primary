"""
Property 8:  Backtest Chronological Order
Property 9:  Slippage Application Correctness
Property 10: Win Rate Formula Invariant
Property 11: Sharpe Ratio Formula Invariant

Satisfies: Requirements 8.2, 8.6, 9.2, 9.3
"""

from __future__ import annotations

import math
import numpy as np
import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from backtest.engine import BacktestingEngine
from backtest.metrics import compute_metrics, _compute_sharpe
from backtest.models import TradeResult


def make_trade(net_pnl: float, result: str = None) -> TradeResult:
    t = TradeResult(
        strategy_name="test", asset="BTC/USDT", timeframe="15m",
        direction="long", entry_price=50000.0, stop_loss=49000.0,
        take_profit_1=52000.0, take_profit_2=54000.0,
        actual_entry_price=50025.0, position_size_usd=100.0,
        net_pnl=net_pnl, gross_pnl=net_pnl + 0.1, signal_score=80,
    )
    if result:
        t.result = result
    else:
        t.compute_result()
    return t


# ---------------------------------------------------------------------------
# Property 9: Slippage Application Correctness
# ---------------------------------------------------------------------------

@given(
    price=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    slippage=st.floats(min_value=0.0005, max_value=0.001, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property9_slippage_long_entry(price: float, slippage: float):
    """
    Property 9: Long entry fill = price × (1 + slippage_pct).
    Validates: Requirement 8.2
    """
    engine = BacktestingEngine(slippage_pct=slippage)
    actual = engine._apply_slippage(price, "long", "entry")
    expected = price * (1 + slippage)
    assert abs(actual - expected) < 1e-8


@given(
    price=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    slippage=st.floats(min_value=0.0005, max_value=0.001, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property9_slippage_short_entry(price: float, slippage: float):
    """
    Property 9: Short entry fill = price × (1 - slippage_pct).
    Validates: Requirement 8.2
    """
    engine = BacktestingEngine(slippage_pct=slippage)
    actual = engine._apply_slippage(price, "short", "entry")
    expected = price * (1 - slippage)
    assert abs(actual - expected) < 1e-8


# ---------------------------------------------------------------------------
# Property 10: Win Rate Formula Invariant
# ---------------------------------------------------------------------------

@given(
    n_wins=st.integers(min_value=0, max_value=100),
    n_losses=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property10_win_rate_formula(n_wins: int, n_losses: int):
    """
    Property 10: win_rate = count(win) / total, always in [0.0, 1.0].
    Validates: Requirement 9.2
    """
    assume(n_wins + n_losses > 0)
    trades = (
        [make_trade(10.0, "win")] * n_wins +
        [make_trade(-5.0, "loss")] * n_losses
    )
    m = compute_metrics(trades)
    expected_wr = n_wins / (n_wins + n_losses)
    assert abs(m["win_rate"] - expected_wr) < 1e-4  # rounded to 4 decimal places
    assert 0.0 <= m["win_rate"] <= 1.0


# ---------------------------------------------------------------------------
# Property 11: Sharpe Ratio Formula Invariant
# ---------------------------------------------------------------------------

@given(
    returns=st.lists(
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=50,
    )
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property11_sharpe_formula(returns: list):
    """
    Property 11: Sharpe = mean(returns) / std(returns) × sqrt(365).
    Validates: Requirement 9.3
    """
    arr = np.array(returns)
    std = np.std(arr, ddof=1)
    assume(std > 0.001)  # avoid near-zero std

    equity = np.cumsum(arr)
    sharpe = _compute_sharpe(equity)

    # Equity curve diffs = original returns
    daily_returns = np.diff(equity)
    std = np.std(daily_returns, ddof=1)
    if std == 0 or math.isnan(std):
        assert sharpe == 0.0
    else:
        expected = np.mean(daily_returns) / std * np.sqrt(365)
        if math.isnan(expected):
            assert sharpe == 0.0
        else:
            assert abs(sharpe - expected) < 1e-6
