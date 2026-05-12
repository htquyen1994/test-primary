# Phần 9: Known Limitations & Design Decisions — Crypto Trading System

---

## 9.1 Current Limitations

| Limitation | Impact | Workaround | Future Fix |
|------------|--------|------------|------------|
| **Order Book Feed chưa start** | OrderFlow module = 0/35 pts. Score bị cap tại 60. Rất khó đạt ALERT. | Chạy OrderBookService thủ công; chấp nhận cap | Start OrderBookService, implement REST polling order book |
| **Trade Tape chưa start** | Cumulative Delta = 0. OrderFlow delta component = 0/15 pts | Chấp nhận thiếu data — system vẫn hoạt động với SMC/VSA/Context | Start DeltaService, implement trade tape REST polling hoặc WebSocket |
| **WebSocket ingestion chưa implement** | REST polling cho OHLCV có latency 60s cho 15m candles | Acceptable cho semi-auto (trader có 15 phút để confirm) | Implement WebSocket OHLCV ingestion (design đã có trong spec) |
| **Testnet mode mặc định** | Không thể live trade mà không thay đổi config | Set `exchange.testnet: false` tường minh khi sẵn sàng live | Safety feature — không nên "fix" |
| **SQLite local dev** | Không hỗ trợ JSONB queries, performance kém hơn với large datasets | Acceptable cho development | Production: chuyển sang SQL Server qua DATABASE_URL |
| **Single-machine deployment** | Không có failover — nếu machine down, system down | Monitor + manual restart | Consider containerized deployment với health checks |
| **Score cap tại 60 khi OB unavailable** | Max achievable score ≤ 60 → WATCH, không phải ALERT | Xem hệ thống như "monitoring mode" cho đến khi OB data available | Start OrderBookService |
| **Không có authentication cho API** | Ai cũng có thể access dashboard và API | Local network only | Implement JWT authentication cho production |
| **Config thay đổi không validate per-field** | Hot-reload có thể fail sau khi đã áp một phần config mới | Atomic validation trước khi apply | Implement config versioning với rollback |
| **Correlation matrix cập nhật theo 1H candle** | Correlation hơi stale (max 1h lag) | Acceptable cho risk management | Cập nhật real-time theo giá |

---

## 9.2 Design Decisions Log

### Decision 1: REST Polling vs WebSocket cho OHLCV

```
Context:
    Cần ingestion OHLCV từ exchange theo thời gian thực.
    WebSocket là lựa chọn "đúng" về kỹ thuật (realtime, no polling overhead).
    Nhưng WebSocket management phức tạp: reconnection, message buffering, diff vs snapshot.

Options Considered:
    Option A: WebSocket streams (ccxt.watch_ohlcv)
    Option B: REST polling với ccxt.fetch_ohlcv

Decision: REST polling (Option B)

Rationale:
    1. Hệ thống trigger theo candle close (mỗi 15 phút) — không cần tick-level data cho OHLCV
    2. Polling mỗi 60s với 15m candles → max 60s delay, acceptable cho semi-auto system
    3. REST polling đơn giản hơn nhiều: không cần handle reconnection, buffer management
    4. ccxt REST API ổn định hơn WebSocket trên nhiều exchanges
    5. WebSocket ingestion là kế hoạch tương lai khi system cần < 1s latency

Trade-offs:
    Pro: Đơn giản, ít lỗi, dễ debug
    Con: Max 60s latency on candle detection, higher API call frequency, exchange rate limit risk

Date: Phase 1 design decision, confirmed in Phase 9
```

---

### Decision 2: asyncio + threading vs Celery

```
Context:
    Cần một mechanism để trigger scoring khi candle close xảy ra.
    ScoringService cần subscribe Redis pub/sub và dispatch coroutines.

Options Considered:
    Option A: Celery workers với Redis broker
    Option B: asyncio event loop + threading.Thread cho pub/sub subscription
    Option C: Pure asyncio với asyncio.create_task

Decision: asyncio + threading (Option B)

Rationale:
    1. Celery cần: broker setup, worker processes, flower monitoring, task serialization
    2. Single-machine deployment không cần distributed task queue
    3. ScoringService scoring 1 candle at a time — không cần horizontal scaling
    4. asyncio + threading.Thread: pub/sub trong thread riêng, scoring coroutines trong asyncio loop
    5. threading.Thread cho Redis blocking LISTEN, asyncio.run_coroutine_threadsafe() để dispatch

Trade-offs:
    Pro: Zero infrastructure overhead, simple debugging, no Celery broker
    Con: Không thể scale horizontally, single thread cho pub/sub

Date: Phase 9 (Design Decision 10 trong spec)
```

---

### Decision 3: SQLite vs PostgreSQL vs SQL Server

```
Context:
    Cần persistent storage cho signal_log, trade_journal, backtest_results, circuit_breaker_state.
    Development: cần zero-config, không cần setup server.
    Production: cần ACID, concurrent writes, JSONB, full SQL support.

Options Considered:
    Option A: SQLite only (đơn giản, portable)
    Option B: PostgreSQL (open source, JSONB, excellent tooling)
    Option C: DATABASE_URL switching — SQLite local, SQL Server production
    Option D: PostgreSQL everywhere (dev + prod)

Decision: DATABASE_URL env var switching (Option C)

Rationale:
    1. Existing infrastructure dùng SQL Server (Windows production environment)
    2. SQLite cho dev: zero-config, file-based, perfect cho single developer
    3. SQLAlchemy ORM: same code works với cả SQLite và SQL Server
    4. Migration files là plain SQL — compatible với cả hai
    5. Không muốn require PostgreSQL setup cho local dev (Docker thêm friction)

Trade-offs:
    Pro: Dev experience tốt, production infrastructure reuse
    Con: Dialect differences (JSONB vs JSON, DATETIME2 vs TIMESTAMPTZ), cần test trên cả hai

Date: Initial design, reviewed in Phase 9
```

---

### Decision 4: Redis as Central Buffer

```
Context:
    Data Pipeline (OHLCVService, OrderBookService, DeltaService) chạy song song với Scoring Engine.
    Cần share data giữa các processes mà không block nhau.

Options Considered:
    Option A: In-memory dict (same process)
    Option B: Redis (separate process, pub/sub support)
    Option C: Message queue (RabbitMQ, Kafka)

Decision: Redis (Option B)

Rationale:
    1. WebSocket tick writer (< 0.1ms/tick) và Scoring Engine không được share process:
       scoring 50–200ms/candle sẽ block WS handler → drop ticks → delta sai
    2. Redis cung cấp atomic LPUSH/LTRIM cho ring buffer
    3. Redis pub/sub cho candle_close trigger — không cần polling
    4. Redis GET/SET cho fast-path Circuit Breaker check (< 1ms)
    5. Redis đã cần cho pub/sub alerts:channel → reuse infrastructure

Trade-offs:
    Pro: Zero-copy data sharing, sub-millisecond latency, pub/sub built-in
    Con: Additional infrastructure, memory limit, không persistent (ring buffer mất khi restart)

Date: Initial design
```

---

### Decision 5: Semi-auto vs Fully-auto Trading

```
Context:
    System có thể fully automate trade execution sau khi signal được generate.
    Fully-auto loại bỏ latency giữa signal và execution.

Options Considered:
    Option A: Fully automated (không cần human confirm)
    Option B: Semi-automated (human CONFIRM required)
    Option C: Configurable (có thể switch)

Decision: Semi-automated (Option B)

Rationale:
    1. AI scoring không perfect — human judgment quan trọng cho edge cases
    2. Market context có thể thay đổi trong 15 phút giữa signal và execution
    3. Kiểm soát rủi ro: trader thấy R:R, regime, biết mình đang làm gì
    4. Regulatory: fully-auto trading cần licenses ở một số jurisdictions
    5. Phase 1: build trust với system trước khi tự động hóa hoàn toàn

Trade-offs:
    Pro: Human oversight, lower risk của false positives, easier debugging
    Con: Miss signals khi trader không online, 15m latency từ signal đến execution

Date: Initial design — fundamental product decision
```

---

### Decision 6: Score Cap khi OB Unavailable

```
Context:
    OrderBookService chưa chạy → OrderFlow score = 0/35.
    System vẫn có thể generate score cao từ SMC/VSA/Context (65–70 pts max).
    Cần quyết định: có nên publish ALERT khi thiếu một module quan trọng?

Options Considered:
    Option A: Không cap — score 65–70 có thể reach ALERT (75)
    Option B: Cap tại 60 khi OB unavailable — chắc chắn không ALERT
    Option C: Lower ALERT threshold về 55 khi OB unavailable

Decision: Cap tại 60 (Option B)

Rationale:
    1. OrderFlow là module quan trọng nhất (35/125 = 28% total score)
    2. Signal không có OF confirmation có độ tin cậy thấp hơn đáng kể
    3. Cap 60 < threshold 75 → không bao giờ ALERT khi thiếu OB
    4. Tốt hơn là false negative (miss good signal) hơn false positive (bad signal)
    5. Trader biết tại sao score thấp qua `ob_warning` field trong Signal Card

Trade-offs:
    Pro: Conservative, tránh bad signals
    Con: Miss tất cả ALERT signals cho đến khi OB available

Date: Phase 9 (Task 31)
```

---

### Decision 7: Dynamic Delta Threshold

```
Context:
    Order Flow module: delta > threshold → +15 pts.
    Static threshold (1000 BTC) không phản ánh market conditions.

Options Considered:
    Option A: Static threshold = 1000 (simple)
    Option B: Dynamic threshold = P75(|delta_24h|) × 1.5
    Option C: Adaptive per-asset threshold (BTC khác ETH khác SOL)

Decision: Dynamic threshold per-asset (Option B — là Option C vì mỗi symbol có lịch sử riêng)

Rationale:
    1. Bull run: average delta 5000+ → threshold 1000 quá thấp → constant false positives
    2. Sideways: average delta 200 → threshold 1000 không bao giờ đạt → constant miss
    3. P75 lọc bỏ 75% "bình thường", chỉ trigger khi top 25% activity
    4. × 1.5 thêm buffer để chỉ trigger khi truly exceptional
    5. Fallback 1000.0 khi < 10 data points — conservative

Trade-offs:
    Pro: Tự điều chỉnh theo market conditions, consistent sensitivity
    Con: Cần 24h data để hoạt động tốt, phức tạp hơn

Date: Phase 9 (Task 30)
```

---

### Decision 8: React (not Next.js) cho Dashboard

```
Context:
    Cần dashboard real-time cho Signal Cards, Journal, Analytics.

Options Considered:
    Option A: React + Vite + TypeScript (SPA)
    Option B: Next.js (SSR + React)
    Option C: Vue.js

Decision: React + Vite (Option A)

Rationale:
    1. Dashboard là SPA — không có SEO requirements
    2. WebSocket connections long-lived và stateful — SSR sẽ complicate connection management
    3. Vite: faster HMR, simpler deployment (static files via FastAPI hoặc nginx)
    4. Next.js App Router, RSC thêm complexity mà không có benefit cho real-time trading UI
    5. Team familiarity với React

Trade-offs:
    Pro: Fast dev, simple deployment, perfect cho real-time SPA
    Con: No SSR, no SEO (không cần), larger initial bundle

Date: Initial design (Design Decision 8 trong spec)
```

---

### Decision 9: MTF 3-Scenario Filter

```
Context:
    Cần filter signals dựa trên 4H bias để tránh trade ngược xu hướng lớn.
    Có thể dùng continuous multiplier hoặc discrete scenarios.

Options Considered:
    Option A: Continuous multiplier (0.0 → 1.0) dựa trên alignment strength
    Option B: 3 discrete scenarios A/B/C
    Option C: Binary (aligned/not) — chỉ 2 cases

Decision: 3 discrete scenarios (Option B)

Rationale:
    1. Scenario C (hard block): 4H opposing với ADX > 25 — không trade ngược strong trend bao giờ
    2. Scenario B (warning): ranging 4H — giảm size 50% và score -10, nhưng không block hoàn toàn
    3. Scenario A (aligned): full confidence
    4. ADX > 25 guard trong Scenario C: tránh block signals trong sideways 4H market
    5. Discrete labels dễ hiểu hơn continuous value khi debug

Trade-offs:
    Pro: Clear, explainable, ADX guard prevents over-blocking
    Con: Binary in Scenario C — có thể miss some valid signals near ADX=25 threshold

Date: Phase 9 (Design Decision 11 trong spec)
```

---

### Decision 10: 4 Circuit Breaker Triggers

```
Context:
    Cần bảo vệ trader khỏi over-trading sau thua lỗ.
    Cần quyết định: bao nhiêu triggers, lock duration bao lâu, unlock như thế nào.

Options Considered:
    Option A: 1 trigger — max daily loss
    Option B: 4 triggers với lock duration khác nhau + Smart Unlock
    Option C: Manual only — trader tự quyết

Decision: 4 triggers + Smart Unlock (Option B)

Rationale:
    1. T1 (consecutive losses): Detect bad streaks trước khi daily loss too large
    2. T2 (single large loss): Single catastrophic trade → immediate lock
    3. T3 (daily cap): Classic risk management — 5% daily limit
    4. T4 (drawdown from peak): Long-term equity protection với 7-day perspective
    5. Smart Unlock: Không unlock tự động vào regime xấu — đợi market change
    6. T4 requires manual review: Force trader reflection sau severe drawdown

Trade-offs:
    Pro: Comprehensive protection, adaptive unlock
    Con: Complex, có thể lock system trong trending market (T1/T2), requires regime tracking for unlock

Date: Phase 9 (Design Decision trong spec)
```

---

## 9.3 Phase 9 Changes Summary

Phase 9 (v2.0) là đợt nâng cấp lớn nhất, thêm 3 filter modules mới và nhiều improvements cho scoring.

| Change | Problem Solved | Implementation | Impact |
|--------|----------------|----------------|--------|
| **MTF Bias Filter** (3 scenarios A/B/C) | Signals không xem xét 4H + Daily trend → nhiều false signals ngược trend lớn | `engine/mtf_bias.py`: detect_4h_bias, detect_daily_bias, get_mtf_alignment | Size reduction, score adjustment, hard block cho opposing trend |
| **BTC Spike Guard** | Alt positions bị tổn thất khi BTC biến động mạnh | `engine/btc_guard.py`: spike detection (>2%), cooldown 30min, cancel Alt alerts | Cancel Alt alerts khi BTC dump, size × 0.5 khi BTC pump |
| **Circuit Breaker** (4 triggers) | Không có protection khi thua lỗ liên tiếp → over-trading | `risk/circuit_breaker.py`: 4 triggers, smart unlock, SQL history | HTTP 423 khi confirm, smart unlock theo regime change |
| **Dynamic Delta Threshold** | Static threshold (1000) không adapt với market conditions | `engine/order_flow.py`: P75(|delta_24h|) × 1.5, fallback 1000 | Better sensitivity — threshold adapts automatically |
| **Data Quality Cap (≤60)** | Score cao khi thiếu OB data → misleading ALERT | `engine/scorer.py`: `if not ob_available: final = min(final, 60)` | Không bao giờ ALERT khi OB unavailable |
| **OB returns List[OrderBlock]** | Single OB miss nhiều confluence opportunities | `engine/smc.py`: find_order_block returns List, sorted by Fib priority | Better SMC analysis, better confluence bonus |
| **Confluence POC fix** | POC counted trong cả VSA và Confluence → double-count | `engine/confluence.py`: remove POC from bonus, poc param ignored | Accurate bonus calculation, no inflation |
| **Daily Bias Size Reduction** | Daily BEAR + long signal → high risk | `engine/mtf_bias.py`: get_daily_size_multiplier — BEAR daily + long → × 0.75 | Size reduced khi trading against daily trend |
| **MTF Score Adjustment** | Score không phản ánh MTF alignment | Scoring pipeline: final += ±10 sau normalization | Aligned signals scored higher, diverging signals lower |
| **CORS explicit origins** | Security: wildcard "*" CORS không an toàn | `api/main.py`: ALLOWED_ORIGINS env var, no wildcard | Security improvement |
| **Circuit Breaker API** | Không có interface để check/manage CB state | `GET /api/circuit-breaker/status`, `POST /api/circuit-breaker/unlock` | Trader có thể monitor và manual unlock |
| **logs:channel** | Chỉ có alerts:channel — không thể debug WATCH/IGNORE | ScoringService: PUBLISH logs:channel cho tất cả signals | Real-time debug view trong Dashboard |
| **circuit_breaker_state table** | Không có persistent history cho CB events | Migration 003: `CREATE TABLE circuit_breaker_state` | Audit trail, smart unlock regime comparison |
