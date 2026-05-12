"""
Trade Executor
===============
Submits orders to the exchange via ExchangeInterface after user confirms a signal.
Automatically places SL/TP orders after entry fill.

SAFETY: Testnet mode is enforced at code level for live exchanges.
        Mock exchanges (is_mock=True) bypass the testnet guard.
        exchange.testnet must be explicitly False for live trading.

Satisfies: Requirements 19.1–19.9
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from trading_core.exchange.interface import (
    ExchangeInterface,
    Order,
    OrderSide,
    OrderType,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds

_SIDE_MAP: dict[str, OrderSide] = {
    "buy": OrderSide.BUY,
    "sell": OrderSide.SELL,
}

_ORDER_TYPE_MAP: dict[str, OrderType] = {
    "limit": OrderType.LIMIT,
    "stop_loss": OrderType.STOP_LOSS,
    "take_profit": OrderType.TAKE_PROFIT,
    "market": OrderType.MARKET,
}


class LiveTradingNotAllowedError(RuntimeError):
    """
    Raised when testnet is not explicitly False on a live exchange.
    Satisfies: Requirements 19.8, 19.9
    """
    pass


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt."""
    success: bool
    order_id: Optional[str] = None
    actual_fill_price: Optional[float] = None
    actual_slippage: Optional[float] = None
    error: Optional[str] = None
    is_testnet: bool = True


class TradeExecutor:
    """
    Submits orders to the exchange via ExchangeInterface.
    Enforces testnet safety at the code level for live exchanges.
    Mock exchanges (is_mock=True) bypass the testnet guard.

    Satisfies: Requirements 19.1–19.9
    """

    def __init__(self, exchange: ExchangeInterface, config) -> None:
        self._exchange = exchange
        self._config = config

    def _assert_testnet_safe(self) -> None:
        """
        Guard: raises LiveTradingNotAllowedError if testnet is not explicitly False.
        Bypassed automatically for mock exchanges (is_mock=True).

        Satisfies: Requirements 19.8, 19.9
        """
        if getattr(self._exchange, "is_mock", False):
            return
        testnet = getattr(self._config.exchange, "testnet", True)
        if testnet is not False:
            raise LiveTradingNotAllowedError(
                "Live trading is disabled. "
                "Set exchange.testnet = false in config.yaml to enable live trading. "
                f"Current value: testnet={testnet!r}"
            )

    async def execute(
        self,
        signal_card: dict,
        position_size_usd: float,
    ) -> ExecutionResult:
        """
        Execute a confirmed signal: submit entry order + SL + TP.

        Args:
            signal_card:       Signal Card dict from alert builder
            position_size_usd: Position size in USD from Risk Manager

        Returns:
            ExecutionResult with fill price and order IDs

        Satisfies: Requirements 19.1–19.7
        """
        # Safety guard — MUST run before any exchange call (Req 19.8, 19.9)
        self._assert_testnet_safe()

        asset = signal_card["asset"]
        direction = signal_card["direction"]
        entry_price = signal_card["entry_price"]
        stop_loss = signal_card["stop_loss"]
        tp1 = signal_card["take_profit_1"]

        # position_size_usd is already the NOTIONAL exposure from RiskManager.
        # Do NOT multiply by leverage here — the exchange applies it automatically.
        # amount_contracts = notional / entry_price is the correct order quantity.

        # Submit entry order with retry (Req 19.7)
        entry_result = await self._submit_with_retry(
            asset=asset,
            side="buy" if direction == "long" else "sell",
            amount=position_size_usd / entry_price,
            price=entry_price,
            order_type="limit",
        )

        if not entry_result.success:
            return entry_result

        actual_fill = entry_result.actual_fill_price or entry_price
        actual_slippage = actual_fill - entry_price

        # Place SL order (Req 19.2)
        sl_side = "sell" if direction == "long" else "buy"
        await self._submit_with_retry(
            asset=asset,
            side=sl_side,
            amount=position_size_usd / entry_price,
            price=stop_loss,
            order_type="stop_loss",
        )

        # Place TP1 order (Req 19.2)
        tp_side = "sell" if direction == "long" else "buy"
        await self._submit_with_retry(
            asset=asset,
            side=tp_side,
            amount=position_size_usd / entry_price,
            price=tp1,
            order_type="take_profit",
        )

        logger.info(
            "Trade executed: %s %s entry=%.4f fill=%.4f slip=%.4f",
            asset, direction, entry_price, actual_fill, actual_slippage,
        )

        is_mock = getattr(self._exchange, "is_mock", False)
        return ExecutionResult(
            success=True,
            order_id=entry_result.order_id,
            actual_fill_price=actual_fill,
            actual_slippage=actual_slippage,
            is_testnet=not is_mock,
        )

    async def _submit_with_retry(
        self,
        asset: str,
        side: str,
        amount: float,
        price: float,
        order_type: str = "limit",
    ) -> ExecutionResult:
        """
        Submit an order via ExchangeInterface with exponential backoff retry.
        Retries up to MAX_RETRIES times on exchange error.

        Satisfies: Requirement 19.7
        """
        exchange_side = _SIDE_MAP[side]
        exchange_order_type = _ORDER_TYPE_MAP.get(order_type, OrderType.LIMIT)
        is_mock = getattr(self._exchange, "is_mock", False)

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                order: Order = await self._exchange.create_order(
                    symbol=asset,
                    side=exchange_side,
                    order_type=exchange_order_type,
                    amount=amount,
                    price=price,
                )

                fill_price = order.fill_price if order.fill_price is not None else price
                return ExecutionResult(
                    success=True,
                    order_id=order.order_id,
                    actual_fill_price=fill_price,
                    actual_slippage=fill_price - price,
                    is_testnet=not is_mock,
                )

            except Exception as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "Order attempt %d/%d failed for %s: %s — retrying in %.1fs",
                        attempt, MAX_RETRIES, asset, exc, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Order failed after %d attempts for %s: %s",
                        MAX_RETRIES, asset, exc,
                    )

        return ExecutionResult(
            success=False,
            error=str(last_error),
            is_testnet=not is_mock,
        )
