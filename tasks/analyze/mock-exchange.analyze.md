  Phân tích Feature: Mock Exchange Service + Audit System

  Đánh giá tổng thể

  Thiết kế có tư duy tốt — nguyên tắc "minimal changes to backend", fire-and-forget audit, và bộ 10 câu hỏi phân tích rất thực tế. Tuy nhiên, có 5 vấn đề nghiêm trọng cần giải quyết trước khi bắt 
  tay implement, và một số giả định sai về trạng thái hiện tại của codebase.

  ---
  1. Vấn đề Nghiêm trọng (Blocking Issues)

  1.1 TradeExecutor KHÔNG dùng ExchangeInterface

  Yêu cầu 4.3 nói "Thay ccxt calls bằng ExchangeInterface calls" như thể đây là việc nhỏ. Nhưng thực tế, TradeExecutor._submit_with_retry() (executor.py:171-185) gọi:

  self._exchange.create_limit_order(asset, side, amount, price)  # ccxt raw
  self._exchange.create_order(asset, "stop_loss_limit", ...)      # ccxt raw
  self._exchange.create_market_order(asset, side, amount)          # ccxt raw

  Trong khi ExchangeInterface chỉ có một method duy nhất: create_order(symbol, side: OrderSide, order_type: OrderType, ...). Không có create_limit_order hay create_market_order nào trên interface 
  cả. Cần rewrite _submit_with_retry() - đây là thay đổi có chủ ý, không phải chỉ swap inject.

  1.2 Audit Hook bị mất khi Filter Block

  Scoring pipeline tại scoring_service.py:264-280 có early return:

  if not result.passed:
      publish_log(r, log_entry)
      return  # ← hook ở cuối _run_cycle() KHÔNG BAO GIỜ được gọi

  Mọi signal bị block bởi MTF/BTC Guard/Circuit Breaker sẽ không xuất hiện trong signal_audit_log và cũng không vào no_signal_audit_log. Đây là một phần lớn của dữ liệu — khi CB locked hoặc BTC   
  Guard kích hoạt, có thể 50%+ signals bị bỏ qua mà không được track.

  Cần: Thêm hook ngay trước mỗi return statement, không chỉ ở cuối function. Hoặc cấu trúc lại với single exit point.

  1.3 signal_id không được expose ra ngoài _publish_alert()

  Hiện tại signal_id được tạo inline tại _publish_alert():
  "signal_id": f"{symbol}_{timeframe}_{int(time.time())}",

  Và _persist_signal() không return DB-generated ID. AuditClient.emit_signal_snapshot() cần một signal_id ổn định để link signal_audit_log.signal_id → signal_log.id. Cần refactor _persist_signal()   để return ID.

  1.4 Cross-DB Foreign Key là Soft Reference

  Schema đề xuất: signal_audit_log.signal_id (FK → signal_log). Nhưng signal_log nằm ở DB của backend-workspace (SQL Server/SQLite), còn mock-exchange-workspace có DB riêng. DB-level FK constraint   không thể enforce cross-service. Cần document rõ đây là application-level FK, không phải DB constraint. Không có FOREIGN KEY clause trong DDL cho relationship này.

  1.5 Công thức PnL thiếu Short Direction

  Section 1.4 chỉ define:
  Gross PnL = (exit_price - entry_price) × amount × leverage  # long only

  System đã support short (CHoCH-derived direction đang hoạt động trong code hiện tại). MockExchange cần:
  Short: Gross PnL = (entry_price - exit_price) × amount × leverage

  ---
  2. Giả định Sai về Trạng thái Code hiện tại

  Requirement document dựa trên system-review (ngày 2026-05-10), nhưng một số bugs đã được fix trong code hiện tại:

  ┌─────────────────────────────────────┬─────────────────────────────────────────────────────┐
  │     Bug trong requirements doc      │                 Trạng thái thực tế                  │
  ├─────────────────────────────────────┼─────────────────────────────────────────────────────┤
  │ "signal_direction hardcoded 'long'" │ ĐÃ FIX — scoring_service.py:195-209 derive từ CHoCH │
  ├─────────────────────────────────────┼─────────────────────────────────────────────────────┤
  │ "SL/TP hardcoded 2%/3%"             │ ĐÃ FIX — scoring_service.py:372-394 dùng ATR        │
  ├─────────────────────────────────────┼─────────────────────────────────────────────────────┤
  │ "_open_positions luôn empty"        │ Vẫn còn bug (api/main.py)                           │
  ├─────────────────────────────────────┼─────────────────────────────────────────────────────┤
  │ "Leverage double-counting"          │ Vẫn còn bug — cần check executor hiện tại           │
  └─────────────────────────────────────┴─────────────────────────────────────────────────────┘

  Điều này ảnh hưởng đến thiết kế: signal_audit_log lưu atr_value và sl_proposed — tốt, phản ánh đúng logic hiện tại.

  ---
  3. Design Gaps Cần Bổ sung

  3.1 SL/TP Check — dùng OHLCV thay vì Polling Price

  Requirement đề xuất poll price mỗi 5-10s và check current_price ≤ SL. Nhưng:
  - Polling ticker chỉ trả về last_price — không capture intra-candle extremes
  - Nếu price spike dips dưới SL rồi recover trong 5 giây giữa 2 polls → miss SL

  Tốt hơn: Subscribe vào Redis candle_close events (ScoringService đã làm). Khi mỗi nến 15m đóng, fetch OHLCV của nến đó, check low ≤ SL và high ≥ TP. Đây là pessimistic SL assumption (đúng logic)   và không cần extra API calls.

  Polling 5s chỉ có giá trị để update unrealized PnL trên UI — không nên dùng để trigger SL/TP fills.

  3.2 T1/T4/T16 — Scheduler Cần Persistent State

  Sau khi service restart, SignalAuditor phải biết signals nào đang pending. Cần startup routine:

  # On service start:
  pending = db.query(signal_audit_log).filter(audit_status='PENDING').all()
  for signal in pending:
      # Compute which T* windows have elapsed
      elapsed = now - signal.timestamp_candle_close
      if elapsed >= 15 minutes and signal.price_at_T1 is None:
          # schedule immediate T1 fill
      if elapsed >= 1 hour and signal.price_at_T4 is None:
          # schedule immediate T4 fill
      ...

  Điều này không được đề cập trong design — nếu service down 2 giờ, tất cả T1/T4 windows bị miss mà không backfill.

  3.3 Funding Cost trong Net PnL

  funding_paid trong công thức chưa được define cách tính:
  funding_periods = floor(hold_duration_hours / 8)
  funding_paid = position_notional × funding_rate × funding_periods

  Nhưng funding_rate thay đổi theo thời gian. Cho phase này nên chấp nhận simplification: dùng funding_rate tại thời điểm entry cho toàn bộ hold duration, và document rõ là approximation.

  3.4 Initial Mock Account Balance

  Design không đề cập mock_account được khởi tạo như thế nào. RiskManager cần call get_account_state() để tính position size. Cần config parameter initial_mock_balance_usd (ví dụ: 10,000 USDT) và 
  logic để persist balance changes qua các trades.

  3.5 Phân tách blocking_reason Chi tiết Hơn

  Schema no_signal_audit_log.blocking_reason chỉ có 5 values: "LOW_SCORE" | "MTF_BLOCK" | "CB_LOCKED" | "BTC_GUARD" | "REGIME". Nhưng FilterRegistry hiện có nhiều filter hơn và mỗi filter có nhiều   loại block khác nhau. Nên lưu thêm blocking_detail text field để capture cụ thể: "BTC pump +3.2% cooldown" vs "MTF 4H bias: bearish".

  ---
  4. Trả lời 7 Câu hỏi Design

  Q1: Poll 5s hay WebSocket?
  → Poll 5s đủ cho phase này, nhưng chỉ dùng để update unrealized PnL. SL/TP check nên dùng candle_close events + OHLCV high/low — không cần tick-by-tick.

  Q2: low/high của candle hay tick-by-tick?
  → Dùng OHLCV low/high. Tick-by-tick cần WebSocket trade stream, phức tạp không cần thiết. Low/high candle là pessimistic SL assumption (nếu low ≤ SL thì assume SL hit) — hợp lý cho validation   
  phase.

  Q3: T1/T4/T16 tính từ candle close hay entry fill?
  → Từ timestamp_candle_close. Mục tiêu là validate xem signal có predict được market direction sau N candles không — không phải execution quality. Entry fill có thể bị slippage/delay, không nên  
  contaminate direction analysis.

  Q4: MFE/MAE cần tick data hay OHLCV đủ?
  → OHLCV đủ. Với 15m candles:
  - MFE (long) = max(candle_high) - entry_price cho tất cả nến từ entry đến close
  - MAE (long) = entry_price - min(candle_low) tương tự
  OHLCV approximation cho MFE/MAE là standard practice và đủ tốt cho algorithm validation.

  Q5: Backfill khi restart?
  → Query signal_audit_log WHERE audit_status='PENDING' khi startup, so sánh now - timestamp_candle_close với các T* thresholds, fetch OHLCV history từ ccxt cho khoảng thời gian đó, fill
  retroactively.

  Q6: Concurrent positions có bottleneck không?
  → Không. 3 open positions = 3 ccxt calls mỗi 10s = trivial. Với tối đa 10 concurrent positions, vẫn chỉ ~60 req/min — rất nhỏ so với 400+ req/min của system hiện tại.

  Q7: Data retention?
  → Giữ 6-12 tháng raw data. Với 15m candles, 20 symbols, và score threshold 75+, dự kiến 10-50 signals/ngày → ~1,800-9,000 records/6 tháng. Rất nhỏ, không cần archiving strategy trong phase này. 
  Add created_at index và document rằng records cần thiết cho analysis engine (không xóa prematurely).

  ---
  5. Rủi ro Kiến trúc

  5.1 AuditClient Fire-and-Forget = Silent Data Loss

  Nếu mock-exchange-workspace down, ScoringService vẫn chạy nhưng signals không được record. Sau khi service up lại, không có cách nào recover các signals đã miss.

  Recommendation: Thay vì HTTP fire-and-forget, publish audit snapshot vào Redis list (audit:pending_snapshots). AuditService consume từ list này. Nếu AuditService down, data buffer trong Redis và   được consumed khi restart. Backend không phụ thuộc vào AuditService being up.

  5.2 AnalysisEngine "≥30 trades" Threshold Quá Cao

  Với score threshold ≥75, system có thể chỉ fire 1-3 signals/ngày trên mỗi symbol. 30 trades có thể mất 2-4 tuần. Nên:
  - Manual trigger via POST /audit/analytics/run
  - Hiển thị recommendations với confidence warning khi sample size < 30: "Results based on N trades — low confidence"

  ---
  6. Gaps trong Thiết kế Frontend

  /audit/no-signals sẽ có lượng data lớn nhất (mọi signal scored nhưng không đạt 75 điểm). Cần pagination bắt buộc và default filter nên show chỉ missed_opportunity = True — không ai muốn review  
  hàng nghìn "NO_SIGNAL" thông thường.

  /audit/analytics — Equity curve cho "mock account" cần mock_account_history table (không thấy trong schema list). Nên thêm table này để track balance theo thời gian.

  ---
  7. Tóm tắt Ưu tiên Trước khi Implement

  ┌──────────┬────────────────────────────────────────────────────────────────────┬──────────────────────────────────────────────┐
  │ Priority │                            Việc cần làm                            │                    Lý do                     │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P0       │ Refactor TradeExecutor._submit_with_retry() dùng ExchangeInterface │ MockExchange không inject được nếu không fix │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P0       │ Đặt audit hook ở mọi exit point của _run_cycle(), không chỉ cuối   │ Filter-blocked signals sẽ bị miss hoàn toàn  │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P0       │ Refactor _persist_signal() return signal_id                        │ Audit link bị broken                         │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  ---
  7. Tóm tắt Ưu tiên Trước khi Implement

  ┌──────────┬────────────────────────────────────────────────────────────────────┬──────────────────────────────────────────────┐
  │ Priority │                            Việc cần làm                            │                    Lý do                     │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P0       │ Refactor TradeExecutor._submit_with_retry() dùng ExchangeInterface │ MockExchange không inject được nếu không fix │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P0       │ Đặt audit hook ở mọi exit point của _run_cycle(), không chỉ cuối   │ Filter-blocked signals sẽ bị miss hoàn toàn  │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P0       │ Refactor _persist_signal() return signal_id                        │ Audit link bị broken                         │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P1       │ Dùng OHLCV candle_close events thay vì poll ticker cho SL/TP check │ Accuracy                                     │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P1       │ Persistent scheduler với startup backfill cho T1/T4/T16            │ Correctness sau restart                      │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P1       │ Thêm Short PnL formula                                             │ System đã hỗ trợ short                       │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P2       │ Buffer audit snapshots qua Redis thay vì HTTP fire-and-forget      │ Data loss prevention                         │
  ├──────────┼────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ P2       │ Soft FK documentation, không hard FK cross-DB                      │ Schema correctness                           │
  └──────────┴────────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────┘

  Nhìn chung thiết kế solid và khả thi — chỉ cần giải quyết P0 items trước khi bắt đầu implement thì tránh được refactor lớn sau này.