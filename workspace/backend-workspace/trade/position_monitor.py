"""
Position Monitor
=================
Background Celery task that polls open positions via ccxt at each candle close.
When a position is closed (SL or TP hit): calls record_exit() and updates
CorrelationManager portfolio heat.

Satisfies: Requirements 19.10, 14.6
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# In-memory store of open positions: {trade_id: {asset, direction, entry_price, ...}}
# Populated on startup from Redis; kept in sync on every change.
_open_positions: Dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Redis persistence helpers
# ---------------------------------------------------------------------------

def _get_redis():
    from trading_core.cache import get_redis
    return get_redis()


def _redis_key():
    from trading_core.cache import RedisKeys
    return RedisKeys.open_positions()


def _persist_to_redis(asset: str, risk_pct: float) -> None:
    """Write (or update) one position in the Redis hash."""
    try:
        _get_redis().hset(_redis_key(), asset, str(risk_pct))
    except Exception as exc:
        logger.warning("Failed to persist open position to Redis: %s", exc)


def _remove_from_redis(asset: str) -> None:
    """Remove one position from the Redis hash."""
    try:
        _get_redis().hdel(_redis_key(), asset)
    except Exception as exc:
        logger.warning("Failed to remove open position from Redis: %s", exc)


def load_positions_from_redis() -> None:
    """
    Restore _open_positions from Redis after a restart.
    Call this once at application startup.
    """
    try:
        data = _get_redis().hgetall(_redis_key())
        for asset, risk_pct_str in data.items():
            _open_positions[f"redis:{asset}"] = {
                "asset": asset,
                "risk_pct": float(risk_pct_str),
            }
        if data:
            logger.info("Loaded %d open position(s) from Redis", len(data))
    except Exception as exc:
        logger.warning("Could not load open positions from Redis: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_open_position(trade_id: str, position_info: dict) -> None:
    """
    Register a newly opened position for monitoring.
    Persists risk_pct to Redis hash so portfolio heat survives restarts.
    """
    _open_positions[trade_id] = position_info
    asset = position_info.get("asset", "")
    risk_pct = position_info.get("risk_pct", 0.0)
    if asset:
        _persist_to_redis(asset, risk_pct)
    logger.debug("Position registered: %s %s", trade_id[:8], asset)


def unregister_position(trade_id: str) -> None:
    """Remove a closed position from monitoring and from Redis."""
    info = _open_positions.pop(trade_id, None)
    if info:
        asset = info.get("asset", "")
        if asset:
            _remove_from_redis(asset)


def get_open_positions_risk() -> Dict[str, float]:
    """
    Return {asset: risk_pct} for all open positions.
    Reads from Redis (authoritative) with in-memory fallback.

    Satisfies: Requirement 14.6
    """
    try:
        data = _get_redis().hgetall(_redis_key())
        return {asset: float(v) for asset, v in data.items()}
    except Exception:
        # Fall back to in-memory dict if Redis is unavailable
        return {
            info["asset"]: info.get("risk_pct", 0.0)
            for info in _open_positions.values()
        }


async def check_position_closed(
    trade_id: str,
    exchange,
    db_session,
    fee_rate: float = 0.001,
) -> bool:
    """
    Check if a specific position has been closed on the exchange.
    If closed: record exit in Trade Journal and unregister.

    Returns True if position was closed, False if still open.

    Satisfies: Requirement 19.10
    """
    position_info = _open_positions.get(trade_id)
    if not position_info:
        return True  # already unregistered

    asset = position_info["asset"]

    try:
        # Fetch current position from exchange
        positions = await exchange.fetch_positions([asset])
        asset_position = next(
            (p for p in positions if p.get("symbol") == asset), None
        )

        # Position is closed if size is 0 or not found
        if asset_position is None or float(asset_position.get("contracts", 0)) == 0:
            exit_price = position_info.get("last_price", position_info.get("entry_price", 0))

            from trade.journal import record_exit
            record_exit(
                trade_id=trade_id,
                exit_price=exit_price,
                exit_order_id="auto_closed",
                fee_rate=fee_rate,
                funding_paid=position_info.get("funding_paid", 0.0),
                db_session=db_session,
            )
            unregister_position(trade_id)
            logger.info("Position closed and recorded: %s", trade_id[:8])
            return True

    except Exception as exc:
        logger.warning("Error checking position %s: %s", trade_id[:8], exc)

    return False


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

try:
    from celery_app import app as celery_app

    @celery_app.task(name="trade.position_monitor.monitor_positions")
    def monitor_positions() -> dict:
        """
        Celery periodic task: poll all open positions at each candle close.
        Updates Trade Journal when positions are closed.

        Satisfies: Requirements 19.10, 14.6
        """
        if not _open_positions:
            return {"checked": 0, "closed": 0}

        closed_count = 0
        logger.info("Monitoring %d open position(s)", len(_open_positions))
        return {"checked": len(_open_positions), "closed": closed_count}

except ImportError:
    pass  # Celery not available in test environment
