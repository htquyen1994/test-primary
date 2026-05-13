# Backend Setup Guide — Crypto Trading System

> **OS:** Windows  
> **Python:** 3.10+  
> **Backend path:** `D:\workspace\trade-workspace\workspace\backend-workspace\`  
> **Mock Exchange path:** `D:\workspace\trade-workspace\workspace\mock-exchange-workspace\`  
> **Database:** SQL Server (localhost:1433) + SQLite (mock exchange)  
> **Message Broker:** Redis (Docker — Redis only, no Celery in Docker)  
> **Celery:** Runs directly on Windows (faster, no Docker overhead)

---

## Architecture Overview

```
SQL Server (localhost:1433)         ← runs natively on Windows
Redis (Docker container :6379)      ← only service in Docker
Mock Exchange (FastAPI :8001)       ← algorithm validation service
Backend API (FastAPI :8000)         ← main trading backend
Data Pipeline (asyncio)             ← OHLCV / OB / Delta / Scoring
Celery Worker                       ← trade execution tasks
Frontend (Vite :5173)               ← React dashboard
```

Docker is used **only for Redis**. Everything else runs natively on Windows for faster development and easier SQL Server connectivity.

### Service Dependencies

```
Redis ──────────────────────────────────────────┐
                                                │
Mock Exchange (:8001) ─── audit events ─────────┤
  ├── AuditConsumer   (Redis → SQLite)          │
  ├── CandleFeed      (candle close → SL/TP)    │
  └── TickerFeed      (price feed → PnL)        │
                                                │
Backend API (:8000) ────────────────────────────┤
  ├── FastAPI REST + WebSocket                  │
  ├── Data Pipeline (OHLCV/OB/Delta/Scoring)   │
  ├── ScoringService → AuditClient → Redis      │
  └── TradeExecutor  → Mock Exchange :8001      │
                                                │
Celery Worker ──────────────────────────────────┘
  └── execute_trade tasks → Mock Exchange :8001

Frontend (:5173)
  └── Proxy → Backend API :8000
              └── Proxy → Mock Exchange :8001
```

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
.\.venv\Scripts\activate

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
.\.venv\Scripts\activate

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
.\.venv\Scripts\activate

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

## Mock Exchange Workspace Setup

> Mock Exchange là service dùng cho **Algorithm Validation** — mô phỏng exchange thật, ghi audit log cho mọi signal và trade, cung cấp position tracking và real-time PnL.  
> **Port:** 8001 | **DB:** SQLite (tự tạo) | **Bắt buộc** khi muốn dùng Trade Monitor UI

### Mock Exchange — Step 1: Navigate

```powershell
cd D:\workspace\trade-workspace\workspace\mock-exchange-workspace
```

### Mock Exchange — Step 2: Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python --version
# Python 3.10.x
```

### Mock Exchange — Step 3: Install Dependencies

> **Lưu ý:** Mỗi dòng là một lệnh riêng biệt — chạy tuần tự, không ghép vào một dòng.

```powershell
# Kích hoạt venv trước (nếu chưa)
.\.venv\Scripts\activate

# Lệnh 1: cài trading-core (shared package — bắt buộc, chạy trước)
pip install -e ..\trading-core

# Lệnh 2: cài dependencies của mock-exchange-workspace
pip install -r requirements.txt
```

Nếu `aioredis` conflict với `redis>=5.0`:
```powershell
pip install -r requirements.txt --ignore-installed aioredis
```

### Mock Exchange — Step 4: Verify Config

File `config.yaml` đã có sẵn với defaults phù hợp:

```yaml
service:
  host: "0.0.0.0"
  port: 8001

database:
  url: "sqlite:///./mock_exchange.db"   # tự tạo khi khởi động

redis:
  url: "redis://localhost:6379/0"       # phải khớp với Redis đang chạy

exchange:
  id: "binance"
  fee_rate: 0.001

mock_account:
  initial_balance_usd: 10000.0         # số dư tài khoản giả lập ban đầu

price_feed:
  ticker_poll_interval_seconds: 10     # cập nhật giá realtime mỗi 10s
```

> Không cần file `.env` — mọi config đều qua `config.yaml`.

### Mock Exchange — Step 5: Start Service

```powershell
# Terminal riêng, với venv đã activate
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\python main.py
```

Service khởi động tự động:
1. Init SQLite DB (tạo 7 tables)
2. Init mock account (balance $10,000)
3. Start AuditConsumer (đọc `audit:pending_snapshots` từ Redis)
4. Start CandleFeed (nhận candle_close → xử lý SL/TP)
5. Start TickerFeed (poll giá Binance → cập nhật unrealized PnL)
6. Start FastAPI/uvicorn trên port 8001

Expected output:
```
INFO | Config loaded from .../config.yaml
INFO | Database initialized: sqlite:////.../mock_exchange.db
INFO | Mock account initialized with balance=10000.00 USD
INFO | AuditConsumer started — listening on audit:pending_snapshots
INFO | CandleFeed started
INFO | TickerFeed started — polling binance every 10s
INFO | Starting mock-exchange-workspace on 0.0.0.0:8001
INFO | Application startup complete.
```

### Mock Exchange — Step 6: Verify

```powershell
# Health check
curl http://localhost:8001/health
# {"status":"ok","service":"mock-exchange-workspace"}

# API docs
# Mở browser: http://localhost:8001/docs
```

### Mock Exchange — Bảng dữ liệu (SQLite tự tạo)

| Table | Mô tả |
|-------|-------|
| `mock_orders` | Lệnh đặt trên exchange giả lập |
| `mock_positions` | Positions đang mở/đã đóng |
| `mock_account` | Số dư, equity, margin |
| `mock_account_history` | Lịch sử số dư |
| `signal_audit_log` | Audit mọi signal từ backend |
| `trade_audit_log` | Audit kết quả từng trade |
| `no_signal_audit_log` | Cơ hội bị bỏ lỡ |

### Mock Exchange — Kích hoạt trong Backend

Sau khi mock exchange đang chạy, bật tích hợp trong `workspace/backend-workspace/config.yaml`:

```yaml
mock_exchange:
  enabled: true            # ← đổi từ false thành true
  url: "http://localhost:8001"
  timeout_seconds: 5

audit:
  enabled: true            # ← đổi từ false thành true
```

> Sau khi đổi config, **hot-reload** bằng `POST http://localhost:8000/api/config/reload` — không cần restart backend.

### Mock Exchange — WebSocket Endpoints

| Endpoint | Mô tả |
|----------|-------|
| `WS ws://localhost:8001/ws/positions` | Real-time position prices + unrealized PnL |
| `WS ws://localhost:8001/ws/audit-feed` | Real-time signal/trade audit events |

> Frontend tự kết nối qua Backend proxy (`/api/exchange/*`, `/api/audit/*` tại :8000).

### Mock Exchange — Troubleshooting

**Issue: `ModuleNotFoundError: No module named 'trading_core'`**
```powershell
# Cài trading-core trước
pip install -e ..\trading-core
# Hoặc set PYTHONPATH
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core"
```

**Issue: SQLite database locked**
```powershell
# Xóa file DB để tạo lại từ đầu (mất toàn bộ audit history)
Remove-Item mock_exchange.db
.venv\Scripts\python main.py
```

**Issue: AuditConsumer không nhận events từ backend**
```powershell
# Kiểm tra Redis có messages không
docker exec trading_redis redis-cli llen audit:pending_snapshots
# Nếu > 0: AuditConsumer đang chờ xử lý
# Nếu = 0: backend chưa gửi (kiểm tra audit.enabled = true trong config.yaml)
```

**Issue: TickerFeed không cập nhật giá**
```powershell
# Kiểm tra kết nối Binance
curl "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
# Cần internet access, không cần API key (public endpoint)
```

---

## Full Startup Sequence

Every time you start the system, run in this order:

```powershell
# ── Terminal 0: Redis ─────────────────────────────
cd D:\workspace\trade-workspace\workspace\backend-workspace
docker-compose up -d
# Verify: docker exec trading_redis redis-cli ping → PONG

# ── Terminal 1: Mock Exchange :8001 ──────────────
cd D:\workspace\trade-workspace\workspace\mock-exchange-workspace
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\python main.py

# ── Terminal 2: Backend API :8000 ─────────────────
cd D:\workspace\trade-workspace\workspace\backend-workspace
# Load env vars
Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process') } }
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\uvicorn api.main:app --reload --port 8000

# ── Terminal 3: Data Pipeline ─────────────────────
cd D:\workspace\trade-workspace\workspace\backend-workspace
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\python main.py

# ── Terminal 4: Celery Worker ─────────────────────
cd D:\workspace\trade-workspace\workspace\backend-workspace
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\celery -A celery_app worker --loglevel=info -Q scoring,default --concurrency=2

# ── Terminal 5: Celery Beat ───────────────────────
cd D:\workspace\trade-workspace\workspace\backend-workspace
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\celery -A celery_app beat --loglevel=info

# ── Terminal 6: Frontend :5173 ────────────────────
cd D:\workspace\trade-workspace\workspace\frontend-workspace
npm run dev
```

> **Tip:** Dùng `.\start.ps1` ở thư mục gốc để tự động hoá toàn bộ quá trình trên.

```powershell
cd D:\workspace\trade-workspace
.\start.ps1          # mở 6 windows tự động, health check từng service
.\stop.ps1           # dừng tất cả
```

---

## Shutdown

```powershell
# Dừng tất cả bằng script (từ thư mục gốc)
.\stop.ps1

# Hoặc thủ công:
# Ctrl+C trong mỗi terminal (Mock Exchange, Backend API, Data Pipeline, Celery)

# Dừng Redis (Docker)
cd workspace\backend-workspace
docker-compose down

# Deactivate venv
deactivate
```

---

## Common Issues & Solutions

### Issue: `ModuleNotFoundError: No module named 'numpy'`
```powershell
.\.venv\Scripts\activate
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

### Tất cả services (một lệnh)
```powershell
# Từ thư mục gốc D:\workspace\trade-workspace
.\start.ps1                              # start tất cả (dev mode)
.\start.ps1 -SkipRedis                   # bỏ qua Redis nếu đang chạy
.\start.ps1 -Services "backend-api,frontend"  # chỉ start một số service
.\stop.ps1                               # dừng tất cả
```

### Backend workspace
```powershell
cd workspace\backend-workspace

# Activate venv
.\.venv\Scripts\activate

# Start Redis (Docker)
docker-compose up -d

# Init database — chỉ lần đầu
.venv\Scripts\python db/init_db.py

# Start FastAPI :8000
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\uvicorn api.main:app --reload --port 8000

# Start Data Pipeline
.venv\Scripts\python main.py

# Start Celery Worker
.venv\Scripts\celery -A celery_app worker --loglevel=info -Q scoring,default --concurrency=2

# Start Celery Beat
.venv\Scripts\celery -A celery_app beat --loglevel=info

# Hot-reload config (không cần restart)
curl -X POST http://localhost:8000/api/config/reload

# Run tests
.venv\Scripts\python -m pytest tests/ -q

# Stop Redis
docker-compose down
```

### Mock Exchange workspace
```powershell
cd workspace\mock-exchange-workspace

# Activate venv
.\.venv\Scripts\activate

# Install (lần đầu — chạy từng lệnh riêng biệt)
pip install -e ..\trading-core      # lệnh 1
pip install -r requirements.txt     # lệnh 2

# Start service :8001
$env:PYTHONPATH = "D:\workspace\trade-workspace\workspace\trading-core;" + $env:PYTHONPATH
.venv\Scripts\python main.py

# Health check
curl http://localhost:8001/health

# API docs
# http://localhost:8001/docs

# Xóa DB để reset toàn bộ audit data
Remove-Item mock_exchange.db
```

### URLs sau khi tất cả services chạy

| Service | URL | Mô tả |
|---------|-----|-------|
| Frontend | http://localhost:5173 | React Dashboard |
| Backend API | http://localhost:8000/docs | FastAPI Swagger |
| Mock Exchange | http://localhost:8001/docs | Mock Exchange Swagger |
| Trade Monitor | http://localhost:5173/monitor | Positions + Orders + Audit |
