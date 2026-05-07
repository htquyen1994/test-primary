"""
Order Book WebSocket Feed
==========================
Subscribes to order book WebSocket and maintains a local snapshot.
Writes bid/ask stack sizes to Redis for Order Flow Analysis.

Redis keys:
  ob:{asset}:snap  → JSON snapshot with bid_stack, ask_stack, spread

Satisfies: Requirement 6.2 (Order Flow component)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

# Price levels to aggregate bid/ask stack (as % from mid price)
STACK_DEPTH_PCT = 0.005  # 0.5% from mid price


class OrderBookFeed:
    """
    Subscribes to order book WebSocket for multiple assets.
    Computes cumulative bid/ask stack sizes at configurable price levels.
    Writes snapshot to Redis on each update.
    """

    def __init__(
        self,
        exchange,
        assets: List[str],
        redis_client,
        stack_depth_pct: float = STACK_DEPTH_PCT,
    ) -> None:
        self._exchange = exchange
        self._assets = assets
        self._redis = redis_client
        self._stack_depth_pct = stack_depth_pct
        self._running = False

    async def start(self) -> None:
        self._running = True
        tasks = [self._watch_orderbook(asset) for asset in self._assets]
        logger.info("Starting Order Book feeds for %d asset(s)", len(self._assets))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        self._running = False

    async def _watch_orderbook(self, asset: str) -> None:
        backoff = 1.0
        while self._running:
            try:
                while self._running:
                    ob = await self._exchange.watch_order_book(asset, limit=50)
                    await self._write_snapshot(asset, ob)
                    backoff = 1.0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.warning(
                    "OrderBook feed %s error: %s — reconnecting in %.1fs",
                    asset, exc, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _write_snapshot(self, asset: str, ob: dict) -> None:
        """
        Compute bid/ask stack sizes within stack_depth_pct of mid price.
        Write to Redis key ob:{asset}:snap.
        """
        bids = ob.get("bids", [])  # [[price, size], ...]
        asks = ob.get("asks", [])

        if not bids or not asks:
            return

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2.0
        spread = best_ask - best_bid

        # Aggregate bid stack within depth_pct below mid
        bid_threshold = mid * (1 - self._stack_depth_pct)
        bid_stack = sum(
            float(size) for price, size in bids
            if float(price) >= bid_threshold
        )

        # Aggregate ask stack within depth_pct above mid
        ask_threshold = mid * (1 + self._stack_depth_pct)
        ask_stack = sum(
            float(size) for price, size in asks
            if float(price) <= ask_threshold
        )

        snapshot = {
            "asset": asset,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid": mid,
            "spread": spread,
            "bid_stack": bid_stack,
            "ask_stack": ask_stack,
            "timestamp": ob.get("timestamp"),
        }

        key = f"ob:{asset}:snap"
        await self._redis.set(key, json.dumps(snapshot), ex=60)  # expire after 60s
