"""
CandleFeed — subscribes to Redis candle_close channel.
On each event: reads OHLCV from Redis, checks SL/TP for open positions,
records price snapshot to DB.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import PriceSnapshot
from exchange.position_tracker import PositionTracker

logger = logging.getLogger(__name__)


class CandleFeed:
    """
    Async background task that:
    1. Subscribes to Redis 'candle_close' pub/sub channel
    2. For each event, reads ohlcv:{symbol}:{timeframe} list from Redis
    3. Runs PositionTracker.check_positions_for_symbol()
    4. Persists candle data to price_snapshots table
    """

    def __init__(
        self,
        redis_client,
        position_tracker: PositionTracker,
        db_factory,
    ) -> None:
        self._redis = redis_client
        self._tracker = position_tracker
        self._db_factory = db_factory
        self._running = False

    async def run(self) -> None:
        """Blocking coroutine — runs until cancelled."""
        self._running = True
        logger.info("CandleFeed starting — subscribing to candle_close channel")

        while self._running:
            try:
                await self._subscribe_loop()
            except asyncio.CancelledError:
                logger.info("CandleFeed cancelled")
                break
            except Exception as exc:
                logger.error("CandleFeed error, restarting in 5s: %s", exc)
                await asyncio.sleep(5)

    async def _subscribe_loop(self) -> None:
        loop = asyncio.get_running_loop()
        pubsub = self._redis.pubsub()
        pubsub.subscribe("candle_close")
        logger.info("CandleFeed subscribed to candle_close")

        try:
            while self._running:
                # Run blocking get_message in thread pool to avoid blocking event loop
                message = await loop.run_in_executor(
                    None, lambda: pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                )
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                if message.get("type") != "message":
                    continue

                data_str = message.get("data", "")
                if not data_str:
                    continue

                try:
                    data = json.loads(data_str)
                    await self._handle_candle_close(data)
                except json.JSONDecodeError as exc:
                    logger.warning("CandleFeed: invalid JSON in candle_close: %s", exc)
                except Exception as exc:
                    logger.error("CandleFeed: error handling candle_close: %s", exc)
        finally:
            try:
                pubsub.unsubscribe("candle_close")
                pubsub.close()
            except Exception:
                pass

    async def _handle_candle_close(self, data: dict) -> None:
        symbol = data.get("symbol")
        timeframe = data.get("timeframe", "15m")
        if not symbol:
            return

        # Read latest OHLCV from Redis ring buffer
        candle = await self._read_latest_candle(symbol, timeframe)
        if candle is None:
            logger.debug("No OHLCV data found for %s %s", symbol, timeframe)
            return

        high = candle.get("high", 0.0)
        low = candle.get("low", 0.0)
        close = candle.get("close", data.get("close", 0.0))
        open_price = candle.get("open", 0.0)
        volume = candle.get("volume", 0.0)
        timestamp = candle.get("timestamp", datetime.now(timezone.utc).isoformat())

        # Persist price snapshot
        await self._save_price_snapshot(
            symbol, timeframe, open_price, high, low, close, volume, timestamp
        )

        # Check SL/TP for open positions
        await self._tracker.check_positions_for_symbol(
            symbol=symbol,
            timeframe=timeframe,
            candle_high=high,
            candle_low=low,
            candle_close=close,
        )

    async def _read_latest_candle(
        self, symbol: str, timeframe: str
    ) -> dict | None:
        """Read the last entry from ohlcv:{symbol}:{timeframe} Redis list."""
        loop = asyncio.get_running_loop()
        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            raw = await loop.run_in_executor(
                None, lambda: self._redis.lindex(key, -1)
            )
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Failed to read OHLCV from Redis: %s", exc)
            return None

    async def _save_price_snapshot(
        self,
        symbol: str,
        timeframe: str,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        timestamp: str,
    ) -> None:
        loop = asyncio.get_running_loop()

        def _insert():
            db: Session = self._db_factory()
            try:
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                from sqlalchemy import insert
                # Use INSERT OR IGNORE for SQLite upsert
                snap = PriceSnapshot(
                    symbol=symbol,
                    timeframe=timeframe,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    timestamp=timestamp,
                    recorded_at=datetime.now(timezone.utc).isoformat(),
                )
                db.merge(snap) if False else db.add(snap)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
            finally:
                db.close()

        try:
            await loop.run_in_executor(None, _insert)
        except Exception as exc:
            logger.debug("Price snapshot insert failed (likely duplicate): %s", exc)

    def stop(self) -> None:
        self._running = False
