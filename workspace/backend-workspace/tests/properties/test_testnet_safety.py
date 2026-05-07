"""
Property 19: Testnet Safety Enforcement
=========================================
For any configuration where exchange.testnet is not explicitly False,
TradeExecutor must never call any live trading endpoint.

Satisfies: Requirements 19.8, 19.9
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from trade.executor import TradeExecutor, LiveTradingNotAllowedError


def make_config(testnet_value):
    cfg = MagicMock()
    cfg.exchange.testnet = testnet_value
    cfg.exchange.market_type = "futures"
    cfg.exchange.leverage = 5
    return cfg


SIGNAL_CARD = {
    "signal_id": "test_001",
    "asset": "BTC/USDT",
    "direction": "long",
    "entry_price": 50000.0,
    "stop_loss": 49000.0,
    "take_profit_1": 52000.0,
    "take_profit_2": 54000.0,
    "final_score": 80,
    "strategy_name": "smc_ob_fvg",
    "timeframe": "15m",
}


# ---------------------------------------------------------------------------
# Property 19: Testnet Safety Enforcement
# ---------------------------------------------------------------------------

@given(
    testnet_value=st.one_of(
        st.just(True),
        st.just(None),
        st.just("false"),   # string "false" is not bool False
        st.just(0),         # int 0 is not bool False
        st.just(""),
        st.just(1),
    )
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property19_testnet_safety_non_false_values(testnet_value):
    """
    Property 19: For any testnet value that is not explicitly False,
    TradeExecutor must raise LiveTradingNotAllowedError before any exchange call.
    Validates: Requirements 19.8, 19.9
    """
    mock_exchange = AsyncMock()
    config = make_config(testnet_value)
    executor = TradeExecutor(mock_exchange, config)

    with pytest.raises(LiveTradingNotAllowedError):
        asyncio.get_event_loop().run_until_complete(
            executor.execute(SIGNAL_CARD, position_size_usd=100.0)
        )

    # Exchange must NOT have been called
    mock_exchange.create_limit_order.assert_not_called()
    mock_exchange.create_market_order.assert_not_called()
    mock_exchange.create_order.assert_not_called()


def test_property19_explicit_false_does_not_raise():
    """
    When testnet is explicitly False, _assert_testnet_safe must NOT raise.
    (The exchange call itself may fail in tests — that's OK.)
    """
    mock_exchange = AsyncMock()
    mock_exchange.create_limit_order = AsyncMock(side_effect=Exception("mock exchange error"))
    config = make_config(False)
    executor = TradeExecutor(mock_exchange, config)

    # Should NOT raise LiveTradingNotAllowedError
    # (may raise other errors from mock exchange)
    try:
        asyncio.get_event_loop().run_until_complete(
            executor.execute(SIGNAL_CARD, position_size_usd=100.0)
        )
    except LiveTradingNotAllowedError:
        pytest.fail("LiveTradingNotAllowedError should not be raised when testnet=False")
    except Exception:
        pass  # other errors from mock are expected
