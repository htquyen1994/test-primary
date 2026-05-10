"""Exchange module — ccxt adapter, singleton, and interface contract."""

from trading_core.exchange.client import ExchangeClient, get_exchange_client
from trading_core.exchange.interface import (
    ExchangeInterface,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    AccountState,
)

__all__ = [
    "ExchangeClient",
    "get_exchange_client",
    "ExchangeInterface",
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Position",
    "AccountState",
]
