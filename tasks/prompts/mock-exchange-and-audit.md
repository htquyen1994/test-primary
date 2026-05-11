# Mock Exchange Service + Audit System Design

> **Phase:** Algorithm Validation Phase
> **Mục tiêu:** Test hiệu quả thuật toán scoring trên dữ liệu thật mà không cần live trading
> **Nguyên tắc:** Ít thay đổi `backend-workspace` nhất có thể — mọi logic mới đặt trong `mock-exchange-workspace`

---

## Tài liệu liên quan:

- `overview.md` — tổng quan hệ thống
- `workspace/trading-core/trading_core/exchange/interface.py` — ExchangeInterface đã có
- `workspace/backend-workspace/trade/executor.py` — TradeExecutor hiện tại
- `workspace/backend-workspace/engine/scoring_service.py` — ScoringService
- `tasks/system-review.md` — review bugs đã biết

---

## Yêu cầu

---

Bạn là một **Senior Backend Engineer** chuyên về distributed systems và financial trading infrastructure. Tôi cần bạn thiết kế một hệ thống **Mock Exchange + Audit** cho dự án crypto trading tool của tôi.

---

## Bối cảnh hệ thống hiện tại

Tôi có một hệ thống AI Semi-Auto Crypto Futures Trading Tool (v2.0) với kiến trúc sau:

**Backend (`workspace/backend-workspace/`):**
- `ScoringService` — chạy mỗi khi nến 15m đóng, tính điểm signal 0–100 từ 4 modules (OrderFlow 35pts + SMC 30pts + VSA 30pts + Context 15pts + Bonus 15pts)
- Signal ≥ 75 → ALERT → gửi Signal Card lên dashboard
- `TradeExecutor` — nhận signal đã confirm, đặt lệnh qua ccxt
- `ExchangeInterface` (abstract) — đã có trong `trading-core`, tất cả exchange implementations phải implement interface này
- Redis — central buffer cho OHLCV, delta, OB data + pub/sub
- SQL Server/SQLite — persistent storage (signal_log, trade_journal)

**Vấn đề hiện tại (từ system review):**
- `signal_direction` hardcoded `"long"` — chưa có short signal
- SL/TP hardcoded 2%/3% — chưa dùng ATR
- `TradeExecutor.execute()` chưa được kết nối thực sự vào confirm endpoint
- `_open_positions` luôn empty — portfolio tracking không hoạt động
- Leverage double-counting bug trong RiskManager + TradeExecutor

**Mục tiêu phase này:**
Tôi muốn **validate thuật toán** — kiểm tra xem scoring model có thực sự predict được market movement không — bằng cách dùng **giá thật từ exchange** nhưng **không đặt lệnh thật**. Cần một Mock Exchange Service giả lập sàn giao dịch, theo dõi lệnh real-time, và một Audit System để phân tích hiệu quả mô hình.

---

## Yêu cầu thiết kế

### Workspace mới: `workspace/mock-exchange-workspace/`

Tạo một service độc lập, **không modify `backend-workspace`** (chỉ thêm minimal hooks để emit audit data).

---

### Phần 1: Mock Exchange Service

Service này đóng vai trò là một sàn giao dịch giả lập. Nó:

**1.1 Nhận lệnh từ backend-workspace**
- Implement `ExchangeInterface` (đã có trong `trading-core`) — backend không cần biết đây là mock hay real
- Nhận `create_order()` calls từ `TradeExecutor`
- Lưu lệnh vào DB với trạng thái `PENDING → OPEN`

**1.2 Fetch giá thật real-time**
- Dùng `trading-core` (ccxt) để fetch giá thật từ Binance/OKX/Gate
- Poll giá mỗi 5–10 giây cho mỗi symbol đang có open position
- Không cần API key — dùng public REST endpoint

**1.3 Kiểm tra SL/TP real-time**
- Với mỗi open position, so sánh current price với SL và TP
- Nếu `low ≤ SL` → trigger SL fill (pessimistic: assume SL hit)
- Nếu `high ≥ TP1` → trigger TP1 fill
- Nếu `high ≥ TP2` → trigger TP2 fill (nếu có)
- Ghi nhận fill price, timestamp, PnL

**1.4 Tính toán PnL**
- Gross PnL = (exit_price - entry_price) × amount × leverage (long)
- Net PnL = Gross PnL - fee_entry - fee_exit - funding_paid
- Fee = entry_price × amount × fee_rate (default 0.1%)

**1.5 Expose API**
- REST API để backend và frontend query trạng thái
- WebSocket stream cho real-time position updates

---

### Phần 2: Audit System

Mục tiêu: **Trả lời được các câu hỏi về hiệu quả mô hình** để tuning.

**2.1 Signal Audit Log (Bước 1 — mọi signal)**

Mỗi khi `ScoringService` tính toán xong (dù là ALERT, WATCH, hay IGNORE), cần ghi lại:

```
signal_audit_log:
  - signal_id (FK → signal_log)
  - timestamp_candle_close     # thời điểm nến đóng
  - symbol, timeframe
  - signal_result: "SIGNAL" | "NO_SIGNAL"  # ≥75 = SIGNAL
  - final_score
  - score_breakdown: {of, smc, vsa, ctx, bonus}
  
  # Input params tại thời điểm tính toán
  - regime: "TRENDING" | "RANGING" | "PARABOLIC" | "CHOPPY"
  - regime_multiplier
  - mtf_scenario: "A" | "B" | "C" | null
  - mtf_4h_bias, daily_bias
  - btc_guard_active: bool
  - circuit_breaker_locked: bool
  
  # Thông số kỹ thuật tại thời điểm signal
  - entry_price_proposed
  - sl_proposed, tp1_proposed, tp2_proposed
  - atr_value                  # ATR tại thời điểm signal
  - adx_value                  # ADX tại thời điểm signal
  - delta_value                # Cumulative delta
  - delta_threshold            # Dynamic threshold đang dùng
  - funding_rate
  - ob_available: bool
  - poc_value
  - htf_bias_1h
  
  # Kết quả sau khi signal được tạo (fill sau)
  - price_at_T1  # giá sau 1 nến (15m)
  - price_at_T4  # giá sau 4 nến (1h)
  - price_at_T16 # giá sau 16 nến (4h)
  - max_favorable_excursion    # MFE: giá đi xa nhất theo hướng signal
  - max_adverse_excursion      # MAE: giá đi ngược nhất
  - would_have_hit_sl: bool    # nếu vào lệnh, SL có bị hit không?
  - would_have_hit_tp1: bool
  - would_have_hit_tp2: bool
  - audit_status: "PENDING" | "PARTIAL" | "COMPLETE"
  - audit_completed_at
```

**2.2 Trade Audit Log (Bước 2 — lệnh đã vào)**

Khi signal là SIGNAL và lệnh được đặt:

```
trade_audit_log:
  - trade_id (FK → trade_journal)
  - signal_audit_id (FK → signal_audit_log)
  
  # Execution quality
  - entry_price_proposed vs entry_price_actual  # slippage
  - sl_proposed vs sl_actual
  - tp1_proposed vs tp1_actual
  
  # Outcome
  - outcome: "SL_HIT" | "TP1_HIT" | "TP2_HIT" | "MANUAL_CLOSE" | "EXPIRED"
  - exit_price, exit_timestamp
  - hold_duration_minutes
  - gross_pnl, net_pnl, pnl_pct
  
  # Post-trade analysis
  - sl_hit_reason: null | "NOISE" | "TREND_REVERSAL" | "NEWS_EVENT" | "BTC_SPIKE"
    # "NOISE": price recovered within 2 candles after SL
    # "TREND_REVERSAL": HTF bias changed before SL
    # "BTC_SPIKE": BTC moved >2% same candle
  - signal_quality_verdict: "TRUE_POSITIVE" | "FALSE_POSITIVE" | "PREMATURE_SL"
    # TRUE_POSITIVE: TP hit
    # FALSE_POSITIVE: SL hit, price continued against direction
    # PREMATURE_SL: SL hit but price recovered and would have hit TP
  - audit_notes: text
  - audit_status: "PENDING" | "ANALYZED" | "REVIEWED"
  - analyzed_at
```

**2.3 No-Signal Audit Log (Bước 3 — signal bị bỏ qua)**

Khi signal là NO_SIGNAL (score < 75), vẫn cần track xem market đi đâu:

```
no_signal_audit_log:
  - signal_audit_id (FK → signal_audit_log)
  - score_at_decision          # score thực tế (< 75)
  - score_gap                  # 75 - score = thiếu bao nhiêu điểm
  - blocking_reason: "LOW_SCORE" | "MTF_BLOCK" | "CB_LOCKED" | "BTC_GUARD" | "REGIME"
  
  # Counterfactual: nếu vào lệnh thì sao?
  - hypothetical_entry_price
  - hypothetical_sl, hypothetical_tp1
  - would_have_been_profitable: bool
  - hypothetical_pnl_pct
  - missed_opportunity: bool   # True nếu would_have_hit_tp1
  
  - audit_status: "PENDING" | "COMPLETE"
  - completed_at
```

---

### Phần 3: Audit Analysis Engine

Service tự động phân tích data để trả lời các câu hỏi:

**3.1 Model Performance Questions**
```
Q1: Win rate tổng thể là bao nhiêu?
    → trade_audit_log: COUNT(outcome=TP1_HIT) / COUNT(*)

Q2: Win rate theo regime?
    → JOIN signal_audit_log ON regime → group by regime

Q3: Win rate theo MTF scenario (A/B/C)?
    → GROUP BY mtf_scenario

Q4: Score threshold tối ưu là bao nhiêu?
    → Tính win rate cho từng score bucket (70-74, 75-79, 80-84, 85+)
    → Tìm threshold maximize (win_rate × avg_rr)

Q5: Module nào đóng góp nhiều nhất vào true positives?
    → Correlation giữa score_breakdown fields và signal_quality_verdict

Q6: Bao nhiêu % NO_SIGNAL thực ra là missed opportunities?
    → no_signal_audit_log: COUNT(missed_opportunity=True) / COUNT(*)

Q7: SL bị hit vì noise hay vì trend reversal?
    → trade_audit_log: GROUP BY sl_hit_reason

Q8: ATR-based SL có tốt hơn fixed 2% không?
    → So sánh would_have_hit_sl (fixed) vs hypothetical với ATR SL

Q9: Thời điểm nào trong ngày có win rate cao nhất?
    → GROUP BY HOUR(timestamp_candle_close)

Q10: Funding rate ảnh hưởng thế nào đến kết quả?
    → Correlation giữa funding_rate và outcome
```

**3.2 Tuning Recommendations Engine**
Sau khi có đủ data (≥ 30 trades), tự động generate:
- Suggested score threshold adjustment
- Suggested ATR multiplier cho SL
- Regime-specific score adjustments
- Module weight recommendations

---

### Phần 4: Minimal Changes to backend-workspace

**Chỉ thêm, không sửa logic hiện có:**

**4.1 Audit Hook trong ScoringService**
```python
# Thêm vào cuối _run_cycle() — không thay đổi logic scoring
if AUDIT_ENABLED:
    await audit_client.emit_signal_snapshot(
        signal_id=signal_id,
        score_data=score_result,
        market_snapshot=market_snapshot,  # ATR, ADX, delta, funding...
        filters_state=filters_state,      # regime, mtf, btc_guard, cb
    )
```

**4.2 Audit Client (lightweight)**
```python
# backend-workspace/audit/client.py
class AuditClient:
    """Fire-and-forget HTTP client to mock-exchange-workspace audit API."""
    async def emit_signal_snapshot(self, ...): ...
    async def emit_trade_opened(self, ...): ...
    async def emit_trade_closed(self, ...): ...
```

**4.3 TradeExecutor → MockExchange**
- Thay `ccxt` calls bằng `ExchangeInterface` calls
- `ExchangeInterface` đã có sẵn trong `trading-core`
- Inject `MockExchangeClient` (implements `ExchangeInterface`) thay vì ccxt

---

### Phần 5: Frontend Audit Dashboard

Thêm các màn hình vào `frontend-workspace`:

**5.1 `/audit/signals` — Signal Audit Table**
- Columns: Timestamp | Symbol | Score | Result | Regime | MTF | Entry | SL | TP | Status
- Filter: date range, symbol, regime, result (SIGNAL/NO_SIGNAL), audit_status
- Click vào row → Signal Detail Modal

**5.2 Signal Detail Modal**
- Score breakdown chart (bar chart per module)
- Market snapshot tại thời điểm signal (ATR, ADX, delta, funding)
- Price chart mini với entry/SL/TP marked
- Outcome: SL hit / TP hit / Pending
- Post-trade analysis: sl_hit_reason, signal_quality_verdict

**5.3 `/audit/trades` — Trade Audit Table**
- Columns: Entry | Exit | Direction | Score | Outcome | PnL | Hold Time | Verdict
- Filter: outcome, verdict, date range
- Summary stats: Win Rate | Avg PnL | Avg Hold Time | Profit Factor

**5.4 `/audit/no-signals` — Missed Opportunities Table**
- Columns: Timestamp | Symbol | Score | Gap | Blocking Reason | Would Have Been Profitable
- Highlight rows where `missed_opportunity = True`

**5.5 `/audit/analytics` — Model Performance Dashboard**
- Win rate by regime (bar chart)
- Win rate by MTF scenario (bar chart)
- Win rate by score bucket (histogram)
- Score distribution (SIGNAL vs NO_SIGNAL)
- SL hit reason breakdown (pie chart)
- Signal quality verdict breakdown (pie chart)
- Equity curve (mock account)
- Tuning recommendations panel

---

## Yêu cầu kỹ thuật

### Architecture

```
workspace/
├── mock-exchange-workspace/
│   ├── main.py                    # Entry point
│   ├── config.yaml
│   │
│   ├── exchange/
│   │   ├── mock_exchange.py       # Implements ExchangeInterface
│   │   ├── order_manager.py       # Order lifecycle management
│   │   ├── position_tracker.py    # Real-time position monitoring
│   │   └── price_feed.py          # ccxt price polling (real prices)
│   │
│   ├── audit/
│   │   ├── signal_auditor.py      # Receives signal snapshots, fills price_at_T*
│   │   ├── trade_auditor.py       # Analyzes trade outcomes
│   │   ├── no_signal_auditor.py   # Tracks counterfactuals
│   │   └── analysis_engine.py    # Generates Q1-Q10 answers + recommendations
│   │
│   ├── api/
│   │   ├── main.py                # FastAPI (port 8001)
│   │   ├── routes/
│   │   │   ├── exchange_routes.py # ExchangeInterface REST endpoints
│   │   │   ├── audit_routes.py    # Audit data endpoints
│   │   │   └── analytics_routes.py # Analysis endpoints
│   │   └── schemas.py
│   │
│   └── db/
│       ├── models.py              # signal_audit_log, trade_audit_log, no_signal_audit_log
│       └── migrations/
│
└── backend-workspace/
    └── audit/
        └── client.py              # AuditClient (fire-and-forget, minimal)
```

### Data Flow

```
backend-workspace (ScoringService)
    │
    │ 1. Candle closes → score computed
    │ 2. AuditClient.emit_signal_snapshot() [fire-and-forget]
    │
    ▼
mock-exchange-workspace (AuditAPI :8001)
    │
    │ 3. Lưu signal_audit_log (status=PENDING)
    │ 4. Nếu SIGNAL → nhận order từ TradeExecutor
    │ 5. PriceFeed poll giá thật mỗi 5s
    │ 6. Kiểm tra SL/TP → update trade_audit_log
    │ 7. Sau T1/T4/T16 candles → fill price_at_T* trong signal_audit_log
    │ 8. Chạy analysis → update audit_status = COMPLETE
    │
    ▼
frontend-workspace (React :5173)
    │
    └── /audit/* pages → query mock-exchange-workspace API
```

### Database Schema (mock-exchange-workspace)

Thiết kế schema đầy đủ cho 3 tables:
- `signal_audit_log` — mọi signal với đầy đủ params
- `trade_audit_log` — lệnh đã vào với outcome analysis
- `no_signal_audit_log` — counterfactual tracking
- `mock_orders` — order book của mock exchange
- `mock_positions` — open positions
- `mock_account` — account state history
- `price_snapshots` — giá tại các thời điểm T1/T4/T16

### API Endpoints (mock-exchange-workspace :8001)

**Exchange API (implements ExchangeInterface):**
```
POST /exchange/orders              → create_order()
DELETE /exchange/orders/{id}       → cancel_order()
GET  /exchange/orders/{id}         → get_order()
GET  /exchange/orders              → get_open_orders()
GET  /exchange/positions/{symbol}  → get_position()
GET  /exchange/positions           → get_all_positions()
GET  /exchange/account             → get_account_state()
GET  /exchange/price/{symbol}      → get_current_price()
```

**Audit API:**
```
POST /audit/signal-snapshot        → nhận từ AuditClient
GET  /audit/signals                → paginated signal audit log
GET  /audit/signals/{id}           → signal detail
GET  /audit/trades                 → paginated trade audit log
GET  /audit/trades/{id}            → trade detail
GET  /audit/no-signals             → no-signal audit log
GET  /audit/analytics/performance  → Q1-Q10 answers
GET  /audit/analytics/tuning       → tuning recommendations
WS   /ws/positions                 → real-time position updates
WS   /ws/audit-feed                → real-time audit events
```

---

## Constraints quan trọng

1. **Không modify scoring logic** trong `backend-workspace` — chỉ thêm audit hook
2. **Dùng `ExchangeInterface`** đã có — không tạo interface mới
3. **Dùng `trading-core`** cho ccxt calls trong price feed
4. **Fire-and-forget** cho audit emissions — không block scoring pipeline
5. **Idempotent** — nếu audit service down, backend vẫn chạy bình thường
6. **Audit data phải đủ** để trả lời 10 câu hỏi model performance ở trên
7. **Không cần authentication** trong phase này (internal service)

---

## Output mong muốn

Hãy thiết kế và output:

### 1. Database Schema (SQL)
Full DDL cho tất cả tables trong `mock-exchange-workspace`, bao gồm indexes và foreign keys.

### 2. MockExchange Implementation
```python
# mock-exchange-workspace/exchange/mock_exchange.py
class MockExchange(ExchangeInterface):
    # Full implementation
```

### 3. AuditClient (backend-workspace)
```python
# backend-workspace/audit/client.py
class AuditClient:
    # Lightweight fire-and-forget HTTP client
```

### 4. SignalAuditor
```python
# mock-exchange-workspace/audit/signal_auditor.py
class SignalAuditor:
    # Receives snapshots, schedules T1/T4/T16 price checks
    # Computes MFE/MAE, would_have_hit_sl/tp
```

### 5. AnalysisEngine
```python
# mock-exchange-workspace/audit/analysis_engine.py
class AnalysisEngine:
    # Answers Q1-Q10
    # Generates tuning recommendations
```

### 6. FastAPI Routes
Full route implementations cho exchange API và audit API.

### 7. Pydantic Schemas
Request/response schemas cho tất cả endpoints.

### 8. Frontend Components (TypeScript/React)
- `AuditSignalTable` component
- `SignalDetailModal` component
- `AuditAnalyticsDashboard` component với charts

### 9. Integration Guide
Hướng dẫn step-by-step để:
- Kết nối `backend-workspace` với `mock-exchange-workspace`
- Inject `MockExchange` vào `TradeExecutor`
- Enable audit hooks trong `ScoringService`
- Chạy toàn bộ stack

---

## Câu hỏi cần trả lời trong design

Trước khi code, hãy trả lời:

1. **Price check frequency:** Poll giá mỗi 5s hay dùng WebSocket stream? Trade-off?
2. **SL/TP check logic:** Dùng `low/high` của candle hay tick-by-tick? Ảnh hưởng đến accuracy?
3. **T1/T4/T16 timing:** Tính từ candle close hay từ entry fill?
4. **MFE/MAE calculation:** Cần tick data hay OHLCV đủ?
5. **Audit backfill:** Nếu audit service restart, làm sao backfill price_at_T* cho pending signals?
6. **Concurrent positions:** Nếu cùng lúc có 3 open positions, price feed có bị bottleneck không?
7. **Data retention:** Giữ audit data bao lâu? Cần archiving strategy không?

---

*Context files đính kèm: `overview.md`, `trading-core/exchange/interface.py`, `backend-workspace/trade/executor.py`, `backend-workspace/engine/scoring_service.py`, `tasks/system-review.md`*
