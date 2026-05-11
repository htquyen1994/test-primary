# Task List — Fix & Implement
**Dựa trên:** `tasks/system-review.md`
**Thứ tự:** Sequential, P1 → P2 → P3

---

## PHASE 1 — Critical fixes (bắt buộc trước live trading)

### TASK-01 — Fix leverage double-counting
- **Status:** DONE
- **Files:** `risk/manager.py`, `trade/executor.py`
- **Vấn đề:** Leverage được nhân 2 lần — lần 1 trong RiskManager (line 170), lần 2 trong TradeExecutor (line 104). Với 10x leverage → position thực tế 100x.
- **Fix:** Bỏ leverage multiplication khỏi RiskManager (chỉ tính notional risk). TradeExecutor là nơi duy nhất apply leverage khi convert USD → contracts.
- **Test:** Unit test verify `position_usd * leverage` chỉ xuất hiện 1 lần trong pipeline.

---

### TASK-02 — ATR-based SL/TP thay vì hardcoded 2%/3%
- **Status:** DONE
- **Files:** `engine/scoring_service.py` (lines 363-365, 393-394)
- **Vấn đề:** `stop_loss = close * 0.98`, `take_profit = close * 1.03` — hardcoded cho mọi asset, mọi volatility. ATR được compute nhưng không được dùng.
- **Fix:**
  ```
  sl_distance = atr_val * SL_ATR_MULT  (default 1.5)
  stop_loss   = close - sl_distance    (long)
  tp1         = close + sl_distance * RR_MIN  (default 1.5)
  tp2         = close + sl_distance * RR_MAX  (default 2.5)
  net_rr      = (tp1 - close - fees) / (close - sl + fees)
  ```
- **Config:** `SL_ATR_MULT` và `RR_MIN` cần expose ra config.yaml.
- **Test:** Verify R:R >= 1.5 net sau phí cho mọi output.

---

### TASK-03 — Fix Circuit Breaker Trigger 4 (7-day equity peak)
- **Status:** DONE
- **Files:** `risk/circuit_breaker.py` (lines 438-448)
- **Vấn đề:** `_get_7day_equity_peak()` luôn trả về 0.0 → Trigger 4 không bao giờ fire.
- **Fix:**
  - Query `trade_journal` để tính cumulative equity theo thời gian (starting equity + sum net_pnl ordered by exit_timestamp)
  - Tìm max equity trong 7 ngày qua
  - Cache kết quả vào Redis key `circuit_breaker:7day_peak` với TTL 1 giờ
- **Test:** Unit test với mock trade journal data verify peak detection đúng.

---

### TASK-04 — Kết nối TradeExecutor vào confirm endpoint
- **Status:** DONE
- **Files:** `api/main.py` (line 134-142)
- **Vấn đề:** `/api/signals/{id}/confirm` chỉ update in-memory state, không gọi TradeExecutor.
- **Fix:**
  - Lấy signal card từ `_active_signals`
  - Gọi `RiskManager.compute_position_size()` với equity từ config/account
  - Dispatch `TradeExecutor.execute()` qua Celery task (async)
  - Update signal status: `"Submitted"` → `"Executing"` → `"Filled"` / `"Failed"`
  - Populate `_open_positions` khi có fill confirmation
- **Note:** Vẫn testnet-only cho đến khi TASK-01 verified.

---

### TASK-05 — Populate `_open_positions` từ trade state
- **Status:** TODO
- **Files:** `api/main.py`
- **Vấn đề:** `_open_positions = {}` luôn empty → portfolio heat = 0%, correlation check không hoạt động.
- **Fix:**
  - Khi trade được fill (từ executor), ghi `_open_positions[asset] = actual_risk_pct`
  - Khi trade đóng (SL/TP/manual), xóa khỏi `_open_positions`
  - Persist `_open_positions` vào Redis để survive API restart
- **Test:** Verify `/api/portfolio` trả về giá trị chính xác sau trade.

---

### TASK-06 — Thêm API authentication
- **Status:** TODO
- **Files:** `api/main.py`
- **Vấn đề:** Không có auth — bất kỳ ai reach port 8000 có thể confirm trade, unlock CB, reload config.
- **Fix:**
  - Thêm static API key header: `X-API-Key` validate qua env var `DASHBOARD_API_KEY`
  - Apply dependency injection lên các endpoints nguy hiểm: `confirm`, `skip`, `circuit-breaker/unlock`, `config/reload`
  - Read-only endpoints (`/api/signals`, `/api/journal`, `/api/analytics`) có thể giữ public hoặc same key
- **Note:** JWT là overkill cho single-user dashboard. Static key là đủ.

---

## PHASE 2 — Logic fixes (sprint tiếp theo)

### TASK-07 — Implement signal direction từ CHoCH
- **Status:** TODO
- **Files:** `engine/scoring_service.py` (line 164), `engine/smc.py`
- **Vấn đề:** `signal_direction = "long"` hardcoded. Hệ thống chỉ trade long.
- **Fix:**
  - Sau khi compute `smc = compute_smc_score(...)`, check `smc.choch.direction`
  - Nếu `choch.direction == "bearish"` AND `htf_bias == "bearish"` → `signal_direction = "short"`
  - Pass direction đúng vào tất cả modules: OF, Context, Regime suppression
  - Update `_publish_alert` để dùng direction đúng cho SL/TP tính toán
- **Test:** Verify short signals được generate khi CHoCH bearish + HTF bearish.

---

### TASK-08 — Filter OB retest theo signal direction
- **Status:** TODO
- **Files:** `engine/smc.py` (lines 457-462)
- **Vấn đề:** Bearish OB retest cộng +10 pts cho long signal (thực ra là resistance).
- **Fix:**
  - `compute_smc_score` nhận thêm param `signal_direction: str`
  - Filter: chỉ score OB retest nếu `ob.type == signal_direction.replace("long","bullish").replace("short","bearish")`
- **Test:** Verify bearish OB không cộng điểm khi signal_direction = "long".

---

### TASK-09 — Fix Context S/R distance (+3 pts đang bị miss)
- **Status:** TODO
- **Files:** `engine/scoring_service.py` (lines 243-246), `engine/context.py`
- **Vấn đề:** `nearest_sr_distance_pct` không được truyền → +3 pts không bao giờ được cộng.
- **Fix:**
  - Tính `nearest_sr_distance_pct` từ OB levels và FVG levels đã detect được:
    ```
    nearest_sr = min distance từ current_price đến (OB boundaries + FVG boundaries)
    nearest_sr_distance_pct = nearest_sr / current_price
    ```
  - Truyền vào `compute_context_score(..., nearest_sr_distance_pct=...)`
- **Test:** Verify +3 pts được cộng khi price > 0.5% từ nearest S/R.

---

### TASK-10 — Loại bỏ duplicate HTF bias computation
- **Status:** TODO
- **Files:** `engine/scoring_service.py`, `engine/smc.py`, `engine/context.py`
- **Vấn đề:** `detect_htf_bias(ohlcv_1h)` được gọi 2 lần: 1 lần trong `compute_smc_score`, 1 lần trong `compute_context_score`.
- **Fix:**
  - Compute HTF bias một lần trong `_run_cycle`:
    ```python
    htf_bias = detect_htf_bias(ohlcv_1h)
    smc = compute_smc_score(ohlcv_15m, ohlcv_1h, htf_bias=htf_bias)
    ctx = compute_context_score(ohlcv_1h, signal_direction, funding_rate, htf_bias=htf_bias)
    ```
  - Modify cả 2 functions để nhận `htf_bias` như optional param.

---

### TASK-11 — Fix CorrelationManager: update + log returns
- **Status:** TODO
- **Files:** `engine/scoring_service.py`, `engine/correlation_manager.py`
- **Vấn đề 1:** `CorrelationManager.update()` không được gọi trong scoring pipeline.
- **Vấn đề 2:** Correlation dùng raw price thay vì log returns → spurious correlations.
- **Fix:**
  - Trong `_run_cycle`, sau khi load OHLCV, gọi:
    ```python
    correlation_manager.update(symbol, ohlcv_1h)
    ```
  - Trong `get_correlation_matrix()`, thay `df.corr()` bằng `df.pct_change().dropna().corr()`

---

### TASK-12 — Fix OB staleness → order_book_available
- **Status:** TODO
- **Files:** `engine/scoring_service.py` (lines 115-126)
- **Vấn đề:** OB data stale (>30s, >60s) chỉ log warning, không set `order_book_available = False`.
- **Fix:**
  ```python
  OB_STALE_THRESHOLD = 60  # seconds
  if ob_age > OB_STALE_THRESHOLD:
      order_book_available = False
      logger.warning(...)
  elif bid_stack == 0.0 and ask_stack == 0.0:
      order_book_available = False
  ```

---

### TASK-13 — Fix DeltaService: string ID comparison + restart safety
- **Status:** TODO
- **Files:** `data/delta_service.py` (lines 78-96)
- **Vấn đề 1:** `str(t["id"]) > str(last_id)` — so sánh lexicographic, "9" > "10" = True.
- **Vấn đề 2:** `_last_trade_id` in-memory → reset khi restart → delta spike.
- **Fix:**
  - Dùng timestamp thay vì ID: `t["timestamp"] > last_timestamp`
  - Persist `last_timestamp` vào Redis: `delta_last_ts:{symbol}`
  - Khi restart, load từ Redis thay vì bắt đầu từ None

---

### TASK-14 — Fix `detect_4h_bias` strict `all()` condition
- **Status:** TODO
- **Files:** `engine/mtf_bias.py` (lines 109-110)
- **Vấn đề:** `all(recent_lows[i] >= recent_lows[i-1] ...)` — một candle vi phạm là "ranging". Gần như không bao giờ True.
- **Fix:** Thay bằng majority vote:
  ```python
  higher_low_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] >= recent_lows[i-1])
  higher_lows = higher_low_count >= len(recent_lows) * 0.7  # 70% threshold
  ```

---

## PHASE 3 — Performance & Infrastructure

### TASK-15 — Fix duplicate computation of `of/ctx/bonus`
- **Status:** TODO
- **Files:** `engine/scoring_service.py` (lines 235-262)
- **Vấn đề:** `of`, `ctx`, `bonus` được tính 2 lần. Lần đầu là dead code.
- **Fix:** Xóa lần tính đầu (lines 235-247). Chỉ giữ lần tính sau filter pipeline.

---

### TASK-16 — Giảm VP window từ 500 → 96 candles (24h)
- **Status:** TODO
- **Files:** `engine/scoring_service.py` (line 91), `engine/volume_profile.py`
- **Vấn đề:** VP tính trên 125 giờ (~5 ngày) — không phù hợp với scalping.
- **Fix:** Truyền `ohlcv_slice = ohlcv.iloc[-96:]` vào `compute_volume_profile()`.

---

### TASK-17 — Fix SMC O(n²) performance
- **Status:** TODO
- **Files:** `engine/smc.py` (lines 161-212)
- **Vấn đề:** Với 500 candles, `find_order_block` có độ phức tạp O(n²).
- **Fix:** Pre-compute invalidation bằng cách scan một lần từ trái sang phải, lưu breakdown points. Hoặc giới hạn lookback cho OB scan xuống 100 candles thay vì toàn bộ 500.

---

### TASK-18 — Fix CHoCH detection: thêm momentum filter
- **Status:** TODO
- **Files:** `engine/smc.py` (lines 383-396)
- **Vấn đề:** 1 tick vượt swing high là đủ để trigger CHoCH.
- **Fix:** Thêm minimum break margin: `last_close > swing_high * (1 + CHOCH_MIN_BREAK)` với `CHOCH_MIN_BREAK = 0.001` (0.1%).

---

### TASK-19 — Fix Fibonacci computation từ swing structure thay vì absolute extremes
- **Status:** TODO
- **Files:** `engine/smc.py:215-230`, `engine/confluence.py:39-62`
- **Vấn đề:** Dùng `high.max()` và `low.min()` absolute — bị lệch bởi spike candles.
- **Fix:** Dùng pivot high/low thực sự (đã có logic trong `detect_htf_bias`). Tìm most recent significant swing high và swing low dựa trên pivot detection.

---

### TASK-20 — Fix No Supply: dùng percentile thay vì max volume
- **Status:** TODO
- **Files:** `engine/vsa.py` (lines 68-75)
- **Vấn đề:** `impulse_vol = volume.max()` — 1 spike candle làm toàn bộ subsequent candles trông như "no supply".
- **Fix:** Dùng `percentile_75` hoặc median của lookback volume thay vì max.

---

### TASK-21 — Fix backtest funding rate calculation
- **Status:** TODO
- **Files:** `backtest/engine.py` (line 259)
- **Vấn đề:** `candle_idx % FUNDING_INTERVAL_HOURS` sai timeframe — với 15m TF, funding apply mỗi 2h thay vì 8h.
- **Fix:** Nhận `timeframe_minutes` param, tính `interval_candles = (8 * 60) / timeframe_minutes` và dùng `candle_idx % interval_candles`.

---

### TASK-22 — Fix `asyncio.get_event_loop()` deprecated
- **Status:** TODO
- **Files:** `engine/scoring_service.py:37`, `data/ohlcv_service.py:114,161`, `data/delta_service.py:65`, `data/orderbook_service.py:54`
- **Fix:** Thay tất cả `asyncio.get_event_loop()` bằng `asyncio.get_running_loop()` khi trong async context.

---

### TASK-23 — Fix `_assert_testnet_safe` error message format
- **Status:** TODO
- **Files:** `trade/executor.py` (line 72)
- **Vấn đề:** `"testnet={testnet!r}"` không phải f-string → không được interpolate.
- **Fix:** Thêm `f` prefix:
  ```python
  raise LiveTradingNotAllowedError(
      f"Live trading is disabled. "
      f"Set exchange.testnet = false in config.yaml to enable live trading. "
      f"Current value: testnet={testnet!r}"
  )
  ```

---

### TASK-24 — Thêm rate limiter cho ccxt calls
- **Status:** TODO
- **Files:** `data/ohlcv_service.py`, `data/orderbook_service.py`, `data/delta_service.py`
- **Vấn đề:** Với 20 assets, ~460 req/min — gần giới hạn Binance. Không có throttling.
- **Fix:** Implement token bucket rate limiter trong `trading_core/exchange/client.py`, shared across tất cả services. Budget: 800 req/min (safety margin dưới 1200).

---

### TASK-25 — Redis persistence + Sentinel setup
- **Status:** TODO
- **Files:** `docker-compose.yml` (hoặc tương đương), infra config
- **Vấn đề:** Redis là SPOF. Restart mất toàn bộ state.
- **Fix:**
  - Enable `appendonly yes` trong Redis config (AOF persistence)
  - Setup Redis Sentinel với 1 replica nếu production
  - Hoặc minimum: đảm bảo `save 60 1` trong redis.conf để RDB snapshot mỗi 60s

---

## Tracking

| Task | Status | Notes |
|------|--------|-------|
| TASK-01 | DONE | `risk/manager.py:176-178`, `trade/executor.py:100-102`, `tests/unit/test_risk_manager.py` updated |
| TASK-02 | TODO | |
| TASK-03 | TODO | |
| TASK-04 | TODO | |
| TASK-05 | TODO | |
| TASK-06 | TODO | |
| TASK-07 | TODO | phụ thuộc TASK-08 |
| TASK-08 | TODO | phụ thuộc TASK-07 |
| TASK-09 | TODO | |
| TASK-10 | TODO | |
| TASK-11 | TODO | |
| TASK-12 | TODO | |
| TASK-13 | TODO | |
| TASK-14 | TODO | |
| TASK-15 | TODO | |
| TASK-16 | TODO | |
| TASK-17 | TODO | |
| TASK-18 | TODO | |
| TASK-19 | TODO | |
| TASK-20 | TODO | |
| TASK-21 | TODO | |
| TASK-22 | TODO | |
| TASK-23 | TODO | |
| TASK-24 | TODO | |
| TASK-25 | TODO | |
