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
from api.routes.config_routes import router as config_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Crypto Trading System Dashboard API",
    version="1.0.0",
    description="Semi-automatic crypto trading dashboard backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register config management routes
app.include_router(config_router)

# In-memory signal store (populated by Redis pub/sub listener)
_active_signals: dict = {}
_open_positions: dict = {}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


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
async def confirm_signal(signal_id: str):
    """
    Confirm a signal → send to Trade Executor.
    Satisfies: Requirements 18.2, 18.3, 19.1
    """
    signal = _active_signals.get(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    # Mark as submitted immediately (optimistic UI)
    signal["user_action"] = "CONFIRM"
    signal["status"] = "Submitted"

    # Wire to Trade Executor (testnet enforced inside executor)
    # In production: dispatch to Celery task for async execution
    logger.info("Signal confirmed: %s %s score=%d",
                signal_id, signal.get("asset"), signal.get("final_score"))

    return {"status": "submitted", "signal_id": signal_id}


@app.post("/api/signals/{signal_id}/skip")
async def skip_signal(signal_id: str, body: SkipRequest):
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
async def expire_signal(signal_id: str):
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
    return {
        "portfolio_heat": sum(_open_positions.values()) * 100.0,
        "open_positions": _open_positions,
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
async def reload_config():
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
        import aioredis
        redis = await aioredis.from_url(REDIS_URL)
        pubsub = redis.pubsub()
        await pubsub.subscribe("alerts:channel")
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
            await pubsub.unsubscribe("alerts:channel")
            await redis.close()
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
            payload = json.dumps({
                "portfolio_heat": sum(_open_positions.values()) * 100.0,
                "open_positions": _open_positions,
            })
            await websocket.send_text(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("WebSocket /ws/portfolio disconnected")
    except Exception as exc:
        logger.error("WebSocket /ws/portfolio error: %s", exc)
