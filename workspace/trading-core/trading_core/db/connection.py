"""
Database Connection — SQLAlchemy Engine Factory
=================================================
Singleton engine factory. All services use get_session_factory() —
never create engines directly.

Supported backends (controlled by DATABASE_URL env var):
  SQL Server:  mssql+pyodbc://user:pass@host:port/db?driver=...
  SQLite:      sqlite:///./trading.db  (local dev / tests)
  PostgreSQL:  postgresql://user:pass@host:5432/db

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
from functools import lru_cache
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

_DEFAULT_DATABASE_URL = "sqlite:///./trading.db"


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
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)


@lru_cache(maxsize=1)
def get_engine():
    """
    Create and cache the SQLAlchemy engine.
    Detects dialect from DATABASE_URL and applies appropriate settings.
    """
    url = get_database_url()
    safe_url = url.split("@")[-1] if "@" in url else url
    logger.info("Database engine: %s", safe_url)

    connect_args = {}
    engine_kwargs: dict = {}

    if "mssql" in url:
        engine_kwargs["fast_executemany"] = True
    elif "sqlite" in url:
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        echo=False,
        **engine_kwargs,
    )

    if "sqlite" in url:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

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
