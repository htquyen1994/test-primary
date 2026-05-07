"""
Crypto Trading System — Entry Point
====================================
Starts all services:
  1. Config System (load + validate config.yaml)
  2. Database (apply migrations if needed)
  3. Data Pipeline (WebSocket feeds → Redis)
  4. Celery workers (signal scoring, regime detection)
  5. FastAPI dashboard backend

Usage:
    # Start the FastAPI server only (development)
    uvicorn main:app --reload --port 8000

    # Start full system (data pipeline + API)
    python main.py
"""

import asyncio
import logging
import os
import sys

from config.config_system import ConfigSystem, ConfigValidationError

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config() -> ConfigSystem:
    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    try:
        cfg = ConfigSystem(config_path)
        logger.info("Config loaded from %s", config_path)
        return cfg
    except ConfigValidationError as exc:
        logger.error("Config validation failed: %s", exc)
        sys.exit(1)
    except FileNotFoundError:
        logger.error("config.yaml not found at %s — copy config.example.yaml to config.yaml", config_path)
        sys.exit(1)


async def main() -> None:
    cfg = load_config()
    setup_logging(cfg.get().logging.level)

    logger.info("Crypto Trading System starting...")
    logger.info("Exchange: %s | Market: %s | Testnet: %s",
                cfg.get().exchange.name,
                cfg.get().exchange.market_type,
                cfg.get().exchange.testnet)

    # TODO Phase 3: start WebSocket data pipeline
    # TODO Phase 3: start Celery workers via subprocess or supervisor
    # TODO Phase 6: start FastAPI server

    logger.info("System ready. Run 'uvicorn api.main:app --reload' for the dashboard.")


# FastAPI app — importable by uvicorn directly
try:
    from api.main import app  # noqa: F401  (populated in Task 21)
except ImportError:
    # api/main.py not yet created — placeholder for uvicorn import
    from fastapi import FastAPI
    app = FastAPI(title="Crypto Trading System", version="0.1.0-scaffold")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "phase": "scaffold"}


if __name__ == "__main__":
    asyncio.run(main())
