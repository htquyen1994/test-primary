"""
Exchange Interface — Abstract Contract
========================================
All exchange implementations (Live, Mock, Testnet, Backtest) must implement
this interface. Services depend ONLY on this — never on ccxt directly.

This enables:
  - Swapping Mock ↔ Live with zero code changes in consumers
  - Testing without network calls
  - Future: multiple exchange support, mock-exchange service

Design: Abstract Base Class (structural contract)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


class OrderStatus(str, Enum):
    PENDING   = "PENDING"
    OPEN      = "OPEN"
    FILLED    = "FILLED"
    PARTIAL   = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED  = "REJECTED"
    EXPIRED   = "EXPIRED"


class OrderType(str, Enum):
    MARKET      = "market"
    LIMIT       = "limit"
    STOP_LOSS   = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderSide(str, Enum):
    BUY  = "buy"
    SELL = "sell"


@dataclass
class Order:
    """Represents a single order on the exchange."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: float
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: float = 0.0
    fill_price: Optional[float] = None
    fee: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None
    client_order_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIAL)

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "amount": self.amount,
            "price": self.price,
            "status": self.status.value,
            "filled_amount": self.filled_amount,
            "fill_price": self.fill_price,
            "fee": self.fee,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "client_order_id": self.client_order_id,
        }


@dataclass
class Position:
    """Represents an open position for a symbol."""
    symbol: str
    direction: str              # "long" | "short"
    entry_price: float
    amount: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    leverage: int = 1
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entry_order_id: Optional[str] = None
    signal_id: Optional[str] = None

    def unrealized_pnl(self, current_price: float) -> float:
        if self.direction == "long":
            return (current_price - self.entry_price) * self.amount * self.leverage
        return (self.entry_price - current_price) * self.amount * self.leverage

    def unrealized_pnl_pct(self, current_price: float) -> float:
        entry_value = self.entry_price * self.amount
        if entry_value == 0:
            return 0.0
        return self.unrealized_pnl(current_price) / entry_value * 100

    def to_dict(self, current_price: float = 0.0) -> dict:
        upnl = self.unrealized_pnl(current_price) if current_price else 0.0
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "amount": self.amount,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "current_price": current_price,
            "unrealized_pnl": round(upnl, 4),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct(current_price), 2),
            "opened_at": self.opened_at.isoformat(),
            "signal_id": self.signal_id,
        }


@dataclass
class AccountState:
    """Current account balance and equity."""
    balance_usd: float
    equity_usd: float
    used_margin: float = 0.0
    free_margin: float = 0.0
    total_realized_pnl: float = 0.0
    total_fees_paid: float = 0.0

    def to_dict(self) -> dict:
        return {
            "balance_usd": round(self.balance_usd, 2),
            "equity_usd": round(self.equity_usd, 2),
            "used_margin": round(self.used_margin, 2),
            "free_margin": round(self.free_margin, 2),
            "total_realized_pnl": round(self.total_realized_pnl, 4),
            "total_fees_paid": round(self.total_fees_paid, 4),
        }


class ExchangeInterface(ABC):
    """
    Abstract interface for all exchange implementations.

    Services depend ONLY on this — never on ccxt directly.
    Implement to add: Mock, Live, Testnet, Backtest exchange.
    """

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: float,
        client_order_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Order: ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool: ...

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]: ...

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]: ...

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]: ...

    @abstractmethod
    async def get_all_positions(self) -> List[Position]: ...

    @abstractmethod
    async def get_account_state(self) -> AccountState: ...

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float: ...

    @property
    @abstractmethod
    def is_mock(self) -> bool: ...

    @property
    @abstractmethod
    def exchange_name(self) -> str: ...
