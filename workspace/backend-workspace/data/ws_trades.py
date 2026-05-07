"""
Trade Tape / Cumulative Delta Writer
======================================
Subscribes to trade tape WebSocket.
Accumulates buy_volume - sell_volume (Cumulative Delta) over a rolling window.
Writes delta to Redis atomically on each tick — < 0.1ms target.

Redis keys:
  delta:{asset}:5m  → float (cumulative delta, resets on candle close)

This is the most latency-sensitive component — the WS handler MUST NOT
be blocked by any scoring or computation logic.

Satisfies: Requirement 6.2 (Order Flow component), Blueprint v1.1 Data Lag fix
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)

DELTA_TTL_SECONDS = 300  # 5 minutes — auto-expire stale delta


class TradesDeltaWriter:
    """
    Subscribes to trade tape WebSocket.
    For each trade tick: atomically increments delta in Redis.

    buy  trade → delta += volume
    sell trade → delta -= volume

    The delta is reset to 0 at each candle close by the Celery scorer.
    """

    def __init__(
        self,
        exchange,
        assets: List[str],
        redis_client,
    ) -> None:
        self._exchange = exchange
        self._assets = assets
        self._redis = redis_client
        self._running = False

    async def start(self) -> None:
        self._running = True
        tasks = [self._watch_trades(asset) for asset in self._assets]
        logger.info("Starting trade delta writers for %d asset(s)", len(self._assets))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        self._running = False

    async def _watch_trades(self, asset: str) -> None:
        """
        Watch trade tape and write delta atomically to Redis.
        Target: < 0.1ms per tick (atomic INCRBYFLOAT).
        """
        backoff = 1.0
        while self._running:
            try:
                while self._running:
                    trades = await self._exchange.watch_trades(asset)
                    for trade in trades:
                        await self._write_tick(asset, trade)
                    backoff = 1.0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.warning(
                    "Trades feed %s error: %s — reconnecting in %.1fs",
                    asset, exc, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _write_tick(self, asset: str, trade: dict) -> None:
        """
        Atomic delta update — INCRBYFLOAT is O(1) and never blocks.

        buy  side → positive delta (buying pressure)
        sell side → negative delta (selling pressure)

        Satisfies: Blueprint v1.1 — WS writer < 0.1ms, never blocks
        """
        volume = float(trade.get("amount", 0))
        side = trade.get("side", "").lower()

        if side == "buy":
            delta = volume
        elif side == "sell":
            delta = -volume
        else:
            return  # unknown side — skip

        key = f"delta:{asset}:5m"
        await self._redis.incrbyfloat(key, delta)
        await self._redis.expire(key, DELTA_TTL_SECONDS)


async def read_delta_from_redis(redis_client, asset: str) -> float:
    """Read current cumulative delta for an asset from Redis."""
    key = f"delta:{asset}:5m"
    val = await redis_client.get(key)
    return float(val) if val else 0.0


async def reset_delta(redis_client, asset: str) -> None:
    """Reset delta to 0 at candle close (called by Celery scorer)."""
    key = f"delta:{asset}:5m"
    await redis_client.set(key, "0", ex=DELTA_TTL_SECONDS)
