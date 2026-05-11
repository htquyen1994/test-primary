# Requirements: Mock Exchange Service + Audit System

> **Phase:** Algorithm Validation
> **Status:** Draft
> **Created:** 2026-05-11
> **Source:** `tasks/prompts/mock-exchange-and-audit.md` + `tasks/analyze/mock-exchange.analyze.md`

---

## 1. Mục tiêu

Validate hiệu quả scoring algorithm bằng cách dùng giá thật từ exchange nhưng không đặt lệnh thật. Cụ thể: đo được win rate, regime performance, và tối ưu threshold từ ít nhất 30 mock trades.

---

## 2. Phạm vi

**In scope:**
- Workspace mới `mock-exchange-workspace` — service độc lập trên port 8001
- Minimal changes tại `backend-workspace` (3 refactors + 2 new files: `AuditClient`, `MockExchangeHttpClient`)
- Thêm `/audit/*` pages vào `frontend-workspace`

**Out of scope:**
- Live trading execution
- Authentication (internal service, phase sau)
- Redis Sentinel / HA infrastructure
- Tick-by-tick data (OHLCV đủ cho phase này)

---

## 3. Pre-conditions (P0 — bắt buộc trước khi implement)

Ba thay đổi trong `backend-workspace` là blocking — MockExchange không inject được nếu chưa fix:

| ID | File | Vấn đề | Thay đổi cần thiết |
|----|------|--------|-------------------|
| P0-1 | `trade/executor.py:171-185` + `exchange/mock_http_client.py` (mới) | `_submit_with_retry()` gọi ccxt raw methods — không có trên `ExchangeInterface`; chưa có HTTP adapter để connect backend tới mock-exchange-workspace | (1) Rewrite `_submit_with_retry()` dùng `ExchangeInterface.create_order()`; (2) Tạo `MockExchangeHttpClient`; (3) Thêm `mock_exchange.{enabled,url}` vào config |
| P0-2 | `engine/scoring_service.py:264-280` | Filter-block early returns thoát trước audit hook ở cuối `_run_cycle()` — filter-blocked signals không được record | Thêm audit emit tại mọi exit point, hoặc cấu trúc lại với single exit |
| P0-3 | `engine/scoring_service.py:528-560` | `_persist_signal()` không return signal_id — không thể link `signal_audit_log` → `signal_log` | Refactor để return DB-generated ID |

---

## 4. Functional Requirements

### REQ-ME: Mock Exchange Service

**REQ-ME-1:** MockExchange phải implement toàn bộ `ExchangeInterface` từ `trading-core` — `TradeExecutor` không được biết đây là mock hay real.

**REQ-ME-2:** Mọi order từ `TradeExecutor.execute()` phải được nhận, lưu vào DB với trạng thái `PENDING → OPEN`, và trả về `Order` object theo đúng schema của `ExchangeInterface`.

**REQ-ME-3:** SL/TP check phải dùng candle OHLCV (high/low), không phải polling ticker price.
- Trigger: subscribe vào Redis `candle_close` events (cùng channel với ScoringService)
- Logic: `low ≤ SL` → SL fill; `high ≥ TP1` → TP1 fill; `high ≥ TP2` → TP2 fill
- Lý do: polling 5s bỏ sót intra-candle spikes; candle close tự nhiên capture extreme giá

**REQ-ME-4:** Ticker polling 5-10s được dùng duy nhất để cập nhật unrealized PnL cho UI — không trigger fills.

**REQ-ME-5:** PnL calculation phải đúng cho cả long và short:
- Long: `Gross PnL = (exit_price - entry_price) × amount × leverage`
- Short: `Gross PnL = (entry_price - exit_price) × amount × leverage`
- Net PnL: `Gross PnL - fee_entry - fee_exit - funding_paid`
- `funding_paid = position_notional × funding_rate_at_entry × floor(hold_hours / 8)` (approximation)
- Fee: `price × amount × fee_rate` (default 0.1%)

**REQ-ME-6:** Initial mock account balance phải được config qua `config.yaml` (`mock_exchange.initial_balance_usd`, default `10000`). Balance phải persist qua service restarts.

**REQ-ME-7:** Service expose REST API (port 8001) và WebSocket stream theo spec tại `tasks/designs/mock-exchange-audit.md`.

---

### REQ-AU: Audit Event Capture

**REQ-AU-1:** `ScoringService` phải emit audit snapshot cho **mọi** scoring cycle — kể cả filter-blocked signals. Không được bỏ sót bất kỳ cycle nào.

**REQ-AU-2:** Audit emission phải fire-and-forget, không block scoring pipeline. Latency budget: < 1ms tại điểm emit.

**REQ-AU-3:** Transport layer phải dùng Redis list (`audit:pending_snapshots`) thay vì HTTP trực tiếp. AuditService consume từ list này. Nếu AuditService down, data buffer trong Redis và được consumed khi restart.

**REQ-AU-4:** `signal_id` phải là stable identifier được tạo từ DB (return từ `_persist_signal()`) — không phải runtime string như `f"{symbol}_{timeframe}_{time()}"`.

**REQ-AU-5:** Signal audit snapshot phải gồm tối thiểu: `signal_id`, `symbol`, `timeframe`, `timestamp_candle_close`, `final_score`, `score_breakdown`, `signal_result`, `regime`, `mtf_scenario`, `btc_guard_active`, `circuit_breaker_locked`, `entry_price_proposed`, `sl_proposed`, `tp1_proposed`, `atr_value`, `adx_value`, `delta_value`, `funding_rate`, `blocking_reason` (nếu filter-blocked), `blocking_detail`.

---

### REQ-SA: Signal Auditor (T1/T4/T16)

**REQ-SA-1:** Sau mỗi signal được record, SignalAuditor phải schedule fetch giá tại:
- T1 = 1 nến (15m) sau `timestamp_candle_close`
- T4 = 4 nến (1h) sau
- T16 = 16 nến (4h) sau

**REQ-SA-2:** Timing tính từ `timestamp_candle_close`, không phải từ entry fill time.

**REQ-SA-3:** Khi service restart, phải backfill tất cả pending T* windows:
- Query `signal_audit_log WHERE audit_status = 'PENDING'`
- Với mỗi record, compute elapsed time từ `timestamp_candle_close`
- Nếu T* window đã qua và giá chưa được fill → fetch OHLCV history từ ccxt và fill retroactively

**REQ-SA-4:** MFE/MAE phải được compute từ OHLCV data (không cần tick):
- MFE (long) = `max(candle_high) - entry_price` cho tất cả nến từ entry đến close
- MAE (long) = `entry_price - min(candle_low)` tương tự
- Short: đảo chiều

**REQ-SA-5:** `would_have_hit_sl`, `would_have_hit_tp1`, `would_have_hit_tp2` phải được compute cho tất cả signals — kể cả NO_SIGNAL (counterfactual).

---

### REQ-AE: Analysis Engine

**REQ-AE-1:** Analysis Engine phải trả lời 10 câu hỏi theo spec ban đầu (Q1-Q10) với data từ `signal_audit_log`, `trade_audit_log`, `no_signal_audit_log`.

**REQ-AE-2:** Recommendations phải kèm confidence level dựa trên sample size:

| Sample size | Level | Behavior |
|---|---|---|
| < 10 trades | Insufficient | Raw stats only, no recommendations |
| 10–19 | Very Low | Recommendations + wide confidence intervals |
| 20–29 | Low | Recommendations + confidence intervals |
| 30–49 | Medium | Standard recommendations |
| 50+ | High | Full analysis + tuning suggestions |

**REQ-AE-3:** `GET /audit/analytics/performance` phải available ở mọi sample size — không lock sau threshold. Hiển thị confidence label và 95% CI cho win rate.

**REQ-AE-4:** Tuning recommendations phải gồm: suggested score threshold, ATR multiplier cho SL, regime-specific adjustments, module weight suggestions.

---

### REQ-BE: Backend Changes (Minimal)

**REQ-BE-1:** `AuditClient` (`backend-workspace/audit/client.py`) là lightweight Redis publisher. Phải implement: `emit_signal_snapshot()`, `emit_trade_opened()`, `emit_trade_closed()`.

**REQ-BE-2:** Nếu Redis unavailable khi emit → log warning và continue. Không raise exception, không retry.

**REQ-BE-3:** `AUDIT_ENABLED` flag trong config cho phép disable hoàn toàn audit emission mà không restart service.

**REQ-BE-4:** `TradeExecutor` phải inject `ExchangeInterface` thay vì ccxt object trực tiếp. Config determines which implementation được inject.

**REQ-BE-5:** `MockExchangeHttpClient` (`backend-workspace/exchange/mock_http_client.py`) phải:
- Implement toàn bộ `ExchangeInterface`
- Translate mọi interface call thành HTTP requests tới `mock-exchange-workspace`
- Đọc URL từ `config.mock_exchange.url` (default `http://localhost:8001`)
- Không chứa business logic — chỉ là HTTP adapter
- Khi `mock-exchange-workspace` unreachable → raise exception để `TradeExecutor` xử lý như exchange error bình thường (không silent fail)

**REQ-BE-6:** Config `mock_exchange.enabled` (default `false`) quyết định inject `MockExchangeHttpClient` hay ccxt exchange vào `TradeExecutor`. Thay đổi config cần restart service.

---

### REQ-FE: Frontend Audit Dashboard

**REQ-FE-1:** `/audit/signals` — paginated table, default 50 rows/page. Filters: date range, symbol, regime, result, audit_status.

**REQ-FE-2:** Signal Detail Modal khi click row — score breakdown chart, market snapshot, mini price chart, outcome.

**REQ-FE-3:** `/audit/trades` — paginated table. Summary stats: win rate, avg PnL, avg hold time, profit factor.

**REQ-FE-4:** `/audit/no-signals` — default filter `missed_opportunity = True`. Pagination bắt buộc.

**REQ-FE-5:** `/audit/analytics` — win rate by regime, by MTF scenario, by score bucket (histogram), equity curve, SL hit reason breakdown, confidence level indicator.

---

## 5. Non-Functional Requirements

**NFR-1 (Isolation):** Failure của `mock-exchange-workspace` không được ảnh hưởng đến `backend-workspace`. Scoring pipeline phải tiếp tục bình thường khi AuditService down.

**NFR-2 (Performance):** Audit emission overhead < 1ms trong scoring hot path. Price feed polling không được gây rate limit issues (budget: < 100 req/min cho MockExchange riêng).

**NFR-3 (Data Completeness):** Không được drop audit events khi AuditService temporarily down (Redis buffer đảm bảo điều này).

**NFR-4 (Correctness):** T*/MFE/MAE/PnL calculations phải deterministic — same input luôn cho same output. Backfill phải cho kết quả giống real-time processing.

**NFR-5 (Retention):** Giữ tất cả audit data ít nhất 6 tháng. Không xóa records đang pending analysis.

---

## 6. Constraints

1. Không modify scoring logic trong `backend-workspace` — chỉ thêm audit hook và refactor P0 items
2. Dùng `ExchangeInterface` đã có — không tạo interface mới
3. Dùng `trading-core` cho tất cả ccxt calls trong price feed
4. Không cần API authentication trong phase này (internal service)
5. Cross-DB FK (`signal_audit_log.signal_id → signal_log.id`) là application-level soft reference — không enforce bằng DB constraint
6. `backend-workspace` không import code từ `mock-exchange-workspace` — giao tiếp duy nhất qua HTTP (`MockExchangeHttpClient`) và Redis (`audit:pending_snapshots`)
