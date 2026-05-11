"""
Mock Exchange HTTP Client
==========================
HTTP adapter implementing ExchangeInterface by delegating all calls
to mock-exchange-workspace REST API.

Injected into TradeExecutor when mock_exchange.enabled = true in config.yaml.
Contains no business logic — pure transport layer.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from trading_core.exchange.interface import (
    AccountState,
    ExchangeInterface,
    Order,
    OrderSide,
    OrderType,
    Position,
)

logger = logging.getLogger(__name__)


class MockExchangeHttpClient(ExchangeInterface):
    """
    Translates ExchangeInterface calls into HTTP requests to mock-exchange-workspace.
    Raises httpx.HTTPStatusError on 4xx/5xx — TradeExecutor handles it like any
    exchange error and will retry via _submit_with_retry().
    """

    is_mock = True
    exchange_name = "mock_http"

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

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
        resp = await self._client.post(
            f"{self._base_url}/exchange/orders",
            json={
                "symbol": symbol,
                "side": side.value,
                "order_type": order_type.value,
                "amount": amount,
                "price": price,
                "client_order_id": client_order_id,
            },
        )
        resp.raise_for_status()
        return Order(**resp.json())

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        resp = await self._client.delete(
            f"{self._base_url}/exchange/orders/{order_id}",
            params={"symbol": symbol},
        )
        resp.raise_for_status()
        return resp.json().get("cancelled", False)

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        resp = await self._client.get(
            f"{self._base_url}/exchange/orders/{order_id}",
            params={"symbol": symbol},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return Order(**resp.json())

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        params = {"symbol": symbol} if symbol else {}
        resp = await self._client.get(
            f"{self._base_url}/exchange/orders", params=params
        )
        resp.raise_for_status()
        return [Order(**o) for o in resp.json()]

    async def get_position(self, symbol: str) -> Optional[Position]:
        resp = await self._client.get(
            f"{self._base_url}/exchange/positions/{symbol}"
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return Position(**resp.json())

    async def get_all_positions(self) -> List[Position]:
        resp = await self._client.get(f"{self._base_url}/exchange/positions")
        resp.raise_for_status()
        return [Position(**p) for p in resp.json()]

    async def get_account_state(self) -> AccountState:
        resp = await self._client.get(f"{self._base_url}/exchange/account")
        resp.raise_for_status()
        return AccountState(**resp.json())

    async def get_current_price(self, symbol: str) -> float:
        resp = await self._client.get(
            f"{self._base_url}/exchange/price/{symbol}"
        )
        resp.raise_for_status()
        return float(resp.json()["price"])

    async def close(self) -> None:
        await self._client.aclose()
