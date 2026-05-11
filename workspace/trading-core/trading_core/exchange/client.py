"""
Exchange Client — ccxt Adapter + Singleton
============================================
Wraps ccxt REST calls behind a clean interface.
All services use get_exchange_client() — never instantiate ccxt directly.

Benefits:
  - Single ccxt instance per exchange_id → shared rate limit counter
  - Services don't import ccxt — only trading_core.exchange
  - Easy to swap implementation (mock, testnet, live) without touching services

Usage:
    from trading_core.exchange import get_exchange_client

    client = get_exchange_client("binance")
    candles = client.fetch_ohlcv("BTC/USDT", "15m", limit=100)
    ob      = client.fetch_order_book("BTC/USDT")
    trades  = client.fetch_trades("BTC/USDT", limit=100)
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time as _time
from functools import lru_cache
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _TokenBucket:
    """
    Thread-safe token bucket for application-level API rate limiting.

    Supplements ccxt's built-in rate limiter with a configurable burst limit.
    Default: 10 req/s sustained, burst up to 20 requests.
    """

    def __init__(self, rate: float = 10.0, capacity: float = 20.0) -> None:
        self._rate = rate          # tokens refilled per second
        self._capacity = capacity  # max burst size
        self._tokens = capacity
        self._last = _time.monotonic()
        self._lock = threading.Lock()

    def consume(self) -> None:
        """Block until a token is available, then consume one."""
        while True:
            with self._lock:
                now = _time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            _time.sleep(wait)


class ExchangeClient:
    """
    Thin adapter wrapping a single ccxt exchange instance.

    All methods are synchronous (ccxt REST).
    Use run_in_executor() for async contexts (already done in services).

    Rate limiting is handled by ccxt internally (enableRateLimit=True).
    """

    def __init__(self, exchange_id: str, options: Optional[Dict[str, Any]] = None) -> None:
        import ccxt
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(
                f"Exchange '{exchange_id}' not found in ccxt. "
                f"Available: {ccxt.exchanges[:10]}..."
            )
        default_options: Dict[str, Any] = {"enableRateLimit": True}
        if options:
            default_options.update(options)

        self._exchange = exchange_class(default_options)
        self._exchange_id = exchange_id
        self._rate_limiter = _TokenBucket()
        logger.info("ExchangeClient created: %s", exchange_id)

    # ------------------------------------------------------------------
    # Market data (public — no API key required)
    # ------------------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: Optional[int] = None,
    ) -> List[list]:
        """
        Fetch OHLCV candles.
        Returns list of [timestamp, open, high, low, close, volume].
        """
        self._rate_limiter.consume()
        return self._exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

    def fetch_order_book(self, symbol: str, limit: int = 20) -> dict:
        """
        Fetch order book snapshot.
        Returns {"bids": [[price, amount], ...], "asks": [[price, amount], ...]}.
        """
        self._rate_limiter.consume()
        return self._exchange.fetch_order_book(symbol, limit=limit)

    def fetch_trades(self, symbol: str, limit: int = 100) -> List[dict]:
        """
        Fetch recent trades (trade tape).
        Returns list of {"id", "timestamp", "side", "price", "amount"}.
        """
        self._rate_limiter.consume()
        return self._exchange.fetch_trades(symbol, limit=limit)

    def fetch_ticker(self, symbol: str) -> dict:
        """
        Fetch current ticker (last price, bid, ask, volume).
        """
        self._rate_limiter.consume()
        return self._exchange.fetch_ticker(symbol)

    def fetch_funding_rate(self, symbol: str) -> dict:
        """
        Fetch current funding rate for a perpetual futures symbol.
        Returns {} if not available (spot markets).
        """
        self._rate_limiter.consume()
        try:
            return self._exchange.fetch_funding_rate(symbol)
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Trading (requires API key)
    # ------------------------------------------------------------------

    def create_limit_order(
        self, symbol: str, side: str, amount: float, price: float
    ) -> dict:
        return self._exchange.create_limit_order(symbol, side, amount, price)

    def create_market_order(
        self, symbol: str, side: str, amount: float
    ) -> dict:
        return self._exchange.create_market_order(symbol, side, amount)

    def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float,
        params: Optional[dict] = None,
    ) -> dict:
        return self._exchange.create_order(
            symbol, order_type, side, amount, price, params or {}
        )

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        return self._exchange.cancel_order(order_id, symbol)

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        return self._exchange.fetch_order(order_id, symbol)

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        return self._exchange.fetch_open_orders(symbol)

    def fetch_balance(self) -> dict:
        return self._exchange.fetch_balance()

    # ------------------------------------------------------------------
    # Async helpers (for use in asyncio contexts)
    # ------------------------------------------------------------------

    async def async_fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> List[list]:
        """Async wrapper — runs fetch_ohlcv in thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.fetch_ohlcv(symbol, timeframe, limit)
        )

    async def async_fetch_order_book(self, symbol: str, limit: int = 20) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.fetch_order_book(symbol, limit)
        )

    async def async_fetch_trades(self, symbol: str, limit: int = 100) -> List[dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.fetch_trades(symbol, limit)
        )

    async def async_fetch_ticker(self, symbol: str) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.fetch_ticker(symbol)
        )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def exchange_id(self) -> str:
        return self._exchange_id

    def __repr__(self) -> str:
        return f"ExchangeClient({self._exchange_id})"


# ---------------------------------------------------------------------------
# Singleton factory — one instance per exchange_id
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def get_exchange_client(
    exchange_id: str,
    options_key: str = "",  # hashable options string for lru_cache
) -> ExchangeClient:
    """
    Return a singleton ExchangeClient for the given exchange_id.

    All services calling get_exchange_client("binance") get the SAME instance,
    sharing the rate limit counter and connection pool.

    Args:
        exchange_id: ccxt exchange identifier (e.g. "binance", "bybit")
        options_key: optional JSON string of extra ccxt options (for cache key)

    Usage:
        client = get_exchange_client("binance")
        candles = client.fetch_ohlcv("BTC/USDT", "15m")
    """
    import json
    options = json.loads(options_key) if options_key else None
    logger.info("Creating ExchangeClient singleton: %s", exchange_id)
    return ExchangeClient(exchange_id, options)
