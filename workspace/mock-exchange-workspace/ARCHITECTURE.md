# Mock Exchange Workspace — Architecture

> **Phase:** Algorithm Validation
> **Port:** 8001
> **Purpose:** Simulate a real exchange with real prices to validate scoring algorithm performance — without placing live orders.

---

## 1. Tổng quan

`mock-exchange-workspace` là một **standalone service** được inject vào `backend-workspace` thay cho ccxt exchange thật. Nó:

- Nhận lệnh từ `TradeExecutor` qua REST (như exchange thật)
- Dùng giá thật từ Binance (public endpoint, không cần API key)
- Tự động kiểm tra SL/TP khi mỗi nến đóng
- Ghi lại **mọi** scoring cycle (kể cả filter-blocked) vào audit log
- Phân tích hiệu quả mô hình qua 10 câu hỏi định lượng

---

## 2. Service Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        backend-workspace (:8000)                        │
│                                                                         │
│  ScoringService._run_cycle()                                            │
│      │                                                                  │
│      ├── emit audit snapshot ──────────────────────────────────────┐   │
│      │   (Redis RPUSH audit:pending_snapshots)                      │   │
│      │                                                              │   │
│      └── (SIGNAL) TradeExecutor.execute()                           │   │
│               └── MockExchangeHttpClient.create_order()             │   │
│                       └── HTTP POST :8001/exchange/orders ──────┐   │   │
└─────────────────────────────────────────────────────────────────│───│───┘
                                                                  │   │
                    Redis ──────────────────────────────────────┐ │   │
                      candle_close channel                      │ │   │
                      audit:pending_snapshots (list)            │ │   │
                      mock_exchange:fills (channel)             │ │   │
                      mock_exchange:pnl (channel)               │ │   │
                    └──────────────────────────────────────────┘ │   │
                                                                  │   │
┌─────────────────────────────────────────────────────────────────│───│───┐
│                    mock-exchange-workspace (:8001)               │   │   │
│                                                                  │   │   │
│  ┌─────────────────────────────────────────────────────────┐    │   │   │
│  │                      FastAPI App                        │◄───┘   │   │
│  │  /exchange/*   /audit/*   /audit/analytics/*   /ws/*   │        │   │
│  └────────────────────────┬────────────────────────────────┘        │   │
│                           │ delegates to                             │   │
│  ┌────────────────────────▼────────────────────────────────┐        │   │
│  │                    MockExchange                         │◄────────┘   │
│  │  implements ExchangeInterface                           │             │
│  │  MARKET → fill immediately                              │             │
│  │  LIMIT/SL/TP → store OPEN, fill on candle trigger       │             │
│  └────────────────────────┬────────────────────────────────┘             │
│                           │                                               │
│              ┌────────────┴───────────┐                                  │
│              ▼                        ▼                                  │
│  ┌────────────────────┐  ┌────────────────────────────────┐             │
│  │   OrderManager     │  │       SQLite DB                │             │
│  │  CRUD orders/      │  │  mock_orders                   │             │
│  │  positions/account │  │  mock_positions                │             │
│  │  PnL calculation   │  │  mock_account (singleton)      │             │
│  └────────────────────┘  │  mock_account_history          │             │
│                           │  signal_audit_log              │             │
│  ┌────────────────────┐   │  trade_audit_log               │             │
│  │  PositionTracker   │   │  no_signal_audit_log           │             │
│  │  SL/TP check on    │   │  price_snapshots               │             │
│  │  candle high/low   │   └────────────────────────────────┘             │
│  └────────────────────┘                                                  │
│                                                                          │
│  Background Tasks (asyncio)                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │   CandleFeed    │  │   AuditConsumer  │  │     TickerFeed         │  │
│  │ Sub candle_close│  │ BLPOP audit queue│  │ Poll ccxt ticker/10s   │  │
│  │ → check SL/TP   │  │ → SignalAuditor  │  │ → unrealized PnL       │  │
│  │ → PriceSnapshot │  │ → TradeAuditor   │  │ → WS broadcast         │  │
│  └─────────────────┘  └──────────────────┘  └────────────────────────┘  │
│                                                                          │
│  Audit Layer                                                             │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ SignalAuditor │  │ TradeAuditor │  │ NoSignal   │  │ Analysis    │  │
│  │ T1/T4/T16     │  │ verdict +    │  │ Auditor    │  │ Engine      │  │
│  │ MFE/MAE       │  │ sl_hit_reason│  │ counter-   │  │ Q1-Q10      │  │
│  │ APScheduler   │  │              │  │ factual    │  │ Wilson CI   │  │
│  └───────────────┘  └──────────────┘  └────────────┘  └─────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

frontend-workspace (:5173)
  /audit/*  →  query :8001/audit/* REST API
  /audit/analytics  →  query :8001/audit/analytics/*
  real-time  →  WS :8001/ws/positions + /ws/audit-feed
```

---

## 3. Data Flows

### Flow 1 — Signal Capture (mọi scoring cycle)

```
ScoringService._run_cycle()
    │
    ├─ Compute indicators, regime, filters
    │
    ├─ [FILTER BLOCK] ──► _emit_audit({blocking_reason, blocking_detail, ...})
    │       │                    │
    │       └─ return early      └─► Redis RPUSH audit:pending_snapshots
    │                                        │
    └─ [NORMAL SCORING]                      ▼
        │                          AuditConsumer.run() [BLPOP]
        ├─ _persist_signal() ──► signal_log (backend DB) ──► returns signal_id
        │
        ├─ _emit_audit({signal_id, final_score, score_breakdown,
        │               entry_price, sl, tp1, tp2, regime, ...})
        │       └─► Redis RPUSH audit:pending_snapshots
        │                    │
        └─ _publish_alert()  │
                             ▼
                   SignalAuditor.process(data)
                       │
                       ├─ INSERT signal_audit_log (status=PENDING)
                       │
                       └─ APScheduler: schedule T1 (+15m), T4 (+60m), T16 (+240m)
                               │
                               ▼ (at T16)
                       Fetch OHLCV history from ccxt
                       Compute MFE, MAE, would_have_hit_sl/tp1/tp2
                       UPDATE signal_audit_log (status=COMPLETE)
                       NoSignalAuditor: compute counterfactual
```

### Flow 2 — Trade Execution (khi signal ALERT được confirm)

```
TradeExecutor.execute(MockExchangeHttpClient)
    │
    ├─ HTTP POST /exchange/orders {LIMIT, entry_price}
    │       │
    │       ▼
    │   MockExchange.create_order()
    │       │
    │       ├─ MARKET → fill immediately, create position, deduct fee
    │       └─ LIMIT  → store as OPEN, create position skeleton
    │       ▼
    │   INSERT mock_orders (status=OPEN)
    │   INSERT mock_positions (status=OPEN, sl, tp1, tp2)
    │   UPDATE mock_account (deduct entry fee)
    │   ← returns Order {order_id, fill_price, ...}
    │
    ├─ HTTP POST /exchange/orders {STOP_LOSS, sl_price}
    │       └─► UPDATE mock_positions.stop_loss
    │
    └─ HTTP POST /exchange/orders {TAKE_PROFIT, tp1_price}
            └─► UPDATE mock_positions.take_profit_1

    AuditClient.emit_trade_opened(signal_id, order_id, ...)
        └─► Redis RPUSH audit:pending_snapshots {type: "trade_opened"}
                │
                ▼
        TradeAuditor.on_trade_opened()
            └─ INSERT trade_audit_log (status=PENDING)
```

### Flow 3 — SL/TP Fill (mỗi nến 15m đóng)

```
OHLCVService (backend) publishes candle_close
    │
    ▼
Redis channel "candle_close"
    {"symbol": "BTC/USDT", "timeframe": "15m", "close": 42000}
    │
    ▼
CandleFeed.run() [subscribed]
    │
    ├─ Redis LINDEX ohlcv:BTC/USDT:15m -1
    │   → parse JSON → {open, high, low, close, volume, timestamp}
    │
    ├─ INSERT price_snapshots (for T* lookups)
    │
    └─ PositionTracker.check_positions_for_symbol("BTC/USDT", high, low)
            │
            ├─ Long position: low ≤ SL? → SL_HIT (fill at stop_loss)
            │                 high ≥ TP2? → TP2_HIT (fill at take_profit_2)
            │                 high ≥ TP1? → TP1_HIT (fill at take_profit_1)
            │
            └─ Short position: high ≥ SL? → SL_HIT
                               low ≤ TP2? → TP2_HIT
                               low ≤ TP1? → TP1_HIT

            On fill:
            ├─ calculate_pnl(long/short, entry, exit, amount, leverage, funding)
            ├─ UPDATE mock_positions (status=CLOSED, exit_price, exit_reason)
            ├─ UPDATE mock_account (balance +/- net_pnl)
            ├─ INSERT mock_account_history
            ├─ Redis PUBLISH mock_exchange:fills {fill event}
            └─ Redis RPUSH audit:pending_snapshots {type: "trade_closed"}
                    │
                    ▼
            TradeAuditor.on_trade_closed()
                ├─ Determine signal_quality_verdict:
                │     TP1_HIT/TP2_HIT → TRUE_POSITIVE
                │     SL_HIT + price recovered later → PREMATURE_SL
                │     SL_HIT + price continued → FALSE_POSITIVE
                ├─ Determine sl_hit_reason:
                │     BTC moved >2% same candle → BTC_SPIKE
                │     Price_at_T1 > entry (recovered) → NOISE
                │     Default → TREND_REVERSAL
                └─ UPDATE trade_audit_log (outcome, net_pnl, verdict, status=ANALYZED)
```

### Flow 4 — T*/MFE/MAE Calculation

```
APScheduler fires job at T1 (15m after candle_close):
    │
    ▼
SignalAuditor._fetch_price_at_T(audit_id, T1_target_ts)
    │
    ├─ fetch_ohlcv("BTC/USDT", "15m", limit=5, since=T1_timestamp)
    │   → get candle's close at T1
    │
    └─ UPDATE signal_audit_log SET price_at_T1 = ...

APScheduler fires at T4 (+60m) → price_at_T4
APScheduler fires at T16 (+240m) → price_at_T16 + finalize:
    │
    ├─ Fetch all candles from entry to T16
    ├─ MFE (long) = max(candle_high) - entry_price_proposed
    ├─ MAE (long) = entry_price_proposed - min(candle_low)
    ├─ would_have_hit_sl = any(candle.low ≤ sl_proposed) for long
    ├─ would_have_hit_tp1 = any(candle.high ≥ tp1_proposed) for long
    └─ UPDATE signal_audit_log (audit_status=COMPLETE)
            └─► NoSignalAuditor.process_completed_no_signals()
                    → compute counterfactual for NO_SIGNAL records
```

### Flow 5 — Startup Backfill

```
main.py startup
    │
    └─ SignalAuditor.backfill_pending()
            │
            └─ Query: signal_audit_log WHERE audit_status IN ('PENDING','PARTIAL')
                    │
                    └─ For each record:
                        elapsed = now - timestamp_candle_close
                        if elapsed ≥ 15m AND price_at_T1 IS NULL:
                            → fetch T1 immediately from ccxt history
                        if elapsed ≥ 60m AND price_at_T4 IS NULL:
                            → fetch T4 immediately
                        if elapsed ≥ 240m AND price_at_T16 IS NULL:
                            → fetch T16 + compute MFE/MAE + set COMPLETE
```

### Flow 6 — Real-time UI Updates

```
TickerFeed.run() [every 10s]
    │
    ├─ Get all OPEN positions from DB
    │
    └─ For each symbol: get_exchange_client().async_fetch_ticker(symbol)
            │
            ├─ Compute unrealized_pnl = (last_price - entry) × amount × leverage
            │
            ├─ Redis PUBLISH mock_exchange:pnl {symbol, price, pnl}
            │
            └─ WebSocket broadcast to /ws/positions subscribers

CandleFeed on fill → WebSocket broadcast to /ws/audit-feed
SignalAuditor on new record → WebSocket broadcast to /ws/audit-feed
```

---

## 4. Component Descriptions

### MockExchange (`exchange/mock_exchange.py`)

Server-side implementation của `ExchangeInterface`. FastAPI routes delegate trực tiếp vào đây.

| Method | Behavior |
|--------|----------|
| `create_order(MARKET)` | Fill ngay tại given price, tạo position, deduct fee |
| `create_order(LIMIT)` | Store OPEN, tạo position skeleton |
| `create_order(STOP_LOSS)` | Update `mock_positions.stop_loss` |
| `create_order(TAKE_PROFIT)` | Update `mock_positions.take_profit_1/2` |
| `get_account_state()` | Read `mock_account` (singleton id=1) |
| `get_current_price(symbol)` | `price_snapshots` latest → fallback ccxt ticker |

### OrderManager (`exchange/order_manager.py`)

CRUD layer thuần SQLAlchemy. Tách biệt hoàn toàn khỏi FastAPI.

- `create_order()` → INSERT mock_orders
- `fill_market_order()` → UPDATE status=FILLED, compute fee
- `fill_order_by_trigger()` → SL/TP fill, triggered by PositionTracker
- `calculate_pnl()` → Long/Short gross, fee entry/exit, funding approximation, net PnL

**PnL Formula:**
```
Long:  gross_pnl = (exit - entry) × amount × leverage
Short: gross_pnl = (entry - exit) × amount × leverage
fee_entry = entry × amount × fee_rate
fee_exit  = exit  × amount × fee_rate
funding_paid = entry × amount × funding_rate_at_entry × floor(hold_hours / 8)
net_pnl = gross_pnl - fee_entry - fee_exit - funding_paid
pnl_pct = net_pnl / (entry × amount) × 100
```

### PositionTracker (`exchange/position_tracker.py`)

Check SL/TP dùng candle `high`/`low` — không dùng ticker.

**Ưu điểm:** Capture intra-candle extremes — ticker polling 5s sẽ miss spike ngắn.

**Logic ưu tiên:** SL > TP2 > TP1 (pessimistic assumption khi cùng candle hit cả SL và TP).

### CandleFeed (`price_feed/candle_feed.py`)

Subscribe Redis pub/sub `candle_close`. Mỗi event:
1. `LINDEX ohlcv:{symbol}:{timeframe} -1` → lấy candle mới nhất từ Redis buffer
2. Parse `{open, high, low, close, volume, timestamp}`
3. `PositionTracker.check_positions_for_symbol()`
4. INSERT `price_snapshots` (dùng cho T* lookups)

### AuditConsumer (`audit/consumer.py`)

`Redis BLPOP audit:pending_snapshots timeout=5s`. Dispatch theo `type`:
- `signal_snapshot` → `SignalAuditor.process()`
- `trade_opened` → `TradeAuditor.on_trade_opened()`
- `trade_closed` → `TradeAuditor.on_trade_closed()`

### SignalAuditor (`audit/signal_auditor.py`)

**3 responsibilities:**
1. INSERT `signal_audit_log` từ snapshot
2. APScheduler: schedule T1/T4/T16 jobs
3. Startup: backfill pending records từ ccxt history

**T* timing:** tính từ `timestamp_candle_close`, không phải từ entry fill — đo khả năng predict của signal, không phải execution quality.

### TradeAuditor (`audit/trade_auditor.py`)

Auto-classify mỗi closed trade:

| Verdict | Điều kiện |
|---------|----------|
| `TRUE_POSITIVE` | Outcome = TP1_HIT hoặc TP2_HIT |
| `PREMATURE_SL` | SL hit nhưng price_at_T4 > entry (long) — price phục hồi |
| `FALSE_POSITIVE` | SL hit, price tiếp tục đi ngược |

| SL Reason | Điều kiện |
|-----------|----------|
| `BTC_SPIKE` | BTC cùng candle move > 2% |
| `NOISE` | price_at_T1 > SL level (long) — phục hồi trong 1 nến |
| `TREND_REVERSAL` | Default cho SL hit còn lại |

### AnalysisEngine (`audit/analysis_engine.py`)

10 câu hỏi phân tích với **Wilson CI** (95% confidence interval):

| Q | Câu hỏi | Method |
|---|---------|--------|
| Q1 | Win rate tổng thể | `COUNT(TP_HIT) / COUNT(*)` + Wilson CI |
| Q2 | Win rate theo regime | JOIN `signal_audit_log.regime` |
| Q3 | Win rate theo MTF scenario | GROUP BY `mtf_scenario` |
| Q4 | Score threshold tối ưu | Win rate × avg_rr per bucket (75-79, 80-84, 85+) |
| Q5 | Module nào predict tốt nhất | Correlation `score_breakdown.*` vs verdict |
| Q6 | Missed opportunity rate | `missed_opportunity=True / COUNT(no_signal)` |
| Q7 | SL hit vì noise hay trend | GROUP BY `sl_hit_reason` |
| Q8 | ATR SL vs fixed 2% | `would_have_hit_sl` comparison |
| Q9 | Win rate theo giờ trong ngày | GROUP BY HOUR(`timestamp_candle_close`) |
| Q10 | Funding rate ảnh hưởng | Correlation `funding_rate` vs `pnl_pct` |

**Confidence levels:**

| Sample size | Level | Behavior |
|---|---|---|
| < 10 | `insufficient` | Raw stats only, no recommendations |
| 10–19 | `very_low` | Recommendations + wide CI |
| 20–29 | `low` | Recommendations + CI |
| 30–49 | `medium` | Standard recommendations |
| ≥ 50 | `high` | Full analysis + tuning suggestions |

---

## 5. Database Schema

```
mock_orders ──────────────────────────────────────
  id (TEXT PK, UUID)
  symbol, side, order_type, amount, price
  status: PENDING|OPEN|FILLED|PARTIAL|CANCELLED|REJECTED|EXPIRED
  filled_amount, fill_price, fee
  client_order_id, signal_id (soft ref to backend signal_log)
  created_at, filled_at

mock_positions ────────────────────────────────────
  id (INT PK)
  symbol, direction (long|short)
  entry_price, amount, leverage
  stop_loss, take_profit_1, take_profit_2
  status: OPEN|CLOSED
  entry_order_id (FK → mock_orders)
  signal_id, funding_rate_at_entry
  opened_at, closed_at, exit_price, exit_reason

mock_account ──────────────────────────────────────
  id = 1 (singleton)
  balance_usd, equity_usd, used_margin
  total_realized_pnl, total_fees_paid
  updated_at

mock_account_history ──────────────────────────────
  id (INT PK)
  balance_usd, equity_usd
  trade_id (FK → mock_positions)
  event: trade_opened|trade_closed|fee_charged
  pnl_delta, recorded_at

signal_audit_log ──────────────────────────────────
  id (INT PK)
  signal_id (soft FK → backend signal_log)
  symbol, timeframe, timestamp_candle_close
  signal_result: SIGNAL|NO_SIGNAL
  final_score, score_breakdown (JSON)
  regime, regime_multiplier, mtf_scenario
  btc_guard_active, circuit_breaker_locked
  blocking_reason, blocking_detail
  entry_price_proposed, sl_proposed, tp1_proposed, tp2_proposed
  atr_value, adx_value, delta_value, delta_threshold
  funding_rate, ob_available
  price_at_T1, price_at_T4, price_at_T16     ← filled by SignalAuditor
  max_favorable_excursion, max_adverse_excursion
  would_have_hit_sl, would_have_hit_tp1, would_have_hit_tp2
  audit_status: PENDING|PARTIAL|COMPLETE

trade_audit_log ───────────────────────────────────
  id (INT PK)
  trade_id (FK → mock_positions)
  signal_audit_id (FK → signal_audit_log)
  entry_price_proposed, entry_price_actual
  sl_proposed, sl_actual, tp1_proposed, tp1_actual
  outcome: SL_HIT|TP1_HIT|TP2_HIT|MANUAL_CLOSE|EXPIRED
  exit_price, exit_timestamp, hold_duration_minutes
  gross_pnl, net_pnl, pnl_pct
  sl_hit_reason: NOISE|TREND_REVERSAL|NEWS_EVENT|BTC_SPIKE
  signal_quality_verdict: TRUE_POSITIVE|FALSE_POSITIVE|PREMATURE_SL
  audit_status: PENDING|ANALYZED|REVIEWED

no_signal_audit_log ───────────────────────────────
  id (INT PK)
  signal_audit_id (FK → signal_audit_log)
  score_at_decision, score_gap
  blocking_reason, blocking_detail
  hypothetical_entry_price, hypothetical_sl, hypothetical_tp1
  would_have_been_profitable, hypothetical_pnl_pct
  missed_opportunity (bool)
  audit_status: PENDING|COMPLETE

price_snapshots ───────────────────────────────────
  id (INT PK)
  symbol, timeframe
  open, high, low, close, volume
  timestamp, recorded_at
  UNIQUE(symbol, timeframe, timestamp)
```

**Cross-DB note:** `signal_id` trong `signal_audit_log` và `mock_orders` là **soft reference** tới `signal_log.log_id` ở backend DB — không có DB-level FK constraint vì hai service có DB riêng.

---

## 6. API Reference

### Exchange API — `ExchangeInterface` over HTTP

```
POST   /exchange/orders              → create_order()
DELETE /exchange/orders/{id}         → cancel_order()
GET    /exchange/orders/{id}         → get_order()
GET    /exchange/orders?symbol=      → get_open_orders()
GET    /exchange/positions/{symbol}  → get_position()
GET    /exchange/positions           → get_all_positions()
GET    /exchange/account             → get_account_state()
GET    /exchange/price/{symbol}      → get_current_price()
```

### Audit API

```
GET /audit/signals
    ?page=1&limit=50&symbol=&result=SIGNAL|NO_SIGNAL
    &regime=&status=PENDING|PARTIAL|COMPLETE&from=&to=

GET /audit/signals/{id}              → signal detail + score breakdown

GET /audit/trades
    ?page=1&limit=50&outcome=SL_HIT|TP1_HIT&verdict=TRUE_POSITIVE|...

GET /audit/trades/{id}               → trade detail + PnL breakdown

GET /audit/no-signals
    ?page=1&limit=50&missed_only=true
```

### Analytics API

```
GET /audit/analytics/performance
Response:
{
  "sample_size": 42,
  "confidence": "medium",
  "win_rate": { "value": 0.571, "ci_95": [0.421, 0.714] },
  "win_rate_by_regime": { "TRENDING": 0.71, "RANGING": 0.40, ... },
  "win_rate_by_mtf_scenario": { "A": 0.75, "B": 0.55, "C": 0.38 },
  "win_rate_by_score_bucket": { "75-79": 0.44, "80-84": 0.60, "85+": 0.78 },
  "sl_hit_reasons": { "NOISE": 0.45, "TREND_REVERSAL": 0.30, "BTC_SPIKE": 0.25 },
  "missed_opportunity_rate": 0.23,
  "questions": { "Q1": "...", ..., "Q10": "..." }
}

GET /audit/analytics/tuning
Response:
{
  "confidence": "medium",
  "suggested_score_threshold": 80,
  "suggested_atr_multiplier": 1.8,
  "regime_adjustments": { "CHOPPY": "increase threshold to 85" },
  "notes": "..."
}
```

### WebSocket

```
WS /ws/positions   → broadcast every 10s
   {"symbol": "BTC/USDT", "price": 42000, "unrealized_pnl": 45.3, ...}

WS /ws/audit-feed  → broadcast on events
   {"event": "signal_recorded", "audit_id": 123, ...}
   {"event": "trade_opened", ...}
   {"event": "trade_closed", ...}
```

### Health Check

```
GET /health  → {"status": "ok", "service": "mock-exchange-workspace"}
```

---

## 7. Startup Sequence

```
python main.py
    │
    ├─ 1. load config.yaml
    ├─ 2. configure SQLite engine (WAL mode) + create_all tables
    ├─ 3. init mock_account (id=1, balance=10000 USD) if not exists
    ├─ 4. create Redis client (trading_core.cache.get_redis)
    ├─ 5. instantiate components:
    │       ConnectionManager (WebSocket)
    │       OrderManager (fee_rate=0.001)
    │       MockExchange (OrderManager + db_factory)
    │       PositionTracker (OrderManager + Redis)
    │       SignalAuditor (APScheduler, exchange_id, ws_manager)
    │       TradeAuditor (Redis, ws_manager)
    │       NoSignalAuditor
    │       AnalysisEngine
    ├─ 6. set_dependencies() → wire into FastAPI DI
    ├─ 7. SignalAuditor.start_scheduler() → APScheduler begins
    ├─ 8. SignalAuditor.backfill_pending() → catch up pending T* windows
    ├─ 9. NoSignalAuditor.process_completed_no_signals() → initial pass
    ├─ 10. asyncio.create_task(CandleFeed.run())
    ├─ 11. asyncio.create_task(AuditConsumer.run())
    ├─ 12. asyncio.create_task(TickerFeed.run())
    ├─ 13. asyncio.create_task(_periodic_no_signal()) → every 5 min
    └─ 14. uvicorn.Server(app).serve() → FastAPI on 0.0.0.0:8001
```

---

## 8. Configuration (`config.yaml`)

```yaml
service:
  host: "0.0.0.0"
  port: 8001                         # FastAPI port

database:
  url: "sqlite:///./mock_exchange.db" # relative to service root

redis:
  url: "redis://localhost:6379/0"     # same Redis as backend-workspace

exchange:
  id: "binance"                       # ccxt exchange for public price feed
  fee_rate: 0.001                     # 0.1% taker fee

mock_account:
  initial_balance_usd: 10000.0        # starting paper balance

price_feed:
  ticker_poll_interval_seconds: 10    # unrealized PnL update interval
```

---

## 9. Dependency Map

```
trading-core (shared lib)
    ExchangeInterface, Order, Position, AccountState, OrderSide, OrderType
    get_redis(), get_exchange_client()
    RedisKeys.Channels.CANDLE_CLOSE = "candle_close"
    RedisKeys.Channels.MOCK_FILLS   = "mock_exchange:fills"
    RedisKeys.Channels.MOCK_PNL     = "mock_exchange:pnl"

backend-workspace (producer)
    MockExchangeHttpClient → HTTP → /exchange/* routes
    AuditClient → Redis RPUSH → audit:pending_snapshots

mock-exchange-workspace (this service)
    Reads: candle_close (Redis sub), audit:pending_snapshots (Redis BLPOP)
    Writes: mock_exchange:fills (Redis pub), mock_exchange:pnl (Redis pub)
    Serves: :8001 REST + WebSocket

frontend-workspace (consumer)
    REST: /audit/*, /audit/analytics/*
    WS:   /ws/positions, /ws/audit-feed
```

---

## 10. Khởi chạy

```bash
cd workspace/mock-exchange-workspace

# Install trading-core in editable mode
pip install -e ../trading-core

# Install service dependencies
pip install -r requirements.txt

# Start service (requires Redis running)
python main.py

# Verify
curl http://localhost:8001/health
# → {"status": "ok", "service": "mock-exchange-workspace"}
```

**Bật mock mode trong backend-workspace** (`config.yaml`):
```yaml
mock_exchange:
  enabled: true
  url: "http://localhost:8001"

audit:
  enabled: true
```
