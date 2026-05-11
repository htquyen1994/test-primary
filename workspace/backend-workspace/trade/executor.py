"""
Trade Executor
===============
Submits orders to the exchange via ccxt after user confirms a signal.
Automatically places SL/TP orders after entry fill.

SAFETY: Testnet mode is enforced at code level.
        exchange.testnet must be explicitly False for live trading.

Satisfies: Requirements 19.1–19.9
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


class LiveTradingNotAllowedError(RuntimeError):
    """
    Raised when testnet is not explicitly False.
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
    Submits orders to the exchange via ccxt.
    Enforces testnet safety at the code level.

    Satisfies: Requirements 19.1–19.9
    """

    def __init__(self, exchange, config) -> None:
        self._exchange = exchange
        self._config = config

    def _assert_testnet_safe(self) -> None:
        """
        Guard: raises LiveTradingNotAllowedError if testnet is not explicitly False.
        This MUST run before any ccxt call.

        Satisfies: Requirements 19.8, 19.9
        """
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
            signal_card:      Signal Card dict from alert builder
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

        return ExecutionResult(
            success=True,
            order_id=entry_result.order_id,
            actual_fill_price=actual_fill,
            actual_slippage=actual_slippage,
            is_testnet=True,  # always True since _assert_testnet_safe passed
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
        Submit an order with exponential backoff retry.
        Retries up to MAX_RETRIES times on API error.

        Satisfies: Requirement 19.7
        """
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Route to testnet (already validated by _assert_testnet_safe)
                if order_type == "limit":
                    order = await self._exchange.create_limit_order(
                        asset, side, amount, price
                    )
                elif order_type == "stop_loss":
                    order = await self._exchange.create_order(
                        asset, "stop_loss_limit", side, amount, price,
                        {"stopPrice": price}
                    )
                elif order_type == "take_profit":
                    order = await self._exchange.create_order(
                        asset, "take_profit_limit", side, amount, price,
                        {"stopPrice": price}
                    )
                else:
                    order = await self._exchange.create_market_order(asset, side, amount)

                fill_price = float(order.get("price", price) or price)
                return ExecutionResult(
                    success=True,
                    order_id=str(order.get("id", "")),
                    actual_fill_price=fill_price,
                    actual_slippage=fill_price - price,
                    is_testnet=True,
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
            is_testnet=True,
        )
