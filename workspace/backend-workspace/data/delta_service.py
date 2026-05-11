"""
Delta Service (Trade Tape)
===========================
Polls recent trades every 10 seconds → computes cumulative delta → stores in Redis.

delta = sum(buy_volume) - sum(sell_volume)
Positive delta = net buying pressure (bullish)
Negative delta = net selling pressure (bearish)

Delta History (Task 34.2):
  After each candle close, appends current delta to delta_history:{symbol}
  Keeps last 96 values (24h × 4 per hour = 96 for 15m TF)
  Used by compute_dynamic_delta_threshold() in order_flow.py

Public data — no API key required.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

from trading_core.exchange import get_exchange_client
from trading_core.cache import get_redis, RedisKeys

logger = logging.getLogger(__name__)

POLL_INTERVAL = 10   # seconds
TRADE_LIMIT = 100    # trades per poll
DELTA_TTL = 300      # 5 minutes — reset after each candle close
DELTA_HISTORY_SIZE = 96   # 24h of 15m candles (24 × 4 = 96)
DELTA_HISTORY_TTL = 25 * 3600  # 25 hours


_LAST_TS_KEY_PREFIX = "delta_last_ts:"  # Redis key: delta_last_ts:{symbol}


class DeltaService:
    """
    Polls trade tape and accumulates cumulative delta in Redis.
    Redis key: delta:{symbol}:5m
    Delta history: delta_history:{symbol} (list of last 96 values)
    """

    def __init__(self, exchange_id: str, symbols: List[str]) -> None:
        self.exchange_id = exchange_id
        self.symbols = symbols
        # _last_trade_id is kept as in-memory cache; authoritative value is in Redis
        self._last_trade_id: dict = {}

    def _get_exchange(self):
        return get_exchange_client(self.exchange_id)

    def _get_redis(self):
        return get_redis()

    async def start(self) -> None:
        """Start polling all symbols concurrently."""
        logger.info("DeltaService starting: %d symbol(s)", len(self.symbols))
        await asyncio.gather(*[self._poll(s) for s in self.symbols])

    async def _poll(self, symbol: str) -> None:
        """Poll trades and accumulate delta in Redis."""
        # Load last-seen timestamp from Redis on first poll (restart safety)
        r_init = self._get_redis()
        _ts_key = f"{_LAST_TS_KEY_PREFIX}{symbol}"
        try:
            _stored = r_init.get(_ts_key)
            if _stored and symbol not in self._last_trade_id:
                self._last_trade_id[symbol] = int(_stored)
        except Exception:
            pass

        while True:
            try:
                exchange = self._get_exchange()
                r = self._get_redis()
                loop = asyncio.get_running_loop()

                trades = await loop.run_in_executor(
                    None,
                    lambda: exchange.fetch_trades(symbol, limit=TRADE_LIMIT),
                )

                if not trades:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                # Use timestamp-based deduplication — avoids lexicographic ID comparison bugs
                # where "9" > "10" evaluates True (string comparison).
                last_ts = self._last_trade_id.get(symbol)
                if last_ts is None:
                    new_trades = trades
                else:
                    new_trades = [t for t in trades if t.get("timestamp", 0) > last_ts]

                if new_trades:
                    latest_ts = max(t.get("timestamp", 0) for t in new_trades)
                    self._last_trade_id[symbol] = latest_ts
                    # Persist to Redis so restarts don't replay old trades
                    try:
                        r.set(_ts_key, str(latest_ts), ex=DELTA_TTL * 10)
                    except Exception:
                        pass
                    delta_increment = sum(
                        t["amount"] if t["side"] == "buy" else -t["amount"]
                        for t in new_trades
                    )
                    r.incrbyfloat(RedisKeys.delta(symbol), delta_increment)
                    r.expire(RedisKeys.delta(symbol), DELTA_TTL)

                    current = float(r.get(RedisKeys.delta(symbol)) or 0)
                    logger.debug(
                        "Delta %s: +%.4f new trades, total=%.4f",
                        symbol, delta_increment, current,
                    )

            except Exception as exc:
                logger.warning("Delta poll error %s: %s", symbol, exc)

            await asyncio.sleep(POLL_INTERVAL)

    def reset_delta(self, symbol: str) -> None:
        """Reset delta to 0 after candle close (called by scoring service)."""
        r = self._get_redis()
        r.set(RedisKeys.delta(symbol), "0", ex=DELTA_TTL)

    def snapshot_delta_to_history(self, symbol: str) -> None:
        """
        Append current delta to rolling 24h history before resetting.
        Called by scoring service after each candle close. (Task 34.2)
        """
        r = self._get_redis()
        try:
            current = float(r.get(RedisKeys.delta(symbol)) or 0)
            r.rpush(RedisKeys.delta_history(symbol), str(current))
            r.ltrim(RedisKeys.delta_history(symbol), -DELTA_HISTORY_SIZE, -1)
            r.expire(RedisKeys.delta_history(symbol), DELTA_HISTORY_TTL)
            logger.debug("Delta history snapshot %s: %.4f", symbol, current)
        except Exception as exc:
            logger.warning("Delta history snapshot error %s: %s", symbol, exc)

    def get_delta_threshold(self, symbol: str) -> float:
        """Get dynamic delta threshold for a symbol based on 24h history."""
        from engine.order_flow import compute_dynamic_delta_threshold
        r = self._get_redis()
        try:
            raw = r.lrange(RedisKeys.delta_history(symbol), 0, -1)
            history = [float(v) for v in raw if v]
            return compute_dynamic_delta_threshold(history)
        except Exception as exc:
            logger.warning("get_delta_threshold error %s: %s", symbol, exc)
            from engine.order_flow import FALLBACK_DELTA_THRESHOLD
            return FALLBACK_DELTA_THRESHOLD
