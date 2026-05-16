"""
Database Connection — SQLAlchemy Engine Factory
=================================================
Singleton engine factory. All services use get_session_factory() —
never create engines directly.

Supported backend: SQL Server (production)
  mssql+pyodbc://user:pass@host:port/db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

DATABASE_URL must be set in .env — no SQLite fallback.

Usage:
    from trading_core.db import get_session_factory, get_session

    # In a service:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        result = db.execute(...)
    finally:
        db.close()

    # In FastAPI (dependency injection):
    @app.get("/example")
    def example(db: Session = Depends(get_session)):
        ...
"""

from __future__ import annotations

import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Load .env file from common locations without requiring python-dotenv."""
    search_paths = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent.parent / "backend-workspace" / ".env",
    ]
    for env_file in search_paths:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
            break


_load_env_file()


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it to workspace/backend-workspace/.env\n"
            "Example: DATABASE_URL=mssql+pyodbc://admin:pass@localhost:1433/trading"
            "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        )
    if "sqlite" in url.lower():
        raise RuntimeError(
            "SQLite is not supported. Set DATABASE_URL to SQL Server.\n"
            "Example: DATABASE_URL=mssql+pyodbc://admin:pass@localhost:1433/trading"
            "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        )
    return url


@lru_cache(maxsize=1)
def get_engine():
    """
    Create and cache the SQLAlchemy engine for SQL Server.
    Raises RuntimeError if DATABASE_URL is not set or points to SQLite.
    """
    url = get_database_url()
    safe_url = url.split("@")[-1] if "@" in url else url
    logger.info("Database engine: %s", safe_url)

    engine = create_engine(
        url,
        fast_executemany=True,
        echo=False,
    )
    return engine


def get_session_factory() -> sessionmaker:
    """Return a session factory bound to the cached engine."""
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency injection helper.

    Usage:
        @app.get("/example")
        def example(db: Session = Depends(get_session)):
            ...
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    """Base class for all ORM models across all services."""
    pass
