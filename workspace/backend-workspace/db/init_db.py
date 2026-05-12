"""
Database Initializer
=====================
Applies 001_initial_schema.sql to the configured SQL Server database.
Safe to run multiple times — uses IF NOT EXISTS guards.

Usage:
    python db/init_db.py

Satisfies: Requirements 17.7, 19.5
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from db.connection import get_engine, get_database_url

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _split_sql_statements(sql: str) -> list[str]:
    """
    Split T-SQL script into individual statements.
    Each statement is executed as a separate batch (no GO separator needed).
    Strips line comments.
    """
    lines = []
    for line in sql.splitlines():
        comment_pos = line.find("--")
        if comment_pos >= 0:
            line = line[:comment_pos]
        lines.append(line)
    clean_sql = "\n".join(lines)

    # Split on blank lines between statements (T-SQL style)
    # Each IF OBJECT_ID / IF NOT EXISTS block is one statement
    statements = []
    current = []
    for line in clean_sql.splitlines():
        stripped = line.strip()
        if stripped:
            current.append(line)
        else:
            if current:
                stmt = "\n".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)
    return statements


def apply_migration(engine, sql_path: Path) -> None:
    """Execute a SQL migration file against the engine."""
    raw_sql = sql_path.read_text(encoding="utf-8")
    statements = _split_sql_statements(raw_sql)

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    logger.info("Applied migration: %s", sql_path.name)


def init_db() -> None:
    """Apply all pending migrations in order."""
    url = get_database_url()
    safe_url = url.split("@")[-1] if "@" in url else url
    logger.info("Initializing database: %s", safe_url)

    engine = get_engine()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    if not migration_files:
        logger.warning("No migration files found in %s", MIGRATIONS_DIR)
        return

    for migration_file in migration_files:
        apply_migration(engine, migration_file)

    logger.info("Database initialization complete. %d migration(s) applied.", len(migration_files))


if __name__ == "__main__":
    init_db()
