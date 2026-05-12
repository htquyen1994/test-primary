# AI Semi-Auto Crypto Futures Trading Tool — Project Overview

> **Version:** 2.0 (Phase 9 — May 2026)
> **Style:** Semi-automatic · Scalping · Crypto Futures
> **Core principle:** AI phân tích, người quyết định — không fully automated

---

## Mục lục

1. [Tổng quan](#1-tổng-quan)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Cấu trúc thư mục](#3-cấu-trúc-thư-mục)
4. [Tech Stack](#4-tech-stack)
5. [AI Engine — Signal Scoring](#5-ai-engine--signal-scoring)
6. [Bộ lọc bảo vệ (Phase 9)](#6-bộ-lọc-bảo-vệ-phase-9)
7. [Quản lý rủi ro](#7-quản-lý-rủi-ro)
8. [Strategies](#8-strategies)
9. [Database](#9-database)
10. [API Endpoints](#10-api-endpoints)
11. [Hướng dẫn chạy](#11-hướng-dẫn-chạy)
12. [Trạng thái hiện tại](#12-trạng-thái-hiện-tại)

---

## 1. Tổng quan

Hệ thống giao dịch crypto futures bán tự động, hoạt động theo phong cách **scalping** trên khung 15 phút. AI quét thị trường liên tục, tính điểm xác suất cho từng setup, và đẩy **Signal Card** lên dashboard để trader xác nhận bằng 1 click.

### Nguyên tắc thiết kế

- **AI phân tích, người quyết định** — không fully automated, tránh rủi ro hệ thống
- **Rule-based trước, ML sau** — quy tắc rõ ràng, có thể giải thích được
- **Tín hiệu phải giải thích được** — mỗi alert đi kèm lý do cụ thể, không "hộp đen"
- **Log mọi thứ** — mọi tín hiệu, quyết định, kết quả đều được ghi lại để tối ưu
- **Tách biệt luồng dữ liệu và tính toán** — data pipeline không bao giờ bị block bởi scoring

### Thông số hoạt động

| Thông số | Giá trị |
|---|---|
| Khung trigger | 15 phút |
| Khung context | 1 giờ |
| Khung MTF filter | 4H + Daily |
| Khung entry | 5 phút |
| Tín hiệu mục tiêu/ngày | 5–12 |
| Thời gian giữ lệnh TB | 15–60 phút |
| Score ngưỡng ALERT | ≥ 75 / 100 |
| Score cap khi OB unavailable | ≤ 60 |
| Đòn bẩy khuyến nghị | 3x – 10x |
| R:R tối thiểu (net sau phí) | 1.5 : 1 |

---

## 2. Kiến trúc hệ thống

Hệ thống gồm 3 lớp chính:

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA INPUT                                   │
│  OHLCVService · OrderBookService · DeltaService         │
│  REST polling qua ccxt (public, không cần API key)      │
└────────────────────────┬────────────────────────────────┘
                         │ atomic writes
                         ▼
┌─────────────────────────────────────────────────────────┐
│  REDIS — CENTRAL BUFFER                                 │
│  ohlcv:{sym}:{tf} · ob:{sym}:snap · delta:{sym}:5m     │
│  poc:{sym} · regime:{sym} · daily_bias:{sym}            │
│  btc_guard:spike · circuit_breaker:locked               │
│  pub/sub: alerts:channel · logs:channel · candle_close  │
└────────────────────────┬────────────────────────────────┘
                         │ candle_close trigger
                         ▼
┌─────────────────────────────────────────────────────────┐
│  LAYER 2 — AI ENGINE (ScoringService)                   │
│  [1] Regime Detector (ADX + ATR)                        │
│  [2] MTF Bias Filter (4H + Daily) → 3 scenarios A/B/C  │
│  [3] BTC Spike Guard → block/reduce Alt alerts          │
│  [4] Circuit Breaker → block nếu đang locked            │
│  [5] Signal Scoring (OF + SMC + VSA + CTX + Bonus)      │
│  [6] Risk Manager → position size + portfolio heat      │
│  [7] Publish alert / log                                │
└────────────────────────┬────────────────────────────────┘
                         │ Redis pub/sub
                         ▼
┌─────────────────────────────────────────────────────────┐
│  LAYER 3 — HUMAN CONFIRM DASHBOARD                      │
│  FastAPI (port 8000) → WebSocket → React (port 5173)    │
│  Signal Card: CONFIRM → Trade Executor → Exchange       │
│                SKIP   → Log + AI feedback               │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Cấu trúc thư mục

```
trade-workspace/
├── overview.md                      ← file này
├── project/
│   ├── design/
│   │   ├── AI_Trade_Tool_Blueprint.md   # Blueprint chi tiết v2.0
│   │   ├── BACKEND_ARCHITECTURE.md     # Kiến trúc backend + luồng dữ liệu
│   │   ├── design.md                   # Architecture & design document
│   │   ├── run.md                      # Hướng dẫn chạy
│   │   └── SETUP_BACKEND.md            # Setup môi trường
│   └── docs/                           # Tài liệu trading (FVG, OB, Fib...)
│
└── workspace/
    ├── backend-workspace/               # Python backend
    │   ├── main.py                      # Entry point — asyncio.gather(4 services)
    │   ├── config.yaml                  # Config (fallback defaults)
    │   ├── docker-compose.yml           # Redis (Docker)
    │   │
    │   ├── data/                        # Data pipeline services
    │   │   ├── ohlcv_service.py         # REST polling OHLCV 15m/1h/4h/1d
    │   │   ├── orderbook_service.py     # REST polling order book mỗi 5s
    │   │   ├── delta_service.py         # Trade tape polling + cumulative delta
    │   │   └── funding.py              # Funding rate REST poll mỗi 8h
    │   │
    │   ├── engine/                      # AI scoring engine
    │   │   ├── scoring_service.py       # Orchestrator — asyncio + threading
    │   │   ├── scorer.py               # SignalScorer — normalize + classify
    │   │   ├── order_flow.py           # Order Flow module (35 pts)
    │   │   ├── smc.py                  # SMC: OB, FVG, CHoCH (30 pts)
    │   │   ├── vsa.py                  # VSA + Volume Profile (30 pts)
    │   │   ├── volume_profile.py       # POC/VAH/VAL calculator
    │   │   ├── context.py              # Context Filter (15 pts)
    │   │   ├── confluence.py           # Fib + OB + FVG bonus (15 pts)
    │   │   ├── regime_detector.py      # TRENDING/RANGING/PARABOLIC/CHOPPY
    │   │   ├── mtf_bias.py             # MTF Bias Filter 4H + Daily
    │   │   ├── btc_guard.py            # BTC Spike Guard
    │   │   ├── correlation_manager.py  # Pearson correlation + Portfolio Heat
    │   │   └── log_publisher.py        # Log entry builder + Redis publisher
    │   │
    │   ├── strategies/                  # Plugin strategy registry
    │   │   ├── registry.py             # @register decorator
    │   │   ├── base.py                 # BaseStrategy interface
    │   │   ├── smc_ob_fvg.py          # SMC Order Block + FVG (active)
    │   │   ├── pinbar.py              # Pin Bar (active)
    │   │   ├── engulfing.py           # Engulfing candle
    │   │   ├── inside_bar.py          # Inside Bar
    │   │   ├── quasimodo.py           # Quasimodo pattern
    │   │   ├── flag.py                # Flag / Pennant
    │   │   ├── rsi_momentum.py        # RSI Momentum
    │   │   └── ema_cross.py           # EMA Cross
    │   │
    │   ├── risk/                        # Risk management
    │   │   ├── circuit_breaker.py      # 4 triggers + smart unlock
    │   │   ├── manager.py              # Position sizing + portfolio heat
    │   │   └── validator.py            # Risk limit enforcement
    │   │
    │   ├── alert/                       # Alert pipeline
    │   │   ├── builder.py              # Signal Card builder
    │   │   ├── invalidator.py          # Time-based invalidation
    │   │   └── sender.py               # Redis pub/sub sender
    │   │
    │   ├── api/                         # FastAPI backend
    │   │   ├── main.py                 # App + all endpoints
    │   │   ├── routes/
    │   │   │   └── config_routes.py    # Config management routes
    │   │   └── schemas.py              # Pydantic models
    │   │
    │   ├── db/                          # Database layer
    │   │   ├── connection.py           # SQLAlchemy engine factory
    │   │   ├── models.py               # ORM models
    │   │   └── migrations/             # SQL migration scripts
    │   │
    │   ├── config/                      # Config system
    │   │   ├── config_system.py        # Load/validate/hot-reload
    │   │   ├── config_service.py       # DB-based config (Group A/B)
    │   │   └── config_resolver.py      # DB + config.yaml merge
    │   │
    │   ├── trade/                       # Trade execution
    │   │   ├── executor.py             # Trade Executor (testnet mode)
    │   │   └── journal.py              # Trade Journal writer
    │   │
    │   ├── backtest/                    # Backtesting engine
    │   ├── indicators/                  # Technical indicators (from scratch)
    │   └── tests/                       # 319 tests (pytest + hypothesis)
    │
    ├── frontend-workspace/              # React dashboard
    │   └── src/                        # TypeScript + Tailwind + Zustand
    │
    └── trading-core/                    # Shared core library
        └── trading_core/               # Exchange interface + utilities
```

---

## 4. Tech Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.11+ |
| Web framework | FastAPI 0.111 + uvicorn |
| Async runtime | asyncio + threading |
| Task queue | Celery 5.3 + Celery Beat |
| Cache / pub-sub | Redis 7 (Docker) |
| Exchange API | ccxt 4.3 |
| Database (prod) | SQL Server (localhost:1433) |
| Database (dev) | SQLite (trading.db) |
| ORM | SQLAlchemy 2.0 |
| Data processing | pandas 2.2 + numpy 1.26 |
| Config validation | Pydantic 2.7 |
| Frontend | React + TypeScript + Tailwind CSS |
| State management | Zustand |
| Build tool | Vite |
| Testing | pytest + Hypothesis (property-based) |

---

## 5. AI Engine — Signal Scoring

Mỗi khi nến 15m đóng, hệ thống tính điểm từ 4 module + bonus:

```
Signal Score = OrderFlow(35) + SMC(30) + VSA+VolProfile(30) + Context(15)
             + Confluence Bonus (tối đa +15)
Tổng tối đa: 125 điểm → normalize về 100
```

### Module 1 — Order Flow Analysis (35 pts)

| Điều kiện | Điểm |
|---|---|
| Cumulative Delta > dynamic threshold (percentile_75 × 1.5) | +15 |
| Bid stack > Ask stack × 2 tại vùng S/R | +10 |
| Absorption: volume cao nhưng giá không giảm | +10 |

> Khi Order Book không có dữ liệu: score bị **cap tại 60** — không thể đạt ALERT.

### Module 2 — SMC Analysis (30 pts)

| Tín hiệu | Điểm |
|---|---|
| CHoCH aligned với 1H bias | +10 |
| Order Block retest (trả về List tối đa 3 OB, ưu tiên Fib 61.8%) | +10 |
| Fair Value Gap midpoint touched | +10 |

### Module 3 — VSA + Volume Profile (30 pts)

| Điều kiện | Điểm |
|---|---|
| No Supply: volume pullback < 40% impulse | +10 |
| Effort vs Result: volume thấp, giá giữ vững | +10 |
| Entry trong ±0.3% của POC (Point of Control) | +10 |
| Entry tại VAH hoặc VAL | +6 |

### Module 4 — Context Filter (15 pts)

| Điều kiện | Điểm |
|---|---|
| 1H bias cùng chiều signal | +8 |
| Funding rate trong ±0.05% | +4 |
| Giá cách S/R gần nhất ≥ 0.5% | +3 |

### Confluence Bonus (tối đa +15 pts)

| Tổ hợp | Normalized |
|---|---|
| OB + Fib 38.2% | 5.0 pts |
| OB + Fib 50% | 8.3 pts |
| OB + Fib 61.8% | 11.7 pts |
| OB + Fib 61.8% + FVG | **15.0 pts** (max) |

### Ngưỡng hành động

| Score | Hành động |
|---|---|
| ≥ 75 | 🟢 **ALERT** — gửi Signal Card lên dashboard |
| 55–74 | 🟡 **WATCH** — log only |
| < 55 | 🔴 **IGNORE** — log only |

---

## 6. Bộ lọc bảo vệ (Phase 9)

### Regime Detector

| Regime | Điều kiện | Score Multiplier |
|---|---|---|
| PARABOLIC | ATR > 3× rolling avg ATR | 0.6 + tắt Short |
| TRENDING | ADX > 25 | 1.0 |
| RANGING | 20 ≤ ADX ≤ 25 | 0.85 |
| CHOPPY | ADX < 20 | 0.85 |

### MTF Bias Filter (4H + Daily)

| Scenario | Điều kiện | Tác động |
|---|---|---|
| A — Aligned | 4H bias đồng thuận với signal | size × 1.0, score +10 |
| B — Diverging | 4H ranging hoặc không rõ | size × 0.5, score -10, warning |
| C — Opposing | 4H bias ngược chiều signal | **BLOCK** — return early |

Daily bias: BEAR + long signal → size × 0.75 thêm.

### BTC Spike Guard

- BTC move > 2%/15m → **Dump**: cancel tất cả Alt alerts, block 30 phút
- BTC move > 2%/15m → **Pump**: Alt size × 0.5
- Alt gain < 0.3× BTC gain trong cooldown → block (relative weakness)

### Circuit Breaker (4 Triggers)

| Trigger | Điều kiện | Lock duration |
|---|---|---|
| 1 | 3 thua liên tiếp trong 24h | 12 giờ |
| 2 | 1 lệnh thua > 4% equity | 6 giờ |
| 3 | Thua ngày > 5% equity | Đến 00:00 UTC |
| 4 | Drawdown > 10% từ đỉnh 7 ngày | 24h + manual review |

Smart unlock: nếu regime thay đổi → auto unlock; nếu không → extend 6h.

---

## 7. Quản lý rủi ro

| Quy tắc | Giá trị |
|---|---|
| Risk mỗi lệnh | Tối đa 2% tài khoản |
| R:R net tối thiểu (sau phí) | 1.5 : 1 |
| Đòn bẩy tối đa | 10x (khuyến nghị 3–5x) |
| Max lệnh đồng thời | 3 lệnh |
| Portfolio Heat limit | 6% tài khoản |
| Correlated group risk | 3% tối đa |
| Max drawdown ngày | 5% tài khoản |

**Position sizing modes:** `fixed_usd` · `risk_pct` · `kelly`

**Correlation check:** Pearson correlation 24h. Nếu 2 assets có correlation > 0.8 và group risk > 3% → từ chối signal mới.

---

## 8. Strategies

Hệ thống dùng **plugin architecture** — thêm strategy mới không cần sửa code cũ.

| Strategy | Key | Mô tả |
|---|---|---|
| SMC Order Block + FVG | `smc_ob_fvg` | ✅ Active — core strategy |
| Pin Bar | `pinbar` | ✅ Active |
| Engulfing | `engulfing` | Có sẵn |
| Inside Bar | `inside_bar` | Có sẵn |
| Quasimodo | `quasimodo` | Có sẵn |
| Flag / Pennant | `flag` | Có sẵn |
| RSI Momentum | `rsi_momentum` | Có sẵn |
| EMA Cross | `ema_cross` | Có sẵn |

Thêm strategy mới: tạo file mới + `@StrategyRegistry.register("name")` + thêm vào `config.yaml`.

---

## 9. Database

### Tables

| Table | Nội dung |
|---|---|
| `signal_log` | Mọi signal (ALERT + WATCH + IGNORE) — dùng để optimize |
| `trade_journal` | Lệnh đã confirm với actual fill, PnL, slippage |
| `backtest_results` | Kết quả backtest từng strategy × timeframe |
| `circuit_breaker_state` | Lịch sử lock/unlock Circuit Breaker |

### Environment

```
Local dev:   SQLite  → sqlite:///./trading.db  (zero config)
Production:  SQL Server → mssql+pyodbc://admin:***@localhost:1433/trading
             Điều khiển bởi DATABASE_URL env var
```

---

## 10. API Endpoints

### WebSocket (real-time)

| Path | Mô tả |
|---|---|
| `/ws/alerts` | Stream Signal Cards khi score ≥ 75 |
| `/ws/logs` | Stream scoring debug log mọi candle |
| `/ws/portfolio` | Stream Portfolio Heat mỗi giây |

### REST — Signals

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/signals` | Active ALERT signals |
| POST | `/api/signals/{id}/confirm` | Xác nhận → Trade Executor (HTTP 423 nếu CB locked) |
| POST | `/api/signals/{id}/skip` | Bỏ qua + log lý do |
| PATCH | `/api/signals/{id}/expire` | Đánh dấu expired |

### REST — Journal & Analytics

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/journal` | Lịch sử giao dịch (paginated) |
| GET | `/api/analytics` | Win rate, profit factor, metrics |
| GET | `/api/portfolio` | Portfolio Heat + open positions |

### REST — Config

| Method | Path | Mô tả |
|---|---|---|
| GET/PUT | `/api/config/exchange` | Exchange settings (keys masked) |
| GET/PUT | `/api/config/trading` | Trading parameters |
| POST | `/api/config/reload` | Hot-reload config.yaml |

### REST — Circuit Breaker

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/circuit-breaker/status` | Trạng thái lock hiện tại |
| POST | `/api/circuit-breaker/unlock` | Manual unlock với review_note |

### REST — Backtest

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/backtest/results` | Benchmark Table |
| POST | `/api/backtest/run` | Trigger async backtest |

---

## 11. Hướng dẫn chạy

Cần **3 terminal** riêng biệt (Windows):

### Prerequisite

```bash
# Khởi động Redis (Docker)
docker-compose up -d

# Init database (lần đầu)
cd workspace\backend-workspace
.venv\Scripts\python db/init_db.py
```

### Terminal 1 — FastAPI Backend

```bash
cd workspace\backend-workspace
.venv\Scripts\activate
.venv\Scripts\uvicorn api.main:app --reload --port 8000
```

Kiểm tra: `http://localhost:8000/health` → `{"status":"ok"}`

### Terminal 2 — Celery Worker

```bash
cd workspace\backend-workspace
.venv\Scripts\activate
.venv\Scripts\celery -A celery_app worker --loglevel=info --pool=solo -Q scoring,default
```

### Terminal 3 — Celery Beat (candle close scheduler)

```bash
cd workspace\backend-workspace
.venv\Scripts\activate
.venv\Scripts\celery -A celery_app beat --loglevel=info
```

### Frontend

```bash
cd workspace\frontend-workspace
npm install
npm run dev
# → http://localhost:5173
```

### Data Pipeline (optional — chạy song song với FastAPI)

```bash
cd workspace\backend-workspace
.venv\Scripts\activate
.venv\Scripts\python main.py
```

### Chạy tests

```bash
cd workspace\backend-workspace
.venv\Scripts\python -m pytest tests/
# 319 tests — bao gồm property-based tests với Hypothesis
```

---

## 12. Trạng thái hiện tại

### ✅ Đã hoàn thành

| Component | Trạng thái |
|---|---|
| Redis (Docker) | ✅ Running |
| FastAPI backend (:8000) | ✅ Running |
| ScoringService (asyncio + threading) | ✅ Running |
| React frontend (:5173) | ✅ Running |
| OHLCV Feed (REST polling Binance) | ✅ Running |
| Signal Scoring (mỗi candle close) | ✅ Running |
| SQL Logging (signal_log table) | ✅ Running |
| MTF Bias Filter (3 scenarios A/B/C) | ✅ Phase 9 |
| BTC Spike Guard (dump/pump/cooldown) | ✅ Phase 9 |
| Circuit Breaker (4 triggers + smart unlock) | ✅ Phase 9 |
| Dynamic Delta Threshold | ✅ Phase 9 |
| Daily Bias Size Reduction | ✅ Phase 9 |
| Data Quality Cap (score ≤ 60 khi OB unavailable) | ✅ Phase 9 |
| OB returns List[OrderBlock] (Fib-prioritized) | ✅ Phase 9 |
| CORS explicit origins | ✅ Phase 9 |

### ⚠️ Chưa hoàn thành / Cần chú ý

| Component | Vấn đề | Tác động |
|---|---|---|
| Order Book Feed | Chưa start | Order Flow score = 0/35 pts → score bị cap tại 60 |
| Trade Tape / Delta | Chưa start | Delta luôn = 0 → mất 15 pts Order Flow |
| Trade Executor | Testnet mode | Chưa test với exchange thật |

> **Tóm tắt:** Hiện tại score tối đa đạt được ~65/100 (thiếu Order Book + Trade Tape). Khi bật đủ 2 feed này, hệ thống mới có thể đạt ngưỡng ALERT (75) và hoạt động đầy đủ.

---

## Tài liệu tham khảo

| File | Nội dung |
|---|---|
| `project/design/AI_Trade_Tool_Blueprint.md` | Blueprint chi tiết toàn bộ hệ thống v2.0 |
| `project/design/BACKEND_ARCHITECTURE.md` | Luồng dữ liệu và giải thích từng khối |
| `project/design/design.md` | Architecture & design document (EN) |
| `project/design/run.md` | Hướng dẫn chạy nhanh |
| `project/design/SETUP_BACKEND.md` | Setup môi trường backend |
| `project/docs/` | Tài liệu trading: FVG, Order Block, Fibonacci, VSA... |
