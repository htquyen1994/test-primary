"""
Trade Execution Celery Task
============================
Dispatched by /api/signals/{id}/confirm after RiskManager validation.
Runs TradeExecutor asynchronously and persists results.

Queue: default
Retries: 2 × 3s delay on failure

Satisfies: Requirements 19.1–19.9, 18.3
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Redis status key prefix — readable by API polling endpoint
_STATUS_KEY_PREFIX = "trade:status:"
_STATUS_TTL = 86400  # 24 hours

# Import Celery app
try:
    from celery_app import app as celery_app
except ImportError:
    celery_app = None  # allow import without Celery in test environments


def _task(fn):
    """Register function as Celery task if celery_app is available."""
    if celery_app is not None:
        return celery_app.task(
            bind=True,
            name=f"trade.tasks.{fn.__name__}",
            max_retries=2,
            default_retry_delay=3,
        )(fn)
    return fn


@_task
def execute_trade(self, signal_card: dict, position_size_usd: float) -> dict:
    """
    Execute a confirmed trade signal via TradeExecutor.

    1. Build exchange client from active ExchangeSettings (DB).
    2. Build TradeExecutor with testnet guard.
    3. Run executor.execute() via asyncio.run().
    4. Record entry fill in trade_journal.
    5. Publish execution result to Redis alerts channel (UI update).
    6. Store execution status in Redis for polling.

    Args:
        signal_card:       Signal Card dict from alert builder (entry_price, stop_loss, etc.)
        position_size_usd: Notional position size in USD from RiskManager

    Returns:
        {"status": "Filled"|"Failed", "signal_id": str, ...}
    """
    from trading_core.cache import get_redis, RedisKeys

    signal_id = signal_card.get("signal_id", "unknown")
    r = get_redis()

    try:
        # --- Build config ---
        from config.config_system import ConfigSystem
        cfg = ConfigSystem(os.environ.get("CONFIG_PATH", "config.yaml"))
        config = cfg.get()

        # --- Build exchange client from DB ---
        from db.connection import get_session_factory
        from config.config_service import build_ccxt_exchange, get_active_exchange_settings
        db = get_session_factory()()
        try:
            exchange = build_ccxt_exchange(db)
            fee_rate = _get_fee_rate(db)
            ex_settings = get_active_exchange_settings(db)
            account_equity = float(ex_settings.get("account_balance_usd", 10000.0))
        finally:
            db.close()

        # --- Run executor (testnet guard inside executor) ---
        from trade.executor import TradeExecutor
        executor = TradeExecutor(exchange, config)
        result = asyncio.run(executor.execute(signal_card, position_size_usd))

        # --- Record entry in trade_journal ---
        if result.success and result.order_id:
            _record_journal_entry(signal_card, result, position_size_usd, fee_rate)
            _register_open_position(signal_card, result, position_size_usd, account_equity)

        # --- Publish result to Redis for UI ---
        status = "Filled" if result.success else "Failed"
        _publish_execution_result(r, signal_id, status, result, signal_card)

        # --- Cache status for polling ---
        _write_status_cache(r, signal_id, status, result)

        return {"status": status, "signal_id": signal_id, "order_id": result.order_id}

    except Exception as exc:
        logger.error("execute_trade failed for %s: %s", signal_id, exc, exc_info=True)

        # Write failure status before retry
        _write_status_cache(r, signal_id, "Failed", error=str(exc))
        _publish_execution_result(r, signal_id, "Failed", error=str(exc))

        if celery_app is not None:
            raise self.retry(exc=exc)
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_fee_rate(db_session) -> float:
    from config.config_service import get_active_exchange_settings
    settings = get_active_exchange_settings(db_session)
    return settings.get("fee_rate", 0.001)


def _register_open_position(
    signal_card: dict,
    result,
    position_size_usd: float,
    account_equity: float,
) -> None:
    """
    Register the filled position for portfolio heat tracking.
    Computes actual risk_pct = (notional × sl_dist_pct) / equity and
    writes to Redis so it survives API/worker restarts.
    """
    try:
        asset = signal_card.get("asset", "")
        entry_price = float(result.actual_fill_price or signal_card.get("entry_price", 0))
        stop_loss = float(signal_card.get("stop_loss", 0))

        sl_dist_pct = abs(entry_price - stop_loss) / entry_price if entry_price else 0.0
        risk_pct = (position_size_usd * sl_dist_pct) / account_equity if account_equity else 0.0

        from trade.position_monitor import register_open_position
        register_open_position(
            trade_id=result.order_id,
            position_info={
                "asset": asset,
                "direction": signal_card.get("direction", "long"),
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "position_size_usd": position_size_usd,
                "risk_pct": risk_pct,
            },
        )
        logger.info(
            "Open position registered: %s risk_pct=%.4f", asset, risk_pct
        )
    except Exception as exc:
        logger.warning("Failed to register open position for %s: %s", signal_card.get("signal_id"), exc)


def _record_journal_entry(signal_card, result, position_size_usd: float, fee_rate: float) -> None:
    """Write entry fill to trade_journal."""
    try:
        from db.connection import get_session_factory
        from trade.journal import record_entry
        db = get_session_factory()()
        try:
            record_entry(
                signal_card=signal_card,
                fill_price=result.actual_fill_price or signal_card.get("entry_price", 0.0),
                order_id=result.order_id or "",
                position_size_usd=position_size_usd,
                fee_rate=fee_rate,
                db_session=db,
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to record journal entry for %s: %s", signal_card.get("signal_id"), exc)


def _write_status_cache(r, signal_id: str, status: str, result=None, error: str = "") -> None:
    """Write execution status to Redis for API polling."""
    payload = {
        "signal_id": signal_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if result is not None:
        payload.update({
            "order_id": result.order_id,
            "fill_price": result.actual_fill_price,
            "slippage": result.actual_slippage,
            "is_testnet": result.is_testnet,
            "error": result.error or error,
        })
    elif error:
        payload["error"] = error

    try:
        r.set(f"{_STATUS_KEY_PREFIX}{signal_id}", json.dumps(payload), ex=_STATUS_TTL)
    except Exception as exc:
        logger.warning("Failed to write status cache for %s: %s", signal_id, exc)


def _publish_execution_result(r, signal_id: str, status: str, result=None, signal_card: dict = None, error: str = "") -> None:
    """Push execution event to Redis alerts channel so the UI WebSocket receives it."""
    from trading_core.cache import RedisKeys
    event = {
        "event": "trade_executed",
        "signal_id": signal_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if result is not None and result.success:
        event.update({
            "order_id": result.order_id,
            "fill_price": result.actual_fill_price,
            "slippage": result.actual_slippage,
            "is_testnet": result.is_testnet,
            "asset": signal_card.get("asset") if signal_card else None,
            "direction": signal_card.get("direction") if signal_card else None,
        })
    if error or (result and result.error):
        event["error"] = error or result.error

    try:
        r.publish(RedisKeys.Channels.ALERTS, json.dumps(event))
    except Exception as exc:
        logger.warning("Failed to publish execution event for %s: %s", signal_id, exc)
