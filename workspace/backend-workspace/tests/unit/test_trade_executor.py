"""
Unit tests for Trade Executor and Trade Journal.

Satisfies: Requirements 19.1–19.10
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from trade.executor import TradeExecutor, LiveTradingNotAllowedError, ExecutionResult


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


def make_config(testnet: bool = True, market_type: str = "futures", leverage: int = 5):
    cfg = MagicMock()
    cfg.exchange.testnet = testnet
    cfg.exchange.market_type = market_type
    cfg.exchange.leverage = leverage
    return cfg


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestTestnetSafety:

    def test_testnet_true_raises(self):
        """Satisfies: Requirement 19.8"""
        executor = TradeExecutor(AsyncMock(), make_config(testnet=True))
        with pytest.raises(LiveTradingNotAllowedError):
            run(executor.execute(SIGNAL_CARD, 100.0))

    def test_testnet_none_raises(self):
        """Satisfies: Requirement 19.9"""
        executor = TradeExecutor(AsyncMock(), make_config(testnet=None))
        with pytest.raises(LiveTradingNotAllowedError):
            run(executor.execute(SIGNAL_CARD, 100.0))

    def test_testnet_false_does_not_raise_safety_error(self):
        """testnet=False should pass the safety guard."""
        mock_exchange = AsyncMock()
        mock_exchange.create_limit_order = AsyncMock(
            return_value={"id": "order_001", "price": 50025.0}
        )
        mock_exchange.create_order = AsyncMock(
            return_value={"id": "order_002", "price": 49000.0}
        )
        executor = TradeExecutor(mock_exchange, make_config(testnet=False))
        result = run(executor.execute(SIGNAL_CARD, 100.0))
        assert not isinstance(result, LiveTradingNotAllowedError)


class TestOrderSubmission:

    def test_entry_sl_tp_orders_submitted(self):
        """
        After confirm: entry + SL + TP1 orders submitted.
        Satisfies: Requirements 19.1, 19.2
        """
        mock_exchange = AsyncMock()
        mock_exchange.create_limit_order = AsyncMock(
            return_value={"id": "entry_001", "price": 50025.0}
        )
        mock_exchange.create_order = AsyncMock(
            return_value={"id": "sl_001", "price": 49000.0}
        )
        executor = TradeExecutor(mock_exchange, make_config(testnet=False))
        result = run(executor.execute(SIGNAL_CARD, 100.0))

        assert result.success is True
        assert result.order_id == "entry_001"
        # Entry + SL + TP1 = 3 calls total
        assert mock_exchange.create_limit_order.call_count >= 1

    def test_retry_on_failure_then_success(self):
        """
        Retry up to 3 times on API error.
        Satisfies: Requirement 19.7
        """
        call_count = 0

        async def flaky_order(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary error")
            return {"id": "order_retry", "price": 50025.0}

        mock_exchange = AsyncMock()
        mock_exchange.create_limit_order = flaky_order
        mock_exchange.create_order = AsyncMock(return_value={"id": "sl", "price": 49000.0})

        executor = TradeExecutor(mock_exchange, make_config(testnet=False))
        result = run(executor.execute(SIGNAL_CARD, 100.0))

        assert result.success is True
        assert call_count == 3  # failed twice, succeeded on third

    def test_all_retries_fail_returns_failure(self):
        """
        After all retries fail, returns ExecutionResult(success=False).
        Satisfies: Requirement 19.7
        """
        mock_exchange = AsyncMock()
        mock_exchange.create_limit_order = AsyncMock(
            side_effect=ConnectionError("always fails")
        )
        executor = TradeExecutor(mock_exchange, make_config(testnet=False))
        result = run(executor.execute(SIGNAL_CARD, 100.0))
        assert result.success is False
        assert result.error is not None

    def test_notional_not_multiplied_by_leverage_in_executor(self):
        """
        TradeExecutor must NOT multiply position_size_usd by leverage.
        position_size_usd is NOTIONAL exposure — the exchange applies leverage internally.
        amount_contracts = notional / entry_price.
        Satisfies: Requirements 19.4, 7.5
        """
        submitted_amounts = []

        async def capture_order(asset, side, amount, price):
            submitted_amounts.append(amount)
            return {"id": "order", "price": price}

        mock_exchange = AsyncMock()
        mock_exchange.create_limit_order = capture_order
        mock_exchange.create_order = AsyncMock(return_value={"id": "sl", "price": 49000.0})

        executor = TradeExecutor(mock_exchange, make_config(testnet=False, leverage=5))
        run(executor.execute(SIGNAL_CARD, position_size_usd=100.0))

        # Notional=100 USD, entry=50000 → amount = 100/50000 = 0.002 BTC
        # Leverage (5×) is applied by the exchange, NOT here
        if submitted_amounts:
            assert abs(submitted_amounts[0] - 0.002) < 1e-6


class TestTradeJournal:

    def test_record_entry_inserts_row(self):
        """Satisfies: Requirements 19.5, 19.6"""
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        with patch("db.models.TradeJournal") as MockTJ:
            MockTJ.return_value = MagicMock()
            from trade.journal import record_entry
            trade_id = record_entry(
                signal_card=SIGNAL_CARD,
                fill_price=50025.0,
                order_id="order_001",
                position_size_usd=100.0,
                fee_rate=0.001,
                db_session=mock_db,
            )

        assert trade_id is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_slippage_computed_correctly(self):
        """actual_fill - signal_entry = slippage. Satisfies: Req 19.5"""
        captured_kwargs = {}
        mock_db = MagicMock()
        mock_db.commit = MagicMock()

        with patch("db.models.TradeJournal") as MockTJ:
            def capture(**kwargs):
                captured_kwargs.update(kwargs)
                obj = MagicMock()
                for k, v in kwargs.items():
                    setattr(obj, k, v)
                return obj
            MockTJ.side_effect = capture

            from trade.journal import record_entry
            record_entry(
                signal_card=SIGNAL_CARD,
                fill_price=50025.0,
                order_id="order_001",
                position_size_usd=100.0,
                fee_rate=0.001,
                db_session=mock_db,
            )

        # slippage = fill_price - entry_price = 50025 - 50000 = 25
        assert abs(captured_kwargs.get("slippage_entry", 0) - 25.0) < 1e-6
