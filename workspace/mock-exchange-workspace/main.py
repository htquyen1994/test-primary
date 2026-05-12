"""
mock-exchange-workspace — Entry Point
=======================================
Starts all services:
  1. Load config.yaml
  2. Init DB (create_all tables)
  3. Init mock_account (id=1) if not exists
  4. Create MockExchange, SignalAuditor, TradeAuditor, etc.
  5. Start backfill (SignalAuditor.backfill_pending())
  6. Start CandleFeed as asyncio task
  7. Start AuditConsumer as asyncio task
  8. Start TickerFeed as asyncio task
  9. Start uvicorn (FastAPI) — run alongside
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# -------------------------------------------------------------------------
# trading-core must be on sys.path before any other local imports
# -------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "..", "trading-core"))

# -------------------------------------------------------------------------
# Now local imports are safe
# -------------------------------------------------------------------------
import yaml

from db.database import configure_database, init_db
from db.models import MockAccount
from exchange.mock_exchange import MockExchange
from exchange.order_manager import OrderManager
from exchange.position_tracker import PositionTracker
from price_feed.candle_feed import CandleFeed
from price_feed.ticker_feed import TickerFeed
from audit.consumer import AuditConsumer
from audit.signal_auditor import SignalAuditor
from audit.trade_auditor import TradeAuditor
from audit.no_signal_auditor import NoSignalAuditor
from audit.analysis_engine import AnalysisEngine
from api.websocket_manager import ConnectionManager
from api.deps import set_dependencies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config loader
# -------------------------------------------------------------------------

def load_config(path: str = None) -> dict:
    config_path = path or os.path.join(_ROOT, "config.yaml")
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    logger.info("Config loaded from %s", config_path)
    return cfg


# -------------------------------------------------------------------------
# FastAPI app factory
# -------------------------------------------------------------------------

def create_app():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from api.routes.exchange import router as exchange_router
    from api.routes.audit import router as audit_router
    from api.routes.analytics import router as analytics_router
    from api.routes.websocket import router as websocket_router

    app = FastAPI(
        title="Mock Exchange Service",
        description="Algorithm Validation — Mock exchange + audit system",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(exchange_router)
    app.include_router(audit_router)
    app.include_router(analytics_router)
    app.include_router(websocket_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "mock-exchange-workspace"}

    return app


# -------------------------------------------------------------------------
# DB initializer
# -------------------------------------------------------------------------

def init_mock_account(db_factory, initial_balance: float) -> None:
    """Create mock_account row (id=1) if it doesn't exist."""
    db = db_factory()
    try:
        account = db.query(MockAccount).filter(MockAccount.id == 1).first()
        if account is None:
            account = MockAccount(
                id=1,
                balance_usd=initial_balance,
                equity_usd=initial_balance,
                used_margin=0.0,
                total_realized_pnl=0.0,
                total_fees_paid=0.0,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(account)
            db.commit()
            logger.info(
                "Mock account initialized with balance=%.2f USD", initial_balance
            )
        else:
            logger.info(
                "Mock account already exists: balance=%.2f USD", account.balance_usd
            )
    except Exception as exc:
        db.rollback()
        logger.error("Failed to init mock account: %s", exc)
    finally:
        db.close()


# -------------------------------------------------------------------------
# Main coroutine
# -------------------------------------------------------------------------

async def main():
    # 1. Load config
    cfg = load_config()
    service_cfg = cfg.get("service", {})
    db_cfg = cfg.get("database", {})
    redis_cfg = cfg.get("redis", {})
    exchange_cfg = cfg.get("exchange", {})
    account_cfg = cfg.get("mock_account", {})
    feed_cfg = cfg.get("price_feed", {})

    host = service_cfg.get("host", "0.0.0.0")
    port = service_cfg.get("port", 8001)
    db_url = db_cfg.get("url", "sqlite:///./mock_exchange.db")
    redis_url = redis_cfg.get("url", "redis://localhost:6379/0")
    exchange_id = exchange_cfg.get("id", "binance")
    fee_rate = exchange_cfg.get("fee_rate", 0.001)
    initial_balance = account_cfg.get("initial_balance_usd", 10000.0)
    ticker_poll_interval = feed_cfg.get("ticker_poll_interval_seconds", 10)

    # 2. Init DB
    # Resolve relative SQLite path relative to workspace dir
    if db_url.startswith("sqlite:///./"):
        db_file = db_url[len("sqlite:///./"):]
        abs_db_path = os.path.join(_ROOT, db_file)
        db_url = f"sqlite:///{abs_db_path}"

    configure_database(db_url)
    init_db()

    # DB session factory
    from db.database import SessionLocal
    db_factory = SessionLocal

    # 3. Init mock_account
    init_mock_account(db_factory, initial_balance)

    # 4. Create Redis client
    from trading_core.cache.redis_client import get_redis
    redis_client = get_redis(redis_url)

    # 5. Create shared components
    ws_manager = ConnectionManager()
    order_manager = OrderManager(fee_rate=fee_rate)
    mock_exchange = MockExchange(
        db_factory=db_factory,
        order_manager=order_manager,
        exchange_id=exchange_id,
    )
    position_tracker = PositionTracker(
        order_manager=order_manager,
        db_factory=db_factory,
        redis_client=redis_client,
    )
    signal_auditor = SignalAuditor(
        db_factory=db_factory,
        exchange_id=exchange_id,
        ws_manager=ws_manager,
    )
    trade_auditor = TradeAuditor(
        db_factory=db_factory,
        redis_client=redis_client,
        ws_manager=ws_manager,
    )
    no_signal_auditor = NoSignalAuditor(db_factory=db_factory)
    analysis_engine = AnalysisEngine(db_factory=db_factory)

    # 6. Wire FastAPI dependencies
    set_dependencies(
        mock_exchange=mock_exchange,
        signal_auditor=signal_auditor,
        trade_auditor=trade_auditor,
        no_signal_auditor=no_signal_auditor,
        analysis_engine=analysis_engine,
        ws_manager=ws_manager,
    )

    # 7. Start APScheduler
    signal_auditor.start_scheduler()

    # 8. Backfill pending T* windows
    logger.info("Running startup backfill...")
    try:
        await signal_auditor.backfill_pending()
    except Exception as exc:
        logger.error("Backfill failed (non-blocking): %s", exc)

    # 9. Process any completed NO_SIGNAL records
    try:
        await no_signal_auditor.process_completed_no_signals()
    except Exception as exc:
        logger.error("NoSignalAuditor startup processing failed: %s", exc)

    # 10. Create background feeds
    candle_feed = CandleFeed(
        redis_client=redis_client,
        position_tracker=position_tracker,
        db_factory=db_factory,
    )
    audit_consumer = AuditConsumer(
        redis_client=redis_client,
        signal_auditor=signal_auditor,
        trade_auditor=trade_auditor,
    )
    ticker_feed = TickerFeed(
        db_factory=db_factory,
        exchange_id=exchange_id,
        poll_interval=ticker_poll_interval,
        ws_manager=ws_manager,
        redis_client=redis_client,
    )

    # 11. Start background tasks
    candle_task = asyncio.create_task(candle_feed.run(), name="candle_feed")
    audit_task = asyncio.create_task(audit_consumer.run(), name="audit_consumer")
    ticker_task = asyncio.create_task(ticker_feed.run(), name="ticker_feed")

    # Periodic NoSignal processing (every 5 minutes)
    async def _periodic_no_signal():
        while True:
            await asyncio.sleep(300)
            try:
                await no_signal_auditor.process_completed_no_signals()
            except Exception as exc:
                logger.error("Periodic NoSignalAuditor error: %s", exc)

    no_signal_task = asyncio.create_task(_periodic_no_signal(), name="no_signal_periodic")

    # 12. Start FastAPI/uvicorn
    import uvicorn
    app = create_app()
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        loop="none",  # use existing asyncio loop
    )
    server = uvicorn.Server(config)

    logger.info("Starting mock-exchange-workspace on %s:%d", host, port)

    try:
        await server.serve()
    finally:
        # Graceful shutdown
        logger.info("Shutting down background tasks...")
        candle_feed.stop()
        audit_consumer.stop()
        ticker_feed.stop()
        signal_auditor.stop_scheduler()

        for task in [candle_task, audit_task, ticker_task, no_signal_task]:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("mock-exchange-workspace shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
