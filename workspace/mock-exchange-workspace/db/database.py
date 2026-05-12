"""
Database setup — SQLAlchemy 2.0 synchronous engine + session factory.
DB file: mock_exchange.db in the workspace directory.
"""

from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve DB URL from config or default
# ---------------------------------------------------------------------------

_DEFAULT_DB_URL = "sqlite:///./mock_exchange.db"
_db_url: str = _DEFAULT_DB_URL


def configure_database(url: str) -> None:
    """Called from main.py with URL from config.yaml."""
    global _db_url, engine, SessionLocal
    _db_url = url
    engine = _make_engine(url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    logger.info("Database configured: %s", url)


def _make_engine(url: str):
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    eng = create_engine(url, echo=False, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_con, _con_record):
            cursor = dbapi_con.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return eng


# Initial engine (overridden by configure_database)
engine = _make_engine(_DEFAULT_DB_URL)


class Base(DeclarativeBase):
    pass


SessionLocal: sessionmaker = sessionmaker(
    bind=engine, autocommit=False, autoflush=False
)


def init_db() -> None:
    """Create all tables if they don't exist."""
    from db import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a Session and close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
