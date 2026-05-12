"""
Crypto Trading System — Entry Point
====================================
Orchestrates all data pipeline services.

Services:
  OHLCVService     — polls candle data → Redis
  OrderBookService — polls order book → Redis
  DeltaService     — polls trade tape → Redis (cumulative delta)
  ScoringService   — listens for candle_close → runs scoring pipeline

All market data is PUBLIC — no API key required for analysis.
API key only needed for placing orders (Trade Executor).

Usage:
    python main.py                              # start data pipeline
    uvicorn api.main:app --reload --port 8000   # start API server (separate terminal)
"""

import asyncio
import logging
import os
import sys

from trading_core.utils import setup_logging as _setup_logging

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    _setup_logging(level)


def load_config():
    from config.config_system import ConfigSystem, ConfigValidationError
    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    try:
        return ConfigSystem(config_path)
    except ConfigValidationError as exc:
        print(f"Config error: {exc}")
        sys.exit(1)
    except FileNotFoundError:
        print("config.yaml not found — copy config.example.yaml to config.yaml")
        sys.exit(1)


def load_exchange_and_assets(cfg):
    """Load exchange ID and asset list from DB (fallback to config.yaml)."""
    try:
        from db.connection import get_session_factory
        from config.config_service import get_active_exchange_settings
        db = get_session_factory()()
        settings = get_active_exchange_settings(db)
        db.close()
        exchange_id = settings.get("exchange_id", cfg.get().exchange.name)
        assets = [a["symbol"] for a in settings.get("assets", []) if a.get("enabled", True)]
    except Exception:
        exchange_id = cfg.get().exchange.name
        assets = [a.symbol for a in cfg.get().assets if a.enabled]

    return exchange_id, assets or ["BTC/USDT", "ETH/USDT"]


async def main():
    cfg = load_config()
    setup_logging(cfg.get().logging.level)

    logger.info("=" * 60)
    logger.info("Crypto Trading System — Data Pipeline")
    logger.info("=" * 60)

    exchange_id, assets = load_exchange_and_assets(cfg)

    trigger_tf = cfg.get().strategy.timeframes.trigger
    context_tf = cfg.get().strategy.timeframes.context
    timeframes = list(dict.fromkeys([trigger_tf, context_tf]))

    logger.info("Exchange:   %s (public data, no API key needed)", exchange_id)
    logger.info("Assets:     %s", assets)
    logger.info("Timeframes: %s", timeframes)
    logger.info("-" * 60)

    # Import services
    from data.ohlcv_service import OHLCVService
    from data.orderbook_service import OrderBookService
    from data.delta_service import DeltaService
    from engine.scoring_service import ScoringService
    from trading_core.cache import get_redis

    raw_cfg = cfg.get()

    # --- Mock Exchange injection (Algorithm Validation Phase) ---
    mock_cfg = getattr(raw_cfg, "mock_exchange", None)
    mock_enabled = getattr(mock_cfg, "enabled", False) if mock_cfg else False
    if mock_enabled:
        from exchange.mock_http_client import MockExchangeHttpClient
        mock_url = getattr(mock_cfg, "url", "http://localhost:8001")
        mock_timeout = getattr(mock_cfg, "timeout_seconds", 5)
        exchange = MockExchangeHttpClient(base_url=mock_url, timeout=float(mock_timeout))
        logger.info("Mock exchange enabled — routing orders to %s", mock_url)
    else:
        exchange = None  # TradeExecutor not used without mock or live config

    # --- Audit Client injection ---
    audit_cfg = getattr(raw_cfg, "audit", None)
    audit_enabled = getattr(audit_cfg, "enabled", False) if audit_cfg else False
    audit_client = None
    if audit_enabled:
        from audit.client import AuditClient
        audit_client = AuditClient(redis_client=get_redis(), enabled=True)
        logger.info("Audit enabled — emitting snapshots to audit:pending_snapshots")

    # Instantiate services
    ohlcv_svc = OHLCVService(exchange_id, assets, timeframes)
    ob_svc = OrderBookService(exchange_id, assets)
    delta_svc = DeltaService(exchange_id, assets)
    scoring_svc = ScoringService(config=cfg, audit_client=audit_client)

    logger.info("Starting all services...")
    await asyncio.gather(
        ohlcv_svc.start(),
        ob_svc.start(),
        delta_svc.start(),
        scoring_svc.start(),
    )


# FastAPI app — importable by uvicorn
from api.main import app  # noqa: F401

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
