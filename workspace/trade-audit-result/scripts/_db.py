"""
Shared DB connection helper for audit scripts.
Always uses SQL Server — never SQLite.
"""
import os
import sys
from pathlib import Path

# Load .env from backend-workspace
_env_file = Path(__file__).parent.parent.parent / "backend-workspace" / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Require SQL Server — fail fast if not configured
DB_URL = os.environ.get("DATABASE_URL", "")
if not DB_URL or "sqlite" in DB_URL.lower():
    # Force SQL Server
    DB_URL = (
        "mssql+pyodbc://admin:Quyen%40135@localhost:1433/trading"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    os.environ["DATABASE_URL"] = DB_URL

if "sqlite" in DB_URL.lower():
    print("ERROR: SQLite is not supported for audit. Set DATABASE_URL to SQL Server.")
    sys.exit(1)

# Add backend-workspace and trading-core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend-workspace"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trading-core"))

from sqlalchemy import create_engine

def get_engine():
    return create_engine(DB_URL, fast_executemany=True)

def get_connection():
    return get_engine().connect()
