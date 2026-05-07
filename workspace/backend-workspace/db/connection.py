"""
Database Connection
====================
SQLAlchemy engine factory.
Reads DATABASE_URL from environment (or .env file).

Supported engines:
  - SQL Server:  mssql+pyodbc://user:pass@host:port/db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
  - SQLite:      sqlite:///./trading.db  (fallback for tests)
  - PostgreSQL:  postgresql://user:pass@host:5432/db

Satisfies: Requirements 17.7, 19.5
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

# Load .env file if present (without requiring python-dotenv as hard dependency)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Default fallback — SQLite for tests / CI environments without SQL Server
DEFAULT_DATABASE_URL = "sqlite:///./trading.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


@lru_cache(maxsize=1)
def get_engine():
    """
    Create and cache the SQLAlchemy engine.
    Detects the dialect from DATABASE_URL and applies appropriate settings.
    """
    url = get_database_url()

    # Safe logging — hide password
    safe_url = url.split("@")[-1] if "@" in url else url
    logger.info("Database engine: %s", safe_url)

    connect_args = {}
    engine_kwargs: dict = {}

    if "mssql" in url:
        # SQL Server — fast_executemany speeds up bulk inserts significantly
        engine_kwargs["fast_executemany"] = True

    elif "sqlite" in url:
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        echo=False,
        **engine_kwargs,
    )

    # SQLite-specific pragmas (only for test/fallback)
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


def get_session() -> Session:
    """
    Dependency-injection helper for FastAPI routes.

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


# ---------------------------------------------------------------------------
# Base class for ORM models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass
