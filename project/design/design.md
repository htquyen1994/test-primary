# Crypto Trading System — Architecture & Design Document

> **Version:** 2.0  
> **Updated:** May 2026  
> **Style:** Semi-automatic · Scalping · Crypto Futures  
> **Stack:** Python · FastAPI · Celery · Redis · SQL Server · React

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [3-Layer Architecture](#2-3-layer-architecture)
3. [Data Flow — Realtime](#3-data-flow--realtime)
4. [Data Flow — Backtest](#4-data-flow--backtest)
5. [Signal Scoring Pipeline](#5-signal-scoring-pipeline)
6. [Regime Detection](#6-regime-detection)
7. [Risk Management Flow](#7-risk-management-flow)
8. [Strategy Plugin Architecture](#8-strategy-plugin-architecture)
9. [Component Interaction Map](#9-component-interaction-map)
10. [Database Schema](#10-database-schema)
11. [API Endpoints](#11-api-endpoints)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Deployment Stack](#13-deployment-stack)
14. [Key Design Decisions](#14-key-design-decisions)
15. [Correctness Properties](#15-correctness-properties-20-properties)

---

## 1. System Overview

A **semi-automatic crypto trading platform** that:
- Ingests real-time OHLCV, Order Book, and Trade Tape data from CEX exchanges via WebSocket
- Runs a multi-module AI scoring engine to detect high-probability setups
- Presents Signal Cards to the trader for 1-click confirm/skip decisions
- Executes orders automatically after confirmation, with testnet safety enforcement
- Logs all signals, trades, and backtest results for continuous learning

**Core principle:** AI analyzes, human decides. No fully automated execution.

---

## 2. 3-Layer Architecture

```
LAYER 1 — DATA INPUT
  OHLCV Feed (ws_ohlcv.py)  |  Order Book (ws_orderbook.py)  |  Funding Rate (funding.py)
  15m / 30m / 1h               Bid/Ask/Tape                     REST poll every 8h
        |                            |                                  |
        └────────────────────────────┴──────────────────────────────────┘
                         asyncio WS Tick Writers (< 0.1ms/tick)
                         ws_trades.py → delta += buy_vol / -= sell_vol
                                    |
                                    | atomic writes (INCRBYFLOAT, SET)
                                    ▼
REDIS — CENTRAL BUFFER LAYER
  ohlcv:{sym}:{tf}  |  delta:{sym}:5m  |  ob:{sym}:snap  |  poc:{sym}
  funding:{sym}     |  regime:{sym}    |  correlation:matrix
  alerts:channel  ◄── signal scorer publishes here
                                    |
                                    | triggered on candle close (Celery Beat)
                                    ▼
LAYER 2 — AI ENGINE (Celery Workers)
  Regime Detector → Correlation Manager → Strategy Registry
  → Signal Scorer → Risk Manager → Alert Builder → Redis pub/sub
  → Signal_Log writer → SQL Server
                                    |
                                    | Redis pub/sub
                                    ▼
LAYER 3 — HUMAN CONFIRM DASHBOARD
  FastAPI Backend → WebSocket → React Dashboard → User Decision
  CONFIRM → Trade Executor → ccxt → Exchange (testnet/live)
  All fills → SQL Server (trade_journal)
```

---

## 3. Data Flow — Realtime

```
Exchange WebSocket (Binance / Bybit)
        |
        ▼ asyncio, < 0.1ms/tick — NEVER blocks
WS Tick Writers (data/)
  ws_ohlcv.py     → Redis: ohlcv:{sym}:{tf}
  ws_orderbook.py → Redis: ob:{sym}:snap
  ws_trades.py    → Redis: delta:{sym}:5m (INCRBYFLOAT)
  funding.py      → Redis: funding:{sym} (REST poll)
        |
        ▼ Celery Beat triggers on each candle close
engine/tasks.py → run_signal_scoring(symbol, tf)
  Step 1: Read OHLCV + delta + OB + POC from Redis
  Step 2: Regime Detector (ADX + ATR spike check)
  Step 3: Correlation Manager (portfolio heat check)
  Step 4: Strategy Registry → generate_signals()
  Step 5: Signal Scorer → final score [0–100]
  Step 6: Risk Manager → position size + limits
  Step 7: Alert Builder → Signal Card payload
  Step 8: redis.publish("alerts:channel", card_json)
  Step 9: Write Signal_Log → SQL Server (ALL signals)
        |
        ▼ Redis pub/sub
FastAPI /ws/alerts WebSocket handler
  → push Signal Card to React Dashboard
        |
        ▼ User clicks CONFIRM
Trade Executor (trade/executor.py)
  _assert_testnet_safe() ← MUST run first
  ccxt.create_limit_order() → entry fill
  ccxt.create_order() → SL order
  ccxt.create_order() → TP1 + TP2 orders
  retry 3× with exponential backoff (1s, 2s, 4s)
        |
        ▼ record fill
Trade Journal (trade/journal.py)
  record_entry() → trade_journal table
  record_exit()  → update PnL, result (win/loss/be)
```

---

## 4. Data Flow — Backtest

```
config.yaml (backtest section)
        |
        ▼
BacktestingEngine.run(strategy, ohlcv)
        |
        ▼ for T in range(1, len(ohlcv)):
  ohlcv[:T+1] → strategy.generate_signals()
  (ONLY closed candles — no look-ahead bias)

  Regime Detector (ADX + ATR on closed candles)
  Signal Scorer → Score
  Risk Manager → position size
  Simulate fill: entry + slippage
  Check SL/TP intra-candle
  Apply funding rate payments
  Record TradeResult
        |
        ▼
compute_metrics() → win_rate, profit_factor, max_drawdown, Sharpe, Recovery Factor
        |
        ▼
Walk-Forward Analysis (optional)
  in-sample → optimize
  out-of-sample → evaluate
  flag overfit if degradation > 20%
        |
        ▼
Benchmark Table → logs/backtest/
AI Feedback → find_underperformance_clusters() → logs/optimization/
```

---

## 5. Signal Scoring Pipeline

```
Input: OHLCV 15m + 1h, delta, OB snap, POC/VAH/VAL, funding_rate

MODULE 1 — Order Flow Analysis (max 35 pts)
  delta > 1,000 BTC (5 candles)    → +15 pts
  bid_stack > ask_stack × 2        → +10 pts
  absorption (high vol, no move)   → +10 pts

MODULE 2 — SMC Analysis (max 30 pts)
  CHoCH aligned with 1H bias       → +10 pts
  Order Block retest               → +10 pts
  FVG midpoint touched             → +10 pts

MODULE 3 — VSA + Volume Profile (max 30 pts)
  No Supply (pullback vol < 40%)   → +10 pts
  Effort vs Result (low vol, holds)→ +10 pts
  Entry within ±0.3% of POC       → +10 pts
  Entry at VAH or VAL             → +6 pts

MODULE 4 — Context Filter (max 15 pts)
  1H bias aligned with direction   → +8 pts
  Funding rate within ±0.05%       → +4 pts
  Price ≥ 0.5% from nearest S/R   → +3 pts

CONFLUENCE BONUS (max 15 pts normalized)
  OB + Fib 38.2%                   → +15 raw
  OB + Fib 50%                     → +25 raw
  OB + Fib 61.8%                   → +35 raw
  OB + Fib 61.8% + POC             → +45 raw
  OB + Fib 61.8% + POC + FVG       → +55 raw (QUAD CONFLUENCE)
  normalized: bonus / 55 × 15

FORMULA:
  raw = OF + SMC + VSA + CTX + bonus   (0–125)
  final = min(round(raw × regime_multiplier / 125 × 100), 100)

  ≥ 75 → ALERT   publish to Redis → Dashboard
  55–74 → WATCH  log only
  < 55  → IGNORE log only
```

---

## 6. Regime Detection

```
Priority order (PARABOLIC checked FIRST):

1. PARABOLIC (highest priority)
   ATR(14) on 15m > 3× rolling_avg_ATR(14) on 15m
   → Score_Multiplier = 0.6
   → suppress ALL Short signals

2. TRENDING
   ADX(14) on 1h > 25
   → Score_Multiplier = 1.0

3. CHOPPY
   ADX(14) on 1h < 20
   → Score_Multiplier = 0.85

4. RANGING (default)
   20 ≤ ADX ≤ 25 or insufficient data
   → Score_Multiplier = 0.85

Why PARABOLIC first: ADX can be high during parabolic moves.
ATR spike check must run before ADX classification.
```

---

## 7. Risk Management Flow

```
New Signal arrives
        |
        ▼
Portfolio Heat check
  current_heat + new_risk > 6% → REJECT
  (sum of all open position risk percentages)
        |
        ▼
Correlated Group check
  rolling 24h Pearson correlation between assets
  correlation(A, B) > 0.8 → same group
  group_risk > 3% → REJECT
        |
        ▼
Position Size calculation
  mode = fixed_usd  → size = config.position.fixed_usd (e.g. $100)
  mode = risk_pct   → size = equity × 2% / (SL_dist / entry)
  mode = kelly      → size = Kelly fraction × equity
        |
        ▼
Max loss cap enforcement
  max_loss = size × (SL_dist / entry) ≤ equity × max_risk_pct
        |
        ▼
Leverage (Futures only)
  final_size = size × leverage
        |
        ▼
APPROVED → Signal Card → Dashboard
```

---

## 8. Strategy Plugin Architecture

```
config.yaml
  strategy:
    active: ["smc_ob_fvg", "pinbar", "engulfing"]
         |
         ▼
StrategyRegistry.load_active(config)
  validates ALL names before instantiating any
         |
         ├── @register("smc_ob_fvg")    → SMCOrderBlockFVGStrategy
         ├── @register("pinbar")        → PinbarStrategy
         ├── @register("engulfing")     → EngulfingStrategy
         ├── @register("inside_bar")    → InsideBarStrategy
         ├── @register("quasimodo")     → QuasimodoStrategy
         ├── @register("flag")          → FlagStrategy
         ├── @register("rsi_momentum")  → RSIMomentumStrategy
         └── @register("ema_cross")     → EMACrossStrategy

Adding a new strategy:
  1. Create strategies/my_strategy.py
  2. Add @StrategyRegistry.register("my_strategy")
  3. Add "my_strategy" to config.yaml strategy.active
  → Zero changes to existing code

BaseStrategy interface:
  generate_signals(ohlcv: DataFrame, context: dict) → List[Signal]
  _check_no_lookahead(ohlcv, T) → raises LookAheadError if violated
  classify_score(score) → "ALERT" | "WATCH" | "IGNORE"
```

---

## 9. Component Interaction Map

```
config.yaml
    |
    ▼
ConfigSystem ──────────────────────────────────────────────────┐
    |                                                           |
    ├──► RegimeDetector.from_config()                          |
    ├──► CorrelationManager.from_config()                      |
    ├──► RiskManager.from_config()                             |
    ├──► SignalScorer.from_config()                            |
    ├──► BacktestingEngine.from_config()                       |
    └──► TradeExecutor(exchange, config)                       |
                                                               |
Exchange WebSocket                                             |
    |                                                          |
    ▼                                                          |
WS Writers ──► Redis ──► Celery Workers                       |
                              |                               |
                              ▼                               |
                    StrategyRegistry.load_active(config) ◄────┘
                              |
                              ▼
                    strategy.generate_signals(ohlcv[:T], context)
                              |
                              ▼
                    SignalScorer.score(ScoreInput)
                              |
                              ▼
                    RiskManager.compute_position_size()
                              |
                              ▼
                    AlertBuilder.build_signal_card()
                              |
                    ┌─────────┴──────────┐
                    ▼                    ▼
              Redis pub/sub        SignalLog → SQL Server
                    |
                    ▼
              FastAPI /ws/alerts
                    |
                    ▼
              React Dashboard
                    |
              User: CONFIRM
                    |
                    ▼
              TradeExecutor.execute()
                    |
              ┌─────┴──────┐
              ▼            ▼
          Exchange    TradeJournal → SQL Server
```

---

## 10. Database Schema

### SQL Server — 3 tables

**signal_log** — every generated signal (ALERT + WATCH + IGNORE)
```
log_id, timestamp, asset, timeframe, strategy_name, direction,
candle_index, entry_price, stop_loss, take_profit_1, take_profit_2,
raw_score, final_score,
score_order_flow, score_smc, score_vsa, score_context, score_bonus,
regime, regime_multiplier, funding_rate, portfolio_heat,
correlated_group_risk, classification, user_action, skip_reason,
expiry_price, expires_at_candle, created_at
```

**trade_journal** — confirmed trades with actual fills and PnL
```
trade_id, signal_log_id, strategy_name, asset, timeframe, direction,
entry_timestamp, exit_timestamp,
entry_price, exit_price, actual_entry_price, actual_exit_price,
stop_loss, take_profit_1, take_profit_2,
position_size_usd, leverage,
slippage_entry, slippage_exit, fee_entry, fee_exit, funding_paid,
gross_pnl, net_pnl, result,
signal_score, exchange_order_id, is_testnet,
created_at, updated_at
```

**backtest_results** — one row per backtest run
```
run_id, strategy_name, asset, timeframe, start_date, end_date,
win_rate, profit_factor, max_drawdown, sharpe_ratio, recovery_factor,
total_trades, winning_trades, losing_trades,
is_walk_forward, wf_window_index, is_in_sample,
is_statistically_insufficient, config_snapshot, completed_at
```

**Connection:** `mssql+pyodbc://admin:***@localhost:1433/trading`  
**Fallback:** `sqlite:///./trading.db` (tests / CI)

---

## 11. API Endpoints

### REST

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/signals` | Active ALERT signals |
| POST | `/api/signals/{id}/confirm` | Confirm → Trade Executor |
| POST | `/api/signals/{id}/skip` | Skip with optional reason |
| PATCH | `/api/signals/{id}/expire` | Mark expired |
| GET | `/api/journal` | Paginated trade journal |
| GET | `/api/analytics` | Aggregated metrics |
| GET | `/api/portfolio` | Portfolio_Heat + positions |
| GET | `/api/strategies` | Registered strategy names |
| GET | `/api/config` | Current config (non-sensitive) |
| POST | `/api/config/reload` | Hot-reload config.yaml |
| GET | `/api/backtest/results` | Benchmark Table |
| POST | `/api/backtest/run` | Trigger async backtest |

### WebSocket

| Path | Description |
|------|-------------|
| `/ws/alerts` | Real-time Signal Card stream (Redis pub/sub) |
| `/ws/portfolio` | Real-time Portfolio_Heat updates |

---

## 12. Frontend Architecture

```
frontend-workspace/src/
├── App.tsx                          Router + Providers
├── providers/
│   ├── AlertsWebSocketProvider.tsx  /ws/alerts → alertsStore
│   └── PortfolioWebSocketProvider.tsx /ws/portfolio → portfolioStore
├── store/
│   ├── alertsStore.ts               Zustand: active Signal Cards
│   └── portfolioStore.ts            Zustand: Portfolio_Heat
├── components/
│   ├── PortfolioHeader.tsx          Persistent: heat gauge + nav
│   ├── SignalCard.tsx               Card + Confirm/Skip + status
│   ├── CountdownTimer.tsx           Candles remaining → onExpire
│   ├── ScoreBreakdown.tsx           Per-module score bars
│   └── JournalTable.tsx             Trade history table
└── pages/
    ├── SignalsPage.tsx              Active alerts queue
    ├── JournalPage.tsx              Paginated trade journal
    └── AnalyticsPage.tsx            Metrics + equity curve

Data flow:
  WebSocket → Provider → Zustand Store → Component re-render
  User action → fetch() → FastAPI → Trade Executor / DB
```

---

## 13. Deployment Stack

```
D:\workspace\trade-workspace\workspace\
│
├── backend-workspace\
│   ├── main.py                  Entry point
│   ├── config.yaml              Single config file (all params)
│   ├── docker-compose.yml       Redis + Celery workers
│   │   services:
│   │     redis:7-alpine         port 6379
│   │     celery_worker          scoring queue
│   │     celery_beat            candle-close scheduler
│   ├── api/main.py              FastAPI port 8000
│   ├── engine/                  AI modules (scorer, regime, correlation)
│   ├── strategies/              Plugin strategies (8 built-in)
│   ├── backtest/                Simulation engine + metrics
│   ├── trade/                   Executor + Journal + Monitor
│   └── db/                      SQL Server localhost:1433
│                                database: trading
│
└── frontend-workspace\
    ├── src/                     React + TypeScript + Tailwind
    └── vite.config.ts           proxy /api → :8000
                                 proxy /ws  → :8000

Run commands:
  docker-compose up -d                          # Redis + Celery
  python db/init_db.py                          # Init SQL Server tables
  uvicorn api.main:app --reload --port 8000     # FastAPI backend
  npm install && npm run dev                    # React frontend → :5173
  .venv\Scripts\python -m pytest tests/         # 319 tests
```

---

## 14. Key Design Decisions

### 1. Redis + Celery — Tách luồng data/scoring
**Problem:** Cumulative Delta cần cập nhật mỗi tick (1,000+ ticks/giây với BTC). Nếu chạy chung với scoring, WebSocket bị block → mất tick → delta sai.  
**Solution:** WS Tick Writer (asyncio, < 0.1ms) ghi atomic vào Redis. Celery Worker chạy riêng, triggered khi nến đóng.

### 2. Plugin Strategy Registry
**Problem:** Thêm strategy mới yêu cầu sửa nhiều file.  
**Solution:** `@StrategyRegistry.register("name")` decorator. Thêm strategy = 1 file mới + 1 dòng config. Zero changes to existing code.

### 3. PARABOLIC check trước ADX
**Problem:** ADX có thể cao trong parabolic move → classify sai là TRENDING.  
**Solution:** ATR spike check (ATR > 3× rolling avg) chạy trước ADX check. PARABOLIC có priority cao nhất.

### 4. Score formula: `raw × multiplier / 125 × 100`
**Rationale:** Denominator 125 = max lý thuyết (35+30+30+15+15). Đảm bảo output luôn trong [0, 100] với bất kỳ combination nào.

### 5. Testnet safety tại code level
**Problem:** Config có thể bị sửa nhầm → live trading không mong muốn.  
**Solution:** `_assert_testnet_safe()` guard chạy trước MỌI ccxt call. `testnet` phải là `False` (bool) — không phải `"false"` hay `0`.

### 6. SQL Server cho persistence, Redis cho hot path
**Rationale:** Trade Journal và Signal_Log cần ACID + complex queries. Redis cung cấp sub-millisecond reads/writes cho tick writing và pub/sub cho real-time dashboard.

### 7. Single config.yaml + hot-reload
**Rationale:** Single source of truth. Hot-reload cho phép tune threshold (ADX, ATR, score) mà không cần restart process — quan trọng trong live trading session.

### 8. Closed-candle-only signal generation
**Rationale:** Look-ahead bias là nguyên nhân phổ biến nhất của inflated backtest results. Runtime enforcement (LookAheadError) bắt vi phạm ngay trong development.

---

## 15. Correctness Properties (20 Properties)

Tất cả 20 properties được verify bằng `hypothesis` property-based testing. Run: `.venv\Scripts\python -m pytest tests/properties/`

| # | Property | Module |
|---|----------|--------|
| 1 | Indicator No-Look-Ahead Invariant | indicators/ |
| 2 | Indicator NaN for Insufficient Data | indicators/ |
| 3 | Gap Detection Completeness | data/gap_filler.py |
| 4 | Linear Interpolation Correctness | data/gap_filler.py |
| 5 | Score Normalization Invariant | engine/scorer.py |
| 6 | Confluence Monotonicity | engine/scorer.py |
| 7 | Risk Cap Invariant | risk/manager.py |
| 8 | Backtest Chronological Order | backtest/engine.py |
| 9 | Slippage Application Correctness | backtest/engine.py |
| 10 | Win Rate Formula Invariant | backtest/metrics.py |
| 11 | Sharpe Ratio Formula Invariant | backtest/metrics.py |
| 12 | Regime Output Validity | engine/regime_detector.py |
| 13 | PARABOLIC Short Suppression | engine/regime_detector.py |
| 14 | Pearson Correlation Bounds | engine/correlation_manager.py |
| 15 | Portfolio Heat Summation | engine/correlation_manager.py |
| 16 | Portfolio Heat Enforcement | engine/correlation_manager.py |
| 17 | Signal Log Completeness | api/signal_log_writer.py |
| 18 | Signal Card Required Fields | alert/builder.py |
| 19 | Testnet Safety Enforcement | trade/executor.py |
| 20 | Config Validation Completeness | config/config_system.py |

**Total test suite:** 319 tests, all passing.
