# Design Document: Crypto Trading System

## Overview

The Crypto Trading System is a modular, data-driven semi-automatic trading platform targeting cryptocurrency futures and spot markets on centralized exchanges. It identifies high-probability entry and exit signals across 15m, 30m, and 1h timeframes, validates strategies through rigorous backtesting, and enforces strict constraints against overfitting, repainting, and look-ahead bias.

The system follows a three-layer architecture:
- **Layer 1 — Data Input**: OHLCV, Order Book, and Funding Rate ingestion via WebSocket and REST, buffered through Redis
- **Layer 2 — AI Engine**: Signal Scoring with Regime Detection, Correlation Risk Management, and a plugin-based Strategy Registry, executed via Celery workers
- **Layer 3 — Human Confirm Dashboard**: FastAPI backend + React frontend presenting Signal Cards, one-click trade execution, Trade Journal, and Analytics

All tunable parameters are controlled through a single `config.yaml` file. The system operates in Testnet Mode by default before any live trading is enabled.

## Workspace Layout

| Component | Path |
|-----------|------|
| **Backend** | `D:\workspace\trade-workspace\workspace\backend-workspace\` |
| **Frontend** | `D:\workspace\trade-workspace\workspace\frontend-workspace\` |
| **Spec / Docs** | `.kiro/specs/crypto-trading-system/` |

**Database:** SQLite for local development and testing; PostgreSQL-compatible SQL schema (SQLAlchemy ORM) for production. All migrations are plain `.sql` files under `backend-workspace/db/migrations/`. The `DATABASE_URL` environment variable switches between engines without code changes.

**Satisfies:** Requirements 1–19 (all)

---

## Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LAYER 1 — DATA INPUT                            │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │   OHLCV Feed     │  │   Order Book     │  │  Funding Rate / OI   │  │
│  │  WS: 15m/30m/1h  │  │  WS: Bid/Ask     │  │  REST: periodic poll │  │
│  │  ccxt + asyncio  │  │  Tape/Trades     │  │  ccxt library        │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
│           │                     │                        │              │
│           └─────────────────────▼────────────────────────┘              │
│                                 │  asyncio WS Tick Writers              │
│                                 │  (< 0.1ms/tick, never block)          │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │ atomic writes
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    REDIS — CENTRAL BUFFER LAYER                         │
│                                                                         │
│   ohlcv:{sym}:{tf}  │  delta:{sym}:5m  │  ob:{sym}:snap               │
│   poc:{sym}         │  funding:{sym}   │  regime:{sym}                 │
│   alerts:channel    │  correlation:matrix                               │
│                                                                         │
│   Phase 9 keys:                                                         │
│   delta_history:{sym}  │  daily_bias:{sym} (TTL 4h)                    │
│   btc_guard:spike      │  circuit_breaker:locked (fast-path cache)      │
│                                                                         │
│   Phase 9 pub/sub channels:                                             │
│   cancel_all_alerts  │  btc_spike  │  circuit_breaker:events            │
│   logs:channel (all signals including WATCH/IGNORE)                     │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │ ScoringService     │ asyncio + threading │
              │ (candle_close      │ (signal scoring,    │
              │  pub/sub trigger)  │  regime detection)  │
              └────────────────────┼────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LAYER 2 — AI ENGINE                             │
│                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │
│  │ Order Flow   │ │ SMC Analysis │ │ VSA + Volume │ │ Context       │  │
│  │ Analysis     │ │ FVG+OB+CHoCH │ │ Profile      │ │ Filter        │  │
│  │ (0–35 pts)   │ │ (0–30 pts)   │ │ (0–30 pts)   │ │ (0–15 pts)    │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └───────┬───────┘  │
│         └────────────────┼────────────────┼─────────────────┘          │
│                          ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Phase 9 Filters (run BEFORE scoring)                           │   │
│  │  MTFBiasDetector (engine/mtf_bias.py)  — 4H + Daily bias        │   │
│  │  BTCVolatilityGuard (engine/btc_guard.py) — spike detection      │   │
│  │  CircuitBreaker (risk/circuit_breaker.py) — 4 triggers           │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 ▼                                       │
│              ┌───────────────────────────┐                              │
│              │  Signal Scorer            │                              │
│              │  raw + Confluence Bonus   │                              │
│              │  × Regime Multiplier      │                              │
│              │  + MTF score adjustment   │                              │
│              │  data quality cap (≤60)   │                              │
│              │  → Score [0–100]          │                              │
│              └─────────────┬─────────────┘                              │
│                            │                                            │
│  ┌─────────────────────────▼──────────────────────────────────────┐     │
│  │  Regime Detector  │  Correlation Manager  │  Risk Manager      │     │
│  │  TRENDING/RANGING │  Rolling 24h Pearson  │  Position Sizing   │     │
│  │  PARABOLIC/CHOPPY │  Portfolio Heat       │  + MTF/BTC mult.   │     │
│  └─────────────────────────┬──────────────────────────────────────┘     │
│                            │ publish alert (score ≥ 75)                 │
└────────────────────────────┼────────────────────────────────────────────┘
                             │ Redis pub/sub
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    LAYER 3 — HUMAN CONFIRM DASHBOARD                    │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Backend                                                 │   │
│  │  REST: /api/signals  /api/journal  /api/analytics  /api/config  │   │
│  │  WS:  /ws/alerts  /ws/portfolio                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│  ┌──────────────────────────────▼───────────────────────────────────┐   │
│  │  React Dashboard                                                 │   │
│  │  SignalCard + Countdown │ Chart (OB/FVG/Fib/POC) │ Journal      │   │
│  │  Portfolio Heat Header  │ Analytics Page          │ Config UI    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│  ┌──────────────────────────────▼───────────────────────────────────┐   │
│  │  Trade Executor (ccxt)                                           │   │
│  │  Testnet by default → limit/market order → auto SL/TP           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│  ┌──────────────────────────────▼───────────────────────────────────┐   │
│  │  SQL Server (production) / SQLite (local dev)                    │   │
│  │  trade_journal  │  signal_log  │  backtest_results               │   │
│  │  circuit_breaker_state (Phase 9)                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Diagrams

#### Realtime Signal Flow

```
Exchange WebSocket
        │
        ▼ (asyncio, < 0.1ms/tick)
WS Tick Writer ──────────────────────────────► Redis
  ws_ohlcv.py                                  ohlcv:{sym}:{tf}
  ws_orderbook.py                              ob:{sym}:snap
  ws_trades.py (delta)                         delta:{sym}:5m
  funding.py (REST poll)                       funding:{sym}
        │
        │ Celery Beat: triggered on candle close
        ▼
Celery Worker: run_signal_scoring(symbol, timeframe)
  1. Read OHLCV, delta, OB snap, POC from Redis
  2. Compute ATR(14), RSI(14), ADX(14)
  3. Regime Detector → Score_Multiplier
  4. Correlation Manager → Portfolio_Heat check
  5. Strategy Registry → active strategies → generate_signals()
  6. Signal Scorer → raw score → final score
  7. Risk Manager → position size, limit checks
  8. If score ≥ 75 AND risk checks pass:
       → Build Signal Card
       → redis.publish("alerts:channel", signal_json)
  9. Write Signal_Log entry (ALL signals, regardless of score)
        │
        ▼ Redis pub/sub
FastAPI WebSocket handler (/ws/alerts)
        │
        ▼ WebSocket push
React Dashboard → SignalCard rendered
        │
        ▼ User action: CONFIRM / SKIP
Trade Executor (if CONFIRM)
  → ccxt.create_order() within 2 seconds
  → ccxt.create_order() for SL
  → ccxt.create_order() for TP1, TP2
  → Record fill price, slippage → Trade Journal (PostgreSQL)
```

#### Backtest Flow

```
config.yaml (backtest section)
        │
        ▼
Backtesting Engine
  1. Load historical OHLCV from PostgreSQL / CSV
  2. Load historical Funding Rates
  3. For each candle T (ascending timestamp order):
       a. Compute indicators (ATR, RSI, ADX, EMA, BB)
       b. Regime Detector (ADX + ATR on closed candles only)
       c. Strategy Registry → generate_signals(ohlcv[:T])
       d. Signal Scorer → Score
       e. Risk Manager → position size
       f. Simulate fill: entry + slippage
       g. Apply funding rate payments during hold
       h. Check SL/TP within candle (intra-candle fill)
       i. Record TradeResult
  4. Compute metrics: win rate, profit factor, max drawdown,
     Sharpe Ratio, Recovery Factor
  5. Walk-Forward Analysis (if enabled):
       → Partition into in-sample / out-of-sample windows
       → Optimize on in-sample, evaluate on out-of-sample
       → Roll forward, aggregate results
  6. Write Benchmark_Table to /logs/
  7. AI Feedback: identify Underperformance Clusters
     → Write optimization suggestions to /logs/
```

---

## Components and Interfaces

### Module Responsibilities

| Module | Directory | Responsibility | Satisfies Requirements |
|--------|-----------|----------------|------------------------|
| Data Pipeline | `data/` | OHLCV + Funding Rate ingestion, gap filling, Redis writes | Req 2, 3 |
| Indicator Library | `indicators/` | Pure indicator functions (ATR, RSI, ADX, EMA, BB) | Req 4 |
| Strategy Registry | `strategies/` | Plugin-based strategy loading and management | Req 1, 16 |
| Signal Scorer | `engine/` | Aggregate module scores, apply regime multiplier | Req 6 |
| Regime Detector | `engine/` | Classify market state, output Score_Multiplier | Req 13 |
| Correlation Manager | `engine/` | Rolling Pearson correlation, Portfolio_Heat | Req 14 |
| Risk Manager | `risk/` | Position sizing (3 modes), limit enforcement | Req 7, 14 |
| Backtesting Engine | `backtest/` | Trade simulation, metrics, walk-forward, AI feedback | Req 8–11 |
| Config System | root | Load/validate/hot-reload config.yaml | Req 15 |
| Alert Builder | `alert/` | Build Signal Cards, time invalidation | Req 17, 18 |
| Trade Executor | `trade/` | ccxt order submission, SL/TP placement, journal | Req 19 |
| Dashboard Backend | `dashboard/` | FastAPI REST + WebSocket endpoints | Req 18 |
| Dashboard Frontend | `dashboard/frontend/` | React UI: Signal Cards, Chart, Journal, Analytics | Req 18 |
| Logger | `logs/` | Signal_Log, backtest results, optimization suggestions | Req 11, 17 |

### Core Abstract Interfaces

```python
# indicators/base.py
from abc import ABC, abstractmethod
from typing import Union
import numpy as np
import pandas as pd

class BaseIndicator(ABC):
    """
    Abstract base for all indicator functions.
    Satisfies: Requirement 4.1, 4.4, 12.3
    """

    @abstractmethod
    def compute(self, ohlcv: pd.DataFrame, period: int) -> Union[np.ndarray, pd.Series]:
        """
        Compute indicator values from OHLCV data.

        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume],
                   indexed by timestamp in ascending order.
            period: Lookback period N.

        Returns:
            Array of same length as ohlcv. Positions requiring more data
            than available SHALL return NaN (Req 4.5).

        Constraint: MUST NOT access ohlcv.iloc[T+1:] during computation
                    of index T (Req 4.3, 5.1).
        """
        ...
```

```python
# strategies/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import pandas as pd

@dataclass
class Signal:
    """
    Discrete buy or sell recommendation produced by a Strategy.
    Satisfies: Requirement 5.4, 6.1, 17.2
    """
    strategy_name: str
    asset: str                        # e.g. "BTC/USDT"
    timeframe: str                    # e.g. "15m"
    direction: str                    # "long" | "short"
    candle_index: int                 # index T of the closed candle
    candle_timestamp: datetime
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    raw_score: float                  # before regime multiplier
    final_score: int                  # [0, 100] after multiplier
    score_breakdown: dict             # {order_flow, smc, vsa, context, bonus}
    regime: str                       # TRENDING | RANGING | PARABOLIC | CHOPPY
    regime_multiplier: float
    funding_rate: float
    portfolio_heat: float
    correlated_group_risk: float
    classification: str               # ALERT | WATCH | IGNORE
    expires_at_candle: int            # candle index for time invalidation
    created_at: datetime = field(default_factory=datetime.utcnow)
    user_action: Optional[str] = None # CONFIRM | SKIP | EXPIRED | IGNORE
    skip_reason: Optional[str] = None


class BaseStrategy(ABC):
    """
    Abstract interface every Strategy class must implement.
    Satisfies: Requirement 12.2, 16.1
    """

    def __init__(self, config: dict) -> None:
        """
        Args:
            config: Validated configuration object from Config_System.
                    Strategy-level parameters are sourced from here (Req 16.7).
        """
        self.config = config

    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame, context: dict) -> List[Signal]:
        """
        Generate signals from closed candle data.

        Args:
            ohlcv: DataFrame of CLOSED candles only (index 0..T).
                   MUST NOT contain any candle that has not yet closed (Req 5.2).
            context: Dict containing regime state, funding rate, correlation
                     data, and higher-timeframe OHLCV for context filter.

        Returns:
            List of Signal objects. Empty list if no signal detected.

        Constraint: SHALL only access ohlcv.iloc[:T+1] — no future data (Req 5.1).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier used in Strategy_Registry."""
        ...
```

```python
# backtest/models.py
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

@dataclass
class TradeResult:
    """
    Result of a single simulated or live trade.
    Satisfies: Requirement 8, 9, 19
    """
    trade_id: str
    strategy_name: str
    asset: str
    timeframe: str
    direction: str                    # "long" | "short"
    entry_timestamp: datetime
    exit_timestamp: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    actual_entry_price: float         # after slippage
    actual_exit_price: Optional[float]
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    position_size_usd: float
    leverage: int
    slippage_entry: float             # actual - expected entry
    slippage_exit: float
    fee_entry: float
    fee_exit: float
    funding_paid: float               # total funding rate payments
    gross_pnl: float
    net_pnl: float                    # gross - fees - slippage - funding
    result: str                       # "win" | "loss" | "be"
    signal_score: int
    exchange_order_id: Optional[str] = None
    is_testnet: bool = True
```

---

## Data Models

### Signal_Log JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SignalLog",
  "description": "Structured log entry for every generated Signal. Satisfies Req 17.1, 17.2",
  "type": "object",
  "required": [
    "log_id", "timestamp", "asset", "timeframe", "strategy_name",
    "direction", "raw_score", "final_score", "score_breakdown",
    "regime", "regime_multiplier", "funding_rate", "portfolio_heat",
    "correlated_group_risk", "classification", "user_action"
  ],
  "properties": {
    "log_id":                 { "type": "string", "format": "uuid" },
    "timestamp":              { "type": "string", "format": "date-time" },
    "asset":                  { "type": "string", "example": "BTC/USDT" },
    "timeframe":              { "type": "string", "enum": ["15m", "30m", "1h"] },
    "strategy_name":          { "type": "string" },
    "direction":              { "type": "string", "enum": ["long", "short"] },
    "candle_index":           { "type": "integer" },
    "entry_price":            { "type": "number" },
    "stop_loss":              { "type": "number" },
    "take_profit_1":          { "type": "number" },
    "take_profit_2":          { "type": "number" },
    "raw_score":              { "type": "number", "minimum": 0, "maximum": 125 },
    "final_score":            { "type": "integer", "minimum": 0, "maximum": 100 },
    "score_breakdown": {
      "type": "object",
      "properties": {
        "order_flow":  { "type": "number", "minimum": 0, "maximum": 35 },
        "smc":         { "type": "number", "minimum": 0, "maximum": 30 },
        "vsa":         { "type": "number", "minimum": 0, "maximum": 30 },
        "context":     { "type": "number", "minimum": 0, "maximum": 15 },
        "bonus":       { "type": "number", "minimum": 0, "maximum": 15 }
      },
      "required": ["order_flow", "smc", "vsa", "context", "bonus"]
    },
    "regime":                 { "type": "string", "enum": ["TRENDING", "RANGING", "PARABOLIC", "CHOPPY"] },
    "regime_multiplier":      { "type": "number" },
    "funding_rate":           { "type": "number" },
    "portfolio_heat":         { "type": "number", "minimum": 0 },
    "correlated_group_risk":  { "type": "number", "minimum": 0 },
    "classification":         { "type": "string", "enum": ["ALERT", "WATCH", "IGNORE"] },
    "user_action":            { "type": "string", "enum": ["CONFIRM", "SKIP", "EXPIRED", "IGNORE", null] },
    "skip_reason":            { "type": ["string", "null"] },
    "expiry_price":           { "type": ["number", "null"] },
    "expires_at_candle":      { "type": "integer" }
  }
}
```

### Trade Journal PostgreSQL Schema

```sql
-- Satisfies: Requirement 17, 18.7, 19.5, 19.6, 19.10
CREATE TABLE trade_journal (
    trade_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_log_id       UUID REFERENCES signal_log(log_id),
    strategy_name       VARCHAR(100) NOT NULL,
    asset               VARCHAR(20)  NOT NULL,
    timeframe           VARCHAR(5)   NOT NULL,
    direction           VARCHAR(5)   NOT NULL CHECK (direction IN ('long', 'short')),
    entry_timestamp     TIMESTAMPTZ  NOT NULL,
    exit_timestamp      TIMESTAMPTZ,
    entry_price         NUMERIC(20, 8) NOT NULL,
    exit_price          NUMERIC(20, 8),
    actual_entry_price  NUMERIC(20, 8) NOT NULL,
    actual_exit_price   NUMERIC(20, 8),
    stop_loss           NUMERIC(20, 8) NOT NULL,
    take_profit_1       NUMERIC(20, 8) NOT NULL,
    take_profit_2       NUMERIC(20, 8),
    position_size_usd   NUMERIC(20, 4) NOT NULL,
    leverage            INTEGER NOT NULL DEFAULT 1,
    slippage_entry      NUMERIC(20, 8) NOT NULL DEFAULT 0,
    slippage_exit       NUMERIC(20, 8) NOT NULL DEFAULT 0,
    fee_entry           NUMERIC(20, 8) NOT NULL DEFAULT 0,
    fee_exit            NUMERIC(20, 8) NOT NULL DEFAULT 0,
    funding_paid        NUMERIC(20, 8) NOT NULL DEFAULT 0,
    gross_pnl           NUMERIC(20, 8),
    net_pnl             NUMERIC(20, 8),
    result              VARCHAR(4) CHECK (result IN ('win', 'loss', 'be')),
    signal_score        INTEGER NOT NULL CHECK (signal_score BETWEEN 0 AND 100),
    exchange_order_id   VARCHAR(100),
    is_testnet          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trade_journal_asset ON trade_journal(asset);
CREATE INDEX idx_trade_journal_strategy ON trade_journal(strategy_name);
CREATE INDEX idx_trade_journal_entry_ts ON trade_journal(entry_timestamp);
```

```sql
-- Satisfies: Requirement 17.1, 17.2, 17.7
CREATE TABLE signal_log (
    log_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp               TIMESTAMPTZ NOT NULL,
    asset                   VARCHAR(20) NOT NULL,
    timeframe               VARCHAR(5)  NOT NULL,
    strategy_name           VARCHAR(100) NOT NULL,
    direction               VARCHAR(5)  NOT NULL,
    candle_index            BIGINT NOT NULL,
    entry_price             NUMERIC(20, 8),
    stop_loss               NUMERIC(20, 8),
    take_profit_1           NUMERIC(20, 8),
    take_profit_2           NUMERIC(20, 8),
    raw_score               NUMERIC(6, 2) NOT NULL,
    final_score             INTEGER NOT NULL,
    score_order_flow        NUMERIC(5, 2) NOT NULL,
    score_smc               NUMERIC(5, 2) NOT NULL,
    score_vsa               NUMERIC(5, 2) NOT NULL,
    score_context           NUMERIC(5, 2) NOT NULL,
    score_bonus             NUMERIC(5, 2) NOT NULL,
    regime                  VARCHAR(20) NOT NULL,
    regime_multiplier       NUMERIC(4, 2) NOT NULL,
    funding_rate            NUMERIC(10, 6) NOT NULL,
    portfolio_heat          NUMERIC(6, 4) NOT NULL,
    correlated_group_risk   NUMERIC(6, 4) NOT NULL,
    classification          VARCHAR(10) NOT NULL,
    user_action             VARCHAR(10),
    skip_reason             TEXT,
    expiry_price            NUMERIC(20, 8),
    expires_at_candle       BIGINT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_signal_log_asset_ts ON signal_log(asset, timestamp);
CREATE INDEX idx_signal_log_classification ON signal_log(classification);
CREATE INDEX idx_signal_log_strategy ON signal_log(strategy_name);
```

```sql
-- Satisfies: Requirement 9, 10, 11
CREATE TABLE backtest_results (
    run_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name       VARCHAR(100) NOT NULL,
    asset               VARCHAR(20)  NOT NULL,
    timeframe           VARCHAR(5)   NOT NULL,
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    win_rate            NUMERIC(6, 4),
    profit_factor       NUMERIC(8, 4),
    max_drawdown        NUMERIC(6, 4),
    sharpe_ratio        NUMERIC(8, 4),
    recovery_factor     NUMERIC(8, 4),
    total_trades        INTEGER,
    winning_trades      INTEGER,
    losing_trades       INTEGER,
    is_walk_forward     BOOLEAN NOT NULL DEFAULT FALSE,
    wf_window_index     INTEGER,
    is_in_sample        BOOLEAN,
    is_statistically_insufficient BOOLEAN NOT NULL DEFAULT FALSE,
    config_snapshot     JSONB NOT NULL,
    completed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### config.yaml Full Example

```yaml
# config.yaml — Full configuration example
# Satisfies: Requirement 15

account:
  balance: 10000.0
  currency: "USDT"

position:
  mode: "risk_pct"          # fixed_usd | risk_pct | kelly
  fixed_usd: 100.0          # used when mode = fixed_usd
  risk_pct: 0.02            # 2% per trade when mode = risk_pct
  max_concurrent: 3
  leverage: 5               # global default leverage

regime:
  enabled: true
  adx_trending_threshold: 25
  adx_choppy_threshold: 20
  atr_parabolic_multiplier: 3.0
  parabolic_score_multiplier: 0.6
  ranging_score_multiplier: 0.85
  trending_score_multiplier: 1.0

risk:
  max_daily_loss_pct: 0.05
  max_drawdown_pct: 0.15
  correlation_threshold: 0.8
  max_correlated_risk_pct: 3.0
  portfolio_heat_limit_pct: 6.0
  atr_sl_multiplier: 1.5

strategy:
  active:
    - "smc_ob_fvg"
    - "pinbar"
    - "engulfing"
    - "rsi_momentum"
  score_threshold:
    alert: 75
    watch: 55
  timeframes:
    trigger: "15m"
    context: "1h"
    entry: "5m"
  time_invalidation_candles: 15

exchange:
  name: "binance"           # ccxt exchange id
  market_type: "futures"    # futures | spot
  fee_rate: 0.001           # 0.1% taker
  slippage_pct: 0.0002      # 0.02% estimated
  testnet: true             # MUST be explicitly false for live trading

assets:
  - symbol: "BTC/USDT"
    enabled: true
    leverage: 10
  - symbol: "ETH/USDT"
    enabled: true
    leverage: 7
  - symbol: "SOL/USDT"
    enabled: true
    leverage: 5

backtest:
  start_date: "2024-01-01"
  end_date: "2024-12-31"
  walk_forward:
    enabled: true
    in_sample_days: 90
    out_sample_days: 30
    step_days: 30
  min_trades_threshold: 30
  overfit_degradation_threshold: 0.20

logging:
  level: "INFO"
  save_all_signals: true
  log_dir: "logs/"
  signal_log_dir: "logs/signals/"
  backtest_log_dir: "logs/backtest/"
```


---

## Signal Scoring Algorithm

### Overview

The Signal Scorer aggregates four module scores plus a Confluence Bonus, applies the Regime Multiplier, and normalizes to [0, 100]. Phase 9 adds MTF score adjustment, data quality cap, and dynamic delta threshold.

```
raw = OrderFlow(0-35) + SMC(0-30) + VSA+VolProfile(0-30) + Context(0-15) + Confluence(0-15)
final = min(round(raw * regime_multiplier / 125 * 100), 100)

# Phase 9 adjustments (applied after normalization):
final += mtf_score_adjustment   # +10 (Scenario A) | -10 (Scenario B) | BLOCK (Scenario C)
if not order_book_available:
    final = min(final, 60)      # data quality cap
```

**Satisfies:** Requirement 6.2, 6.3, 6.7, 6.8

### Scoring Pipeline (v2.0)

```
Candle closes (15m)
        │
        ▼
[1] Regime Detector (ADX + ATR)
        │
        ▼
[2] MTF Bias Filter (4H + Daily)          ← Phase 9
    Scenario A: size × 1.0, score +10
    Scenario B: size × 0.5, score -10, warning
    Scenario C: BLOCK (return early, log rejection)
        │
        ▼
[3] BTC Spike Guard (for Alt symbols)     ← Phase 9
    Dump spike: cancel all Alt alerts, return early
    Pump spike: size × 0.5
    Cooldown: suppress for 30 min
        │
        ▼
[4] Circuit Breaker check                 ← Phase 9
    If locked: skip alert, log reason
        │
        ▼
[5] Signal Scoring (OF + SMC + VSA + CTX + Bonus)
    Dynamic delta threshold               ← Phase 9
    Score capped at 60 if OB unavailable  ← Phase 9
        │
        ▼
[6] Risk Manager
    Apply MTF size multiplier            ← Phase 9
    Apply Daily bias multiplier          ← Phase 9
    Apply BTC spike multiplier           ← Phase 9
        │
        ▼
[7] Publish alert / log
```

### Module 1: Order Flow Analysis (max 35 pts)

```python
def order_flow_score(delta: float, bid_stack: float, ask_stack: float,
                     absorption: bool, delta_threshold: float = 1000.0) -> float:
    """
    Measures institutional order flow pressure.
    Satisfies: Requirement 6.2 (Order Flow component), Req 23

    Args:
        delta:           Cumulative buy_volume - sell_volume over last 5 candles
        bid_stack:       Total bid size at S/R zone
        ask_stack:       Total ask size at S/R zone
        absorption:      True if high volume but price did not move significantly
        delta_threshold: Dynamic threshold = percentile_75(|delta_24h|) × 1.5
                         Fallback: 1000.0 if fewer than 10 data points
    """
    score = 0.0
    # Institutional buying pressure
    if delta > delta_threshold:
        score += 15.0
    # Bid dominance at key level
    if bid_stack > ask_stack * 2.0:
        score += 10.0
    # Absorption: large volume absorbed without price decline
    if absorption:
        score += 10.0
    return min(score, 35.0)


def compute_dynamic_delta_threshold(delta_history: list) -> float:
    """
    Dynamic threshold from 24h delta history.
    threshold = percentile_75(abs(delta_values_24h)) × 1.5
    Fallback to 1000.0 if fewer than 10 data points.
    History stored in Redis: delta_history:{symbol} (96 values = 24h of 15m candles)
    Satisfies: Requirement 23
    """
    if len(delta_history) < 10:
        return 1000.0
    abs_deltas = [abs(d) for d in delta_history if d != 0]
    if not abs_deltas:
        return 1000.0
    p75 = float(np.percentile(abs_deltas, 75))
    return max(100.0, min(p75 * 1.5, 50000.0))
```

### Module 2: SMC Analysis (max 30 pts)

```python
def compute_smc_score(ohlcv_15m: pd.DataFrame, ohlcv_1h: pd.DataFrame) -> SMCResult:
    """
    Smart Money Concepts: CHoCH, Order Block, Fair Value Gap.
    Satisfies: Requirement 6.2 (SMC component)

    Scoring:
        CHoCH aligned with 1H bias:  +10 pts
        Order Block retest:          +10 pts
        FVG midpoint touched:        +10 pts

    Returns SMCResult with:
        order_blocks: List[OrderBlock]  — up to 3, sorted by Fib priority then proximity
        order_block:  OrderBlock | None — best/retesting OB (primary)
        htf_bias:     str               — computed here, used by MTF filter
    """
    ...


def find_order_block(ohlcv: pd.DataFrame, atr_multiplier: float = 1.5,
                     max_obs: int = 3) -> List[OrderBlock]:
    """
    Returns up to max_obs valid Order Blocks.
    Sorted by: Fibonacci alignment (61.8% > 50% > 38.2%) first,
               then by proximity to current price.
    Satisfies: Requirement 1.2 (OB mathematical logic), Phase 9 Task 30.2
    """
    ...
```

### Module 3: VSA + Volume Profile (max 30 pts)

```python
def compute_vsa_score(ohlcv: pd.DataFrame, poc: float,
                       vah: float, val: float) -> float:
    """
    Volume Spread Analysis + Volume Profile confirmation.
    Satisfies: Requirement 6.2 (VSA+VolProfile component)

    VSA (max 20 pts):
        No Supply (pullback vol < 40% impulse vol):  +10 pts
        Effort vs Result (low vol, price holds):     +10 pts

    Volume Profile (max 10 pts):
        Entry within 0.3% of POC:                   +10 pts
        Entry at VAH or VAL:                         +6 pts
    """
    score = 0.0
    entry = ohlcv.iloc[-1]["close"]

    # Identify impulse and pullback candles
    impulse_vol  = ohlcv.iloc[-3]["volume"]  # 3 candles back = impulse
    pullback_vol = ohlcv.iloc[-1]["volume"]  # current = pullback

    ratio = pullback_vol / impulse_vol if impulse_vol > 0 else 1.0

    # No Supply: low volume on pullback
    if ratio < 0.40:
        score += 10.0
    # Effort vs Result: low volume but price holds
    price_change = abs(ohlcv.iloc[-1]["close"] - ohlcv.iloc[-1]["open"])
    avg_range = ohlcv["high"].iloc[-20:].sub(ohlcv["low"].iloc[-20:]).mean()
    if ratio < 0.50 and price_change < 0.3 * avg_range:
        score += 10.0

    # Volume Profile bonus
    if poc > 0 and abs(entry - poc) / poc <= 0.003:
        score += 10.0
    elif vah > 0 and val > 0:
        if abs(entry - vah) / vah <= 0.003 or abs(entry - val) / val <= 0.003:
            score += 6.0

    return min(score, 30.0)


def compute_volume_profile(ohlcv_1m: pd.DataFrame, bins: int = 100) -> dict:
    """
    Compute POC, VAH, VAL from 1-day OHLCV (390 x 1m candles).
    Stored in Redis key poc:{symbol}, updated every 15m.
    Satisfies: Requirement 6.2 (Volume Profile data)
    """
    price_min = ohlcv_1m["low"].min()
    price_max = ohlcv_1m["high"].max()
    price_bins = pd.cut(ohlcv_1m["close"], bins=bins)
    vol_by_price = ohlcv_1m.groupby(price_bins)["volume"].sum()

    poc_bin = vol_by_price.idxmax()
    poc = (poc_bin.left + poc_bin.right) / 2

    total_vol = vol_by_price.sum()
    target_vol = total_vol * 0.70  # 70% value area

    # Expand from POC outward until 70% volume captured
    sorted_bins = vol_by_price.sort_values(ascending=False)
    cumvol = 0.0
    value_area_bins = []
    for bin_interval, vol in sorted_bins.items():
        cumvol += vol
        value_area_bins.append(bin_interval)
        if cumvol >= target_vol:
            break

    vah = max(b.right for b in value_area_bins)
    val = min(b.left  for b in value_area_bins)

    return {"poc": poc, "vah": vah, "val": val}
```

### Module 4: Context Filter (max 15 pts)

```python
def compute_context_score(ohlcv_1h: pd.DataFrame, funding_rate: float,
                           nearest_sr_distance_pct: float = 0.005) -> float:
    """
    Higher-timeframe context validation.
    Satisfies: Requirement 6.2 (Context component), Requirement 1.4

    Scoring:
        1H bias aligned with signal direction:  +8 pts
        Funding rate within ±0.05%:             +4 pts
        Price >= 0.5% from nearest S/R:         +3 pts
    """
    score = 0.0

    # 1H bias check (HTF context filter — Req 1.4)
    htf_bias = _detect_htf_bias(ohlcv_1h)
    # Caller passes direction; this function returns max possible
    # Actual direction check done in SignalScorer
    score += 8.0  # awarded when direction matches htf_bias

    # Funding rate filter
    if abs(funding_rate) <= 0.0005:  # ±0.05%
        score += 4.0

    # Distance from S/R
    if nearest_sr_distance_pct >= 0.005:
        score += 3.0

    return min(score, 15.0)
```

### Confluence Bonus (max 15 pts)

```python
def compute_confluence_bonus(ohlcv, ob_or_obs, fvg, poc=0.0) -> float:
    """
    Bonus for multi-layer confluence: OB + Fibonacci + FVG.
    POC check REMOVED (Phase 9 fix) — POC belongs only in compute_vsa_score().
    This prevents double-counting the same POC signal in both modules.
    Satisfies: Requirement 6.2 (Confluence Bonus), Requirement 6.4

    Bonus table (raw points):
        OB + Fib 38.2%:           +15 raw pts
        OB + Fib 50%:             +25 raw pts
        OB + Fib 61.8%:           +35 raw pts
        OB + Fib 61.8% + FVG:     +45 raw pts  ← max raw = 45 (not 55)

    Normalization: min(bonus / 45 * 15, 15.0)
    Note: poc parameter kept for API compatibility but is ignored.

    Accepts both single OrderBlock and List[OrderBlock] (Phase 9 Task 30.2).
    """
    ...
```

---

## Regime Detection Algorithm

```python
def detect_regime(ohlcv_1h: pd.DataFrame, ohlcv_15m: pd.DataFrame,
                  config: dict) -> RegimeState:
    """
    State machine for market regime classification.
    Satisfies: Requirement 13.1–13.9

    States and transitions:
        PARABOLIC  ← ATR_15m > 3x rolling_avg_ATR_15m (highest priority)
        TRENDING   ← ADX_1h > 25
        CHOPPY     ← ADX_1h < 20
        RANGING    ← 20 <= ADX_1h <= 25

    Score multipliers:
        PARABOLIC: 0.6  (suppress Short signals)
        TRENDING:  1.0
        RANGING:   0.85
        CHOPPY:    0.85
    """
    adx_threshold_trending = config["regime"]["adx_trending_threshold"]  # 25
    adx_threshold_choppy   = config["regime"]["adx_choppy_threshold"]    # 20
    atr_parabolic_mult     = config["regime"]["atr_parabolic_multiplier"] # 3.0

    # Compute indicators on CLOSED candles only (Req 5.1)
    adx_series = compute_adx(ohlcv_1h, period=14)
    atr_series = compute_atr(ohlcv_15m, period=14)

    current_adx = adx_series.iloc[-1]
    current_atr = atr_series.iloc[-1]
    rolling_avg_atr = atr_series.rolling(20).mean().iloc[-1]

    # Priority 1: PARABOLIC (Req 13.4)
    if current_atr > atr_parabolic_mult * rolling_avg_atr:
        return RegimeState(
            regime="PARABOLIC",
            score_multiplier=config["regime"]["parabolic_score_multiplier"],
            suppress_short=True
        )

    # Priority 2: TRENDING (Req 13.2)
    if current_adx > adx_threshold_trending:
        return RegimeState(
            regime="TRENDING",
            score_multiplier=config["regime"]["trending_score_multiplier"],
            suppress_short=False
        )

    # Priority 3: CHOPPY (Req 13.3)
    if current_adx < adx_threshold_choppy:
        return RegimeState(
            regime="CHOPPY",
            score_multiplier=config["regime"]["ranging_score_multiplier"],
            suppress_short=False
        )

    # Default: RANGING (Req 13.3)
    return RegimeState(
        regime="RANGING",
        score_multiplier=config["regime"]["ranging_score_multiplier"],
        suppress_short=False
    )
```

---

## Correlation Risk Algorithm

```python
def compute_correlation_matrix(ohlcv_1h_by_asset: dict[str, pd.DataFrame],
                                lookback_hours: int = 24) -> pd.DataFrame:
    """
    Rolling 24h Pearson correlation between all active asset pairs.
    Updated at each 1h candle close.
    Satisfies: Requirement 14.1, 14.2
    """
    closes = {
        asset: df["close"].iloc[-lookback_hours:]
        for asset, df in ohlcv_1h_by_asset.items()
    }
    return pd.DataFrame(closes).corr(method="pearson")


def compute_portfolio_heat(open_positions: dict[str, float]) -> float:
    """
    Sum of risk percentages across all open positions.
    Satisfies: Requirement 14.6

    Args:
        open_positions: {asset: risk_pct_of_equity}
    Returns:
        Total portfolio heat as percentage of equity
    """
    return sum(open_positions.values())


def check_correlated_risk(
    new_asset: str,
    new_risk_pct: float,
    open_positions: dict[str, float],
    correlation_matrix: pd.DataFrame,
    correlation_threshold: float,
    max_correlated_risk_pct: float,
    portfolio_heat_limit: float,
) -> tuple[bool, str]:
    """
    Validate new signal against correlated-risk and portfolio-heat limits.
    Satisfies: Requirement 14.3–14.7

    Returns:
        (allowed: bool, rejection_reason: str)
    """
    # Portfolio heat check (Req 14.7)
    current_heat = compute_portfolio_heat(open_positions)
    if current_heat + new_risk_pct > portfolio_heat_limit:
        return False, (
            f"Portfolio_Heat {current_heat:.2%} + {new_risk_pct:.2%} "
            f"exceeds limit {portfolio_heat_limit:.2%}"
        )

    # Find correlated group for new_asset (Req 14.3)
    if new_asset in correlation_matrix.columns:
        correlated_assets = {
            asset for asset in correlation_matrix.columns
            if asset != new_asset and
               abs(correlation_matrix.loc[new_asset, asset]) > correlation_threshold
        }
        # Include new_asset itself in group risk calculation
        group_risk = new_risk_pct + sum(
            open_positions.get(a, 0.0) for a in correlated_assets
        )
        if group_risk > max_correlated_risk_pct:
            return False, (
                f"Correlated group {correlated_assets | {new_asset}} "
                f"combined risk {group_risk:.2%} exceeds limit {max_correlated_risk_pct:.2%}. "
                f"Members: {list(correlated_assets)}"
            )

    return True, ""
```

---

## API Endpoints

### FastAPI Routes

```python
# dashboard/routes.py
# Satisfies: Requirement 18.1–18.10

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncio

app = FastAPI(title="Crypto Trading System Dashboard API")

app.add_middleware(CORSMiddleware,
                   allow_origins=_allowed_origins,  # explicit origins, no wildcard
                   allow_methods=["*"], allow_headers=["*"])
# ALLOWED_ORIGINS env var overrides defaults (comma-separated list)
# Default: ["http://localhost:5173", "http://localhost:3000"]

# ─── REST Endpoints ───────────────────────────────────────────────────────────

# GET /api/signals
# Returns active ALERT-class signals (Signal Cards)
# Satisfies: Req 18.1

# GET /api/signals/{signal_id}
# Returns full detail for a single signal

# POST /api/signals/{signal_id}/confirm
# Triggers Trade Executor for the given signal
# Checks Circuit Breaker first — returns 423 Locked if active
# Satisfies: Req 18.2, 18.3

# POST /api/signals/{signal_id}/skip
# Body: {"reason": "optional skip reason"}
# Records skip action in Signal_Log
# Satisfies: Req 18.2, 18.4

# GET /api/journal
# Query params: asset, strategy, start_date, end_date, page, page_size
# Returns paginated Trade Journal entries
# Satisfies: Req 18.7

# GET /api/analytics
# Returns aggregated performance metrics
# Satisfies: Req 18.8

# GET /api/portfolio
# Returns current Portfolio_Heat and per-asset correlated group risk
# Satisfies: Req 14.8, 18.9

# GET /api/strategies
# Returns list of registered strategy names
# Satisfies: Req 16.6

# GET /api/config
# Returns current config (non-sensitive fields only)

# POST /api/config/reload
# Triggers hot-reload of config.yaml
# Satisfies: Req 15.11

# GET /api/backtest/results
# Returns backtest result records and Benchmark_Table
# Satisfies: Req 9.6, 17.5

# POST /api/backtest/run
# Body: {strategy, asset, timeframe, start_date, end_date}
# Triggers async backtest run
# Satisfies: Req 8, 9, 10

# Phase 9 — Circuit Breaker endpoints:
# GET  /api/circuit-breaker/status  — returns lock state, trigger type, time remaining
# POST /api/circuit-breaker/unlock  — manual unlock with review_note (required for Trigger 4)

# ─── WebSocket Endpoints ──────────────────────────────────────────────────────

# WS /ws/alerts
# Streams new Signal Cards in real time via Redis pub/sub (alerts:channel)
# Signal Card payload includes Phase 9 fields:
#   data_quality, ob_warning, mtf_scenario, mtf_warning,
#   bias_4h, daily_bias, size_multiplier
# Satisfies: Req 18.10

# WS /ws/portfolio
# Streams Portfolio_Heat and correlated risk updates
# Satisfies: Req 14.8, 18.9, 18.10

# WS /ws/logs
# Streams ALL signals (ALERT + WATCH + IGNORE) with full debug breakdown
# Separate channel from alerts — does not affect scoring performance
# Satisfies: Req 17.1
```

```python
# Concrete WebSocket implementation
@app.websocket("/ws/alerts")
async def alert_stream(websocket: WebSocket):
    """
    Real-time Signal Card stream via Redis pub/sub.
    Satisfies: Requirement 18.10
    """
    await websocket.accept()
    import aioredis
    redis = await aioredis.from_url("redis://localhost")
    pubsub = redis.pubsub()
    await pubsub.subscribe("alerts:channel")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("alerts:channel")
    finally:
        await redis.close()


@app.websocket("/ws/portfolio")
async def portfolio_stream(websocket: WebSocket):
    """
    Real-time Portfolio_Heat and correlated risk stream.
    Satisfies: Requirement 14.8, 18.9
    """
    await websocket.accept()
    import aioredis
    redis = await aioredis.from_url("redis://localhost")
    try:
        while True:
            heat_data = await redis.get("portfolio:heat")
            if heat_data:
                await websocket.send_text(heat_data)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    finally:
        await redis.close()
```

---

## Directory Structure

The project is split into two separate workspaces:

```
D:\workspace\trade-workspace\workspace\
│
├── backend-workspace\               # Python backend (FastAPI + Celery + AI Engine)
│   ├── main.py                      # Entry point — starts all services
│   ├── config.yaml                  # Single config file (Req 15)
│   ├── requirements.txt
│   ├── docker-compose.yml           # Redis + Celery services
│   ├── celery_app.py                # Celery app instance
│   │
│   ├── db/                          # Database layer (SQL)
│   │   ├── migrations/
│   │   │   ├── 001_initial_schema.sql  # signal_log, trade_journal, backtest_results
│   │   │   ├── 002_config_versions.sql
│   │   │   └── 003_circuit_breaker.sql # Phase 9: circuit_breaker_state table
│   │   ├── connection.py            # SQLAlchemy engine (DATABASE_URL env var)
│   │   └── models.py                # SQLAlchemy ORM models
│   │
│   ├── docs/                        # Strategy Spec documents (Req 1)
│   │   ├── pinbar.md
│   │   ├── engulfing.md
│   │   ├── inside_bar.md
│   │   ├── order_block.md
│   │   ├── breaker_block.md
│   │   ├── fair_value_gap.md
│   │   ├── quasimodo.md
│   │   ├── double_top_bottom.md
│   │   ├── flag.md
│   │   ├── rsi_momentum.md
│   │   ├── bollinger_band_squeeze.md
│   │   └── ema_cross.md
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── system.py                # ConfigSystem class (Req 15)
│   │
│   ├── data/                        # Data Pipeline (Req 2, 3)
│   │   ├── ws_ohlcv.py
│   │   ├── ws_orderbook.py
│   │   ├── ws_trades.py
│   │   ├── funding.py
│   │   ├── redis_writer.py
│   │   ├── redis_reader.py
│   │   └── gap_filler.py
│   │
│   ├── indicators/                  # Indicator Library (Req 4)
│   │   ├── base.py
│   │   ├── atr.py
│   │   ├── rsi.py
│   │   ├── bollinger.py
│   │   ├── ema.py
│   │   ├── adx.py
│   │   └── candle_measurements.py
│   │
│   ├── strategies/                  # Strategy Registry + Implementations (Req 16)
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── smc_ob_fvg.py
│   │   ├── pinbar.py
│   │   ├── engulfing.py
│   │   ├── inside_bar.py
│   │   ├── quasimodo.py
│   │   ├── double_top_bottom.py
│   │   ├── flag.py
│   │   ├── rsi_momentum.py
│   │   ├── bollinger_squeeze.py
│   │   └── ema_cross.py
│   │
│   ├── engine/                      # AI Engine (Req 6, 13, 14)
│   │   ├── scorer.py
│   │   ├── order_flow.py
│   │   ├── smc.py
│   │   ├── vsa.py
│   │   ├── volume_profile.py
│   │   ├── context.py
│   │   ├── confluence.py
│   │   ├── regime_detector.py
│   │   ├── correlation_manager.py
│   │   ├── mtf_bias.py              # Phase 9: MTFBiasDetector (4H + Daily)
│   │   ├── btc_guard.py             # Phase 9: BTCVolatilityGuard
│   │   ├── scoring_service.py       # ScoringService (asyncio + threading)
│   │   └── tasks.py                 # Celery tasks
│   │
│   ├── risk/                        # Risk Management (Req 7, 14)
│   │   ├── manager.py
│   │   ├── position_sizer.py
│   │   ├── circuit_breaker.py       # Phase 9: CircuitBreaker (4 triggers)
│   │   └── validator.py
│   │
│   ├── alert/                       # Alert Building (Req 17, 18)
│   │   ├── builder.py
│   │   ├── invalidator.py
│   │   └── sender.py
│   │
│   ├── trade/                       # Trade Execution (Req 19)
│   │   ├── executor.py
│   │   ├── journal.py
│   │   └── position_monitor.py
│   │
│   ├── backtest/                    # Backtesting Engine (Req 8–11)
│   │   ├── engine.py
│   │   ├── models.py
│   │   ├── metrics.py
│   │   ├── walk_forward.py
│   │   ├── benchmark.py
│   │   └── ai_feedback.py
│   │
│   ├── api/                         # FastAPI app (Req 18)
│   │   ├── main.py                  # FastAPI app instance
│   │   ├── routes/
│   │   │   ├── signals.py
│   │   │   ├── journal.py
│   │   │   ├── analytics.py
│   │   │   ├── config.py
│   │   │   └── trade.py
│   │   ├── schemas.py               # Pydantic request/response models
│   │   └── websockets.py            # /ws/alerts, /ws/portfolio
│   │
│   ├── logs/                        # Logging (Req 11, 17)
│   │   ├── signals/
│   │   ├── backtest/
│   │   └── optimization/
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── properties/              # hypothesis property-based tests
│
└── frontend-workspace\              # React dashboard (Req 18)
    ├── package.json
    ├── vite.config.ts               # Proxy → backend-workspace API
    ├── tsconfig.json
    └── src/
        ├── App.tsx
        ├── providers/
        │   ├── AlertsWebSocketProvider.tsx
        │   └── PortfolioWebSocketProvider.tsx
        ├── store/
        │   ├── alertsStore.ts       # Zustand store for signals
        │   └── portfolioStore.ts
        ├── components/
        │   ├── SignalCard.tsx
        │   ├── ScoreBreakdown.tsx
        │   ├── ChartView.tsx        # lightweight-charts + OB/FVG/Fib/POC
        │   ├── CountdownTimer.tsx
        │   ├── ConfirmButton.tsx
        │   ├── SkipButton.tsx
        │   ├── PortfolioHeader.tsx
        │   ├── JournalTable.tsx
        │   └── AnalyticsPage.tsx
        ├── pages/
        │   ├── SignalsPage.tsx
        │   ├── JournalPage.tsx
        │   └── AnalyticsPage.tsx
        ├── hooks/
        │   ├── useAlertWebSocket.ts
        │   └── usePortfolioWebSocket.ts
        └── types/
            └── index.ts
```

### Database: SQL Server / SQLite

The system uses **SQLAlchemy** with a SQL backend. `DATABASE_URL` in the environment controls the engine:

| Environment | `DATABASE_URL` example | Notes |
|-------------|------------------------|-------|
| Local dev / test | `sqlite:///./trading.db` | Zero-config, file-based |
| Production | `mssql+pyodbc://...` | SQL Server (Windows production) |

All schema is defined in plain SQL migration files (`db/migrations/`). SQLAlchemy ORM models in `db/models.py` map to the same schema.

#### Phase 9: circuit_breaker_state Table (Migration 003)

```sql
-- db/migrations/003_circuit_breaker.sql
-- Satisfies: Requirement 21 (Phase 9 Circuit Breaker)
CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    triggered_at          DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    unlock_at             DATETIME2 NOT NULL,
    trigger_type          NVARCHAR(50) NOT NULL,
        -- 'CONSECUTIVE_LOSSES' | 'LOSS_MAGNITUDE' | 'DAILY_LOSS_CAP' | 'DRAWDOWN_FROM_PEAK'
    trigger_detail        NVARCHAR(500) NULL,
    regime_at_trigger     NVARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    is_locked             BIT NOT NULL DEFAULT 1,
    unlock_requires_review BIT NOT NULL DEFAULT 0,
        -- True for Trigger 4 (drawdown from peak) — requires manual review note
    review_note           NVARCHAR(1000) NULL,
    unlocked_at           DATETIME2 NULL,
    unlocked_by           NVARCHAR(100) NULL,
        -- 'auto_regime_change' | 'manual_user' | 'timer_expired'
    created_at            DATETIME2 NOT NULL DEFAULT GETUTCDATE()
);
CREATE INDEX IF NOT EXISTS idx_cb_is_locked ON circuit_breaker_state (is_locked, unlock_at);
```


---

## Frontend Component Tree

```
App
├── PortfolioHeader                  # Persistent: Portfolio_Heat + correlated risk (Req 18.9)
│   ├── HeatGauge                    # Visual heat indicator
│   └── CorrelatedGroupList          # Per-asset group risk
│
├── Router
│   ├── /dashboard → DashboardPage
│   │   ├── ActiveSignalQueue        # List of ALERT-class Signal Cards
│   │   │   └── SignalCard[]         # One per active signal (Req 18.1)
│   │   │       ├── SignalHeader     # Asset, direction, score badge
│   │   │       ├── PriceLevels      # Entry, SL, TP1, TP2, R:R gross/net
│   │   │       ├── ScoreBreakdown   # Per-module score bars
│   │   │       ├── RegimeTag        # Current regime state
│   │   │       ├── CountdownTimer   # Candles remaining (Req 18.1)
│   │   │       ├── ConfirmButton    # → POST /api/signals/{id}/confirm (Req 18.3)
│   │   │       └── SkipButton       # → POST /api/signals/{id}/skip (Req 18.4)
│   │   │
│   │   └── ChartView                # Real-time chart (Req 18.6)
│   │       ├── CandlestickChart     # TradingView Lightweight Charts
│   │       ├── OBOverlay            # Order Block zones
│   │       ├── FVGOverlay           # Fair Value Gap zones
│   │       ├── FibOverlay           # Fibonacci levels
│   │       └── POCOverlay           # POC / VAH / VAL lines
│   │
│   ├── /journal → JournalPage
│   │   ├── JournalFilters           # Asset, strategy, date range
│   │   └── JournalTable             # All confirmed trades (Req 18.7)
│   │       └── TradeRow[]           # timestamp, pair, dir, score, entry,
│   │                                #   SL, TP, fill, slippage, PnL, result
│   │
│   └── /analytics → AnalyticsPage
│       ├── OverallMetrics           # Win rate, profit factor, max DD, Sharpe (Req 18.8)
│       ├── StrategyBreakdown        # Per-strategy performance table
│       └── BenchmarkTable           # Multi-strategy × timeframe matrix (Req 17.5)
│
└── WebSocket Providers
    ├── AlertWebSocketProvider       # /ws/alerts → updates ActiveSignalQueue
    └── PortfolioWebSocketProvider   # /ws/portfolio → updates PortfolioHeader
```

### Technology Choice: React (not Next.js)

**Decision:** Use React (Vite + TypeScript) rather than Next.js.

**Rationale:**
- The dashboard is a single-page application with no SEO requirements and no server-side rendering needs
- WebSocket connections are long-lived and stateful — SSR would complicate this
- React + Vite provides faster HMR during development and simpler deployment (static files served by FastAPI or nginx)
- Next.js adds complexity (App Router, RSC) that provides no benefit for a real-time trading dashboard

---

## Error Handling

### Data Pipeline Errors

| Error | Handling | Satisfies |
|-------|----------|-----------|
| ccxt API error | Retry up to 3× with exponential backoff (1s, 2s, 4s), then raise structured error | Req 2.6 |
| Missing candles | Linear interpolation for OHLCV fields; log gap with asset, timeframe, timestamp range | Req 2.4, 2.5 |
| Funding rate unavailable | Log warning; use 0.0 for that period | Req 3.4 |
| WebSocket disconnect | Reconnect with exponential backoff; buffer missed ticks in Redis | Req 2 |

### Signal Generation Errors

| Error | Handling | Satisfies |
|-------|----------|-----------|
| Future candle access | Raise `LookAheadBiasError(strategy_name, offending_index)` at runtime | Req 5.3 |
| ATR = 0 | Reject signal; log rejection with asset, timeframe, timestamp | Req 7.4 |
| Strategy not in registry | Raise `StrategyNotFoundError(name)` at startup before any data fetch | Req 16.4 |
| Missing config param | Raise `ConfigValidationError(param, expected_type, received)` at startup | Req 12.6, 15.10 |

### Trade Execution Errors

| Error | Handling | Satisfies |
|-------|----------|-----------|
| Exchange API error | Retry up to 3× with exponential backoff; notify user via Dashboard on all-retry failure | Req 19.7 |
| Testnet not set | Default to testnet; require explicit `testnet: false` for live | Req 19.8, 19.9 |
| Correlated risk exceeded | Reject signal; log with asset, group members, current combined risk | Req 14.5 |
| Portfolio heat exceeded | Reject all new signals until heat drops below limit | Req 14.7 |

### Custom Exception Hierarchy

```python
# exceptions.py
class TradingSystemError(Exception):
    """Base exception for all system errors."""

class LookAheadBiasError(TradingSystemError):
    """Raised when a strategy accesses future candle data. Satisfies Req 5.3"""
    def __init__(self, strategy_name: str, offending_index: int):
        super().__init__(
            f"Strategy '{strategy_name}' accessed future candle at index {offending_index}. "
            f"Only indices 0..T are allowed during computation of index T."
        )

class ConfigValidationError(TradingSystemError):
    """Raised when config.yaml has missing or invalid parameters. Satisfies Req 15.10"""

class StrategyNotFoundError(TradingSystemError):
    """Raised when a strategy name in active list is not registered. Satisfies Req 16.4"""

class RiskLimitExceededError(TradingSystemError):
    """Raised when a signal violates risk limits. Satisfies Req 14.5, 14.7"""

class InsufficientDataError(TradingSystemError):
    """Raised when OHLCV array has fewer than N elements for indicator. Satisfies Req 4.5"""
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

**Property Reflection:** After analyzing all acceptance criteria, the following redundancies were identified and resolved:
- Req 6.1 (score in [0,100]) and Req 6.3 (formula produces [0,100]) are combined into one score normalization property — the formula IS the normalization invariant.
- Req 7.1 (position size formula) and Req 7.3 (risk cap) are combined — the cap is part of the formula invariant.
- Req 13.5 (PARABOLIC suppresses shorts) is a specific case of Req 13.1 (regime output validity) but tests a distinct behavior — kept separate.
- Req 19.8 and Req 19.9 (testnet safety) are combined into one testnet enforcement property.
- Req 9.2 (win rate formula) and Req 9.3 (Sharpe formula) are kept separate as they test different computations.

---

### Property 1: Indicator No-Look-Ahead Invariant

*For any* OHLCV array of length N, any indicator function, and any index T in [0, N-1], computing the indicator on `ohlcv[:T+1]` must produce the same value at index T as computing it on the full array `ohlcv[:N]` at index T. Extending the array with future candles must not change the value at T.

**Validates: Requirements 4.3, 5.1**

---

### Property 2: Indicator NaN for Insufficient Data

*For any* indicator with period N and any OHLCV array of length L, all output values at indices 0 through N-2 must be NaN (not a number), because those positions require more historical data than is available.

**Validates: Requirements 4.5**

---

### Property 3: Gap Detection Completeness

*For any* expected timestamp sequence and any received sequence with gaps, the gap detection algorithm must identify every missing timestamp — no gap may be silently skipped.

**Validates: Requirements 2.4**

---

### Property 4: Linear Interpolation Correctness

*For any* two OHLCV candles as endpoints A and B, and any number of interpolated candles between them, each interpolated OHLCV field value must lie exactly on the linear path between A's value and B's value for that field.

**Validates: Requirements 2.5**

---

### Property 5: Score Normalization Invariant

*For any* combination of module scores (OrderFlow in [0,35], SMC in [0,30], VSA in [0,30], Context in [0,15], Bonus in [0,15]) and any regime multiplier in [0.6, 1.0], the final score computed by `min(round(raw * multiplier / 125 * 100), 100)` must always be an integer in [0, 100].

**Validates: Requirements 6.1, 6.3**

---

### Property 6: Confluence Monotonicity

*For any* two positive module scores s1 and s2, the combined score produced by the Signal_Scorer when both factors are active must be strictly greater than the score produced by either factor alone.

**Validates: Requirements 6.4**

---

### Property 7: Risk Cap Invariant

*For any* account equity, risk percentage, entry price, and stop-loss distance, the maximum possible loss computed from the position size returned by RiskManager must never exceed `equity * max_risk_pct`. This must hold for all three position sizing modes (fixed_usd, risk_pct, kelly).

**Validates: Requirements 7.1, 7.3**

---

### Property 8: Backtest Chronological Order

*For any* collection of OHLCV candles in any initial order, the Backtesting_Engine must process them in strictly ascending timestamp order, and at simulation time T, must not access any candle with timestamp greater than candles[T].timestamp.

**Validates: Requirements 8.6, 5.1**

---

### Property 9: Slippage Application Correctness

*For any* fill price and slippage percentage in [0.0005, 0.001], the actual fill price applied by the Backtesting_Engine must equal `fill_price * (1 + slippage_pct)` for long entries and `fill_price * (1 - slippage_pct)` for short entries.

**Validates: Requirements 8.2**

---

### Property 10: Win Rate Formula Invariant

*For any* list of closed TradeResult objects, the win rate computed by the Backtesting_Engine must equal `count(result == 'win') / len(results)` and must always be a value in [0.0, 1.0].

**Validates: Requirements 9.2**

---

### Property 11: Sharpe Ratio Formula Invariant

*For any* list of daily returns with non-zero standard deviation, the Sharpe Ratio computed by the Backtesting_Engine must equal `mean(returns) / std(returns) * sqrt(365)`.

**Validates: Requirements 9.3**

---

### Property 12: Regime Output Validity

*For any* valid OHLCV DataFrame (1h and 15m), the Regime_Detector must always return exactly one of the four valid states: TRENDING, RANGING, PARABOLIC, or CHOPPY — never null, never an undefined state.

**Validates: Requirements 13.1**

---

### Property 13: PARABOLIC Short Suppression

*For any* OHLCV data where the current ATR(14) on 15m exceeds 3× the 20-period rolling average ATR(14), the Signal_Scorer must suppress all Short signals (return IGNORE for any short direction signal) and the regime multiplier must equal 0.6.

**Validates: Requirements 13.4, 13.5**

---

### Property 14: Pearson Correlation Bounds

*For any* two price series of length >= 2, the Pearson correlation coefficient computed by the Correlation_Manager must always be in the range [-1.0, 1.0].

**Validates: Requirements 14.1**

---

### Property 15: Portfolio Heat Summation

*For any* set of open positions with associated risk percentages, the Portfolio_Heat value returned by the Correlation_Manager must equal exactly the sum of all individual position risk percentages.

**Validates: Requirements 14.6**

---

### Property 16: Portfolio Heat Enforcement

*For any* portfolio state where the current Portfolio_Heat is greater than or equal to the configured limit, the Risk_Manager must reject every new signal regardless of its score, asset, or direction.

**Validates: Requirements 14.7**

---

### Property 17: Signal Log Completeness

*For any* batch of N signals generated by the system (regardless of their ALERT/WATCH/IGNORE classification or user action), exactly N Signal_Log entries must be written to persistent storage.

**Validates: Requirements 17.1**

---

### Property 18: Signal Card Required Fields

*For any* Signal with classification ALERT, the Signal_Card payload produced by the alert builder must contain all required fields: asset, direction, final_score, entry_price, stop_loss, take_profit_1, take_profit_2, gross_rr, net_rr, score_breakdown (with all five sub-scores), regime, and expires_at_candle.

**Validates: Requirements 18.1**

---

### Property 19: Testnet Safety Enforcement

*For any* configuration where `exchange.testnet` is not explicitly set to `false`, the Trade_Executor must route all order submissions to the exchange sandbox/testnet environment and must never call any live trading endpoint.

**Validates: Requirements 19.8, 19.9**

---

### Property 20: Config Validation Completeness

*For any* config.yaml with any required parameter removed or set to an invalid type or out-of-range value, the Config_System must raise a descriptive error that includes the parameter name, expected type or range, and received value — before any module is initialized or any data is fetched.

**Validates: Requirements 15.10, 12.6**

---

## Testing Strategy

### Dual Testing Approach

The system uses both unit/example-based tests and property-based tests for comprehensive coverage.

**Unit Tests** focus on:
- Specific examples demonstrating correct behavior
- Integration points between components
- Edge cases and error conditions

**Property Tests** focus on:
- Universal properties that hold for all valid inputs
- Comprehensive input coverage through randomization (minimum 100 iterations per property)

### Property-Based Testing Library

**Choice:** `hypothesis` (Python) — the standard PBT library for Python, actively maintained, integrates with pytest.

```python
# Example property test structure
from hypothesis import given, settings
from hypothesis import strategies as st

@given(
    of_score=st.floats(min_value=0, max_value=35),
    smc_score=st.floats(min_value=0, max_value=30),
    vsa_score=st.floats(min_value=0, max_value=30),
    ctx_score=st.floats(min_value=0, max_value=15),
    bonus=st.floats(min_value=0, max_value=15),
    multiplier=st.floats(min_value=0.6, max_value=1.0),
)
@settings(max_examples=100)
def test_score_normalization_invariant(of_score, smc_score, vsa_score,
                                        ctx_score, bonus, multiplier):
    # Feature: crypto-trading-system, Property 5: Score Normalization Invariant
    raw = of_score + smc_score + vsa_score + ctx_score + bonus
    final = min(round(raw * multiplier / 125 * 100), 100)
    assert 0 <= final <= 100
    assert isinstance(final, int)
```

### Property Test Configuration

Each property test must:
- Run minimum **100 iterations** (configured via `@settings(max_examples=100)`)
- Reference its design property via comment: `# Feature: crypto-trading-system, Property N: <text>`
- Be implemented as a single `@given`-decorated test function per property

### Unit Test Coverage

| Component | Test Type | Key Scenarios |
|-----------|-----------|---------------|
| Indicator functions | Unit + Property | Correct values, NaN for insufficient data, no future access |
| Signal Scorer | Unit + Property | Score normalization, regime multiplier application |
| Regime Detector | Unit | All 4 state transitions, threshold boundaries |
| Risk Manager | Unit + Property | Position sizing formula, limit enforcement |
| Config System | Unit | Missing params, invalid types, hot-reload |
| Strategy Registry | Unit | Registration, loading, missing strategy error |
| Backtesting Engine | Unit + Property | Chronological order, fee/slippage application |
| Trade Executor | Unit (mocked) | Testnet enforcement, retry logic, SL/TP placement |

### Integration Tests

| Scenario | Coverage |
|----------|----------|
| Full signal pipeline (WS → Redis → Celery → Dashboard) | End-to-end data flow |
| Backtest run with walk-forward | Req 10 |
| Config hot-reload | Req 15.11 |
| Testnet order execution | Req 19.8 |

---

## Design Decisions

### 1. Redis + Celery for Async Signal Processing

**Decision:** Use Redis as the central buffer and Celery for signal scoring workers, completely decoupled from the WebSocket tick writers.

**Rationale:** The core problem is that cumulative delta computation requires processing 1,000+ ticks/second for BTC. If signal scoring runs in the same thread as the WebSocket handler, the handler blocks and drops ticks, corrupting the delta calculation. By separating the WS tick writer (asyncio, < 0.1ms/tick) from the Celery scorer (triggered on candle close), we guarantee zero tick loss and accurate delta values.

**Alternative considered:** Single-threaded asyncio pipeline — rejected because scoring (ATR, ADX, OB detection, FVG scan) takes 50–200ms per candle, which would block the WS handler.

**Satisfies:** Requirement 2 (data accuracy), Requirement 6 (signal scoring)

### 2. Plugin Pattern for Strategies

**Decision:** Decorator-based `@StrategyRegistry.register("name")` plugin pattern.

**Rationale:** Adding a new strategy requires creating one file and adding one decorator — no changes to existing code, no registry file edits, no config schema changes. This directly satisfies the open/closed principle and Requirement 16.5.

**Alternative considered:** Config-driven class loading via `importlib` — more complex, harder to type-check, no benefit over the decorator pattern.

**Satisfies:** Requirement 16.2, 16.5

### 3. Single config.yaml with Hot-Reload

**Decision:** All parameters in one `config.yaml` with runtime hot-reload via `ConfigSystem.reload()`.

**Rationale:** A single source of truth eliminates parameter drift between modules. Hot-reload (Req 15.11) allows threshold tuning (ADX, ATR multiplier, score thresholds) without restarting the process, which is critical during live trading sessions.

**Satisfies:** Requirement 15

### 4. Closed-Candle-Only Signal Generation

**Decision:** Strict enforcement that strategies only access `ohlcv[:T+1]` — any access to `ohlcv[T+1:]` raises `LookAheadBiasError` at runtime.

**Rationale:** Look-ahead bias is the most common cause of inflated backtest results. Runtime enforcement (not just convention) catches violations during development and in backtesting, ensuring backtest metrics are trustworthy.

**Satisfies:** Requirement 5.1–5.4

### 5. Regime Detection Priority Order

**Decision:** PARABOLIC check takes priority over TRENDING/RANGING/CHOPPY.

**Rationale:** A parabolic move (ATR > 3× rolling average) is a market emergency state where normal signal scoring is unreliable. Applying a 0.6 multiplier and suppressing Short signals protects against entering counter-trend shorts during violent upward moves. This check must run before ADX-based classification because ADX can be high during parabolic moves.

**Satisfies:** Requirement 13.4, 13.5

### 6. Normalized Score Formula

**Decision:** `final = min(round(raw * multiplier / 125 * 100), 100)` where 125 is the theoretical maximum raw score.

**Rationale:** The denominator 125 = 35 + 30 + 30 + 15 + 15 (max of all modules + bonus). Dividing by 125 before multiplying by 100 ensures the score is always in [0, 100] regardless of which modules fire. The `min(..., 100)` cap handles floating-point edge cases.

**Satisfies:** Requirement 6.1, 6.3

### 7. PostgreSQL for Trade Journal, Redis for Real-Time State

**Decision:** PostgreSQL for persistent trade/signal records; Redis for ephemeral real-time state (OHLCV buffers, delta, OB snapshots, pub/sub).

**Rationale:** Trade Journal and Signal_Log require ACID guarantees, complex queries (analytics, benchmark tables), and long-term retention. Redis provides sub-millisecond reads/writes for the hot path (tick writing, candle scoring) and pub/sub for real-time dashboard updates. Using PostgreSQL for real-time state would add 5–50ms latency per tick.

**Satisfies:** Requirement 17, 18.10

### 8. React (not Next.js) for Dashboard

**Decision:** React + Vite + TypeScript for the frontend.

**Rationale:** The dashboard is a single-page application with no SEO requirements. WebSocket connections are long-lived and stateful — SSR would complicate connection management. React + Vite provides faster development iteration and simpler deployment as static files served by FastAPI or nginx.

**Satisfies:** Requirement 18

### 9. REST Polling vs WebSocket for OHLCV

**Decision:** Use REST polling (ccxt `fetch_ohlcv`) instead of WebSocket for OHLCV ingestion.

**Rationale:** The current implementation uses `OHLCVService` with REST polling at configurable intervals (15m candles polled every 60s, 4H every 300s, Daily every 3600s). This avoids WebSocket connection management complexity and is sufficient for the 15m trigger timeframe. WebSocket ingestion (Req 2.1–2.6) is planned but not yet implemented.

**Trade-off:** REST polling introduces up to 60s latency on candle close detection for 15m candles. Acceptable for semi-auto trading where the user has 15 minutes to confirm.

**Satisfies:** Requirement 2 (partially — REST polling instead of WebSocket)

### 10. ScoringService Threading Model

**Decision:** `ScoringService` uses `asyncio + threading` (not Celery) for scoring trigger.

**Rationale:** The scoring trigger subscribes to `candle_close` Redis pub/sub in a background thread (`threading.Thread`), then dispatches scoring coroutines via `asyncio.run_coroutine_threadsafe()`. This avoids Celery worker setup complexity while maintaining non-blocking behavior. The `OHLCVService`, `OrderBookService`, and `DeltaService` are all async classes orchestrated by `asyncio.gather()` in `main.py`.

**Alternative considered:** Celery workers — more complex setup, requires broker configuration, overkill for single-machine deployment.

**Satisfies:** Requirement 6 (signal scoring pipeline)

### 11. MTF 3-Scenario Filter Rationale

**Decision:** Three discrete scenarios (A/B/C) for MTF alignment rather than a continuous multiplier.

**Rationale:**
- **Scenario A** (4H aligned): Full confidence — no size reduction, +10 score bonus rewards alignment
- **Scenario B** (4H ranging): Partial confidence — 50% size reduction and -10 score penalty signals uncertainty without blocking
- **Scenario C** (4H opposing with ADX > 25): Zero confidence — hard block prevents entering against a confirmed strong trend, regardless of 15m score

The hard block in Scenario C is intentional: a 15m signal scoring 90/100 against a strong 4H downtrend is more likely a dead-cat bounce than a genuine reversal. The ADX > 25 requirement prevents blocking during sideways 4H markets that happen to be slightly bearish.

**Satisfies:** Requirement 20
