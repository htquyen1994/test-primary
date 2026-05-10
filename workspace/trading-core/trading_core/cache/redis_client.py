"""
Redis Client — Singleton Factory
==================================
All services use get_redis() — never instantiate redis.Redis directly.

Benefits:
  - Single connection pool per URL → efficient resource usage
  - Consistent decode_responses=True across all services
  - Easy to mock in tests

Usage:
    from trading_core.cache import get_redis

    r = get_redis()
    r.set("key", "value")
    data = r.get("key")

    # Async (for FastAPI WebSocket handlers):
    from trading_core.cache import get_async_redis
    redis = await get_async_redis()
    await redis.publish("channel", "message")
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_REDIS_URL_ENV = "REDIS_URL"
_DEFAULT_URL = "redis://localhost:6379/0"


def _get_url(url: Optional[str] = None) -> str:
    return url or os.environ.get(_REDIS_URL_ENV, _DEFAULT_URL)


@lru_cache(maxsize=4)
def get_redis(url: Optional[str] = None):
    """
    Return a singleton synchronous Redis client.

    Args:
        url: Redis URL (default: REDIS_URL env var or redis://localhost:6379/0)

    Returns:
        redis.Redis instance with decode_responses=True
    """
    import redis as redis_lib
    resolved_url = _get_url(url)
    client = redis_lib.from_url(resolved_url, decode_responses=True)
    logger.info("Redis client created: %s", resolved_url.split("@")[-1])
    return client


# Async client cache — keyed by URL string
_async_clients: dict = {}


async def get_async_redis(url: Optional[str] = None):
    """
    Return a singleton async Redis client (aioredis).

    Used in FastAPI WebSocket handlers and async pub/sub.

    Args:
        url: Redis URL (default: REDIS_URL env var or redis://localhost:6379/0)

    Returns:
        aioredis.Redis instance
    """
    import aioredis
    resolved_url = _get_url(url)
    if resolved_url not in _async_clients:
        _async_clients[resolved_url] = await aioredis.from_url(
            resolved_url, decode_responses=True
        )
        logger.info("Async Redis client created: %s", resolved_url.split("@")[-1])
    return _async_clients[resolved_url]
