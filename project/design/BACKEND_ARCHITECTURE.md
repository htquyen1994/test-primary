# Backend Architecture — Crypto Trading System
# Luồng Dữ Liệu & Chức Năng Từng Khối

> Tài liệu này giải thích toàn bộ kiến trúc backend, từng service làm gì, dữ liệu chạy như thế nào từ exchange đến tín hiệu giao dịch.

---

## Tổng quan luồng dữ liệu

> **Lưu ý triển khai hiện tại:** OHLCV và Order Book dùng REST polling (ccxt `fetch_ohlcv`, `fetch_order_book`) thay vì WebSocket. WebSocket ingestion là kế hoạch tương lai.

```
EXCHANGE (Binance/Bybit/Gate...)
        |
        | REST polling (public, không cần API key)
        |
   ┌────┴────────────────────────────────────────────────────┐
   │                   DATA LAYER (data/)                    │
   │                                                         │
   │  ┌──────────────────┐  ┌──────────────────────────────┐ │
   │  │  OHLCVService    │  │  OrderBookService            │ │
   │  │  ohlcv_service.py│  │  orderbook_service.py        │ │
   │  │  15m/1h/4h/1d    │  │  poll every 5s               │ │
   │  │  REST polling    │  │  bid/ask stack computation   │ │
   │  └──────┬───────────┘  └──────────────┬───────────────┘ │
   │         │                             │                 │
   │  ┌──────┴───────────┐  ┌──────────────┴───────────────┐ │
   │  │  DeltaService    │  │  Funding Rate (future)       │ │
   │  │  delta_service.py│  │  funding.py (REST)           │ │
   │  │  trade tape poll │  │  poll every 8h               │ │
   │  └──────┬───────────┘  └──────────────┬───────────────┘ │
   └─────────┼─────────────────────────────┼─────────────────┘
             │ atomic writes               │
             ▼                             ▼
   ┌─────────────────────────────────────────────────────────┐
   │                    REDIS (Buffer)                       │
   │                                                         │
   │  Core keys:                                             │
   │  ohlcv:{sym}:{tf}     → ring buffer (15m:500, 4h:200)  │
   │  delta:{sym}:5m       → cumulative delta (float)       │
   │  ob:{sym}:snap        → order book snapshot (JSON)     │
   │  funding:{sym}        → funding rate (JSON)            │
   │  poc:{sym}            → Point of Control               │
   │  regime:{sym}         → current regime state           │
   │                                                         │
   │  Phase 9 keys:                                          │
   │  delta_history:{sym}  → 24h delta history (96 values)  │
   │  daily_bias:{sym}     → BULL/BEAR/NEUTRAL (TTL 4h)     │
   │  btc_guard:spike      → spike state + cooldown_until   │
   │  circuit_breaker:locked → "1"/"0" fast-path cache      │
   │                                                         │
   │  Pub/sub channels:                                      │
   │  candle_close         → trigger scoring on close       │
   │  alerts:channel       → ALERT signals → Dashboard      │
   │  logs:channel         → ALL signals (debug log)        │
   │  cancel_all_alerts    → BTC dump → cancel Alt alerts   │
   │  btc_spike            → BTC spike notification         │
   │  circuit_breaker:events → lock/unlock/extend events    │
   └──────────────────────────────┬──────────────────────────┘
                                  │ candle_close pub/sub
                                  ▼
   ┌─────────────────────────────────────────────────────────┐
   │         SCORING ENGINE (engine/scoring_service.py)      │
   │         ScoringService — asyncio + threading            │
   │                                                         │
   │  [1] Regime Detector (ADX + ATR)                        │
   │       ↓                                                 │
   │  [2] MTF Bias Filter (4H + Daily)    ← Phase 9         │
   │       Scenario A: size×1.0, +10pts                      │
   │       Scenario B: size×0.5, -10pts, warning             │
   │       Scenario C: BLOCK → return early                  │
   │       ↓                                                 │
   │  [3] BTC Spike Guard (Alt symbols)   ← Phase 9         │
   │       Dump: cancel all Alt alerts → return early        │
   │       Pump: size×0.5                                    │
   │       Cooldown: suppress 30 min                         │
   │       ↓                                                 │
   │  [4] Signal Scoring                                     │
   │       OF(35) + SMC(30) + VSA(30) + CTX(15) + Bonus(15) │
   │       Dynamic delta threshold        ← Phase 9         │
   │       Data quality cap (≤60 if OB unavailable) ← P9    │
   │       ↓                                                 │
   │  [5] Risk Manager                                       │
   │       Portfolio Heat check (< 6%)                       │
   │       Combined size multiplier (MTF × Daily × BTC)     │
   │       ↓                                                 │
   │  [6] Publish alert / log                                │
   └──────────────────────────────┬──────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
   │  Redis Publish   │  │  SQL Server      │  │  Circuit Breaker     │
   │  alerts:channel  │  │  signal_log      │  │  risk/circuit_       │
   │  logs:channel    │  │  trade_journal   │  │  breaker.py          │
   └──────────┬───────┘  │  backtest_results│  │  circuit_breaker_    │
              │          │  circuit_breaker_│  │  state table         │
              │          │  state           │  └──────────────────────┘
              │          └──────────────────┘
              ▼
   ┌──────────────────────────────────────────────────────────┐
   │         FastAPI Backend (api/main.py)                    │
   │  WS /ws/alerts    → Signal Cards to UI                   │
   │  WS /ws/logs      → Debug log to UI                      │
   │  WS /ws/portfolio → Portfolio heat to UI                 │
   │  REST /api/signals, /api/journal, /api/analytics         │
   │  REST /api/config/*, /api/circuit-breaker/*              │
   └──────────────────────────────┬───────────────────────────┘
                                  │
                                  ▼
   ┌──────────────────────────────────────────────────────────┐
   │         React Dashboard (frontend/)                      │
   │  /           → Signal Cards (CONFIRM/SKIP)               │
   │  /logs       → Real-time scoring log                     │
   │  /journal    → Trade history                             │
   │  /analytics  → Performance metrics                       │
   │  /config/*   → Exchange & trading params                 │
   └──────────────────────────────────────────────────────────┘
```

---

## Giải thích từng khối

### 1. OHLCV Feed (`data/ws_ohlcv.py`)

**OHLCV = Open, High, Low, Close, Volume**

Đây là dữ liệu nến (candlestick) — thứ cơ bản nhất trong trading.

```
Mỗi nến 5m chứa:
  Open  = giá mở cửa lúc 09:00:00
  High  = giá cao nhất trong 5 phút
  Low   = giá thấp nhất trong 5 phút
  Close = giá đóng cửa lúc 09:05:00
  Volume = tổng khối lượng giao dịch
```

**Công dụng:**
- Tính ATR (độ biến động) → xác định SL/TP
- Tính ADX (sức mạnh xu hướng) → Regime Detection
- Phát hiện Order Block, FVG, CHoCH
- Tính RSI, EMA, Bollinger Bands

**Không cần API key** — đây là public market data.

**Lưu vào Redis:** `ohlcv:BTC/USDT:5m` (ring buffer 500 nến)

---

### 2. Order Book Feed (`data/ws_orderbook.py`)

**Order Book = Sổ lệnh** — danh sách tất cả lệnh mua/bán đang chờ.

```
Bid (mua):          Ask (bán):
  79,900 × 2.5 BTC    79,910 × 1.2 BTC
  79,890 × 5.0 BTC    79,920 × 3.8 BTC
  79,880 × 8.2 BTC    79,930 × 2.1 BTC
```

**Công dụng:**
- Tính **Bid Stack vs Ask Stack** → xem ai đang chiếm ưu thế
- Phát hiện **Absorption** → tổ chức đang hấp thụ lệnh bán
- Đóng góp vào **Order Flow Score** (max 10 pts)

**Lưu vào Redis:** `ob:BTC/USDT:snap`

---

### 3. Trade Tape / Delta (`data/ws_trades.py`)

**Trade Tape** = luồng giao dịch thực tế xảy ra theo thời gian thực.

```
09:00:01  BUY  0.5 BTC @ 79,905  → delta += 0.5
09:00:02  SELL 1.2 BTC @ 79,903  → delta -= 1.2
09:00:03  BUY  2.0 BTC @ 79,906  → delta += 2.0
...
Cumulative Delta = +1.3 BTC (net buying pressure)
```

**Công dụng:**
- **Cumulative Delta** = tổng (buy_vol - sell_vol) → đo áp lực mua/bán
- Delta > 1000 BTC → tổ chức đang mua mạnh → +15 pts Order Flow
- Phát hiện **Absorption** kết hợp với Order Book

**Lưu vào Redis:** `delta:BTC/USDT:5m` (reset mỗi nến)

---

### 4. Funding Rate (`data/funding.py`)

**Funding Rate** = phí định kỳ giữa long và short trong futures perpetual.

```
Funding Rate > +0.05%  → thị trường quá nhiều long → cảnh báo
Funding Rate < -0.05%  → thị trường quá nhiều short → squeeze risk
Funding Rate ≈ 0%      → cân bằng → tốt cho trading
```

**Công dụng:**
- Lọc tín hiệu khi thị trường quá lệch một phía
- Đóng góp vào **Context Filter Score** (+4 pts nếu neutral)
- Poll mỗi 8 giờ (không cần WebSocket)

**Lưu vào Redis:** `funding:BTC/USDT`

---

### 5. Redis — Central Buffer

Redis là **bộ nhớ đệm trung tâm** — tất cả data đi qua đây.

**Tại sao cần Redis?**
- WebSocket writer (< 0.1ms/tick) và Scoring Engine chạy **tách biệt hoàn toàn**
- Nếu chạy chung → WebSocket bị block → mất tick → delta sai
- Redis cho phép ghi atomic, đọc nhanh, pub/sub real-time

**Các key quan trọng:**
```
ohlcv:{symbol}:{tf}        → ring buffer nến (list, 500 items)
delta:{symbol}:5m          → cumulative delta (float)
ob:{symbol}:snap           → order book snapshot (JSON)
funding:{symbol}           → funding rate (JSON)
poc:{symbol}               → Point of Control từ Volume Profile
regime:{symbol}            → trạng thái thị trường hiện tại
alerts:channel             → pub/sub channel cho ALERT signals
logs:channel               → pub/sub channel cho debug logs (ALL signals)
candle_close               → pub/sub trigger khi nến đóng

Phase 9 — Redis keys mới:
delta_history:{symbol}     → lịch sử 24h delta (96 values = 24h × 15m), TTL 25h
daily_bias:{symbol}        → Daily bias: BULL/BEAR/NEUTRAL, TTL 4h
btc_guard:spike            → BTC spike state (direction, magnitude, cooldown_until)
circuit_breaker:locked     → fast-path cache: "1" hoặc "0"

Phase 9 — pub/sub channels mới:
cancel_all_alerts          → hủy tất cả Alt alerts khi BTC dump
btc_spike                  → thông báo BTC spike cho frontend
circuit_breaker:events     → thông báo lock/unlock/extend cho frontend
```

---

### 6. Regime Detector (`engine/regime_detector.py`)

**Regime = Trạng thái thị trường** — quyết định hệ thống có nên trade không.

```
PARABOLIC  → ATR > 3× rolling avg ATR  → multiplier = 0.6, tắt Short
TRENDING   → ADX > 25                  → multiplier = 1.0 (tốt nhất)
RANGING    → 20 ≤ ADX ≤ 25            → multiplier = 0.85
CHOPPY     → ADX < 20                  → multiplier = 0.85
```

**Tại sao quan trọng?**
- SMC/VSA hoạt động tốt trong TRENDING và RANGING
- PARABOLIC (BTC pump 15% trong 1h) → OB bị xuyên thủng → tắt Short
- Multiplier nhân vào final score → giảm độ tin cậy khi thị trường xấu

---

### 7. Signal Scoring Engine (`engine/scorer.py`)

**Trái tim của hệ thống** — tổng hợp tất cả module thành 1 điểm số.

```
Module 1: Order Flow Analysis (max 35 pts)
  delta > dynamic threshold     → +15 pts  (tổ chức đang mua)
  bid_stack > ask_stack × 2    → +10 pts  (bid chiếm ưu thế)
  absorption detected           → +10 pts  (hấp thụ lệnh bán)

  Dynamic threshold = percentile_75(|delta_24h|) × 1.5
  Fallback: 1000.0 nếu < 10 data points
  Lịch sử: delta_history:{symbol} (96 values = 24h)

Module 2: SMC Analysis (max 30 pts)
  CHoCH aligned with 1H     → +10 pts  (đảo chiều xác nhận)
  Order Block retest        → +10 pts  (giá về vùng tổ chức)
  FVG midpoint touched      → +10 pts  (lấp vùng imbalance)

  OB detection: trả về List[OrderBlock] (tối đa 3)
  Sắp xếp: Fib 61.8% > Fib 50% > Fib 38.2% > proximity

Module 3: VSA + Volume Profile (max 30 pts)
  No Supply (vol < 40%)     → +10 pts  (không có áp lực bán)
  Effort vs Result          → +10 pts  (volume thấp, giá giữ)
  Entry at POC ±0.3%        → +10 pts  (vùng giá quan trọng nhất)

Module 4: Context Filter (max 15 pts)
  1H bias aligned           → +8 pts   (xu hướng lớn đồng thuận)
  Funding rate neutral      → +4 pts   (thị trường cân bằng)
  Price away from S/R       → +3 pts   (không vào giữa không khí)

Confluence Bonus (max 15 pts)
  OB + Fib 61.8% + FVG → +45 raw → normalized 15 pts
  (POC đã được chuyển sang VSA module — không double-count)
  Max raw = 45 (35 Fib + 10 FVG), normalize: bonus/45 × 15

FORMULA:
  raw = OF + SMC + VSA + CTX + bonus  (0–125)
  final = min(round(raw × regime_mult / 125 × 100), 100)

  Phase 9 adjustments (sau normalization):
  final += mtf_score_adjustment  (+10 Scenario A, -10 Scenario B)
  if not order_book_available: final = min(final, 60)  ← data quality cap

  ≥ 75 → ALERT  🟢  → gửi Signal Card đến Dashboard
  55–74 → WATCH 🟡  → log only
  < 55  → IGNORE 🔴 → log only
```

---

### 8. SMC Analysis (`engine/smc.py`)

**SMC = Smart Money Concepts** — phân tích dấu vết của tổ chức.

**Order Block (OB):**
```
Nến bearish trước impulse bullish lớn = vùng tổ chức đặt lệnh mua
Khi giá retest về OB → tổ chức mua thêm → xác suất bounce cao
```

**Fair Value Gap (FVG):**
```
3 nến: nến 1 high < nến 3 low → có "khoảng trống" giá
Thị trường có xu hướng lấp FVG → entry tại midpoint FVG
```

**Change of Character (CHoCH):**
```
Giá phá vỡ swing high/low gần nhất → đảo chiều xu hướng
CHoCH bullish + 1H bias bullish → tín hiệu mạnh
```

---

### 9. VSA + Volume Profile (`engine/vsa.py`, `engine/volume_profile.py`)

**VSA = Volume Spread Analysis** — phân tích mối quan hệ giá-volume.

**No Supply:**
```
Volume pullback < 40% volume impulse → không có áp lực bán
Tổ chức đang giữ giá, không ai muốn bán → bullish
```

**Volume Profile:**
```
POC (Point of Control) = mức giá có volume cao nhất trong ngày
VAH/VAL = biên trên/dưới của 70% volume
Entry tại POC → vùng giá "công bằng" nhất, tổ chức hay đặt lệnh
```

---

### 10. Risk Manager (`risk/manager.py`)

**Kiểm soát rủi ro** trước khi cho phép signal đi tiếp.

**Portfolio Heat:**
```
Tổng risk của tất cả lệnh đang mở
Nếu heat > 6% account → từ chối signal mới
Ví dụ: 3 lệnh × 2% = 6% → đã đầy, không mở thêm
```

**Correlation Check:**
```
BTC và ETH thường tương quan > 0.8
Nếu đang có BTC long 2% + muốn mở ETH long 2% → group risk = 4% > 3% → từ chối
Tránh "double exposure" khi thị trường crash
```

**Position Sizing:**
```
fixed_usd: mỗi lệnh vào đúng $100 (đơn giản, dễ kiểm soát)
risk_pct:  mỗi lệnh risk 2% account, size tính từ SL distance
kelly:     Kelly Criterion dựa trên win rate lịch sử
```

---

### 11. Alert Builder + Sender (`alert/builder.py`, `alert/sender.py`)

Sau khi score ≥ 75 và risk check pass:

```
1. Build Signal Card:
   - Entry price, SL, TP1, TP2
   - Gross R:R và Net R:R (sau phí)
   - Score breakdown (5 modules)
   - Countdown timer (expires_at_candle)

2. Publish to Redis alerts:channel
   → FastAPI /ws/alerts nhận
   → Push đến React Dashboard
   → User thấy Signal Card
```

---

### 12. FastAPI Backend (`api/main.py`)

**Cầu nối giữa backend và frontend.**

```
WebSocket endpoints (real-time):
  /ws/alerts    → stream Signal Cards khi score ≥ 75
  /ws/logs      → stream scoring debug log mọi candle
  /ws/portfolio → stream Portfolio Heat mỗi giây

REST endpoints — Signals:
  GET  /api/signals              → active ALERT signals
  POST /api/signals/{id}/confirm → user xác nhận → Trade Executor
                                   (blocked với HTTP 423 nếu Circuit Breaker locked)
  POST /api/signals/{id}/skip    → user bỏ qua
  PATCH /api/signals/{id}/expire → đánh dấu expired

REST endpoints — Journal & Analytics:
  GET  /api/journal              → lịch sử giao dịch (paginated)
  GET  /api/analytics            → win rate, profit factor...
  GET  /api/portfolio            → Portfolio Heat + open positions

REST endpoints — Config:
  GET  /api/config               → current config (non-sensitive)
  POST /api/config/reload        → hot-reload config.yaml
  GET  /api/config/exchange      → exchange settings (keys masked)
  PUT  /api/config/exchange      → lưu exchange settings
  GET  /api/config/trading       → trading parameters
  PUT  /api/config/trading       → lưu version mới
  GET  /api/config/trading/history → version history

REST endpoints — Circuit Breaker (Phase 9):
  GET  /api/circuit-breaker/status  → trạng thái lock hiện tại
  POST /api/circuit-breaker/unlock  → manual unlock với review_note

REST endpoints — Backtest:
  GET  /api/backtest/results     → backtest results + Benchmark_Table
  POST /api/backtest/run         → trigger async backtest
```

---

### 13. Trade Executor (`trade/executor.py`)

**Thực thi lệnh sau khi user bấm CONFIRM.**

```
1. _assert_testnet_safe() → kiểm tra testnet flag TRƯỚC KHI gọi exchange
2. ccxt.create_limit_order() → đặt lệnh entry
3. Sau khi fill: đặt SL order + TP1 + TP2 tự động
4. Retry 3× với exponential backoff nếu lỗi
5. Ghi vào trade_journal (SQL Server)
```

**Testnet safety:** `exchange.testnet` phải là `False` (bool) mới cho live trading.

---

### 14. SQL Server — Persistent Storage

**4 tables chính:**

```
signal_log              → MỌI signal (ALERT + WATCH + IGNORE)
                          Dùng để: phân tích tại sao signal không đủ điểm,
                          tìm pattern, optimize thresholds

trade_journal           → Lệnh đã confirm với actual fill price
                          Dùng để: tính PnL thực tế, slippage, win rate

backtest_results        → Kết quả backtest từng strategy × timeframe
                          Dùng để: so sánh strategy, tìm best params

circuit_breaker_state   → Lịch sử lock/unlock Circuit Breaker (Phase 9)
                          Fields: id, triggered_at, unlock_at, trigger_type,
                                  trigger_detail, regime_at_trigger, is_locked,
                                  unlock_requires_review, review_note,
                                  unlocked_at, unlocked_by
                          Migration: db/migrations/003_circuit_breaker.sql
```

**Database environment:**
```
Local dev:   SQLite (sqlite:///./trading.db) — zero config
Production:  SQL Server (:1433, database=trading, user=admin)
             DATABASE_URL env var controls engine
```

---

### 15. MTF Bias Detector (`engine/mtf_bias.py`) — Phase 9

**Lọc tín hiệu theo xu hướng 4H và Daily.**

```
detect_4h_bias(ohlcv_4h):
  bullish: price > EMA200 AND higher lows AND ADX > 20
  bearish: price < EMA200 AND lower highs AND ADX > 20
  ranging: ADX < 20 OR price oscillating around EMA200

detect_daily_bias(ohlcv_daily):
  BULL: close > EMA200 AND close > EMA50 AND 3+ higher lows in 10 days
  BEAR: close < EMA200 AND close < EMA50 AND 3+ lower highs in 10 days
  NEUTRAL: otherwise

get_mtf_alignment(bias_4h, bias_1h, signal_direction):
  Scenario A (aligned):  size × 1.0, score +10
  Scenario B (diverging): size × 0.5, score -10, warning
  Scenario C (opposing):  size × 0.0, BLOCK signal

get_daily_size_multiplier(daily_bias, signal_direction):
  BEAR + long → size × 0.75 (giảm thêm 25%)
  BULL + long → size × 1.0 (không giảm)
```

**Lưu vào Redis:** `daily_bias:{symbol}` (TTL 4h)

---

### 16. BTC Volatility Guard (`engine/btc_guard.py`) — Phase 9

**Bảo vệ Alt positions khi BTC có biến động đột ngột.**

```
check_btc_spike(ohlcv_btc_15m):
  Spike = |close - open| / open > 2% trong 1 nến 15m
  Dump spike → size_multiplier = 0.0 (block hoàn toàn)
  Pump spike → size_multiplier = 0.5 (giảm 50%)
  Cooldown: 30 phút sau spike

check_alt_signal(alt_symbol, alt_gain_pct, signal_direction):
  Trong cooldown + BTC dump → block Alt long
  Trong cooldown + BTC pump + Alt gain < 0.3× BTC gain → block (relative weakness)
  Trong cooldown + BTC pump + Alt gain ≥ 0.3× BTC gain → size × 0.5

cancel_all_alt_alerts():
  Publish cancel_all_alerts event → frontend hủy tất cả Alt Signal Cards

reset_alt_deltas(symbols):
  Reset delta:{symbol}:5m = 0 cho tất cả Alt symbols
```

**Lưu vào Redis:** `btc_guard:spike` (TTL = cooldown + 60s)

---

### 17. Circuit Breaker (`risk/circuit_breaker.py`) — Phase 9

**Tự động khóa trading khi vượt ngưỡng thua lỗ.**

```
4 Triggers:
  Trigger 1: 3 consecutive losses in 24h → lock 12h
  Trigger 2: single loss > 4% equity → lock 6h
  Trigger 3: daily loss > 5% equity → lock until 00:00 UTC
  Trigger 4: drawdown > 10% from 7-day peak → lock 24h + manual review

Smart Unlock:
  Sau khi lock hết hạn:
    Regime changed → auto unlock
    Regime unchanged → extend 6h, notify user
    Trigger 4 → luôn cần manual review note (≥ 10 ký tự)

API Integration:
  POST /api/signals/{id}/confirm → HTTP 423 nếu locked
  GET  /api/circuit-breaker/status → trạng thái hiện tại
  POST /api/circuit-breaker/unlock → manual unlock
```

**State storage:**
- SQL Server: `circuit_breaker_state` table (persistent history)
- Redis: `circuit_breaker:locked` (fast-path cache, TTL = lock duration + 60s)
- Pub/sub: `circuit_breaker:events` (lock/unlock/extend notifications)

---

```
✅ Redis          — running (Docker)
✅ FastAPI        — running (:8000)
✅ ScoringService — running (asyncio + threading, không dùng Celery)
✅ Frontend       — running (:5173)
✅ SQL Server     — running (:1433) [production] / SQLite [local dev]

✅ OHLCV Feed     — running (OHLCVService, REST polling Binance)
   → BTC/USDT luôn được monitor bất kể config
   → 4H và 1D luôn được thêm vào timeframes bất kể config
   → Seed 200 nến 4H + 250 nến Daily khi startup
✅ Signal Scoring — running (mỗi candle close)
✅ Log Publisher  — running (logs:channel)
✅ SQL Logging    — running (signal_log table)

Phase 9 — Đã implement:
✅ MTF Bias Filter     — engine/mtf_bias.py (3 scenarios A/B/C)
✅ BTC Spike Guard     — engine/btc_guard.py (dump/pump/cooldown)
✅ Circuit Breaker     — risk/circuit_breaker.py (4 triggers + smart unlock)
✅ Dynamic Delta Threshold — percentile_75 × 1.5, fallback 1000
✅ Daily Bias Size Reduction — EMA200/EMA50 on Daily, BEAR → size × 0.75
✅ Data Quality Cap    — score ≤ 60 khi Order Book unavailable
✅ OB returns List[OrderBlock] — up to 3, Fib-prioritized
✅ Confluence POC fix  — POC chỉ trong VSA module, không double-count
✅ CORS explicit origins — ALLOWED_ORIGINS env var
✅ Circuit Breaker API — GET/POST /api/circuit-breaker/*

⚠️ Order Book Feed — chưa start (ws_orderbook.py)
   → Order Flow score luôn = 0 pts (bid/ask stack = 0)
   → Score bị cap tại 60 khi OB unavailable

⚠️ Trade Tape     — chưa start (ws_trades.py)
   → Delta luôn = 0 (không có cumulative delta)

⚠️ Trade Executor — testnet mode, chưa test với exchange thật
```

---

## Tóm tắt: Tại sao score thường thấp?

Hiện tại Order Book và Trade Tape chưa chạy → 2 module bị thiếu:

```
Order Flow (max 35 pts):
  delta = 0 → 0/15 pts  ← thiếu Trade Tape
  bid/ask = 0 → 0/10 pts ← thiếu Order Book
  absorption = false → 0/10 pts
  → Order Flow luôn = 0/35 pts

SMC (max 30 pts):
  Hoạt động bình thường từ OHLCV
  → Có thể đạt 10-30 pts

VSA (max 30 pts):
  Hoạt động bình thường từ OHLCV
  → Có thể đạt 10-20 pts

Context (max 15 pts):
  Hoạt động bình thường
  → Có thể đạt 8-15 pts

Tổng tối đa hiện tại: ~65/100 → khó đạt 75 (ALERT)
Khi có Order Book + Trade Tape: ~100/100 → dễ đạt ALERT
```

---

## Phase 9 — Enhancement Components (v2.0)

### New Modules

```
engine/
  mtf_bias.py          ← MTFBiasDetector: 4H + Daily bias classification
                          detect_4h_bias(): EMA200 + market structure + ADX
                          detect_daily_bias(): EMA200 + EMA50 + lower highs/higher lows
                          get_mtf_alignment(): 3 scenarios A/B/C
                          get_daily_size_multiplier(): BEAR daily → size × 0.75

  btc_guard.py         ← BTCVolatilityGuard: spike detection + cooldown
                          check_btc_spike(): |close-open|/open > 2% in 15m candle
                          check_alt_signal(): relative weakness check (Alt < 0.3× BTC)
                          cancel_all_alt_alerts(): publish to cancel_all_alerts channel
                          reset_alt_deltas(): reset delta cho tất cả Alt symbols

risk/
  circuit_breaker.py   ← CircuitBreaker: 4 triggers + smart unlock
                          Trigger 1: 3 consecutive losses in 24h → lock 12h
                          Trigger 2: single loss > 4% equity → lock 6h
                          Trigger 3: daily loss > 5% → lock until 00:00 UTC
                          Trigger 4: drawdown > 10% from 7-day peak → lock 24h + review
                          Smart unlock: regime changed → auto unlock
                                        regime unchanged → extend 6h
                          State: SQL Server circuit_breaker_state table
                          Cache: Redis circuit_breaker:locked (fast-path)

db/migrations/
  003_circuit_breaker.sql ← circuit_breaker_state table schema
```

### Updated Scoring Pipeline (v2.0)

```
Candle closes (15m)
        |
        ▼
[1] Regime Detector (ADX + ATR)
        |
        ▼
[2] MTF Bias Filter (4H + Daily)          ← NEW
    Scenario A: size × 1.0, score +10
    Scenario B: size × 0.5, score -10, warning
    Scenario C: BLOCK (return early)
        |
        ▼
[3] BTC Spike Guard (for Alt symbols)     ← NEW
    Dump spike: cancel all Alt alerts
    Pump spike: size × 0.5
    Cooldown: suppress for 30 min
        |
        ▼
[4] Circuit Breaker check                 ← NEW
    If locked: skip alert, log reason
        |
        ▼
[5] Signal Scoring (OF + SMC + VSA + CTX + Bonus)
    Dynamic delta threshold               ← NEW
    OF capped at 60 if no OB data        ← BUG FIX
        |
        ▼
[6] Risk Manager
    Apply MTF size multiplier            ← NEW
    Apply Daily bias multiplier          ← NEW
    Apply BTC spike multiplier           ← NEW
        |
        ▼
[7] Publish alert / log
```

### Circuit Breaker State Machine

```
UNLOCKED
    |
    | Trigger 1: 3 consecutive losses → lock 12h
    | Trigger 2: single loss > 4% equity → lock 6h
    | Trigger 3: daily loss > 5% → lock until 00:00 UTC
    | Trigger 4: drawdown > 10% from peak → lock 24h + review
    ▼
LOCKED
    |
    | Lock expires
    ▼
CHECK UNLOCK CONDITIONS
    |
    ├── Regime changed? → UNLOCKED
    ├── Regime same? → extend 6h → LOCKED
    └── Requires review? → wait for manual confirmation → UNLOCKED
```

### MTF Alignment Matrix

```
4H Bias    | 1H Bias  | Signal | Scenario | Size Mult | Score Adj
-----------|----------|--------|----------|-----------|----------
Bullish    | Bullish  | Long   | A        | 1.0       | +10
Bullish    | Bearish  | Short  | A        | 1.0       | +10
Ranging    | Bullish  | Long   | B        | 0.5       | -10
Bearish    | Bullish  | Long   | C        | 0.0       | BLOCK
Bearish    | Bearish  | Short  | A        | 1.0       | +10
```
