"""
Order Book Service
===================
Polls order book every 5 seconds → computes bid/ask stack → stores in Redis.

Public data — no API key required.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as time_module
from typing import List

from trading_core.exchange import get_exchange_client
from trading_core.cache import get_redis, RedisKeys

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5       # seconds
STACK_DEPTH_PCT = 0.005  # 0.5% from mid price
REDIS_TTL = 30          # seconds


class OrderBookService:
    """
    Polls order book and computes bid/ask stack sizes.
    Stores snapshot in Redis: ob:{symbol}:snap
    """

    def __init__(self, exchange_id: str, symbols: List[str]) -> None:
        self.exchange_id = exchange_id
        self.symbols = symbols

    def _get_exchange(self):
        return get_exchange_client(self.exchange_id)

    def _get_redis(self):
        return get_redis()

    async def start(self) -> None:
        """Start polling all symbols concurrently."""
        logger.info("OrderBookService starting: %d symbol(s)", len(self.symbols))
        await asyncio.gather(*[self._poll(s) for s in self.symbols])

    async def _poll(self, symbol: str) -> None:
        """Poll order book and store snapshot in Redis."""
        while True:
            try:
                exchange = self._get_exchange()
                r = self._get_redis()
                loop = asyncio.get_running_loop()

                ob = await loop.run_in_executor(
                    None,
                    lambda: exchange.fetch_order_book(symbol, limit=20),
                )

                bids = ob.get("bids", [])
                asks = ob.get("asks", [])
                if not bids or not asks:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                mid = (best_bid + best_ask) / 2.0

                bid_stack = sum(
                    float(b[1]) for b in bids
                    if float(b[0]) >= mid * (1 - STACK_DEPTH_PCT)
                )
                ask_stack = sum(
                    float(a[1]) for a in asks
                    if float(a[0]) <= mid * (1 + STACK_DEPTH_PCT)
                )

                now_ts = time_module.time()
                snapshot = {
                    "asset": symbol,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "mid": mid,
                    "spread": best_ask - best_bid,
                    "bid_stack": bid_stack,
                    "ask_stack": ask_stack,
                    "bid_dominant": bid_stack > ask_stack * 2,
                    "updated_at": now_ts,
                    "age_seconds": 0,  # always 0 at write time; reader computes age
                }
                r.set(RedisKeys.ob_snap(symbol), json.dumps(snapshot), ex=REDIS_TTL)
                logger.debug(
                    "OB %s bid=%.2f ask=%.2f bid_stack=%.3f ask_stack=%.3f dominant=%s",
                    symbol, best_bid, best_ask, bid_stack, ask_stack, snapshot["bid_dominant"],
                )

            except Exception as exc:
                logger.warning("OrderBook poll error %s: %s", symbol, exc)

            await asyncio.sleep(POLL_INTERVAL)
