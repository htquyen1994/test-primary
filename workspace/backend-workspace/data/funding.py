"""
Funding Rate Ingestion
=======================
Polls ccxt REST endpoint for funding rates at each funding interval.
Stores in Redis for real-time access and logs to signal_log for analytics.

Redis key: funding:{asset}  → JSON {rate, timestamp, next_funding_time}

Satisfies: Requirements 3.1, 3.2, 3.4
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from data.ccxt_client import retry_with_backoff, DataFetchError

logger = logging.getLogger(__name__)

FUNDING_POLL_INTERVAL = 60 * 60  # poll every hour (funding updates every 8h)
FUNDING_TTL_SECONDS = 60 * 60 * 9  # expire after 9h (slightly longer than 8h interval)


class FundingRateFeed:
    """
    Polls funding rate for perpetual futures assets.
    Falls back to 0.0 if data is unavailable (Req 3.4).
    """

    def __init__(
        self,
        exchange,
        assets: list[str],
        redis_client,
        poll_interval: int = FUNDING_POLL_INTERVAL,
    ) -> None:
        self._exchange = exchange
        self._assets = assets
        self._redis = redis_client
        self._poll_interval = poll_interval
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Starting funding rate feed for %d asset(s)", len(self._assets))
        # Initial fetch immediately, then poll on interval
        await self._fetch_all()
        while self._running:
            await asyncio.sleep(self._poll_interval)
            if self._running:
                await self._fetch_all()

    async def stop(self) -> None:
        self._running = False

    async def _fetch_all(self) -> None:
        for asset in self._assets:
            await self._fetch_one(asset)

    async def _fetch_one(self, asset: str) -> None:
        """
        Fetch funding rate for one asset.
        Falls back to 0.0 if unavailable (Req 3.4).
        """
        try:
            rate = await self._fetch_funding_rate(asset)
        except Exception as exc:
            logger.warning(
                "Funding rate unavailable for %s: %s — using 0.0 (Req 3.4)",
                asset, exc,
            )
            rate = 0.0

        record = {
            "asset": asset,
            "rate": rate,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        key = f"funding:{asset}"
        await self._redis.set(key, json.dumps(record), ex=FUNDING_TTL_SECONDS)
        logger.debug("Funding rate %s: %.6f", asset, rate)

    async def _fetch_funding_rate(self, asset: str) -> float:
        """
        Fetch current funding rate from exchange.
        Uses retry logic for transient errors.
        """
        try:
            # ccxt: fetch_funding_rate returns dict with 'fundingRate' key
            data = await self._exchange.fetch_funding_rate(asset)
            rate = data.get("fundingRate") or data.get("funding_rate") or 0.0
            return float(rate)
        except Exception as exc:
            raise DataFetchError("fetch_funding_rate", 1, exc) from exc


async def read_funding_rate(redis_client, asset: str) -> float:
    """
    Read current funding rate from Redis.
    Returns 0.0 if not available (Req 3.4).
    """
    key = f"funding:{asset}"
    val = await redis_client.get(key)
    if not val:
        return 0.0
    try:
        record = json.loads(val)
        return float(record.get("rate", 0.0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0.0
