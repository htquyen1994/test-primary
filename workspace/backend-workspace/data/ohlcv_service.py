"""
OHLCV Service
==============
Polls OHLCV candles from exchange → stores in Redis ring buffer.
Publishes candle_close event when a new closed candle is detected.

Public data — no API key required.

Timeframes supported:
  15m  — trigger timeframe (scoring)
  1h   — context timeframe (HTF bias)
  4h   — MTF filter (Task 31.1)
  1d   — Daily macro bias (Task 35.1)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import List

from trading_core.exchange import get_exchange_client
from trading_core.cache import get_redis, RedisKeys

logger = logging.getLogger(__name__)

# Poll intervals per timeframe (seconds)
TF_POLL_INTERVALS = {
    "1m": 15, "3m": 30, "5m": 30, "15m": 60,
    "30m": 90, "1h": 120, "4h": 300, "1d": 3600,
}

# Ring buffer sizes per timeframe
TF_RING_BUFFER = {
    "15m": 500,
    "30m": 500,
    "1h": 200,
    "4h": 200,   # Task 31.1: 200 candles ≈ 33 days
    "1d": 250,   # Task 35.1: 250 candles ≈ 1 year (for EMA200)
}
DEFAULT_RING_BUFFER = 500

# HTF timeframes — do NOT trigger scoring (only used as context)
HTF_TIMEFRAMES = {"4h", "1d"}

# Startup fetch sizes — fetch more candles on first run for indicator warmup
TF_STARTUP_FETCH = {
    "15m": 100, "30m": 100, "1h": 100,
    "4h": 200,   # need 200 for EMA200 on 4H
    "1d": 250,   # need 250 for EMA200 on Daily
}
DEFAULT_STARTUP_FETCH = 100


class OHLCVService:
    """
    Polls OHLCV candles from exchange and stores in Redis.
    Triggers signal scoring on each new closed candle (15m/1h only).
    4H and Daily are polled for context but do NOT trigger scoring.
    """

    def __init__(self, exchange_id: str, symbols: List[str], timeframes: List[str]) -> None:
        self.exchange_id = exchange_id
        # Always include BTC/USDT for spike monitoring (Task 33.4)
        all_symbols = list(symbols)
        if "BTC/USDT" not in all_symbols:
            all_symbols.insert(0, "BTC/USDT")
            logger.info("BTC/USDT added to monitoring for spike guard")
        self.symbols = all_symbols
        # Always include 4h and 1d for MTF/Daily bias regardless of config
        all_tfs = list(timeframes)
        for htf in ("4h", "1d"):
            if htf not in all_tfs:
                all_tfs.append(htf)
        self.timeframes = all_tfs
        self._last_ts: dict = {}
        self._initialized: set = set()  # tracks which keys have been seeded

    def _get_exchange(self):
        return get_exchange_client(self.exchange_id)

    def _get_redis(self):
        return get_redis()

    async def start(self) -> None:
        """Start polling all symbol/timeframe combinations concurrently."""
        logger.info(
            "OHLCVService starting: %d symbols × %d timeframes",
            len(self.symbols), len(self.timeframes),
        )
        tasks = [
            self._poll(symbol, tf)
            for symbol in self.symbols
            for tf in self.timeframes
        ]
        await asyncio.gather(*tasks)

    async def _seed_history(self, symbol: str, timeframe: str) -> None:
        """
        Fetch historical candles on startup to warm up indicators.
        Especially important for 4H (EMA200 needs 200 bars) and Daily (250 bars).
        """
        key = f"{symbol}:{timeframe}"
        if key in self._initialized:
            return

        fetch_limit = TF_STARTUP_FETCH.get(timeframe, DEFAULT_STARTUP_FETCH)
        ring_size = TF_RING_BUFFER.get(timeframe, DEFAULT_RING_BUFFER)

        try:
            exchange = self._get_exchange()
            r = self._get_redis()
            loop = asyncio.get_running_loop()

            candles = await loop.run_in_executor(
                None,
                lambda: exchange.fetch_ohlcv(symbol, timeframe, limit=fetch_limit),
            )

            # Store all historical candles (skip last — still forming)
            redis_key = RedisKeys.ohlcv(symbol, timeframe)
            pipe = r.pipeline()
            for candle in candles[:-1]:
                ts, o, h, l, c, v = candle[0], candle[1], candle[2], candle[3], candle[4], candle[5]
                candle_dict = {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}
                pipe.lpush(redis_key, json.dumps(candle_dict))
            pipe.ltrim(redis_key, 0, ring_size - 1)
            pipe.execute()

            if candles:
                self._last_ts[key] = candles[-2][0] if len(candles) >= 2 else candles[-1][0]

            self._initialized.add(key)
            logger.info(
                "Seeded %d historical candles for %s %s",
                min(len(candles) - 1, fetch_limit), symbol, timeframe,
            )
        except Exception as exc:
            logger.warning("History seed error %s %s: %s", symbol, timeframe, exc)

    async def _poll(self, symbol: str, timeframe: str) -> None:
        """Poll one symbol/timeframe and detect new closed candles."""
        interval = TF_POLL_INTERVALS.get(timeframe, 60)
        ring_size = TF_RING_BUFFER.get(timeframe, DEFAULT_RING_BUFFER)
        key = f"{symbol}:{timeframe}"
        is_htf = timeframe in HTF_TIMEFRAMES

        logger.info(
            "OHLCV polling %s %s every %ds (HTF=%s)",
            symbol, timeframe, interval, is_htf,
        )

        # Seed historical data on startup
        await self._seed_history(symbol, timeframe)

        while True:
            try:
                exchange = self._get_exchange()
                r = self._get_redis()
                loop = asyncio.get_running_loop()

                candles = await loop.run_in_executor(
                    None,
                    lambda: exchange.fetch_ohlcv(symbol, timeframe, limit=10),
                )

                for candle in candles[:-1]:  # skip last (still forming)
                    ts = candle[0]
                    if self._last_ts.get(key) == ts:
                        continue
                    self._last_ts[key] = ts

                    o, h, l, c, v = candle[1], candle[2], candle[3], candle[4], candle[5]
                    candle_dict = {
                        "timestamp": ts, "open": o, "high": h,
                        "low": l, "close": c, "volume": v,
                    }
                    redis_key = RedisKeys.ohlcv(symbol, timeframe)
                    r.lpush(redis_key, json.dumps(candle_dict))
                    r.ltrim(redis_key, 0, ring_size - 1)

                    logger.info(
                        "New candle: %s %s close=%.4f vol=%.2f",
                        symbol, timeframe, c, v,
                    )

                    # Only trigger scoring for non-HTF timeframes
                    if not is_htf:
                        r.publish(RedisKeys.Channels.CANDLE_CLOSE, json.dumps({
                            "symbol": symbol, "timeframe": timeframe, "close": c,
                        }))

                    # Task 33.4: BTC spike monitoring — check on every BTC 15m candle
                    if symbol == "BTC/USDT" and timeframe == "15m":
                        self._check_btc_spike(symbol, r)

            except Exception as exc:
                logger.warning("OHLCV poll error %s %s: %s", symbol, timeframe, exc)

            await asyncio.sleep(interval)

    def _check_btc_spike(self, symbol: str, r) -> None:
        """
        Check BTC 15m candles for spike and publish btc_spike event.
        Called on every new BTC/USDT 15m candle close. (Task 33.4)
        """
        try:
            import pandas as pd
            from engine.btc_guard import BTCVolatilityGuard

            raw = r.lrange(RedisKeys.ohlcv(symbol, "15m"), 0, 9)
            if not raw:
                return

            ohlcv_btc = pd.DataFrame([json.loads(c) for c in reversed(raw)])
            guard = BTCVolatilityGuard()
            result = guard.check_btc_spike(ohlcv_btc)

            if result.spike_detected:
                logger.warning(
                    "BTC spike detected in OHLCVService: %s %.2f%%",
                    result.direction, result.magnitude_pct * 100,
                )
                # Cancel all Alt alerts on BTC dump
                if result.direction == "dump":
                    guard.cancel_all_alt_alerts()
                    guard.reset_alt_deltas(self.symbols)
        except Exception as exc:
            logger.warning("BTC spike check error: %s", exc)
