# Phần 6: Object Model Documentation — Crypto Trading System

> **Cập nhật sau code review:** Bổ sung FilterResult, ScoreInput, ScoreOutput, ScoreBreakdown (tách riêng), và sửa file path cho Signal.

---

## 6.1 Core Domain Objects

### Signal

**File:** `workspace/backend-workspace/strategies/signal.py` *(không phải strategies/base.py)*
**Type:** `@dataclass` với `__post_init__` validation
**Mục đích:** Discrete buy/sell recommendation được tạo bởi một Strategy. Đây là đối tượng trung tâm truyền qua toàn bộ pipeline từ Strategy → SignalScorer → RiskManager → AlertBuilder.

**Fields:**

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `strategy_name` | `str` | required | non-empty | Tên strategy tạo signal |
| `asset` | `str` | required | non-empty, e.g. "BTC/USDT" | Symbol giao dịch |
| `timeframe` | `str` | required | "15m"\|"30m"\|"1h" | Timeframe trigger |
| `direction` | `str` | required | "long"\|"short" | Hướng giao dịch |
| `candle_index` | `int` | required | ≥ 0 | Index của closed candle trong buffer |
| `candle_timestamp` | `datetime` | required | UTC | Timestamp của candle |
| `entry_price` | `float` | required | > 0 | Giá entry đề xuất |
| `stop_loss` | `float` | required | > 0, long: < entry, short: > entry | Giá stop loss |
| `take_profit_1` | `float` | required | > 0, long: > entry, short: < entry | TP1 |
| `take_profit_2` | `float` | required | > 0 | TP2 (xa hơn TP1) |
| `raw_score` | `float` | required | [0.0, 125.0] | Score trước normalization |
| `final_score` | `int` | required | [0, 100] | Score sau normalization |
| `score_breakdown` | `dict` | required | keys: order_flow, smc, vsa, context, bonus | Chi tiết từng module |
| `regime` | `str` | required | TRENDING\|RANGING\|PARABOLIC\|CHOPPY | Regime tại thời điểm tạo |
| `regime_multiplier` | `float` | required | [0.6, 1.0] | Multiplier áp dụng |
| `funding_rate` | `float` | required | [-0.01, 0.01] | Funding rate tại thời điểm |
| `portfolio_heat` | `float` | required | ≥ 0 | Portfolio heat % |
| `correlated_group_risk` | `float` | required | ≥ 0 | Correlated group risk % |
| `classification` | `str` | required | ALERT\|WATCH\|IGNORE | Final classification |
| `expires_at_candle` | `int` | required | > candle_index | Candle index hết hạn |
| `created_at` | `datetime` | `datetime.utcnow()` | — | Tự động set |
| `user_action` | `Optional[str]` | `None` | CONFIRM\|SKIP\|EXPIRED\|IGNORE\|None | Set sau khi trader action |
| `skip_reason` | `Optional[str]` | `None` | — | Lý do skip |

**Lifecycle:**
- **Tạo:** BaseStrategy.generate_signals() — mỗi candle close
- **Đọc:** SignalScorer.score(), RiskManager.check(), AlertBuilder.build()
- **Modify:** ScoringService (set final_score, classification sau Phase 9 adjustments)
- **Destroy:** Sau khi ghi vào signal_log SQL và publish (hoặc bị block)

**Serialization:**
```json
{
  "signal_id": "uuid",
  "strategy_name": "smc_ob_fvg",
  "asset": "BTC/USDT",
  "timeframe": "15m",
  "direction": "long",
  "candle_timestamp": "2024-01-15T09:15:00Z",
  "entry_price": 45230.5,
  "stop_loss": 44800.0,
  "take_profit_1": 46000.0,
  "take_profit_2": 47500.0,
  "raw_score": 87.5,
  "final_score": 80,
  "score_breakdown": {
    "order_flow": 0.0,
    "smc": 30.0,
    "vsa": 20.0,
    "context": 15.0,
    "bonus": 12.5
  },
  "regime": "TRENDING",
  "regime_multiplier": 1.0,
  "funding_rate": 0.000125,
  "portfolio_heat": 0.04,
  "correlated_group_risk": 0.02,
  "classification": "ALERT",
  "expires_at_candle": 12465,
  "created_at": "2024-01-15T09:15:01Z",
  "user_action": null
}
```

---

### TradeResult

**File:** `workspace/backend-workspace/backtest/models.py`
**Type:** `@dataclass`
**Mục đích:** Kết quả một giao dịch mô phỏng (backtest) hoặc live. Lưu trữ đầy đủ thông tin để tính metrics.

**Fields:**

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `trade_id` | `str` | required | UUID format | Unique ID |
| `strategy_name` | `str` | required | non-empty | Strategy |
| `asset` | `str` | required | — | Symbol |
| `timeframe` | `str` | required | — | Timeframe |
| `direction` | `str` | required | "long"\|"short" | Hướng |
| `entry_timestamp` | `datetime` | required | UTC | Thời điểm vào |
| `exit_timestamp` | `Optional[datetime]` | `None` | UTC | Thời điểm thoát (None nếu đang mở) |
| `entry_price` | `float` | required | > 0 | Giá entry theo signal |
| `exit_price` | `Optional[float]` | `None` | > 0 | Giá thoát (SL hoặc TP) |
| `actual_entry_price` | `float` | required | > 0 | Sau slippage: `entry × (1 + slippage)` cho long |
| `actual_exit_price` | `Optional[float]` | `None` | > 0 | Sau slippage |
| `stop_loss` | `float` | required | > 0 | SL |
| `take_profit_1` | `float` | required | > 0 | TP1 |
| `take_profit_2` | `float` | required | > 0 | TP2 |
| `position_size_usd` | `float` | required | > 0 | Size (USD) |
| `leverage` | `int` | required | ≥ 1 | Leverage |
| `slippage_entry` | `float` | required | ≥ 0 | `actual - expected` entry |
| `slippage_exit` | `float` | required | ≥ 0 | `actual - expected` exit |
| `fee_entry` | `float` | required | ≥ 0 | Entry fee = size × fee_rate |
| `fee_exit` | `float` | required | ≥ 0 | Exit fee = size × fee_rate |
| `funding_paid` | `float` | required | — | Tổng funding rate đã trả |
| `gross_pnl` | `float` | required | — | PnL trước fees/slippage |
| `net_pnl` | `float` | required | — | gross - fees - slippage - funding |
| `result` | `str` | required | "win"\|"loss"\|"be" | Kết quả |
| `signal_score` | `int` | required | [0, 100] | Score tại thời điểm tạo signal |
| `exchange_order_id` | `Optional[str]` | `None` | — | Order ID (live trading only) |
| `is_testnet` | `bool` | `True` | — | Testnet hay live |

**Lifecycle:**
- **Tạo:** BacktestEngine (simulation) hoặc TradeExecutor (live)
- **Đọc:** MetricsCalculator, WalkForwardAnalyzer, JournalPage
- **Modify:** Khi position đóng (exit_price, net_pnl, result được set)
- **Destroy:** Không — lưu persistent trong trade_journal SQL

---

### OrderFlowResult

**File:** `workspace/backend-workspace/engine/order_flow.py`
**Type:** `@dataclass`
**Mục đích:** Kết quả tính toán của OrderFlowAnalysis module.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score` | `float` | required | Score [0.0, 35.0] |
| `delta` | `float` | required | Cumulative delta value |
| `delta_threshold` | `float` | required | Dynamic threshold đã tính |
| `bid_stack` | `float` | required | Total bid size tại vùng S/R |
| `ask_stack` | `float` | required | Total ask size tại vùng S/R |
| `absorption` | `bool` | required | Absorption detected? |
| `delta_dominance` | `bool` | required | delta > threshold? |
| `bid_dominance` | `bool` | required | bid > ask × 2? |

---

### ContextResult

**File:** `workspace/backend-workspace/engine/context.py`
**Type:** `@dataclass`
**Mục đích:** Kết quả tính toán của ContextFilter module.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score` | `float` | required | Score [0.0, 15.0] |
| `htf_bias` | `str` | required | BULLISH\|BEARISH\|NEUTRAL từ 1H |
| `bias_aligned` | `bool` | required | 1H bias aligned với signal direction? |
| `funding_neutral` | `bool` | required | \|funding_rate\| ≤ 0.0005? |
| `price_away_from_sr` | `bool` | required | Distance ≥ 0.5%? |
| `funding_rate` | `float` | required | Funding rate tại thời điểm |
| `nearest_sr_distance_pct` | `float` | required | % distance từ nearest S/R |

---

### LockInfo

**File:** `workspace/backend-workspace/risk/circuit_breaker.py`
**Type:** `@dataclass`
**Mục đích:** Thông tin về một Circuit Breaker lock event.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `int` | required | DB ID |
| `trigger_type` | `str` | required | CONSECUTIVE_LOSSES\|LOSS_MAGNITUDE\|DAILY_LOSS_CAP\|DRAWDOWN_FROM_PEAK |
| `trigger_detail` | `Optional[str]` | `None` | Human-readable detail |
| `triggered_at` | `datetime` | required | UTC |
| `unlock_at` | `datetime` | required | UTC — khi nào tự unlock |
| `regime_at_trigger` | `str` | required | Regime state khi trigger |
| `is_locked` | `bool` | required | Đang locked? |
| `unlock_requires_review` | `bool` | required | T4: cần review note |
| `review_note` | `Optional[str]` | `None` | Manual review note |
| `unlocked_at` | `Optional[datetime]` | `None` | UTC — khi nào unlock |
| `unlocked_by` | `Optional[str]` | `None` | auto_regime_change\|manual_user\|timer_expired |

**Serialization (cho API response):**
```json
{
  "is_locked": true,
  "trigger_type": "CONSECUTIVE_LOSSES",
  "trigger_detail": "3 losses: -2.1%, -3.5%, -4.2% in 24h",
  "triggered_at": "2024-01-15T09:00:00Z",
  "unlock_at": "2024-01-15T21:00:00Z",
  "time_remaining_seconds": 43200,
  "requires_review": false,
  "regime_at_trigger": "TRENDING"
}
```

---

### SignalCard

**File:** `workspace/backend-workspace/alert/builder.py`
**Type:** `@dataclass` / dict
**Mục đích:** Payload được gửi đến React Dashboard qua WebSocket. Bao gồm tất cả thông tin cần hiển thị trên Signal Card UI.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `signal_id` | `str` | UUID |
| `asset` | `str` | Symbol |
| `timeframe` | `str` | Timeframe |
| `direction` | `str` | long\|short |
| `entry_price` | `float` | Giá entry |
| `stop_loss` | `float` | SL |
| `take_profit_1` | `float` | TP1 |
| `take_profit_2` | `float` | TP2 |
| `gross_rr` | `float` | R:R trước phí = `(tp1-entry)/(entry-sl)` |
| `net_rr` | `float` | R:R sau phí |
| `final_score` | `int` | Score [0–100] |
| `score_breakdown` | `dict` | 5 module scores |
| `regime` | `str` | Market regime |
| `regime_multiplier` | `float` | Score multiplier |
| `expires_at_candle` | `int` | Candle index hết hạn |
| `timestamp` | `str` | ISO datetime |
| `mtf_scenario` | `str` | A\|B |
| `mtf_warning` | `Optional[str]` | Warning nếu Scenario B |
| `bias_4h` | `str` | 4H bias |
| `daily_bias` | `str` | Daily bias |
| `size_multiplier` | `float` | Combined size multiplier |
| `data_quality` | `str` | full\|limited |
| `ob_warning` | `Optional[str]` | Warning nếu OB unavailable |

---

### RegimeState

**File:** `workspace/backend-workspace/engine/regime_detector.py`
**Type:** `@dataclass`

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `regime` | `str` | TRENDING\|RANGING\|PARABOLIC\|CHOPPY |
| `score_multiplier` | `float` | [0.6, 1.0] |
| `suppress_short` | `bool` | True chỉ khi PARABOLIC |
| `adx` | `float` | ADX_14 giá trị hiện tại |
| `atr` | `float` | ATR_14 giá trị hiện tại |
| `rolling_avg_atr` | `float` | 20-period rolling avg ATR |

---

### MTFAlignment

**File:** `workspace/backend-workspace/engine/mtf_bias.py`
**Type:** `@dataclass`

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `scenario` | `str` | A\|B\|C |
| `size_multiplier` | `float` | 1.0 (A), 0.5 (B), 0.0 (C) |
| `score_adjustment` | `int` | +10 (A), -10 (B), BLOCK (C) |
| `bias_4h` | `str` | BULLISH\|BEARISH\|RANGING |
| `bias_1h` | `str` | BULLISH\|BEARISH\|NEUTRAL |
| `warning_message` | `Optional[str]` | None hoặc mô tả lý do Scenario B |
| `daily_size_multiplier` | `float` | 0.75 hoặc 1.0 |

---

### BTCSpikeState

**File:** `workspace/backend-workspace/engine/btc_guard.py`
**Type:** `@dataclass`

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `spike_detected` | `bool` | True nếu spike > 2% |
| `direction` | `Optional[str]` | dump\|pump\|None |
| `magnitude` | `float` | Spike % (e.g., 0.025 = 2.5%) |
| `cooldown_until` | `Optional[int]` | Unix timestamp hết cooldown |
| `in_cooldown` | `bool` | Hiện tại đang trong cooldown? |
| `size_multiplier` | `float` | 0.0 (dump), 0.5 (pump/cooldown), 1.0 (normal) |

---

### ScoreBreakdown

> **GAP đã sửa:** ScoreBreakdown là dataclass riêng trong `strategies/signal.py`, không phải dict.

**File:** `workspace/backend-workspace/strategies/signal.py`
**Type:** `@dataclass`
**Mục đích:** Per-module score breakdown, component của Signal object.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `order_flow` | `float` | `0.0` | OrderFlow module score (0–35) |
| `smc` | `float` | `0.0` | SMC module score (0–30) |
| `vsa` | `float` | `0.0` | VSA module score (0–30) |
| `context` | `float` | `0.0` | Context filter score (0–15) |
| `bonus` | `float` | `0.0` | Confluence bonus (0–15) |

**Methods:** `to_dict() → dict`

---

### ScoreInput

> **GAP đã sửa:** Đây là dataclass thực tế được truyền vào `SignalScorer.score()`.

**File:** `workspace/backend-workspace/engine/scorer.py`
**Type:** `@dataclass`
**Mục đích:** Input container cho SignalScorer — gom tất cả module scores và metadata.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `order_flow` | `float` | `0.0` | OrderFlow score (0–35) |
| `smc` | `float` | `0.0` | SMC score (0–30) |
| `vsa` | `float` | `0.0` | VSA score (0–30) |
| `context` | `float` | `0.0` | Context score (0–15) |
| `bonus` | `float` | `0.0` | Confluence bonus (0–15) |
| `regime_multiplier` | `float` | `1.0` | Regime score multiplier |
| `direction` | `str` | `"long"` | Signal direction |
| `regime` | `str` | `"RANGING"` | For PARABOLIC short suppression check |
| `order_book_available` | `bool` | `True` | False → score capped tại 60 inside scorer |

---

### ScoreOutput

> **GAP đã sửa:** Output của `SignalScorer.score()`.

**File:** `workspace/backend-workspace/engine/scorer.py`
**Type:** `@dataclass`
**Mục đích:** Kết quả đầy đủ của SignalScorer.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `raw_score` | `float` | required | Raw score trước normalization (0–125) |
| `final_score` | `int` | required | Normalized score [0–100] sau regime mult + cap |
| `classification` | `str` | required | ALERT \| WATCH \| IGNORE |
| `suppressed` | `bool` | `False` | True nếu PARABOLIC short suppression |
| `data_quality` | `dict` | `{"order_flow_available": bool, "order_book_available": bool}` | Data quality metadata |

**Lưu ý:** `final_score` là score TRƯỚC khi áp filter score adjustments. ScoringService áp adjustment sau khi nhận ScoreOutput:
```python
adjusted = max(0, min(100, score.final_score + int(total_score_adj)))
```

---

### FilterResult

> **GAP đã sửa:** Output của mỗi `BaseSignalFilter.apply()`.

**File:** `workspace/backend-workspace/engine/filters/base.py`
**Type:** `@dataclass`
**Mục đích:** Kết quả của một filter — quyết định signal có tiếp tục hay bị block.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `passed` | `bool` | `True` | False → signal bị block ngay lập tức |
| `block_reason` | `Optional[str]` | `None` | Lý do block (logged + stored in audit) |
| `score_adjustment` | `float` | `0.0` | +10 (Scenario A) / -10 (Scenario B) / -999 (block) |
| `size_multiplier` | `float` | `1.0` | 1.0 / 0.5 / 0.0 — multiplied với combined_size_mult |
| `warning` | `Optional[str]` | `None` | Warning message hiển thị trên Signal Card |
| `filter_name` | `str` | `""` | Tên filter tạo result này |
| `metadata` | `dict` | `{}` | Extra data từ filter |

**Factory methods:**
- `FilterResult.block(reason, filter_name)` → passed=False, size=0.0
- `FilterResult.pass_with_warning(score_adj, size_mult, warning, ...)` → Scenario B
- `FilterResult.pass_clean(score_adjustment=0.0, ...)` → Scenario A

---

## 6.2 Abstract Interfaces

### BaseIndicator

**File:** `workspace/backend-workspace/indicators/base.py`

```python
from abc import ABC, abstractmethod
from typing import Union
import numpy as np
import pandas as pd

class BaseIndicator(ABC):
    @abstractmethod
    def compute(self, ohlcv: pd.DataFrame, period: int) -> Union[np.ndarray, pd.Series]:
        """
        Compute indicator values from OHLCV data.

        Args:
            ohlcv: DataFrame columns=[open, high, low, close, volume], ascending timestamp.
            period: Lookback period N.

        Returns:
            Array same length as ohlcv.
            Positions at index < N-1 MUST return NaN (insufficient data).

        Invariant:
            compute(ohlcv[:T+1], period)[T] == compute(ohlcv[:N], period)[T]
            for any T and any N >= T+1 (no look-ahead bias)
        """
        ...
```

**Contract:**
- **No look-ahead:** Giá trị tại index T không được thay đổi khi thêm future data
- **NaN for insufficient data:** index 0 đến N-2 phải trả về NaN
- **Deterministic:** Cùng input luôn cho cùng output

**Implementations:**
- `indicators/atr.py` — ATR(14)
- `indicators/adx.py` — ADX(14)
- `indicators/rsi.py` — RSI(14)
- `indicators/ema.py` — EMA(N)
- `indicators/bollinger.py` — Bollinger Bands(20, 2)

---

### BaseStrategy

**File:** `workspace/backend-workspace/strategies/base.py`

```python
from abc import ABC, abstractmethod
from typing import List
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame, context: dict) -> List[Signal]:
        """
        Generate signals from closed candle data.

        Args:
            ohlcv: DataFrame of CLOSED candles only (index 0..T).
                   MUST NOT contain any unclosed candle.
            context: Dict with keys:
                     - regime_state: RegimeState
                     - funding_rate: float
                     - correlation_matrix: pd.DataFrame
                     - ohlcv_1h: pd.DataFrame (higher timeframe)
                     - portfolio_heat: float
                     - open_positions: dict

        Returns:
            List[Signal] — empty list if no signal detected.

        Constraint:
            SHALL only access ohlcv.iloc[:T+1] — no future data.
            LookAheadBiasError raised at runtime if violated.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier for Strategy Registry."""
        ...
```

**Invariants:**
- Pre-condition: `ohlcv` chỉ chứa closed candles
- Post-condition: Mỗi Signal trong list phải có `candle_index == len(ohlcv) - 1`
- Constraint: Không được access `ohlcv.iloc[T+1:]` — runtime check bằng `LookAheadBiasError`

---

## 6.3 Configuration Object Model

Config được load từ `config.yaml` và validated bởi `ConfigSystem`. Tất cả modules đọc config qua `self.config` dict (không đọc file trực tiếp).

### Namespace: account

| Field | Type | Default | Valid Range | Description | Affects |
|-------|------|---------|-------------|-------------|---------|
| `account.balance` | float | `10000.0` | > 0 | Account balance (USD) | RiskManager (position sizing) |
| `account.currency` | str | `"USDT"` | — | Base currency | Display only |

### Namespace: position

| Field | Type | Default | Valid Range | Description | Affects |
|-------|------|---------|-------------|-------------|---------|
| `position.mode` | str | `"risk_pct"` | fixed_usd\|risk_pct\|kelly | Position sizing mode | RiskManager |
| `position.fixed_usd` | float | `100.0` | > 0 | Fixed USD per trade | RiskManager (mode=fixed_usd) |
| `position.risk_pct` | float | `0.02` | [0.001, 0.1] | Risk % per trade | RiskManager (mode=risk_pct) |
| `position.max_concurrent` | int | `3` | [1, 10] | Max open positions | RiskManager |
| `position.leverage` | int | `5` | [1, 125] | Default leverage | TradeExecutor |

### Namespace: regime

| Field | Type | Default | Valid Range | Description | Affects |
|-------|------|---------|-------------|-------------|---------|
| `regime.enabled` | bool | `true` | — | Enable regime filter | ScoringService |
| `regime.adx_trending_threshold` | int | `25` | [15, 40] | ADX > này = TRENDING | RegimeDetector |
| `regime.adx_choppy_threshold` | int | `20` | [10, 30] | ADX < này = CHOPPY | RegimeDetector |
| `regime.atr_parabolic_multiplier` | float | `3.0` | [2.0, 5.0] | ATR > N× avg = PARABOLIC | RegimeDetector |
| `regime.parabolic_score_multiplier` | float | `0.6` | [0.3, 0.8] | Score mult cho PARABOLIC | SignalScorer |
| `regime.ranging_score_multiplier` | float | `0.85` | [0.5, 1.0] | Score mult cho RANGING/CHOPPY | SignalScorer |
| `regime.trending_score_multiplier` | float | `1.0` | [0.8, 1.2] | Score mult cho TRENDING | SignalScorer |

### Namespace: risk

| Field | Type | Default | Valid Range | Description | Affects |
|-------|------|---------|-------------|-------------|---------|
| `risk.max_daily_loss_pct` | float | `0.05` | [0.01, 0.20] | CB Trigger 3 threshold | CircuitBreaker |
| `risk.max_drawdown_pct` | float | `0.15` | [0.05, 0.30] | Tham khảo (không dùng cho CB trigger) | RiskManager |
| `risk.correlation_threshold` | float | `0.8` | [0.5, 0.99] | Pearson threshold | CorrelationManager |
| `risk.max_correlated_risk_pct` | float | `0.03` | [0.01, 0.10] | Max group risk | CorrelationManager |
| `risk.portfolio_heat_limit_pct` | float | `0.06` | [0.02, 0.20] | Max total risk | RiskManager |
| `risk.atr_sl_multiplier` | float | `1.5` | [1.0, 3.0] | SL = entry ± ATR × này | Strategy (SL calculation) |

### Namespace: strategy

| Field | Type | Default | Valid Range | Description | Affects |
|-------|------|---------|-------------|-------------|---------|
| `strategy.active` | list[str] | `["smc_ob_fvg"]` | registered names | Active strategies | StrategyRegistry |
| `strategy.score_threshold.alert` | int | `75` | [60, 95] | Min score cho ALERT | SignalScorer |
| `strategy.score_threshold.watch` | int | `55` | [40, 74] | Min score cho WATCH | SignalScorer |
| `strategy.timeframes.trigger` | str | `"15m"` | 15m\|30m\|1h | Timeframe trigger scoring | OHLCVService |
| `strategy.timeframes.context` | str | `"1h"` | 1h\|4h | Higher-timeframe context | ContextFilter |
| `strategy.time_invalidation_candles` | int | `15` | [5, 50] | Candles trước khi signal expire | AlertBuilder |

### Namespace: exchange

| Field | Type | Default | Valid Range | Description | Affects |
|-------|------|---------|-------------|-------------|---------|
| `exchange.name` | str | `"binance"` | ccxt exchange IDs | Exchange identifier | ccxt init |
| `exchange.market_type` | str | `"futures"` | futures\|spot | Market type | TradeExecutor |
| `exchange.fee_rate` | float | `0.001` | [0.0001, 0.01] | Taker fee rate (0.1%) | Backtest, net R:R |
| `exchange.slippage_pct` | float | `0.0002` | [0.0001, 0.005] | Estimated slippage | Backtest |
| `exchange.testnet` | bool | `true` | — | **MUST be `false` cho live trading** | TradeExecutor |

### Namespace: assets

List of asset configs:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `assets[].symbol` | str | required | e.g. "BTC/USDT" |
| `assets[].enabled` | bool | `true` | Enable/disable symbol |
| `assets[].leverage` | int | config.position.leverage | Per-symbol leverage override |

### Namespace: backtest

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backtest.start_date` | str | `"2024-01-01"` | ISO date |
| `backtest.end_date` | str | `"2024-12-31"` | ISO date |
| `backtest.walk_forward.enabled` | bool | `true` | Walk-forward on/off |
| `backtest.walk_forward.in_sample_days` | int | `90` | In-sample window size |
| `backtest.walk_forward.out_sample_days` | int | `30` | Out-of-sample window |
| `backtest.walk_forward.step_days` | int | `30` | Step between windows |
| `backtest.min_trades_threshold` | int | `30` | Min trades — dưới ngưỡng = statistically insufficient |
| `backtest.overfit_degradation_threshold` | float | `0.20` | Max in/out degradation trước khi cảnh báo overfit |

### Namespace: logging

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `logging.level` | str | `"INFO"` | DEBUG\|INFO\|WARNING\|ERROR |
| `logging.save_all_signals` | bool | `true` | Ghi tất cả signals vào SQL |
| `logging.log_dir` | str | `"logs/"` | Base log directory |
