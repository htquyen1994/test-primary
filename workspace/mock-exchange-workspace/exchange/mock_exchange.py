"""
MockExchange — server-side ExchangeInterface implementation.
Called by FastAPI routes; delegates to OrderManager for DB persistence.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from db.models import MockAccount, MockPosition
from exchange.order_manager import OrderManager
from trading_core.exchange.interface import (
    AccountState, ExchangeInterface, Order, OrderSide, OrderType, Position,
)

logger = logging.getLogger(__name__)


class MockExchange(ExchangeInterface):
    """
    Server-side mock exchange. Implements ExchangeInterface so it can be
    tested with the same interface consumers use in production.
    """

    _is_mock = True
    _exchange_name = "mock"

    def __init__(
        self,
        db_factory,
        order_manager: OrderManager,
        exchange_id: str = "binance",
    ) -> None:
        """
        Args:
            db_factory: callable() -> Session (used for synchronous DB access)
            order_manager: OrderManager instance
            exchange_id: ccxt exchange id for public price lookups
        """
        self._db_factory = db_factory
        self._om = order_manager
        self._exchange_id = exchange_id

    @property
    def is_mock(self) -> bool:
        return self._is_mock

    @property
    def exchange_name(self) -> str:
        return self._exchange_name

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: float,
        client_order_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Order:
        db: Session = self._db_factory()
        try:
            meta = metadata or {}
            signal_id = meta.get("signal_id")
            direction = meta.get("direction", "long")
            stop_loss = meta.get("stop_loss")
            take_profit_1 = meta.get("take_profit_1")
            take_profit_2 = meta.get("take_profit_2")
            leverage = meta.get("leverage", 1)
            funding_rate = meta.get("funding_rate")

            if order_type == OrderType.MARKET:
                # Immediate fill
                db_order = self._om.create_order(
                    db, symbol, side, order_type, amount, price,
                    client_order_id, signal_id, metadata,
                )
                db_order = self._om.fill_market_order(db, db_order, price)

                # Create position for entry orders
                if stop_loss and take_profit_1:
                    pos = self._om.create_position(
                        db=db,
                        symbol=symbol,
                        direction=direction,
                        entry_price=price,
                        amount=amount,
                        stop_loss=stop_loss,
                        take_profit_1=take_profit_1,
                        take_profit_2=take_profit_2,
                        leverage=leverage,
                        entry_order_id=db_order.id,
                        signal_id=signal_id,
                        funding_rate=funding_rate,
                    )
                    self._om.record_trade_opened(db, pos.id, db_order.fee)

            elif order_type in (OrderType.LIMIT,):
                db_order = self._om.create_order(
                    db, symbol, side, order_type, amount, price,
                    client_order_id, signal_id, metadata,
                )
                # Create position immediately for limit entry orders
                if stop_loss and take_profit_1:
                    pos = self._om.create_position(
                        db=db,
                        symbol=symbol,
                        direction=direction,
                        entry_price=price,
                        amount=amount,
                        stop_loss=stop_loss,
                        take_profit_1=take_profit_1,
                        take_profit_2=take_profit_2,
                        leverage=leverage,
                        entry_order_id=db_order.id,
                        signal_id=signal_id,
                        funding_rate=funding_rate,
                    )
                    fee = price * amount * self._om._fee_rate
                    self._om.record_trade_opened(db, pos.id, fee)

            elif order_type in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
                # SL/TP orders: update existing position with SL/TP values
                db_order = self._om.create_order(
                    db, symbol, side, order_type, amount, price,
                    client_order_id, signal_id, metadata,
                )
                # Update open position SL/TP if provided
                pos = self._om.get_position(db, symbol)
                if pos and order_type == OrderType.STOP_LOSS:
                    pos.stop_loss = price
                    db.commit()
                elif pos and order_type == OrderType.TAKE_PROFIT:
                    if pos.take_profit_1 == price:
                        pass  # already set
                    elif pos.take_profit_2 is None:
                        pos.take_profit_2 = price
                    db.commit()
            else:
                db_order = self._om.create_order(
                    db, symbol, side, order_type, amount, price,
                    client_order_id, signal_id, metadata,
                )

            return OrderManager.db_order_to_domain(db_order)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        db: Session = self._db_factory()
        try:
            return self._om.cancel_order(db, order_id)
        finally:
            db.close()

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        db: Session = self._db_factory()
        try:
            db_order = self._om.get_order(db, order_id)
            if db_order is None:
                return None
            return OrderManager.db_order_to_domain(db_order)
        finally:
            db.close()

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        db: Session = self._db_factory()
        try:
            db_orders = self._om.get_open_orders(db, symbol)
            return [OrderManager.db_order_to_domain(o) for o in db_orders]
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Position operations
    # ------------------------------------------------------------------

    async def get_position(self, symbol: str) -> Optional[Position]:
        db: Session = self._db_factory()
        try:
            pos = self._om.get_position(db, symbol)
            if pos is None:
                return None
            return self._db_pos_to_domain(pos)
        finally:
            db.close()

    async def get_all_positions(self) -> List[Position]:
        db: Session = self._db_factory()
        try:
            positions = self._om.get_open_positions(db)
            return [self._db_pos_to_domain(p) for p in positions]
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    async def get_account_state(self) -> AccountState:
        db: Session = self._db_factory()
        try:
            account = self._om.get_account(db)
            if account is None:
                return AccountState(
                    balance_usd=0.0,
                    equity_usd=0.0,
                )
            return AccountState(
                balance_usd=account.balance_usd,
                equity_usd=account.equity_usd,
                used_margin=account.used_margin,
                free_margin=account.balance_usd - account.used_margin,
                total_realized_pnl=account.total_realized_pnl,
                total_fees_paid=account.total_fees_paid,
            )
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Price
    # ------------------------------------------------------------------

    async def get_current_price(self, symbol: str) -> float:
        """Fetch latest price from ccxt public ticker (no API key needed)."""
        try:
            from trading_core.exchange.client import get_exchange_client
            client = get_exchange_client(self._exchange_id)
            ticker = await client.async_fetch_ticker(symbol)
            return float(ticker.get("last", ticker.get("close", 0.0)))
        except Exception as exc:
            logger.warning("get_current_price failed for %s: %s", symbol, exc)
            return 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _db_pos_to_domain(pos: MockPosition) -> Position:
        from datetime import datetime
        opened_at = datetime.fromisoformat(pos.opened_at)
        return Position(
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            amount=pos.amount,
            stop_loss=pos.stop_loss,
            take_profit_1=pos.take_profit_1,
            take_profit_2=pos.take_profit_2,
            leverage=pos.leverage,
            opened_at=opened_at,
            entry_order_id=pos.entry_order_id,
            signal_id=pos.signal_id,
        )
