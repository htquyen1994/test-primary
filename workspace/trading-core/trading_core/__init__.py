"""
trading-core — Shared infrastructure library
=============================================
Provides reusable infrastructure components for all trading services:
  - exchange: ccxt adapter + singleton + interface contract
  - cache:    Redis singleton + key schema
  - db:       SQLAlchemy engine factory + ORM base
  - models:   Shared dataclasses (Order, Position, Signal)
  - utils:    retry, logging helpers

Usage:
    from trading_core.exchange import get_exchange_client
    from trading_core.cache import get_redis, RedisKeys
    from trading_core.db import get_engine, get_session_factory
    from trading_core.models import Signal, Order, Position
    from trading_core.utils.retry import retry_with_backoff
"""

__version__ = "0.1.0"
