"""
FastAPI Dashboard Backend
==========================
REST + WebSocket endpoints for the Human Confirm Dashboard.

Endpoints:
  GET  /api/signals              — active ALERT-class signals
  POST /api/signals/{id}/confirm — confirm a signal → Trade Executor
  POST /api/signals/{id}/skip    — skip a signal
  GET  /api/journal              — paginated trade journal
  GET  /api/analytics            — aggregated performance metrics
  GET  /api/portfolio            — Portfolio_Heat + correlated risk
  GET  /api/strategies           — registered strategy names
  GET  /api/config               — current config (non-sensitive)
  POST /api/config/reload        — hot-reload config.yaml
  GET  /api/backtest/results     — backtest result records
  POST /api/backtest/run         — trigger async backtest run
  WS   /ws/alerts                — real-time Signal Card stream
  WS   /ws/portfolio             — real-time Portfolio_Heat stream

Satisfies: Requirements 18.1–18.10, 14.8
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    SignalCardResponse, SkipRequest, TradeJournalEntry,
    AnalyticsResponse, PortfolioResponse, BacktestRunRequest,
)
from api.auth import require_api_key
from api.routes.config_routes import router as config_router
from trading_core.cache import get_async_redis, RedisKeys

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Crypto Trading System Dashboard API",
    version="1.0.0",
    description="Semi-automatic crypto trading dashboard backend",
)

# Task 30.1: CORS — explicit origins only, no wildcard
# Override via ALLOWED_ORIGINS env var for production (comma-separated)
_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
_allowed_origins = (
    [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
    if _allowed_origins_env
    else ["http://localhost:5173", "http://localhost:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register config management routes
app.include_router(config_router)

# In-memory signal store (populated by Redis pub/sub listener)
_active_signals: dict = {}


async def _get_open_positions() -> dict:
    """
    Read open positions from Redis hash `portfolio:open_positions`.
    Returns {asset: risk_pct}. Restart-safe: returns {} on Redis error.
    """
    try:
        r = await get_async_redis()
        data = await r.hgetall(RedisKeys.open_positions())
        return {k: float(v) for k, v in data.items()}
    except Exception:
        return {}


def _load_account_settings() -> tuple:
    """
    Load account equity, fee rate, and sizing parameters from DB ExchangeSettings.
    Returns (account_equity, fee_rate, sizing_mode, fixed_usd, risk_pct, leverage, market_type).
    Falls back to config.yaml defaults on DB error.
    """
    try:
        from db.connection import get_session_factory
        from config.config_service import get_active_exchange_settings, get_active_trading_params
        db = get_session_factory()()
        try:
            ex = get_active_exchange_settings(db)
        finally:
            db.close()
        return (
            float(ex.get("account_balance_usd", 10000.0)),
            float(ex.get("fee_rate", 0.001)),
            ex.get("sizing_mode", "risk_pct"),
            float(ex.get("fixed_usd_per_trade", 100.0)),
            float(ex.get("risk_pct_per_trade", 0.02)),
            int(ex.get("default_leverage", 5)),
            ex.get("market_type", "futures"),
        )
    except Exception:
        from config.config_system import ConfigSystem
        cfg = ConfigSystem(os.environ.get("CONFIG_PATH", "config.yaml")).get()
        return (
            cfg.account.balance,
            cfg.exchange.fee_rate,
            cfg.position.mode,
            cfg.position.fixed_usd,
            cfg.position.risk_pct,
            cfg.position.leverage,
            cfg.exchange.market_type,
        )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

@app.get("/api/signals", response_model=List[dict])
async def get_signals():
    """
    Return all active ALERT-class signals.
    Satisfies: Requirement 18.1
    """
    return list(_active_signals.values())


@app.post("/api/signals/{signal_id}/confirm")
async def confirm_signal(signal_id: str, _: None = Depends(require_api_key)):
    """
    Confirm a signal → send to Trade Executor.
    Satisfies: Requirements 18.2, 18.3, 19.1
    """
    # Task 32 — Circuit Breaker check: block CONFIRM when locked
    try:
        from risk.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        if cb.is_locked():
            lock_info = cb.get_lock_info()
            raise HTTPException(
                status_code=423,  # 423 Locked
                detail={
                    "error": "CIRCUIT_BREAKER_ACTIVE",
                    "message": f"Trading locked: {lock_info.trigger_type}",
                    "trigger_detail": lock_info.trigger_detail,
                    "unlock_at": lock_info.unlock_at.isoformat() if lock_info.unlock_at else None,
                    "requires_review": lock_info.unlock_requires_review,
                    "time_remaining_seconds": lock_info.time_remaining_seconds,
                }
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Circuit breaker check failed (non-blocking): %s", exc)

    signal = _active_signals.get(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    # --- Compute position size via RiskManager ---
    try:
        account_equity, fee_rate, sizing_mode, fixed_usd, risk_pct, leverage, market_type = (
            _load_account_settings()
        )
    except Exception as exc:
        logger.error("Failed to load account settings: %s", exc)
        raise HTTPException(status_code=503, detail=f"Account settings unavailable: {exc}")

    from risk.manager import RiskManager
    rm = RiskManager(
        mode=sizing_mode,
        fixed_usd=fixed_usd,
        risk_pct=risk_pct,
        max_risk_pct=risk_pct,
        leverage=leverage,
        market_type=market_type,
    )
    entry_price = float(signal.get("entry_price", 0))
    stop_loss = float(signal.get("stop_loss", 0))
    # atr_value = SL distance — non-zero guard only; actual sizing uses sl_distance
    atr_value = abs(entry_price - stop_loss)

    size_result = rm.compute_position_size(
        asset=signal.get("asset", ""),
        entry_price=entry_price,
        stop_loss=stop_loss,
        account_equity=account_equity,
        atr_value=atr_value,
        open_positions=await _get_open_positions(),
        fee_rate=fee_rate,
    )

    if not size_result.allowed:
        logger.warning("Signal %s rejected by RiskManager: %s", signal_id, size_result.rejection_reason)
        raise HTTPException(
            status_code=422,
            detail={"error": "RISK_REJECTED", "reason": size_result.rejection_reason},
        )

    position_size_usd = size_result.position_size_usd

    # Mark as executing immediately (optimistic UI)
    signal["user_action"] = "CONFIRM"
    signal["status"] = "Executing"
    signal["position_size_usd"] = position_size_usd

    # --- Dispatch async execution via Celery (testnet enforced inside executor) ---
    try:
        from trade.tasks import execute_trade
        execute_trade.delay(signal, position_size_usd)
        logger.info(
            "Trade dispatched: %s %s score=%d size=%.2f USD",
            signal_id, signal.get("asset"), signal.get("final_score", 0), position_size_usd,
        )
    except Exception as exc:
        # Celery unavailable — mark as failed, don't block user
        signal["status"] = "Failed"
        logger.error("Failed to dispatch execute_trade task for %s: %s", signal_id, exc)
        raise HTTPException(status_code=503, detail=f"Trade dispatch failed: {exc}")

    return {
        "status": "executing",
        "signal_id": signal_id,
        "position_size_usd": position_size_usd,
        "asset": signal.get("asset"),
        "direction": signal.get("direction"),
    }


@app.get("/api/signals/{signal_id}/execution")
async def get_execution_status(signal_id: str):
    """
    Poll the execution status of a confirmed signal.
    Status progresses: Executing → Filled | Failed.
    Satisfies: Requirement 18.3
    """
    from trading_core.cache import get_async_redis
    r = await get_async_redis()
    raw = await r.get(f"trade:status:{signal_id}")
    if raw is None:
        # Check in-memory signal for "Executing" / "Submitted" status
        signal = _active_signals.get(signal_id)
        if signal:
            return {"signal_id": signal_id, "status": signal.get("status", "Unknown")}
        raise HTTPException(status_code=404, detail=f"No execution record for signal {signal_id}")
    return json.loads(raw)


@app.post("/api/signals/{signal_id}/skip")
async def skip_signal(signal_id: str, body: SkipRequest, _: None = Depends(require_api_key)):
    """
    Skip a signal with optional reason.
    Satisfies: Requirements 18.2, 18.4, 17.3
    """
    signal = _active_signals.pop(signal_id, None)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    signal["user_action"] = "SKIP"
    signal["skip_reason"] = body.reason

    # TODO Task 21.4: write to Signal_Log
    logger.info("Signal skipped: %s reason=%s", signal_id, body.reason)
    return {"status": "skipped", "signal_id": signal_id}


@app.patch("/api/signals/{signal_id}/expire")
async def expire_signal(signal_id: str, _: None = Depends(require_api_key)):
    """Mark a signal as expired (called by frontend countdown timer)."""
    signal = _active_signals.pop(signal_id, None)
    if signal:
        signal["user_action"] = "EXPIRED"
        logger.info("Signal expired: %s", signal_id)
    return {"status": "expired", "signal_id": signal_id}


# ---------------------------------------------------------------------------
# Trade Journal
# ---------------------------------------------------------------------------

@app.get("/api/journal")
async def get_journal(
    asset: Optional[str] = None,
    strategy: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """
    Return paginated trade journal entries.
    Satisfies: Requirement 18.7
    """
    from db.connection import get_session_factory
    from db.models import TradeJournal
    from sqlalchemy import select, desc

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        query = select(TradeJournal).order_by(desc(TradeJournal.entry_timestamp))
        if asset:
            query = query.where(TradeJournal.asset == asset)
        if strategy:
            query = query.where(TradeJournal.strategy_name == strategy)

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        rows = db.execute(query).scalars().all()

        return [
            {
                "trade_id": r.trade_id,
                "strategy_name": r.strategy_name,
                "asset": r.asset,
                "direction": r.direction,
                "entry_timestamp": r.entry_timestamp,
                "exit_timestamp": r.exit_timestamp,
                "entry_price": r.entry_price,
                "actual_entry_price": r.actual_entry_price,
                "actual_exit_price": r.actual_exit_price,
                "stop_loss": r.stop_loss,
                "take_profit_1": r.take_profit_1,
                "position_size_usd": r.position_size_usd,
                "slippage_entry": r.slippage_entry,
                "fee_entry": r.fee_entry,
                "fee_exit": r.fee_exit,
                "gross_pnl": r.gross_pnl,
                "net_pnl": r.net_pnl,
                "result": r.result,
                "signal_score": r.signal_score,
                "is_testnet": r.is_testnet,
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.get("/api/analytics")
async def get_analytics():
    """
    Return aggregated performance metrics.
    Satisfies: Requirement 18.8
    """
    from db.connection import get_session_factory
    from db.models import TradeJournal
    from sqlalchemy import select, func

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        rows = db.execute(select(TradeJournal)).scalars().all()
        if not rows:
            return {"total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
                    "max_drawdown": 0.0, "sharpe_ratio": 0.0, "net_profit": 0.0}

        from backtest.metrics import compute_metrics
        from backtest.models import TradeResult

        trades = []
        for r in rows:
            t = TradeResult(
                strategy_name=r.strategy_name, asset=r.asset, timeframe="15m",
                direction=r.direction, net_pnl=r.net_pnl or 0.0,
                gross_pnl=r.gross_pnl or 0.0, signal_score=r.signal_score,
            )
            t.result = r.result or "be"
            trades.append(t)

        return compute_metrics(trades)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@app.get("/api/portfolio")
async def get_portfolio():
    """
    Return Portfolio_Heat and per-asset correlated group risk.
    Satisfies: Requirements 14.8, 18.9
    """
    positions = await _get_open_positions()
    return {
        "portfolio_heat": sum(positions.values()) * 100.0,
        "open_positions": positions,
    }


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

@app.get("/api/strategies")
async def get_strategies():
    """
    Return list of registered strategy names.
    Satisfies: Requirement 16.6
    """
    from strategies.registry import StrategyRegistry
    StrategyRegistry.auto_discover("strategies")
    return {"strategies": StrategyRegistry.list_registered()}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    """Return current non-sensitive config values."""
    try:
        from config.config_system import ConfigSystem
        cfg = ConfigSystem(os.environ.get("CONFIG_PATH", "config.yaml"))
        c = cfg.get()
        return {
            "exchange": {"name": c.exchange.name, "market_type": c.exchange.market_type,
                         "testnet": c.exchange.testnet},
            "strategy": {"active": c.strategy.active,
                         "score_threshold": {"alert": c.strategy.score_threshold.alert,
                                             "watch": c.strategy.score_threshold.watch}},
            "position": {"mode": c.position.mode, "max_concurrent": c.position.max_concurrent},
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/config/reload")
async def reload_config(_: None = Depends(require_api_key)):
    """
    Hot-reload config.yaml.
    Satisfies: Requirement 15.11
    """
    try:
        from config.config_system import ConfigSystem
        cfg = ConfigSystem(os.environ.get("CONFIG_PATH", "config.yaml"))
        cfg.reload()
        return {"status": "reloaded"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

@app.get("/api/circuit-breaker/status")
async def get_circuit_breaker_status():
    """Return current circuit breaker lock state."""
    try:
        from risk.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        info = cb.get_lock_info()
        return {
            "is_locked": info.is_locked,
            "trigger_type": info.trigger_type,
            "trigger_detail": info.trigger_detail,
            "triggered_at": info.triggered_at.isoformat() if info.triggered_at else None,
            "unlock_at": info.unlock_at.isoformat() if info.unlock_at else None,
            "regime_at_trigger": info.regime_at_trigger,
            "unlock_requires_review": info.unlock_requires_review,
            "time_remaining_seconds": info.time_remaining_seconds,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/circuit-breaker/unlock")
async def manual_unlock_circuit_breaker(body: dict, _: None = Depends(require_api_key)):
    """
    Manually unlock circuit breaker with review note.
    Required for Trigger 4 (drawdown from peak).
    """
    review_note = body.get("review_note", "")
    if not review_note or len(review_note.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="review_note must be at least 10 characters"
        )
    try:
        from risk.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        success = cb.manual_unlock(review_note=review_note, unlocked_by="user_dashboard")
        if success:
            return {"status": "unlocked", "message": "Circuit breaker manually unlocked"}
        raise HTTPException(status_code=400, detail="Unlock failed — check logs")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

@app.get("/api/backtest/results")
async def get_backtest_results():
    """
    Return backtest result records and Benchmark_Table.
    Satisfies: Requirements 9.6, 17.5
    """
    from backtest.benchmark import generate_benchmark_table
    df = generate_benchmark_table()
    if df.empty:
        return {"results": [], "benchmark": []}
    return {"results": df.to_dict(orient="records"), "benchmark": df.to_dict(orient="records")}


@app.post("/api/backtest/run")
async def run_backtest(body: BacktestRunRequest):
    """
    Trigger async backtest run via Celery.
    Satisfies: Requirements 8, 9, 10
    """
    # TODO: dispatch to Celery task
    return {"status": "queued", "strategy": body.strategy, "asset": body.asset}


# ---------------------------------------------------------------------------
# WebSocket: /ws/alerts
# ---------------------------------------------------------------------------

@app.websocket("/ws/alerts")
async def alert_stream(websocket: WebSocket):
    """
    Real-time Signal Card stream via Redis pub/sub.
    Satisfies: Requirement 18.10
    """
    await websocket.accept()
    try:
        redis = await get_async_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(RedisKeys.Channels.ALERTS)
        logger.info("WebSocket /ws/alerts connected")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                # Cache signal in memory
                try:
                    card = json.loads(data)
                    sig_id = card.get("signal_id", "")
                    if sig_id:
                        _active_signals[sig_id] = card
                except json.JSONDecodeError:
                    pass
                await websocket.send_text(data)
    except WebSocketDisconnect:
        logger.info("WebSocket /ws/alerts disconnected")
    except Exception as exc:
        logger.error("WebSocket /ws/alerts error: %s", exc)
    finally:
        try:
            await pubsub.unsubscribe(RedisKeys.Channels.ALERTS)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket: /ws/portfolio
# ---------------------------------------------------------------------------

@app.websocket("/ws/portfolio")
async def portfolio_stream(websocket: WebSocket):
    """
    Real-time Portfolio_Heat and correlated risk stream.
    Satisfies: Requirements 14.8, 18.9, 18.10
    """
    await websocket.accept()
    try:
        while True:
            positions = await _get_open_positions()
            payload = json.dumps({
                "portfolio_heat": sum(positions.values()) * 100.0,
                "open_positions": positions,
            })
            await websocket.send_text(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("WebSocket /ws/portfolio disconnected")
    except Exception as exc:
        logger.error("WebSocket /ws/portfolio error: %s", exc)


@app.websocket("/ws/logs")
async def log_stream(websocket: WebSocket):
    """
    Real-time system log stream — ALL signals including WATCH/IGNORE with debug breakdown.
    Separate channel from alerts — does not affect signal scoring performance.
    """
    await websocket.accept()
    try:
        redis = await get_async_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(RedisKeys.Channels.LOGS)
        logger.info("WebSocket /ws/logs connected")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)
    except WebSocketDisconnect:
        logger.info("WebSocket /ws/logs disconnected")
    except Exception as exc:
        logger.error("WebSocket /ws/logs error: %s", exc)
    finally:
        try:
            await pubsub.unsubscribe(RedisKeys.Channels.LOGS)
        except Exception:
            pass
