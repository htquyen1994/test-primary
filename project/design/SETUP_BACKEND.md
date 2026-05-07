# Backend Setup Guide — Crypto Trading System

> **OS:** Windows  
> **Python:** 3.10+  
> **Backend path:** `D:\workspace\trade-workspace\workspace\backend-workspace\`  
> **Database:** SQL Server (localhost:1433)  
> **Message Broker:** Redis (Docker — Redis only, no Celery in Docker)  
> **Celery:** Runs directly on Windows (faster, no Docker overhead)

---

## Architecture Overview

```
SQL Server (localhost:1433)   ← runs natively on Windows
Redis (Docker container)      ← only service in Docker
FastAPI (uvicorn)             ← runs directly on Windows
Celery Worker                 ← runs directly on Windows
Celery Beat                   ← runs directly on Windows
```

Docker is used **only for Redis**. Everything else runs natively on Windows for faster development and easier SQL Server connectivity.

---

## Prerequisites

### 1. Python 3.10

Download from https://www.python.org/downloads/  
**Important:** Use Python 3.10 specifically (not 3.11 or 3.12 — some packages have compatibility issues).

Verify:
```powershell
python --version
# Python 3.10.x
```

### 2. Docker Desktop (for Redis only)

Download from https://www.docker.com/products/docker-desktop/

After install:
- Open Docker Desktop
- Wait for the whale icon in taskbar to turn green (running)
- Settings → General → Enable "Use the WSL 2 based engine"

Verify:
```powershell
docker --version
```

### 3. SQL Server

Already installed at `localhost:1433`.

Verify SQL Server is running:
```powershell
netstat -an | findstr 1433
# Should show: TCP 0.0.0.0:1433 ... LISTENING
```

### 4. ODBC Driver 18 for SQL Server

Required for pyodbc connection.  
Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

Verify:
```python
import pyodbc
print([d for d in pyodbc.drivers() if 'SQL Server' in d])
# Should show: ['ODBC Driver 18 for SQL Server']
```

---

## Step 1 — Navigate to Backend

```powershell
cd D:\workspace\trade-workspace\workspace\backend-workspace
```

---

## Step 2 — Create Virtual Environment

```powershell
# Create venv with Python 3.10
python -m venv .venv

# Activate
.venv\Scripts\activate

# Verify — should show Python 3.10.x
python --version
```

---

## Step 3 — Install Dependencies

```powershell
# With venv activated
pip install -r requirements.txt
```

If you see errors, install in groups:
```powershell
# Core data packages
.venv\Scripts\pip install pandas==2.2.2 numpy==1.26.4

# Config & validation
.venv\Scripts\pip install pydantic==2.7.4 PyYAML==6.0.1 sqlalchemy==2.0.31 pyodbc==5.3.0

# Web framework
.venv\Scripts\pip install fastapi==0.111.1 "uvicorn[standard]==0.30.1"

# Celery + Redis
.venv\Scripts\pip install celery==5.3.6 redis==5.0.8

# Exchange
.venv\Scripts\pip install ccxt==4.3.89

# Testing
.venv\Scripts\pip install pytest==8.2.2 hypothesis==6.100.1 pytest-asyncio==0.23.7

# Others
.venv\Scripts\pip install watchdog==4.0.1 python-dotenv==1.0.1 httpx==0.27.0
```

> **Note:** `aioredis` may conflict — skip it if errors occur. `redis>=5.0` has built-in async support.

---

## Step 4 — Configure Environment Variables

```powershell
copy .env.example .env
```

Edit `.env`:
```env
# Database — SQL Server
DATABASE_URL=mssql+pyodbc://admin:YourPassword@localhost:1433/trading?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# Redis (local Docker container)
REDIS_URL=redis://localhost:6379/0

# Config file path
CONFIG_PATH=config.yaml

# Encryption key for API credentials stored in DB
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
CONFIG_ENCRYPTION_KEY=your_32_char_hex_key_here

# Exchange API keys (testnet only to start)
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_SECRET=your_testnet_secret
```

> **Security:** Never commit `.env` to version control.

---

## Step 5 — Configure config.yaml

```powershell
copy config.example.yaml config.yaml
```

Key settings in `config.yaml`:

```yaml
# config.yaml is the FALLBACK — DB settings take priority after first run
# Manage trading params and exchange settings via the UI at /config/trading and /config/exchange

strategy:
  active:
    - "smc_ob_fvg"   # Start with this strategy
    - "pinbar"

exchange:
  testnet: true      # KEEP TRUE until ready for live trading
```

---

## Step 6 — Start Redis (Docker)

Docker is used **only for Redis**. This is fast — no build required.

```powershell
# Start Redis container (pulls image automatically, ~5 seconds)
docker-compose up -d

# Verify Redis is running
docker ps
# Should show: trading_redis ... Up

# Test Redis connection
docker exec trading_redis redis-cli ping
# PONG
```

If Docker Desktop is not running, open it first and wait for the green icon.

---

## Step 7 — Initialize Database

Create the SQL Server tables:
```powershell
.venv\Scripts\python db/init_db.py
```

Expected output:
```
INFO | Initializing database: localhost:1433/trading
INFO | Applied migration: 001_initial_schema.sql
INFO | Applied migration: 002_config_tables.sql
INFO | Database initialization complete. 2 migration(s) applied.
```

Tables created (6 total):
- `signal_log` — every generated signal
- `trade_journal` — confirmed trades with PnL
- `backtest_results` — backtest run results
- `trading_params` — versioned trading parameters (Group A)
- `exchange_settings` — exchange credentials (Group B, encrypted)
- `exchange_assets` — per-asset config

---

## Step 8 — Run Tests

```powershell
# Run full test suite (319 tests)
.venv\Scripts\python -m pytest tests/ -v

# Quick run (unit tests only)
.venv\Scripts\python -m pytest tests/unit/ -q

# Property-based tests
.venv\Scripts\python -m pytest tests/properties/ -q
```

Expected: **319 passed, 0 failed**

> **Note:** Always use `.venv\Scripts\python -m pytest` (not `python -m pytest`) to avoid conflicts with globally installed packages like `web3`.

---

## Step 9 — Start FastAPI Backend

```powershell
# Development mode (auto-reload on file changes)
.venv\Scripts\uvicorn api.main:app --reload --port 8000
```

Verify:
```powershell
# Health check
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0"}
```

Open API docs: http://localhost:8000/docs

---

## Step 10 — Start Celery Workers (Windows Native)

Celery runs **directly on Windows** — no Docker needed. Open **two separate PowerShell terminals**:

### Terminal 1 — Celery Worker (signal scoring)

```powershell
cd D:\workspace\trade-workspace\workspace\backend-workspace
.venv\Scripts\activate

# Start worker — listens on 'scoring' and 'default' queues
.venv\Scripts\celery -A celery_app worker --loglevel=info -Q scoring,default --concurrency=2
```

Expected output:
```
[config]
.> app:         trading_system
.> transport:   redis://localhost:6379/0
.> results:     redis://localhost:6379/0
.> concurrency: 2 (prefork)

[queues]
.> scoring        exchange=celery(direct) key=scoring
.> default        exchange=celery(direct) key=default

[tasks]
  . engine.tasks.run_signal_scoring

[2026-05-07 ...] celery@HOSTNAME ready.
```

### Terminal 2 — Celery Beat (candle-close scheduler)

```powershell
cd D:\workspace\trade-workspace\workspace\backend-workspace
.venv\Scripts\activate

# Start beat scheduler
.venv\Scripts\celery -A celery_app beat --loglevel=info
```

Expected output:
```
celery beat v5.3.6 is starting.
LocalTime -> 2026-05-07 ...
Configuration ->
    . broker -> redis://localhost:6379/0
    . loader -> celery.loaders.app.AppLoader
    . scheduler -> celery.beat.PersistentScheduler
```

> **Why Windows native instead of Docker?**
> - No 20-minute Docker build time
> - Direct access to SQL Server at localhost
> - Faster code reload during development
> - No WSL2 overhead

---

## Step 11 — Configure Exchange Settings (First Time)

After the system is running, configure your exchange via the UI:

1. Open http://localhost:5173/config/exchange (after starting frontend)
2. Select your exchange (Binance, Bybit, Gate.io, etc.)
3. Enter API keys (stored encrypted in SQL Server)
4. Set position sizing mode and amount
5. Add assets to trade
6. Keep **Testnet: ON** until ready for live trading

Or via API directly:
```powershell
curl -X PUT http://localhost:8000/api/config/exchange `
  -H "Content-Type: application/json" `
  -d '{
    "exchange_id": "binance",
    "market_type": "futures",
    "testnet": true,
    "api_key": "your_testnet_key",
    "api_secret": "your_testnet_secret",
    "sizing_mode": "fixed_usd",
    "fixed_usd_per_trade": 100.0,
    "assets": [
      {"symbol": "BTC/USDT", "enabled": true, "leverage": 10},
      {"symbol": "ETH/USDT", "enabled": true, "leverage": 7}
    ]
  }'
```

---

## Full Startup Sequence

Every time you start the system, run in this order:

```powershell
# 1. Start Redis (Docker)
docker-compose up -d

# 2. Activate venv
.venv\Scripts\activate

# 3. Start FastAPI (Terminal 1)
.venv\Scripts\uvicorn api.main:app --reload --port 8000

# 4. Start Celery Worker (Terminal 2)
.venv\Scripts\celery -A celery_app worker --loglevel=info -Q scoring,default --concurrency=2

# 5. Start Celery Beat (Terminal 3)
.venv\Scripts\celery -A celery_app beat --loglevel=info

# 6. Start Frontend (Terminal 4 — see SETUP_FRONTEND.md)
# cd D:\workspace\trade-workspace\workspace\frontend-workspace
# npm run dev
```

---

## Shutdown

```powershell
# Stop Celery: Ctrl+C in each terminal

# Stop Redis
docker-compose down

# Deactivate venv
deactivate
```

---

## Common Issues & Solutions

### Issue: `ModuleNotFoundError: No module named 'numpy'`
```powershell
.venv\Scripts\activate
.venv\Scripts\pip install numpy pandas
```

### Issue: `pyodbc.InterfaceError: ('IM002', ...)`
ODBC Driver 18 not installed. Download from:
https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

### Issue: Docker `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`
Docker Desktop is not running. Open Docker Desktop from Start Menu and wait for green icon.

### Issue: `redis.exceptions.ConnectionError`
Redis container is not running:
```powershell
docker-compose up -d
docker ps  # verify trading_redis is Up
```

### Issue: pytest conflicts with global packages
```powershell
# Always use venv Python explicitly
.venv\Scripts\python -m pytest tests/
# NOT: python -m pytest tests/
```

### Issue: Celery worker exits immediately on Windows
Windows has known issues with Celery's default prefork pool. Use:
```powershell
.venv\Scripts\celery -A celery_app worker --loglevel=info --pool=solo -Q scoring,default
```

### Issue: `ConfigValidationError` on startup
```powershell
.venv\Scripts\python -c "from config.config_system import ConfigSystem; ConfigSystem('config.yaml')"
```

### Issue: SQL Server connection fails
```powershell
.venv\Scripts\python -c "
from db.connection import get_engine
from sqlalchemy import text
with get_engine().connect() as conn:
    print(conn.execute(text('SELECT @@VERSION')).scalar()[:60])
"
```

---

## Quick Reference

```powershell
# Activate venv
.venv\Scripts\activate

# Start Redis only (Docker)
docker-compose up -d

# Init database (first time only)
.venv\Scripts\python db/init_db.py

# Start FastAPI
.venv\Scripts\uvicorn api.main:app --reload --port 8000

# Start Celery Worker (new terminal)
.venv\Scripts\celery -A celery_app worker --loglevel=info -Q scoring,default --concurrency=2

# Start Celery Beat (new terminal)
.venv\Scripts\celery -A celery_app beat --loglevel=info

# Run tests
.venv\Scripts\python -m pytest tests/ -q

# Stop Redis
docker-compose down
```
