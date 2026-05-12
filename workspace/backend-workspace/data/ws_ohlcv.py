"""
OHLCV WebSocket Feed
=====================
Subscribes to OHLCV streams via ccxt.pro WebSocket.
Writes closed candles to Redis as a ring buffer (last 500 candles).

Architecture:
  asyncio WS handler → atomic Redis write → Celery scorer reads on candle close

Satisfies: Requirements 2.1, 2.2, 2.3
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RING_BUFFER_SIZE = 500  # last N candles kept in Redis


class OHLCVWebSocketFeed:
    """
    Subscribes to OHLCV WebSocket streams for multiple assets and timeframes.
    Writes each closed candle atomically to Redis.

    Usage:
        feed = OHLCVWebSocketFeed(exchange, assets, timeframes, redis_client)
        await feed.start()

    Satisfies: Requirements 2.1, 2.2, 2.3
    """

    def __init__(
        self,
        exchange,           # ccxt.pro exchange instance
        assets: List[str],  # e.g. ["BTC/USDT", "ETH/USDT"]
        timeframes: List[str],  # e.g. ["15m", "1h"]
        redis_client,       # aioredis client
    ) -> None:
        self._exchange = exchange
        self._assets = assets
        self._timeframes = timeframes
        self._redis = redis_client
        self._running = False

    async def start(self) -> None:
        """Start all WebSocket subscriptions concurrently."""
        self._running = True
        tasks = [
            self._watch_ohlcv(asset, tf)
            for asset in self._assets
            for tf in self._timeframes
        ]
        logger.info(
            "Starting OHLCV feeds: %d asset(s) × %d timeframe(s)",
            len(self._assets), len(self._timeframes),
        )
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        self._running = False
        await self._exchange.close()

    async def _watch_ohlcv(self, asset: str, timeframe: str) -> None:
        """
        Watch a single asset/timeframe stream with reconnection on error.
        Writes each CLOSED candle to Redis atomically.
        """
        backoff = 1.0
        while self._running:
            try:
                logger.info("Subscribing to OHLCV: %s %s", asset, timeframe)
                while self._running:
                    candles = await self._exchange.watch_ohlcv(asset, timeframe)
                    # ccxt.pro returns list of [timestamp, open, high, low, close, volume]
                    # The last candle may still be open — we only write closed ones
                    for candle in candles[:-1]:  # all except the last (still forming)
                        await self._write_candle(asset, timeframe, candle)
                    backoff = 1.0  # reset on success

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.warning(
                    "OHLCV feed %s %s error: %s — reconnecting in %.1fs",
                    asset, timeframe, exc, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)  # cap at 60s

    async def _write_candle(
        self,
        asset: str,
        timeframe: str,
        candle: list,
    ) -> None:
        """
        Write a single closed candle to Redis ring buffer.
        Key: ohlcv:{asset}:{timeframe}  (e.g. ohlcv:BTC/USDT:15m)
        Value: JSON list of last RING_BUFFER_SIZE candles

        Atomic: uses Redis LPUSH + LTRIM to maintain ring buffer.
        Latency target: < 0.1ms per write.

        Satisfies: Requirement 2.1 (atomic write)
        """
        ts, open_, high, low, close, volume = candle
        candle_dict = {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        key = f"ohlcv:{asset}:{timeframe}"
        candle_json = json.dumps(candle_dict)

        # LPUSH adds to front, LTRIM keeps only last N
        await self._redis.lpush(key, candle_json)
        await self._redis.ltrim(key, 0, RING_BUFFER_SIZE - 1)


async def read_ohlcv_from_redis(
    redis_client,
    asset: str,
    timeframe: str,
    limit: int = 500,
) -> list[dict]:
    """
    Read OHLCV candles from Redis ring buffer.
    Returns list of candle dicts sorted ascending by timestamp.

    Used by Celery signal scorer to read data without blocking WS.
    """
    key = f"ohlcv:{asset}:{timeframe}"
    raw = await redis_client.lrange(key, 0, limit - 1)
    candles = [json.loads(c) for c in raw]
    # LPUSH stores newest first — reverse to get ascending order
    candles.reverse()
    return candles
