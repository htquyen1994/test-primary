"""
OrderManager — CRUD for mock_orders + OPEN → FILLED transitions.
All operations are synchronous (SQLAlchemy Session).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from db.models import MockAccount, MockAccountHistory, MockOrder, MockPosition
from trading_core.exchange.interface import (
    Order, OrderSide, OrderStatus, OrderType,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrderManager:
    """Handles all order persistence and state transitions."""

    def __init__(self, fee_rate: float = 0.001) -> None:
        self._fee_rate = fee_rate

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_order(
        self,
        db: Session,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: float,
        client_order_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> MockOrder:
        order_id = str(uuid.uuid4())
        db_order = MockOrder(
            id=order_id,
            symbol=symbol,
            side=side.value,
            order_type=order_type.value,
            amount=amount,
            price=price,
            status="OPEN",
            filled_amount=0.0,
            fill_price=None,
            fee=0.0,
            client_order_id=client_order_id,
            signal_id=signal_id,
            created_at=_now_iso(),
            filled_at=None,
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        logger.debug("Order created: %s %s %s @ %s", order_id, side.value, symbol, price)
        return db_order

    # ------------------------------------------------------------------
    # Fill (MARKET — immediate)
    # ------------------------------------------------------------------

    def fill_market_order(
        self,
        db: Session,
        order: MockOrder,
        fill_price: float,
    ) -> MockOrder:
        fee = fill_price * order.amount * self._fee_rate
        order.status = "FILLED"
        order.filled_amount = order.amount
        order.fill_price = fill_price
        order.fee = fee
        order.filled_at = _now_iso()
        db.commit()
        db.refresh(order)
        return order

    # ------------------------------------------------------------------
    # Fill (SL / TP — triggered by candle)
    # ------------------------------------------------------------------

    def fill_order_by_trigger(
        self,
        db: Session,
        order_id: str,
        fill_price: float,
    ) -> Optional[MockOrder]:
        order = db.query(MockOrder).filter(MockOrder.id == order_id).first()
        if order is None or order.status not in ("OPEN", "PENDING"):
            return None
        fee = fill_price * order.amount * self._fee_rate
        order.status = "FILLED"
        order.filled_amount = order.amount
        order.fill_price = fill_price
        order.fee = fee
        order.filled_at = _now_iso()
        db.commit()
        db.refresh(order)
        return order

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_order(self, db: Session, order_id: str) -> bool:
        order = db.query(MockOrder).filter(MockOrder.id == order_id).first()
        if order is None or order.status not in ("OPEN", "PENDING"):
            return False
        order.status = "CANCELLED"
        db.commit()
        return True

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_order(self, db: Session, order_id: str) -> Optional[MockOrder]:
        return db.query(MockOrder).filter(MockOrder.id == order_id).first()

    def get_open_orders(
        self, db: Session, symbol: Optional[str] = None
    ) -> List[MockOrder]:
        q = db.query(MockOrder).filter(MockOrder.status.in_(["OPEN", "PENDING"]))
        if symbol:
            q = q.filter(MockOrder.symbol == symbol)
        return q.all()

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def create_position(
        self,
        db: Session,
        symbol: str,
        direction: str,
        entry_price: float,
        amount: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: Optional[float],
        leverage: int,
        entry_order_id: Optional[str],
        signal_id: Optional[str],
        funding_rate: Optional[float] = None,
    ) -> MockPosition:
        pos = MockPosition(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            amount=amount,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            status="OPEN",
            entry_order_id=entry_order_id,
            signal_id=signal_id,
            opened_at=_now_iso(),
            funding_rate_at_entry=funding_rate,
        )
        db.add(pos)
        db.commit()
        db.refresh(pos)
        logger.info(
            "Position opened: id=%s %s %s entry=%.4f sl=%.4f tp1=%.4f",
            pos.id, direction, symbol, entry_price, stop_loss, take_profit_1,
        )
        return pos

    def close_position(
        self,
        db: Session,
        position: MockPosition,
        exit_price: float,
        exit_reason: str,
    ) -> MockPosition:
        position.status = "CLOSED"
        position.exit_price = exit_price
        position.exit_reason = exit_reason
        position.closed_at = _now_iso()
        db.commit()
        db.refresh(position)
        return position

    def get_open_positions(
        self, db: Session, symbol: Optional[str] = None
    ) -> List[MockPosition]:
        q = db.query(MockPosition).filter(MockPosition.status == "OPEN")
        if symbol:
            q = q.filter(MockPosition.symbol == symbol)
        return q.all()

    def get_position(self, db: Session, symbol: str) -> Optional[MockPosition]:
        return (
            db.query(MockPosition)
            .filter(MockPosition.symbol == symbol, MockPosition.status == "OPEN")
            .first()
        )

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def get_account(self, db: Session) -> MockAccount:
        return db.query(MockAccount).filter(MockAccount.id == 1).first()

    def deduct_fee(self, db: Session, fee: float) -> None:
        account = self.get_account(db)
        if account:
            account.balance_usd -= fee
            account.total_fees_paid += fee
            account.updated_at = _now_iso()
            db.commit()

    def apply_pnl(
        self,
        db: Session,
        net_pnl: float,
        fee_total: float,
        position_id: int,
        exit_reason: str,
    ) -> None:
        account = self.get_account(db)
        if account is None:
            logger.warning("No account found when applying PnL")
            return
        account.balance_usd += net_pnl
        account.equity_usd = account.balance_usd
        account.total_realized_pnl += net_pnl
        account.total_fees_paid += fee_total
        account.updated_at = _now_iso()

        history = MockAccountHistory(
            balance_usd=account.balance_usd,
            equity_usd=account.equity_usd,
            trade_id=position_id,
            event="trade_closed",
            pnl_delta=net_pnl,
            recorded_at=_now_iso(),
        )
        db.add(history)
        db.commit()

    def record_trade_opened(
        self, db: Session, position_id: int, fee: float
    ) -> None:
        account = self.get_account(db)
        if account is None:
            return
        account.balance_usd -= fee
        account.total_fees_paid += fee
        account.updated_at = _now_iso()
        history = MockAccountHistory(
            balance_usd=account.balance_usd,
            equity_usd=account.equity_usd,
            trade_id=position_id,
            event="trade_opened",
            pnl_delta=-fee,
            recorded_at=_now_iso(),
        )
        db.add(history)
        db.commit()

    # ------------------------------------------------------------------
    # PnL helpers
    # ------------------------------------------------------------------

    def calculate_pnl(
        self,
        direction: str,
        entry_price: float,
        exit_price: float,
        amount: float,
        leverage: int,
        opened_at_iso: str,
        closed_at_iso: str,
        funding_rate: Optional[float],
    ) -> dict:
        """Returns dict with gross_pnl, fee_entry, fee_exit, funding_paid, net_pnl, pnl_pct."""
        if direction == "long":
            gross_pnl = (exit_price - entry_price) * amount * leverage
        else:
            gross_pnl = (entry_price - exit_price) * amount * leverage

        fee_entry = entry_price * amount * self._fee_rate
        fee_exit = exit_price * amount * self._fee_rate

        opened_dt = datetime.fromisoformat(opened_at_iso)
        closed_dt = datetime.fromisoformat(closed_at_iso)
        hold_hours = (closed_dt - opened_dt).total_seconds() / 3600
        funding_periods = int(hold_hours / 8)
        fr = funding_rate or 0.0
        funding_paid = entry_price * amount * fr * funding_periods

        net_pnl = gross_pnl - fee_entry - fee_exit - funding_paid
        entry_value = entry_price * amount
        pnl_pct = (net_pnl / entry_value * 100) if entry_value != 0 else 0.0

        return {
            "gross_pnl": gross_pnl,
            "fee_entry": fee_entry,
            "fee_exit": fee_exit,
            "funding_paid": funding_paid,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "hold_hours": hold_hours,
        }

    # ------------------------------------------------------------------
    # Conversions
    # ------------------------------------------------------------------

    @staticmethod
    def db_order_to_domain(db_order: MockOrder) -> Order:
        return Order(
            order_id=db_order.id,
            symbol=db_order.symbol,
            side=OrderSide(db_order.side),
            order_type=OrderType(db_order.order_type),
            amount=db_order.amount,
            price=db_order.price,
            status=OrderStatus(db_order.status),
            filled_amount=db_order.filled_amount,
            fill_price=db_order.fill_price,
            fee=db_order.fee,
            created_at=datetime.fromisoformat(db_order.created_at),
            filled_at=datetime.fromisoformat(db_order.filled_at) if db_order.filled_at else None,
            client_order_id=db_order.client_order_id,
        )
