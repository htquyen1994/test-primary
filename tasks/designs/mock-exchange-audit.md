# Design: Mock Exchange Service + Audit System

> **Phase:** Algorithm Validation
> **Status:** Draft
> **Created:** 2026-05-11
> **Requirements:** `tasks/requirements/mock-exchange-audit.md`

---

## 1. Architecture Overview

```
backend-workspace (port 8000)
  ScoringService
    │ candle_close (Redis pub/sub)
    │
    ├─► AuditClient.emit_signal_snapshot()
    │       └─► Redis RPUSH audit:pending_snapshots   [fire-and-forget]
    │
    └─► (SIGNAL) _publish_alert() → Redis alerts:channel
             └─► TradeExecutor.execute(ExchangeInterface)
                     └─► MockExchangeHttpClient.create_order()   ← in backend-workspace
                             └─► HTTP POST http://{mock_exchange.url}/exchange/orders

mock-exchange-workspace (port 8001)
  ├── FastAPI: /exchange/* routes
  │       └─► MockExchange (server-side, implements ExchangeInterface in-process)
  │               └─► OrderManager → mock_orders, mock_positions (DB)
  │
  ├── AuditConsumer (Redis BLPOP audit:pending_snapshots)
  │       └─► SignalAuditor.process_snapshot()
  │               └─► signal_audit_log (DB)
  │               └─► schedule T1/T4/T16 price checks
  │
  ├── PriceFeed
  │       ├── Subscribe Redis candle_close → SL/TP check per position
  │       └── Poll ticker 5s → unrealized PnL update only
  │
  ├── TradeAuditor (triggered by position close)
  │       └─► trade_audit_log (DB)
  │
  └── AnalysisEngine (on-demand)
          └─► Q1-Q10 + tuning recommendations

frontend-workspace (port 5173)
  /audit/* → query mock-exchange-workspace API
```

**Hai components khác nhau:**

| Component | Location | Role |
|---|---|---|
| `MockExchangeHttpClient` | `backend-workspace/exchange/mock_http_client.py` | HTTP adapter, implements `ExchangeInterface`, injected vào `TradeExecutor` |
| `MockExchange` | `mock-exchange-workspace/exchange/mock_exchange.py` | Server-side implementation, implements `ExchangeInterface` in-process, called bởi FastAPI routes |

---

## 2. P0 Pre-conditions

Các thay đổi này phải complete trước khi bắt đầu implement mock-exchange-workspace.

### P0-1: Refactor `TradeExecutor._submit_with_retry()` + Tạo `MockExchangeHttpClient`

**Files:**
- `workspace/backend-workspace/trade/executor.py:152-215` — refactor
- `workspace/backend-workspace/exchange/mock_http_client.py` — file mới

**Bước 1:** Refactor `_submit_with_retry()` để dùng `ExchangeInterface`. Hiện tại gọi ccxt raw methods. Cần chuyển sang `ExchangeInterface`:

```python
# BEFORE (ccxt raw):
order = await self._exchange.create_limit_order(asset, side, amount, price)
order = await self._exchange.create_order(asset, "stop_loss_limit", side, amount, price, {...})
order = await self._exchange.create_market_order(asset, side, amount)

# AFTER (ExchangeInterface):
from trading_core.exchange.interface import OrderSide, OrderType

order = await self._exchange.create_order(
    symbol=asset,
    side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
    order_type=OrderType.LIMIT,
    amount=amount,
    price=price,
    client_order_id=client_order_id,
)
# stop_loss:
order = await self._exchange.create_order(
    symbol=asset,
    side=OrderSide.SELL if direction == "long" else OrderSide.BUY,
    order_type=OrderType.STOP_LOSS,
    amount=amount,
    price=stop_loss_price,
)
# take_profit similarly with OrderType.TAKE_PROFIT
```

Return value cần update: `Order.order_id` thay vì `order.get("id")`.

**Bước 2:** Tạo `MockExchangeHttpClient` trong `backend-workspace`:

```python
# backend-workspace/exchange/mock_http_client.py
import httpx
from trading_core.exchange.interface import (
    ExchangeInterface, Order, Position, AccountState, OrderSide, OrderType
)

class MockExchangeHttpClient(ExchangeInterface):
    """
    HTTP adapter: translates ExchangeInterface calls to REST requests
    to mock-exchange-workspace. Injected into TradeExecutor in mock mode.
    """
    is_mock = True
    exchange_name = "mock_http"

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def create_order(self, symbol, side, order_type, amount, price,
                           client_order_id=None, metadata=None) -> Order:
        resp = await self._client.post(f"{self._base_url}/exchange/orders", json={
            "symbol": symbol, "side": side.value,
            "order_type": order_type.value, "amount": amount, "price": price,
            "client_order_id": client_order_id,
        })
        resp.raise_for_status()
        return Order(**resp.json())

    async def cancel_order(self, order_id, symbol) -> bool: ...
    async def get_order(self, order_id, symbol) -> Order: ...
    async def get_open_orders(self, symbol=None) -> list: ...
    async def get_position(self, symbol) -> Position: ...
    async def get_all_positions(self) -> list: ...
    async def get_account_state(self) -> AccountState: ...
    async def get_current_price(self, symbol) -> float: ...
```

**Bước 3:** Thêm `mock_exchange` section vào `config.yaml`:

```yaml
mock_exchange:
  enabled: false
  url: "http://localhost:8001"
  timeout_seconds: 5
```

**Bước 4:** Inject `MockExchangeHttpClient` tại app startup:

```python
# backend-workspace/main.py (hoặc app entry point)
if config.mock_exchange.enabled:
    from exchange.mock_http_client import MockExchangeHttpClient
    exchange = MockExchangeHttpClient(base_url=config.mock_exchange.url)
else:
    exchange = ccxt_exchange  # live/testnet như hiện tại

trade_executor = TradeExecutor(exchange=exchange, config=config)
```

### P0-2: Audit Hook tại mọi exit point của `_run_cycle()`

**File:** `workspace/backend-workspace/engine/scoring_service.py`

Pattern hiện tại có 2 loại exit:
1. Filter block early return (line ~279)
2. Normal exit sau khi publish alert (cuối function)

Cần capture trạng thái tại mỗi exit. Approach: dùng local `_audit_state` dict được populate dần, emit trước mỗi return:

```python
async def _run_cycle(self, symbol: str, timeframe: str) -> None:
    _audit = {
        "symbol": symbol, "timeframe": timeframe,
        "timestamp_candle_close": datetime.now(timezone.utc).isoformat(),
        "signal_result": "NO_SIGNAL", "final_score": 0,
        "blocking_reason": None, "blocking_detail": None,
    }

    # ... existing code ...

    for f in active_filters:
        result = f.apply(filter_context)
        if not result.passed:
            _audit["blocking_reason"] = _map_filter_to_reason(f.name)
            _audit["blocking_detail"] = result.block_reason
            _emit_audit(_audit)   # ← emit trước early return
            publish_log(r, log_entry)
            return

    # ... scoring ...
    _audit["final_score"] = score.final_score
    _audit["score_breakdown"] = {...}
    _audit["signal_result"] = "SIGNAL" if score.classification == "ALERT" else "NO_SIGNAL"
    # ... populate remaining fields ...

    _emit_audit(_audit)  # ← emit tại exit bình thường

def _emit_audit(self, audit_data: dict) -> None:
    if not self._audit_enabled:
        return
    try:
        r = self._get_redis()
        r.rpush("audit:pending_snapshots", json.dumps(audit_data))
    except Exception as exc:
        logger.warning("Audit emit failed (non-blocking): %s", exc)

def _map_filter_to_reason(self, filter_name: str) -> str:
    return {
        "mtf_bias": "MTF_BLOCK",
        "btc_guard": "BTC_GUARD",
        "circuit_breaker": "CB_LOCKED",
        "daily_bias": "REGIME",
    }.get(filter_name, "LOW_SCORE")
```

### P0-3: `_persist_signal()` return signal_id

**File:** `workspace/backend-workspace/engine/scoring_service.py:528-560`

```python
def _persist_signal(self, ...) -> Optional[str]:
    """Returns DB-generated signal_id, or None on failure."""
    try:
        # ... existing code ...
        signal_log_id = write_signal_log(signal_obj, db)  # write_signal_log must return ID
        db.close()
        return str(signal_log_id)
    except Exception as exc:
        logger.warning("Failed to persist signal_log: %s", exc)
        return None
```

`write_signal_log` cần update để return inserted row ID.

---

## 3. Data Flow Chi tiết

### Flow 1: Signal capture (mọi cycle)
```
ScoringService._run_cycle()
  → populate _audit dict
  → (filter block?) emit to Redis audit:pending_snapshots
  → (normal?) _persist_signal() → returns signal_id
  → populate _audit["signal_id"] = signal_id
  → emit to Redis audit:pending_snapshots

AuditConsumer (mock-exchange-workspace)
  → BLPOP audit:pending_snapshots (blocking pop, no spin)
  → SignalAuditor.process_snapshot(data)
  → INSERT signal_audit_log (status=PENDING)
  → Schedule T1/T4/T16 jobs
```

### Flow 2: Trade execution
```
TradeExecutor.execute(MockExchangeHttpClient)       ← injected, lives in backend-workspace
  → MockExchangeHttpClient.create_order()
        → HTTP POST http://{mock_exchange.url}/exchange/orders
              → FastAPI route /exchange/orders      ← lives in mock-exchange-workspace
                    → MockExchange.create_order()   ← server-side, in-process
                          → OrderManager.accept_order()
                          → INSERT mock_orders (status=OPEN)
                          → INSERT mock_positions
                    ← returns Order JSON

  AuditClient.emit_trade_opened(signal_id, order_id)
  → Redis RPUSH audit:pending_snapshots {type: "trade_opened", ...}
  → AuditConsumer → trade_audit_log INSERT (status=PENDING)
```

### Flow 3: SL/TP fill (mỗi candle close)
```
Redis candle_close event
  → PriceFeed.on_candle_close(symbol, ohlcv)
  → PositionTracker.check_all_positions(symbol, ohlcv)
  → position: low ≤ SL? → SL fill
  → position: high ≥ TP1? → TP1 fill
  → position: high ≥ TP2? → TP2 fill
  → UPDATE mock_positions (status=CLOSED)
  → UPDATE mock_orders (status=FILLED, fill_price=...)
  → UPDATE mock_account (balance +/- PnL)
  → INSERT mock_account_history
  → TradeAuditor.analyze_closed_trade()
  → UPDATE trade_audit_log (outcome, pnl, verdict)
  → UPDATE signal_audit_log (audit_status=PARTIAL)
```

### Flow 4: T1/T4/T16 backfill
```
SignalAuditor startup:
  → query signal_audit_log WHERE audit_status IN ('PENDING', 'PARTIAL')
  → for each pending signal:
      elapsed = now - timestamp_candle_close
      if elapsed ≥ 15m AND price_at_T1 IS NULL:
          fetch ohlcv[T1 candle] from ccxt
          UPDATE signal_audit_log SET price_at_T1 = ...
      if elapsed ≥ 1h AND price_at_T4 IS NULL:
          (similar)
      if elapsed ≥ 4h AND price_at_T16 IS NULL:
          (similar)
          compute MFE, MAE, would_have_hit_sl/tp
          UPDATE audit_status = COMPLETE
```

---

## 4. Component Design

### 4.1a MockExchangeHttpClient (`backend-workspace/exchange/mock_http_client.py`)

HTTP adapter, implements `ExchangeInterface`, injected vào `TradeExecutor` khi `mock_exchange.enabled = true`. Không chứa bất kỳ business logic — chỉ translate interface calls thành HTTP requests.

- Dùng `httpx.AsyncClient` (async, compatible với asyncio)
- Raise `httpx.HTTPStatusError` nếu mock-exchange-workspace trả về 4xx/5xx → TradeExecutor xử lý như exchange error bình thường
- Timeout configurable qua `mock_exchange.timeout_seconds`

### 4.1b MockExchange (`mock-exchange-workspace/exchange/mock_exchange.py`)

Server-side implementation, implements `ExchangeInterface` để tái sử dụng trong tests. Được gọi bởi FastAPI `/exchange/*` routes — không exposed trực tiếp ra ngoài.

```python
class MockExchange(ExchangeInterface):
    is_mock = True
    exchange_name = "mock"

    def __init__(self, db_session, account_config) -> None:
        self._db = db_session
        self._initial_balance = account_config.initial_balance_usd

    async def create_order(self, symbol, side, order_type, amount, price, ...) -> Order:
        # Immediate fill for MARKET orders
        # LIMIT/SL/TP: store as OPEN, filled when PriceFeed triggers
        # Returns Order with status OPEN

    async def get_position(self, symbol) -> Optional[Position]:
        # Query mock_positions table

    async def get_account_state(self) -> AccountState:
        # Query mock_account table (single-row, always up to date)

    async def get_current_price(self, symbol) -> float:
        # Latest entry from price_snapshots, fallback to ccxt public ticker
```

Không cần ccxt API key — chỉ public endpoint.

### 4.2 PriceFeed (`exchange/price_feed.py`)

Hai modes:
- **Candle close mode** (SL/TP check): subscribe Redis `candle_close`, gọi `PositionTracker.check_positions()`
- **Ticker poll mode** (unrealized PnL): asyncio task, poll ccxt ticker mỗi 10s, publish price update qua WebSocket

### 4.3 SignalAuditor (`audit/signal_auditor.py`)

Chạy như background coroutine, consume từ Redis:

```python
class SignalAuditor:
    async def run(self):
        await asyncio.gather(
            self._consume_loop(),     # BLPOP audit:pending_snapshots
            self._scheduler_loop(),   # APScheduler for T* jobs
            self._backfill_on_start() # One-time startup routine
        )

    async def _process_snapshot(self, data: dict):
        # INSERT or UPDATE signal_audit_log
        # Schedule T1/T4/T16 jobs via APScheduler

    async def _fetch_price_at_T(self, signal_audit_id, target_ts: datetime):
        # Fetch OHLCV from ccxt for candle containing target_ts
        # UPDATE signal_audit_log price_at_T*
        # If T16 done: compute MFE/MAE, would_have_hit_*, set COMPLETE
```

### 4.4 AnalysisEngine (`audit/analysis_engine.py`)

Pure query engine — không có side effects:

```python
class AnalysisEngine:
    def get_performance_report(self, filters: dict) -> PerformanceReport:
        # Returns answers to Q1-Q10 + confidence metadata

    def get_confidence_level(self, n_trades: int) -> ConfidenceLevel:
        if n_trades < 10: return ConfidenceLevel.INSUFFICIENT
        if n_trades < 20: return ConfidenceLevel.VERY_LOW
        if n_trades < 30: return ConfidenceLevel.LOW
        if n_trades < 50: return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.HIGH

    def get_tuning_recommendations(self) -> TuningReport:
        # Only generate when confidence >= LOW
        # Includes confidence intervals for each recommendation
```

---

## 5. Database Schema

```sql
-- mock-exchange-workspace database

-- Mock Exchange tables

CREATE TABLE mock_orders (
    id              TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type      TEXT NOT NULL CHECK (order_type IN ('market', 'limit', 'stop_loss', 'take_profit')),
    amount          REAL NOT NULL,
    price           REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','OPEN','FILLED','PARTIAL','CANCELLED','REJECTED','EXPIRED')),
    filled_amount   REAL NOT NULL DEFAULT 0.0,
    fill_price      REAL,
    fee             REAL NOT NULL DEFAULT 0.0,
    client_order_id TEXT,
    signal_id       TEXT,  -- soft ref to backend signal_log
    created_at      TEXT NOT NULL,
    filled_at       TEXT
);

CREATE TABLE mock_positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    entry_price     REAL NOT NULL,
    amount          REAL NOT NULL,
    leverage        INTEGER NOT NULL DEFAULT 1,
    stop_loss       REAL NOT NULL,
    take_profit_1   REAL NOT NULL,
    take_profit_2   REAL,
    status          TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    entry_order_id  TEXT REFERENCES mock_orders(id),
    signal_id       TEXT,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT,
    exit_price      REAL,
    exit_reason     TEXT CHECK (exit_reason IN ('SL_HIT','TP1_HIT','TP2_HIT','MANUAL_CLOSE','EXPIRED'))
);

CREATE TABLE mock_account (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    balance_usd          REAL NOT NULL,
    equity_usd           REAL NOT NULL,
    used_margin          REAL NOT NULL DEFAULT 0.0,
    total_realized_pnl   REAL NOT NULL DEFAULT 0.0,
    total_fees_paid      REAL NOT NULL DEFAULT 0.0,
    updated_at           TEXT NOT NULL
);

CREATE TABLE mock_account_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    balance_usd     REAL NOT NULL,
    equity_usd      REAL NOT NULL,
    trade_id        INTEGER REFERENCES mock_positions(id),
    event           TEXT NOT NULL,  -- 'trade_opened', 'trade_closed', 'fee_charged'
    pnl_delta       REAL NOT NULL DEFAULT 0.0,
    recorded_at     TEXT NOT NULL
);

-- Audit tables

CREATE TABLE signal_audit_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id               TEXT,  -- soft ref to backend signal_log (no FK constraint)
    symbol                  TEXT NOT NULL,
    timeframe               TEXT NOT NULL,
    timestamp_candle_close  TEXT NOT NULL,

    -- Signal result
    signal_result           TEXT NOT NULL CHECK (signal_result IN ('SIGNAL', 'NO_SIGNAL')),
    final_score             REAL NOT NULL DEFAULT 0,
    score_breakdown         TEXT,  -- JSON: {of, smc, vsa, ctx, bonus}

    -- Filter state
    regime                  TEXT,
    regime_multiplier       REAL,
    mtf_scenario            TEXT,
    mtf_4h_bias             TEXT,
    daily_bias              TEXT,
    btc_guard_active        INTEGER NOT NULL DEFAULT 0,
    circuit_breaker_locked  INTEGER NOT NULL DEFAULT 0,
    blocking_reason         TEXT CHECK (blocking_reason IN
                                ('LOW_SCORE','MTF_BLOCK','CB_LOCKED','BTC_GUARD','REGIME')),
    blocking_detail         TEXT,

    -- Technical params at signal time
    entry_price_proposed    REAL,
    sl_proposed             REAL,
    tp1_proposed            REAL,
    tp2_proposed            REAL,
    atr_value               REAL,
    adx_value               REAL,
    delta_value             REAL,
    delta_threshold         REAL,
    funding_rate            REAL,
    ob_available            INTEGER NOT NULL DEFAULT 0,
    poc_value               REAL,
    htf_bias_1h             TEXT,

    -- Forward prices (filled by SignalAuditor)
    price_at_T1             REAL,  -- price 15m after candle_close
    price_at_T4             REAL,  -- price 1h after
    price_at_T16            REAL,  -- price 4h after
    max_favorable_excursion REAL,
    max_adverse_excursion   REAL,
    would_have_hit_sl       INTEGER,
    would_have_hit_tp1      INTEGER,
    would_have_hit_tp2      INTEGER,

    -- Audit lifecycle
    audit_status            TEXT NOT NULL DEFAULT 'PENDING'
                                CHECK (audit_status IN ('PENDING','PARTIAL','COMPLETE')),
    audit_completed_at      TEXT,
    created_at              TEXT NOT NULL
);

CREATE TABLE trade_audit_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id                INTEGER NOT NULL REFERENCES mock_positions(id),
    signal_audit_id         INTEGER REFERENCES signal_audit_log(id),

    -- Execution quality
    entry_price_proposed    REAL NOT NULL,
    entry_price_actual      REAL NOT NULL,
    sl_proposed             REAL NOT NULL,
    sl_actual               REAL NOT NULL,
    tp1_proposed            REAL NOT NULL,
    tp1_actual              REAL NOT NULL,

    -- Outcome
    outcome                 TEXT NOT NULL
                                CHECK (outcome IN ('SL_HIT','TP1_HIT','TP2_HIT','MANUAL_CLOSE','EXPIRED')),
    exit_price              REAL,
    exit_timestamp          TEXT,
    hold_duration_minutes   REAL,
    gross_pnl               REAL,
    net_pnl                 REAL,
    pnl_pct                 REAL,

    -- Post-trade analysis
    sl_hit_reason           TEXT CHECK (sl_hit_reason IN ('NOISE','TREND_REVERSAL','NEWS_EVENT','BTC_SPIKE')),
    signal_quality_verdict  TEXT CHECK (signal_quality_verdict IN
                                ('TRUE_POSITIVE','FALSE_POSITIVE','PREMATURE_SL')),
    -- TRUE_POSITIVE: TP hit
    -- FALSE_POSITIVE: SL hit, price continued against direction
    -- PREMATURE_SL: SL hit but price recovered and would have hit TP

    audit_notes             TEXT,
    audit_status            TEXT NOT NULL DEFAULT 'PENDING'
                                CHECK (audit_status IN ('PENDING','ANALYZED','REVIEWED')),
    analyzed_at             TEXT
);

CREATE TABLE no_signal_audit_log (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_audit_id             INTEGER NOT NULL REFERENCES signal_audit_log(id),

    score_at_decision           REAL NOT NULL,
    score_gap                   REAL NOT NULL,  -- 75 - score
    blocking_reason             TEXT NOT NULL,
    blocking_detail             TEXT,

    -- Counterfactual
    hypothetical_entry_price    REAL,
    hypothetical_sl             REAL,
    hypothetical_tp1            REAL,
    would_have_been_profitable  INTEGER,
    hypothetical_pnl_pct        REAL,
    missed_opportunity          INTEGER,  -- True if would_have_hit_tp1

    audit_status                TEXT NOT NULL DEFAULT 'PENDING'
                                    CHECK (audit_status IN ('PENDING','COMPLETE')),
    completed_at                TEXT
);

CREATE TABLE price_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      REAL NOT NULL,
    timestamp   TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(symbol, timeframe, timestamp)
);

-- Indexes
CREATE INDEX idx_signal_audit_symbol_ts ON signal_audit_log(symbol, timestamp_candle_close);
CREATE INDEX idx_signal_audit_status ON signal_audit_log(audit_status);
CREATE INDEX idx_signal_audit_result ON signal_audit_log(signal_result);
CREATE INDEX idx_trade_audit_signal ON trade_audit_log(signal_audit_id);
CREATE INDEX idx_no_signal_missed ON no_signal_audit_log(missed_opportunity);
CREATE INDEX idx_mock_positions_status ON mock_positions(status, symbol);
CREATE INDEX idx_price_snapshots_lookup ON price_snapshots(symbol, timeframe, timestamp);
```

---

## 6. API Contracts

### Exchange API (implements ExchangeInterface)

```
POST   /exchange/orders              → create_order()
DELETE /exchange/orders/{id}         → cancel_order()
GET    /exchange/orders/{id}         → get_order()
GET    /exchange/orders              → get_open_orders(?symbol=)
GET    /exchange/positions/{symbol}  → get_position()
GET    /exchange/positions           → get_all_positions()
GET    /exchange/account             → get_account_state()
GET    /exchange/price/{symbol}      → get_current_price()
```

### Audit API

```
POST /audit/signal-snapshot            → consume by AuditClient (internal, Redis preferred)
GET  /audit/signals                    → ?page=&limit=&symbol=&regime=&result=&status=&from=&to=
GET  /audit/signals/{id}               → signal detail
GET  /audit/trades                     → ?page=&limit=&outcome=&verdict=&from=&to=
GET  /audit/trades/{id}                → trade detail
GET  /audit/no-signals                 → ?page=&limit=&missed_only=true
GET  /audit/analytics/performance      → Q1-Q10 answers + confidence metadata
GET  /audit/analytics/tuning           → tuning recommendations (with confidence level)
WS   /ws/positions                     → real-time position updates (price, unrealized PnL)
WS   /ws/audit-feed                    → real-time: new signal, trade opened/closed events
```

### Key Response Schemas

**`GET /audit/analytics/performance`:**
```json
{
  "sample_size": 42,
  "confidence": "medium",
  "confidence_note": "Based on 42 trades. Results are directional.",
  "win_rate": { "value": 0.571, "ci_95": [0.421, 0.714] },
  "win_rate_by_regime": { "TRENDING": 0.71, "RANGING": 0.40, "CHOPPY": 0.33 },
  "win_rate_by_mtf_scenario": { "A": 0.75, "B": 0.55, "C": 0.38 },
  "win_rate_by_score_bucket": { "75-79": 0.44, "80-84": 0.60, "85+": 0.78 },
  "optimal_threshold_suggestion": 80,
  "sl_hit_reasons": { "NOISE": 0.45, "TREND_REVERSAL": 0.30, "BTC_SPIKE": 0.25 },
  "missed_opportunity_rate": 0.23,
  "questions": { "Q1": "...", "Q2": "...", ... }
}
```

---

## 7. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Exchange injection | `MockExchangeHttpClient` (HTTP adapter) trong backend-workspace | Separate service = isolation; backend không import code từ mock-exchange-workspace |
| SL/TP trigger | OHLCV candle close + low/high | Poll ticker misses intra-candle spikes; candle_close reuses existing Redis infra |
| Audit transport | Redis list (`audit:pending_snapshots`) | HTTP fire-and-forget = silent data loss; Redis buffer survives service restart |
| T* timing base | `timestamp_candle_close` | Measures signal prediction quality, not execution quality |
| MFE/MAE data source | OHLCV high/low | Tick data not needed for 15m TF validation |
| Cross-DB FK | Soft reference (application-level only) | Backend and mock-exchange have separate DBs |
| Confidence levels | Progressive (10/20/30/50) | Lock at ≥30 makes data unavailable too long; progressive + CI is more informative |
| Funding cost | Entry-rate × hold_periods (approximation) | Funding rate history adds complexity; approximation acceptable for algorithm validation |

---

## 8. Implementation Order

```
Phase A: P0 Pre-conditions (backend-workspace)
  A1. Refactor TradeExecutor._submit_with_retry() → ExchangeInterface
  A2. _persist_signal() return signal_id
  A3. Audit hook at all _run_cycle() exit points + AuditClient
  A4. Tạo MockExchangeHttpClient + config mock_exchange.{enabled,url} + injection tại startup

Phase B: mock-exchange-workspace scaffold
  B1. Project structure + config.yaml + DB setup + migrations
  B2. MockExchange (ExchangeInterface impl) + OrderManager
  B3. PriceFeed (candle_close subscribe + ticker poll)
  B4. PositionTracker (SL/TP check logic)
  B5. mock_account init + PnL calculation

Phase C: Audit system
  C1. AuditConsumer (Redis BLPOP loop)
  C2. SignalAuditor (process_snapshot + T* scheduler + backfill)
  C3. TradeAuditor (outcome analysis + verdict)
  C4. NoSignalAuditor (counterfactual computation)
  C5. AnalysisEngine (Q1-Q10 + recommendations)

Phase D: API
  D1. FastAPI app + exchange routes
  D2. Audit routes (signals, trades, no-signals)
  D3. Analytics routes
  D4. WebSocket endpoints

Phase E: Frontend
  E1. API client (TypeScript)
  E2. AuditSignalTable + filters
  E3. SignalDetailModal
  E4. TradeAuditTable
  E5. NoSignalTable
  E6. AuditAnalyticsDashboard + charts
```
