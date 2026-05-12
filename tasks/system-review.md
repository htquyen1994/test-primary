# System Review — AI Semi-Auto Crypto Futures Trading Tool
**Version:** v2.0 Phase 9 | **Review date:** 2026-05-10
**Reviewer:** Claude Sonnet 4.6 (Senior Software Architect perspective)
**Scope:** Full codebase deep-review — backend-workspace + trading-core

---

## Tổng điểm: 6.2 / 10

| Hạng mục | Điểm |
|---|---|
| 1. Kiến trúc tổng thể | 6.5/10 |
| 2. Signal Scoring Logic | 5.0/10 |
| 3. Risk Management | 5.5/10 |
| 4. Reliability | 5.0/10 |
| 5. Backtesting & Correctness | 6.0/10 |
| 6. Security | 6.5/10 |
| 7. Scalability | 6.0/10 |

---

## Top 5 Rủi ro (theo thứ tự ưu tiên)

### RISK-1 (Critical) — Leverage double-counting trong live trading
**File:** `risk/manager.py:170`, `trade/executor.py:104`

`RiskManager.compute_position_size()` nhân leverage lần 1:
```python
if self.market_type == "futures":
    position_usd *= self.leverage   # lần 1
```
`TradeExecutor.execute()` nhân leverage lần 2:
```python
if market_type == "futures":
    position_size_usd *= leverage   # lần 2 — BUG
```
Với leverage = 10x, position thực tế sẽ là **100x thay vì 10x**. Cần audit toàn bộ luồng trước bất kỳ live trade nào.

**Hơn nữa**, cách tính `risk_pct` mode đã sai về mặt logic:
```python
position_usd = (account_equity * self.risk_pct) / net_risk_pct
# → sau đó nhân leverage (sai)
```
Formula `equity × risk_pct / SL%` đã cho ra notional position chính xác để risk đúng `risk_pct`. Nhân thêm leverage thay đổi position size nhưng không thay đổi rủi ro thực sự — kết quả là oversizing nghiêm trọng.

---

### RISK-2 (Critical) — SL/TP hardcoded, bỏ qua ATR
**File:** `engine/scoring_service.py:363-365`, `engine/scoring_service.py:393-394`

```python
"stop_loss": close * 0.98,      # 2% cố định cho mọi asset, mọi volatility
"take_profit_1": close * 1.03,  # 3% cố định
"net_rr": 1.3,                  # hardcoded
```

ATR được compute tại `scoring_service.py:154` nhưng không được dùng để tính SL/TP. Trong giai đoạn volatility cao (ATR > 3%), SL 2% sẽ bị hit liên tục do market noise. Điều này vô hiệu hóa mọi edge từ scoring engine — một signal chính xác 100% vẫn thua nếu SL quá chật.

---

### RISK-3 (High) — Signal direction hardcoded "long"
**File:** `engine/scoring_service.py:164`

```python
signal_direction = "long"  # TODO: derive from CHoCH direction
```

Toàn bộ hệ thống chỉ tạo long signals. CHoCH detection, HTF bias, Order Flow, Context module — tất cả đều chạy với assumption `direction = "long"`. Hệ thống không có khả năng phản ứng khi market bearish. PARABOLIC short suppression tồn tại trong code nhưng không bao giờ được trigger vì không có short signal nào.

---

### RISK-4 (High) — Circuit Breaker Trigger 4 (drawdown) bị broken
**File:** `risk/circuit_breaker.py:438-448`

```python
def _get_7day_equity_peak(self) -> float:
    cached = r.get("circuit_breaker:7day_peak")
    if cached:
        return float(cached)
    # Fallback: compute from DB (simplified — use cumulative PnL)
    return 0.0   # ← luôn trả về 0 nếu không có cache
```

`peak = 0.0` → `check_drawdown` check: `(0 - equity) / 0` → ZeroDivisionError hoặc `drawdown = -∞` → không bao giờ > 10%. Trigger 4 không bao giờ fire. Cache key `circuit_breaker:7day_peak` không được set ở bất kỳ đâu trong codebase.

---

### RISK-5 (High) — Redis là Single Point of Failure không có fallback
**File:** `trading_core/cache/redis_client.py`, `main.py`

Không có Redis Sentinel, không có Cluster, không có persistence config. Nếu Redis down:
- Tất cả OHLCV buffer bị mất (cần warmup lại)
- BTC spike cooldown bị xóa → Alt alerts bật lại giữa chừng
- Circuit breaker cache mất → cần re-query DB cho mọi candle
- Delta history mất → dynamic threshold về fallback 1000.0
- Toàn bộ system halt cho đến khi Redis restart

---

## 1. Kiến trúc tổng thể (6.5/10)

### 1.1 Thiết kế 3 lớp — Hợp lý
Phân tách Data / Engine / UI rõ ràng. Redis pub/sub (`candle_close` → `ScoringService`) là decoupling tốt.

### 1.2 REST polling vs WebSocket — Trade-off chấp nhận được, nhưng DeltaService cần WebSocket
- Order Book poll 5s là ổn cho 15m trigger
- **DeltaService poll 10s, limit=100 trades là không đủ**: Trong giai đoạn high volume, BTC có thể có >1000 trades/10s. Delta bị underestimate liên tục.
- **String ID comparison bug** (`delta_service.py:84`): `str("9") > str("10")` là True (lexicographic). Khi exchange dùng numeric trade ID, sẽ miss hoặc double-count trades.
- **Memory-based last_id** (`delta_service.py:78`): Khi service restart, `last_id = None` → tất cả 100 trades trong poll đầu tiên được count là "new" → delta spike giả.

### 1.3 Redis bottleneck
- `ScoringService._run_cycle` thực hiện 8+ Redis calls per cycle (lrange × 4 timeframes + get OB + get delta + get funding + pipeline). Với 20 assets đóng nến cùng lúc = 160 Redis calls gần như đồng thời.
- Không có connection pooling config được thấy — mỗi DB write trong `_persist_signal` tạo session mới.

### 1.4 asyncio + threading — Anti-pattern tiềm ẩn
```python
# scoring_service.py:37
self._loop = asyncio.get_event_loop()  # deprecated từ Python 3.10+
```
Nên dùng `asyncio.get_running_loop()`. `asyncio.get_event_loop()` trong context của thread có thể tạo loop mới thay vì lấy loop đang chạy.

Không có backpressure: nếu scoring 1 cycle mất >15m (DB chậm, nhiều assets), các candle_close events tiếp theo sẽ stack up trong Redis pub/sub buffer mà không có cơ chế drain.

### 1.5 Bug: Duplicate computation trong scoring pipeline
**File:** `engine/scoring_service.py:235-262`

`of`, `ctx`, `bonus` được tính 2 lần. Lần đầu (line 235-247) là dead code bị overwrite ngay:
```python
of = compute_order_flow_score(...)   # tính lần 1 — dead code
ctx = compute_context_score(...)     # tính lần 1 — dead code
bonus = compute_confluence_bonus(...)# tính lần 1 — dead code
# ... (các giá trị trên không được dùng)
of = compute_order_flow_score(...)   # tính lần 2 — ghi đè
ctx = compute_context_score(...)     # tính lần 2
bonus = compute_confluence_bonus(...)# tính lần 2
```

---

## 2. Signal Scoring Logic (5.0/10)

### 2.1 SMC Module (`engine/smc.py`)

**Bug: OB retest không lọc theo signal direction**
`find_order_block` trả về cả bullish và bearish OBs. `compute_smc_score` check retest cho tất cả:
```python
for ob in obs:
    if ob.valid and ob.is_price_retesting(current_price):
        result.ob_retested = True
        result.score += 10.0  # cộng điểm cho cả bearish OB khi signal là long
        break
```
Một bearish OB được retest trong khi tìm long entry = thực ra là resistance, không phải support. Cần filter `ob.type == "bullish"` khi `signal_direction == "long"`.

**Performance: O(n²) trong `find_order_block`**
```python
for i in range(n - 2, 0, -1):          # O(n)
    ...
    for j in range(i + 1, n):           # O(n) inner
        ob.invalidate_if_broken(...)    # worst case O(n²)
```
Với 500 candles: 500 × 500 / 2 = 125,000 iterations per scoring cycle. Với 20 assets = 2.5M iterations per 15m close event.

**CHoCH detection quá nhạy**
```python
# smc.py:375-376
swing_high = float(reference["high"].max())  # absolute max
if last_close > swing_high:                  # 1 tick là đủ để trigger CHoCH
    return CHoCH(direction="bullish", ...)
```
Bất kỳ close nào vượt absolute high của 20 nến trước đó đều trigger CHoCH. Trong ranging market, mọi bounce đều generate CHoCH. Nên thêm minimum momentum filter (ví dụ: close > swing_high × 1.001).

**Fibonacci levels tính từ absolute extremes**
`_compute_fib_levels` dùng `high.max()` và `low.min()` over 50 candles — không phải swing structure thực sự. Nếu có 1 spike candle outlier trong 50 candles, toàn bộ Fib levels bị lệch.

**HTF bias fallback không ổn định**
```python
# smc.py:336-338
if second_close > first_close * 1.002:   # chỉ cần 0.2% thay đổi
    return "bullish"
```
Khi không đủ pivot points (rất phổ biến trong ranging markets), 0.2% difference trong mean close là quá nhỏ và dễ flip theo noise.

**HTF bias tính hai lần**
`detect_htf_bias` được gọi trong cả `compute_smc_score` (smc.py) và `compute_context_score` (context.py), với cùng `ohlcv_1h` input. Duplicate computation mỗi cycle.

### 2.2 VSA Module (`engine/vsa.py`)

**`detect_no_supply` dùng max volume làm reference**
```python
impulse_vol = float(ohlcv.iloc[-lookback - 1:-1]["volume"].max())
```
Nếu có 1 spike volume outlier trong lookback window, mọi candle tiếp theo sẽ có `ratio < 0.4` — tức là "No Supply" signal liên tục. Nên dùng rolling mean hoặc percentile thay vì max.

**`detect_effort_vs_result` — double threshold quá strict**
`vol_ratio < 0.5 AND range_ratio < 0.3` — cả hai phải thỏa mãn đồng thời. EFFORT_RANGE_RATIO = 0.3 là rất chật: range phải nhỏ hơn 30% ATR. Trong high-volatility assets, range 30% ATR là rất hiếm khi price "holds".

**Absorption không cộng vào VSA score**
`detect_absorption` được gọi và set `result.absorption = True` nhưng không có `result.score += X`. Absorption chỉ được dùng như metadata cho Order Flow module. Điều này intentional (tránh double-count) nhưng không được document rõ.

### 2.3 Context Module (`engine/context.py`)

**CRITICAL: S/R distance +3 pts KHÔNG BAO GIỜ được cộng**
```python
# context.py:74 — parameter có giá trị mặc định 0.0
def compute_context_score(ohlcv_1h, signal_direction, funding_rate,
                          nearest_sr_distance_pct: float = 0.0):
```
Trong `scoring_service.py`:
```python
ctx = compute_context_score(
    ohlcv_1h if not ohlcv_1h.empty else ohlcv,
    "long",
    funding_rate,
    # nearest_sr_distance_pct không được truyền vào!
)
```
`nearest_sr_distance_pct` mặc định là `0.0 < SR_DISTANCE_THRESHOLD (0.005)` → condition không bao giờ True. **Context module max score thực tế là 12 pts (HTF+8, Funding+4), không phải 15 pts.** Điều này làm giảm hệ thống khoảng 2.4 điểm trên thang 100 với mọi signal.

**Funding rate threshold cứng ±0.05%**
Trong thị trường cực kỳ bullish (bull run), funding rate 0.1-0.3% là bình thường. Threshold 0.05% sẽ block điểm funding hầu hết thời gian trong trending markets — đây là thời điểm system nên trade mạnh nhất.

### 2.4 Volume Profile Module (`engine/volume_profile.py`)

**VP tính trên 500 candles (125 giờ)**
`scoring_service.py:91`: `r.lrange(ohlcv_key, 0, 499)` lấy 500 candles. VP được tính trên toàn bộ 500 nến này (~5 ngày). Đây là **session volume profile**, không phải intraday VP. POC từ 5 ngày trước kém relevance cho scalping hiện tại. Nên dùng 1 ngày (96 × 15m candles) hoặc theo session.

**O(n × bins) mỗi cycle**
500 candles × 50 bins = 25,000 iterations. Không tệ nhưng cộng với O(n²) của SMC → mỗi scoring cycle là ~127,500 operations thuần Python. Với 20 assets đồng thời là 2.5M operations.

**Không có time-based weighting**
Candle hôm qua = candle 5 ngày trước trong VP calculation. Nên weighted VP theo recency.

### 2.5 Confluence Module (`engine/confluence.py`)

**Fibonacci levels cùng vấn đề với SMC**: Dùng absolute max/min, không phải swing highs/lows. Xem mục 2.1.

**Bonus normalization không nhất quán với scoring formula**
```python
# confluence.py:130
normalized = min(best_bonus / 45.0 * 15.0, 15.0)
```
Module tự normalize về 15. Nhưng scorer cũng cộng bonus vào raw trước khi normalize toàn bộ:
```python
raw = OF + SMC + VSA + CTX + bonus  # bonus đã là [0, 15]
final = min(round(raw * regime_mult / 125 * 100), 100)
```
Max raw = 35+30+30+15+15 = 125. Bonus đã được cap tại 15, đúng. Không có lỗi logic nhưng normalization trong module khiến khó maintain — bonus nên trả về raw [0-45] và để scorer normalize.

### 2.6 Regime Detector (`engine/regime_detector.py`)

**TRENDING không phân biệt direction**
ADX chỉ đo strength, không đo direction. Một downtrend mạnh (ADX > 25) và một uptrend mạnh đều return `RegimeState(regime="TRENDING", multiplier=1.0)`. Long signal trong strong downtrend vẫn nhận multiplier 1.0.

**ADX (1H) vs ATR (15m) trên 2 timeframes khác nhau**
PARABOLIC dùng ATR 15m, TRENDING/CHOPPY dùng ADX 1H. Một spike 15m mạnh (PARABOLIC) trong khi ADX 1H = 15 (CHOPPY) → PARABOLIC override đúng. Nhưng trường hợp ngược lại (ADX 1H = 30, ATR 15m bình thường) sẽ classify TRENDING mà không check if 15m đang trong chaos.

---

## 3. Risk Management (5.5/10)

### 3.1 Circuit Breaker (`risk/circuit_breaker.py`)

**Trigger 4 broken (đã nêu trong RISK-4)**

**`_check_consecutive_losses` không handle restart**
Timestamps được lưu trong Redis key `circuit_breaker:recent_losses`. Nếu Redis restart, history bị xóa. 3 losses liên tiếp trước restart = reset về 0 loss.

**Daily loss check query không chính xác**
```python
# circuit_breaker.py:428
"WHERE entry_timestamp >= :today"  # dùng entry_timestamp
```
Nên dùng `exit_timestamp` — một trade mở ngày hôm qua và đóng hôm nay sẽ không được count vào daily loss của hôm nay dù loss thực sự xảy ra hôm nay.

**Smart unlock chỉ check BTC/ETH regime**
```python
# circuit_breaker.py:454
for symbol in ["BTC/USDT", "ETH/USDT"]:
    regime = r.get(RedisKeys.regime(symbol))
```
Nếu circuit breaker trigger vì SOL/USDT loss nhưng BTC/ETH regime không được lưu vào Redis (hoặc đã expire), smart unlock sẽ dùng `regime_at_trigger = "UNKNOWN"` → condition `current_regime == regime_at_trigger` = False → auto unlock dù market unchanged. Regime cần được persist reliably.

**Không có notification khi CB sắp hết hạn**
User không biết CB sắp unlock. Cần notification 30-60 phút trước unlock.

### 3.2 BTC Guard (`engine/btc_guard.py`)

**Alt short trong BTC pump không được xử lý**
```python
# btc_guard.py:182
if direction == "pump" and signal_direction == "long":
    # check relative weakness...
```
Short signals trong BTC pump period không bị filter. Nếu hệ thống sau này hỗ trợ short, BTC pump + Alt short sẽ pass qua guard mà không có reduction.

**Relative weakness check dùng alt_gain_pct = 0**
Trong `check_alt_signal`, `alt_gain_pct` được nhận từ caller. Trong `btc_guard_filter.py`, giá trị này không được tính từ actual data:
```python
# engine/filters/btc_guard_filter.py (không được review nhưng pattern tương tự)
```
Cần verify `alt_gain_pct` được tính đúng trong filter context.

**Cooldown không persistent**
Redis key với TTL — xem RISK-5.

### 3.3 Risk Manager (`risk/manager.py`)

**Kelly mode là stub hoàn toàn**
```python
elif self.mode == "kelly":
    # Simplified Kelly: use risk_pct as fallback
    position_usd = (account_equity * self.risk_pct) / sl_pct
```
Đây là risk_pct mode. Kelly formula thực sự: `f = (p × b - q) / b` cần win rate và payoff ratio từ historical data — chưa implement.

**Leverage trong risk_pct mode sai logic** (đã nêu trong RISK-1)

**CorrelationManager không được update trong scoring pipeline**
`RiskManager` nhận `correlation_manager` nhưng `CorrelationManager.update(asset, ohlcv_1h)` không được gọi trong `scoring_service.py`. Correlation matrix sẽ luôn rỗng → `get_correlated_group` luôn trả về `[]` → group risk check không bao giờ block.

### 3.4 Correlation Manager (`engine/correlation_manager.py`)

**Dùng raw price thay vì log returns**
```python
self._correlation_matrix = df.corr(method="pearson")
```
Correlation tính trên close prices. Trong bull market, tất cả assets đều trend up → correlation matrix gần như toàn số 0.9+ → mọi pair đều "correlated" → limit bị kích hoạt quá thường xuyên. Nên dùng log returns: `df.pct_change().corr()`.

---

## 4. Reliability (5.0/10)

### 4.1 OHLCVService (`data/ohlcv_service.py`)

**`asyncio.get_event_loop()` deprecated**
```python
# ohlcv_service.py:114, 161
loop = asyncio.get_event_loop()  # deprecated Python 3.10+
```
Tương tự trong `delta_service.py:65`, `orderbook_service.py:54`.

**`_last_ts` in-memory — restart reset**
Khi OHLCVService restart, `_last_ts = {}` → mọi candle trong poll đầu tiên được xử lý như "new" → N candle_close events được publish → N scoring cycles cùng lúc. Nếu đang chạy nhiều assets, đây là thundering herd problem.

**BTC spike detection chỉ check candle `iloc[-2]`**
```python
# btc_guard.py:100
last_candle = ohlcv_btc_15m.iloc[-2]
```
Chỉ check candle ngay trước candle đang form. Nếu spike xảy ra 2 candles trước (và cooldown chưa được set vì spike state không persistent), nó sẽ bị bỏ qua.

### 4.2 ScoringService (`engine/scoring_service.py`)

**OB staleness warning nhưng không block**
```python
# scoring_service.py:117-118
if ob_age > 30:
    logger.warning("OB data stale...")  # chỉ warn
# order_book_available = not (bid_stack == 0.0 and ask_stack == 0.0)
```
OB data 5 phút cũ vẫn được dùng mà không set `order_book_available = False`. Nếu OrderBookService crash, scoring sẽ dùng stale data (bid_stack, ask_stack != 0 từ last successful poll) mà không biết data đã expired. Nên: nếu `ob_age > 60` → set `order_book_available = False`.

**`_persist_signal` tạo DB session mới mỗi cycle**
```python
# scoring_service.py:355
db = get_session_factory()()  # new session mỗi lần
...
db.close()
```
Không có connection pooling. Với 20 assets = 20 concurrent DB connections khi tất cả đóng nến cùng lúc. SQL Server có connection limit.

**`_get_active_filters` tạo ConfigSystem mới mỗi cycle**
```python
# scoring_service.py:418
cfg = ConfigSystem(os.environ.get("CONFIG_PATH", "config.yaml"))
```
Parse config.yaml từ disk mỗi 15 phút × 20 assets = 80 file reads/giờ. Nên cache filter config.

### 4.3 API Server (`api/main.py`)

**`_active_signals` in-memory không có size limit**
```python
# api/main.py:76
_active_signals: dict = {}  # never pruned automatically
```
Signals chỉ bị remove khi confirmed, skipped, hoặc expired qua endpoint. Nếu frontend disconnect, signals accumulate indefinitely → memory leak dài hạn.

**`_open_positions` không được populate**
```python
_open_positions: dict = {}  # luôn empty
```
`/api/portfolio` và `/ws/portfolio` luôn trả về `portfolio_heat = 0.0`. Portfolio monitoring hoàn toàn không hoạt động.

**`/api/signals/{id}/confirm` không thực sự execute trade**
```python
# api/main.py:134-136
signal["user_action"] = "CONFIRM"
signal["status"] = "Submitted"
# In production: dispatch to Celery task for async execution
logger.info("Signal confirmed: ...")
return {"status": "submitted"}
```
TradeExecutor không được gọi. Confirm button không làm gì ngoài update in-memory state.

**`/api/backtest/run` là stub**
```python
# api/main.py:417
return {"status": "queued", "strategy": body.strategy, "asset": body.asset}
# TODO: dispatch to Celery task
```
Không có backtest nào được chạy.

**Không có authentication trên bất kỳ endpoint nào**
`/api/circuit-breaker/unlock`, `/api/config/reload`, `/api/signals/{id}/confirm` — tất cả đều public. Bất kỳ ai reach được port 8000 có thể unlock circuit breaker hoặc trigger trade execution.

**`/api/circuit-breaker/unlock` nhận `body: dict` thay vì Pydantic model**
Không có input validation schema.

---

## 5. Backtesting & Correctness (6.0/10)

### 5.1 BacktestingEngine (`backtest/engine.py`)

**Position size hardcoded $100**
```python
# backtest/engine.py:141
position_size_usd=100.0,  # simplified; use RiskManager in production
```
Backtest results không có ý nghĩa về mặt position sizing và PnL tương đối. Win rate và profit factor vẫn meaningful, nhưng expected return không thể scale sang live.

**`entry_timestamp` dùng `datetime.now()` thay vì candle timestamp**
```python
# backtest/engine.py:133
entry_timestamp=datetime.now(timezone.utc),  # sai — nên dùng candle timestamp
```
Trade journal trong backtest không có accurate timeline.

**SL/TP kiểm tra: SL luôn được check trước TP**
```python
# backtest/engine.py:200-208
if low <= trade.stop_loss:     # SL check trước
    ...
    return trade
if high >= trade.take_profit_1: # TP check sau
```
Nếu cùng candle hit cả SL lẫn TP (candle range rộng), SL luôn thắng. Trong thực tế, chúng ta không biết SL hay TP hit trước. Điều này tạo ra pessimistic bias trong backtest.

**Không check TP2**
Chỉ TP1 được check trong backtest. TP2 không được model.

**Funding rate calculation không chính xác**
```python
# backtest/engine.py:259
if candle_idx % FUNDING_INTERVAL_HOURS == 0:  # mỗi 8 candles (nếu TF = 1H)
```
`FUNDING_INTERVAL_HOURS = 8`. Nếu timeframe là 15m, funding nên apply mỗi 32 candles (8h × 4). Nhưng code dùng `candle_idx % 8` = mỗi 8 candles = mỗi 2 giờ (với 15m TF). Funding rate bị charge 4x quá nhiều.

**Backtest và live engine không dùng cùng scoring logic**
Backtest dùng `strategy.generate_signals()` (từ `strategies/` folder), live dùng `ScoringService._run_cycle()`. Đây là hai code paths hoàn toàn khác nhau. Walk-forward backtest không validate live engine logic.

### 5.2 Walk-Forward Analysis

**Cần verify `backtest/walk_forward.py` không leak test-period data vào train window**

### 5.3 Tests

319 tests + Hypothesis PBT là solid về unit coverage. Tuy nhiên:
- Không có integration test cho full pipeline (candle close → alert published)
- Không có test cho `scoring_service.py` end-to-end
- Không có test nào verify ATR-based SL/TP (vì SL/TP là hardcoded %)
- Không có property test nào check `signal_direction != "long"` path

---

## 6. Security (6.5/10)

### 6.1 Testnet guard bug nhỏ
**File:** `trade/executor.py:68-72`

```python
raise LiveTradingNotAllowedError(
    "Live trading is disabled. "
    "Set exchange.testnet = false in config.yaml to enable live trading. "
    "Current value: testnet={testnet!r}"  # ← KHÔNG phải f-string!
)
```
`{testnet!r}` không được interpolate. Sửa: thêm `f` prefix.

### 6.2 Không có authentication
Xem mục 4.3. Bất kỳ service nào trong cùng network đều có thể call API. Với live trading, đây là rủi ro nghiêm trọng.

### 6.3 CORS config ổn
```python
_allowed_origins = ["http://localhost:5173", "http://localhost:3000"]
```
Explicit origins, không dùng wildcard. Tốt. Nhưng cần ALLOWED_ORIGINS env var cho production.

### 6.4 `.env` file tồn tại trong workspace
Cần verify `.gitignore` cover `.env`. Không được commit API keys.

---

## 7. Scalability (6.0/10)

### 7.1 Rate limit risk
Với 20 assets:
- OHLCVService: 20 symbols × 5 TF × poll_interval riêng = ~40-100 req/min cho OHLCV
- OrderBook: 20 symbols × 12 req/min = 240 req/min
- Delta: 20 symbols × 6 req/min = 120 req/min
- Tổng: ~400-460 req/min

Binance public API limit là 1200 req/min với 20 weight. Với 20 assets đang gần giới hạn. Không có rate limiter/token bucket trong code.

### 7.2 O(n²) SMC + O(n × bins) VP mỗi cycle
Với 20 assets: `20 × (125,000 + 25,000) = 3M` operations thuần Python mỗi 15 phút. Ổn cho single machine nhưng không scale tốt lên 50+ assets.

### 7.3 DB write trong hot path
`_persist_signal` viết vào SQL Server synchronously trong scoring pipeline. Nên queue vào Celery task.

---

## Danh sách vấn đề theo priority

### Priority 1 — Fix trước live trading

| ID | Vấn đề | File | Mức độ |
|---|---|---|---|
| P1-01 | Leverage double-counting | `risk/manager.py:170`, `trade/executor.py:104` | CRITICAL |
| P1-02 | SL/TP hardcoded 2%/3% — nên dùng ATR | `engine/scoring_service.py:363-365, 393-394` | CRITICAL |
| P1-03 | Circuit Breaker Trigger 4 stub | `risk/circuit_breaker.py:438-448` | HIGH |
| P1-04 | `_open_positions` không được populate | `api/main.py:76` | HIGH |
| P1-05 | Confirm signal không gọi TradeExecutor | `api/main.py:134-142` | HIGH |
| P1-06 | Không có authentication trên API | `api/main.py` | HIGH |

### Priority 2 — Fix trong sprint tiếp theo

| ID | Vấn đề | File | Mức độ |
|---|---|---|---|
| P2-01 | Signal direction hardcoded "long" | `engine/scoring_service.py:164` | HIGH |
| P2-02 | OB retest không filter theo direction | `engine/smc.py:457-462` | MEDIUM |
| P2-03 | Context S/R distance không được truyền | `engine/scoring_service.py:243-246` | MEDIUM |
| P2-04 | HTF bias tính 2 lần (SMC + Context) | `engine/smc.py`, `engine/context.py` | MEDIUM |
| P2-05 | CorrelationManager không được update | `engine/scoring_service.py` | MEDIUM |
| P2-06 | Correlation dùng raw price thay vì returns | `engine/correlation_manager.py:136` | MEDIUM |
| P2-07 | OB staleness không set `order_book_available=False` | `engine/scoring_service.py:117-121` | MEDIUM |
| P2-08 | DeltaService string ID comparison bug | `data/delta_service.py:84` | MEDIUM |
| P2-09 | DeltaService last_id reset khi restart | `data/delta_service.py:78` | MEDIUM |
| P2-10 | Duplicate computation of `of/ctx/bonus` | `engine/scoring_service.py:235-262` | LOW |

### Priority 3 — Cải thiện dài hạn

| ID | Vấn đề | File | Mức độ |
|---|---|---|---|
| P3-01 | SMC O(n²) performance | `engine/smc.py:161-212` | MEDIUM |
| P3-02 | VP window 500 candles — quá dài cho scalping | `engine/scoring_service.py:91` | MEDIUM |
| P3-03 | DeltaService cần WebSocket thay vì polling | `data/delta_service.py` | MEDIUM |
| P3-04 | Funding threshold 0.05% quá chật | `engine/context.py:25` | LOW |
| P3-05 | `_get_active_filters` parse config.yaml mỗi cycle | `engine/scoring_service.py:418` | LOW |
| P3-06 | `asyncio.get_event_loop()` deprecated | nhiều files | LOW |
| P3-07 | `_active_signals` không có size limit | `api/main.py:76` | LOW |
| P3-08 | Backtest funding rate calculation sai TF | `backtest/engine.py:259` | MEDIUM |
| P3-09 | Backtest/live engine code path khác nhau | `backtest/engine.py`, `engine/scoring_service.py` | HIGH |
| P3-10 | Redis SPOF — cần Sentinel | infra | HIGH |
| P3-11 | CHoCH detection quá nhạy | `engine/smc.py:383` | MEDIUM |
| P3-12 | Fibonacci từ absolute extremes, không phải swing | `engine/smc.py:226`, `engine/confluence.py:56` | MEDIUM |
| P3-13 | No Supply dùng max volume làm reference | `engine/vsa.py:69` | MEDIUM |
| P3-14 | `_assert_testnet_safe` error message format bug | `trade/executor.py:72` | LOW |
| P3-15 | Backtest SL/TP check order (SL bias) | `backtest/engine.py:200-208` | LOW |
| P3-16 | Kelly mode là stub | `risk/manager.py:143-146` | LOW |
| P3-17 | `detect_4h_bias` `all()` quá strict | `engine/mtf_bias.py:109-110` | MEDIUM |
| P3-18 | Per-asset delta fallback threshold | `engine/order_flow.py:33` | LOW |

---

## Đề xuất ưu tiên implement

### Giai đoạn 1 — Trước live trading (P1)
1. Fix leverage logic: chỉ apply leverage ở **một chỗ** (executor), không apply ở RiskManager
2. ATR-based SL/TP: `sl = entry - 1.5 × atr`, `tp = entry + rr × sl_distance`
3. Implement `_get_7day_equity_peak()` từ trade_journal hoặc dedicated equity_log table
4. Kết nối TradeExecutor thực sự vào confirm endpoint
5. Thêm JWT auth hoặc ít nhất API key header cho `/api/signals/*/confirm`
6. Populate `_open_positions` từ trade_journal khi có open trade

### Giai đoạn 2 — Sprint tiếp theo (P2)
7. Implement signal direction từ CHoCH: nếu bearish CHoCH → `signal_direction = "short"`
8. Filter OB theo direction trong `compute_smc_score`
9. Truyền `nearest_sr_distance_pct` vào `compute_context_score`
10. Gộp HTF bias computation (tính một lần, share giữa SMC và Context)
11. Gọi `CorrelationManager.update()` trong scoring pipeline
12. Chuyển correlation sang log returns

### Giai đoạn 3 — Infrastructure
13. Redis Sentinel (ít nhất 1 replica + persistence `appendonly yes`)
14. DeltaService → WebSocket (trade stream)
15. Rate limiter cho ccxt calls (token bucket, ~800 req/min budget)
16. Tách `_persist_signal` ra Celery task
17. Volume Profile: giảm window xuống 96 candles (24h)

---

*Review này dựa trên code tại commit `202ca30` (develop branch). Để review sâu hơn từng module cụ thể (walk-forward analysis, DB schema, frontend WebSocket), hỏi thêm.*
