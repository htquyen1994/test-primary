# Implementation Plan: Crypto Trading System

## Overview

Bottom-up implementation of a semi-automatic crypto trading platform. The build order follows infrastructure dependencies: foundation layers (config, indicators, data) are built first, then the AI engine, signal pipeline, strategy implementations, backtesting, dashboard, and trade execution. Property-based tests using `hypothesis` are integrated throughout, with Task 29 serving as a final verification sweep of all 20 correctness properties.

## Workspace Paths

| Component | Path |
|-----------|------|
| **Backend** | `D:\workspace\trade-workspace\workspace\backend-workspace\` |
| **Frontend** | `D:\workspace\trade-workspace\workspace\frontend-workspace\` |
| **Database** | SQL via SQLAlchemy — SQLite (local dev), PostgreSQL (production) |

All backend tasks are executed inside `backend-workspace\`. All frontend tasks are executed inside `frontend-workspace\`. The `DATABASE_URL` environment variable controls the SQL engine — defaults to `sqlite:///./trading.db` if not set.

## Tasks

---

## Phase 1 — Foundation

- [x] 1. Project scaffolding, Config System, and infrastructure setup
  - [x] 1.1 Create backend workspace directory structure
    - Working directory: `D:\workspace\trade-workspace\workspace\backend-workspace\`
    - Create directories: `config/`, `data/`, `indicators/`, `strategies/`, `engine/`, `risk/`, `alert/`, `trade/`, `backtest/`, `api/`, `db/migrations/`, `docs/`, `logs/signals/`, `logs/backtest/`, `logs/optimization/`, `tests/unit/`, `tests/integration/`, `tests/properties/`
    - Create `main.py` entry point with placeholder startup sequence
    - Create `requirements.txt` with pinned versions: `ccxt==4.3.x`, `redis==5.0.x`, `celery==5.3.x`, `fastapi==0.111.x`, `sqlalchemy==2.0.x`, `pydantic==2.7.x`, `pyyaml==6.0.x`, `pandas==2.2.x`, `numpy==1.26.x`, `hypothesis==6.100.x`, `pytest==8.2.x`, `pytest-asyncio==0.23.x`, `aioredis==2.0.x`, `watchdog==4.0.x`
    - Note: `psycopg2-binary` only needed for PostgreSQL production; SQLite works out of the box with SQLAlchemy
    - _Requirements: 12.1_

  - [x] 1.2 Create Docker Compose for infrastructure services
    - Working directory: `D:\workspace\trade-workspace\workspace\backend-workspace\`
    - Write `docker-compose.yml` with services: `redis` (redis:7-alpine, port 6379), `celery_worker` (build from backend-workspace, command `celery -A celery_app worker`), `celery_beat` (command `celery -A celery_app beat`)
    - Note: Database is SQL (SQLite for local dev, no Docker container needed); only add a `postgres` service if deploying to production
    - Write `docker-compose.override.yml` for local dev with volume mounts
    - Create `celery_app.py` at backend-workspace root with Celery app instance pointing to Redis broker
    - _Requirements: 12.4_

  - [x] 1.3 Implement Config System (`config/config_system.py`)
    - Define `ConfigSystem` class that loads `config.yaml` using PyYAML and validates with Pydantic models
    - Define Pydantic models for each namespace: `AccountConfig`, `PositionConfig` (mode: `fixed_usd|risk_pct|kelly`), `RegimeConfig`, `RiskConfig`, `StrategyConfig`, `ExchangeConfig`, `AssetConfig`, `BacktestConfig`, `LoggingConfig`
    - Raise `ConfigValidationError` with parameter name, expected type/range, and received value for any missing or invalid field before any module initializes
    - Expose a `get()` method returning the validated config object
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8, 15.9, 15.10, 12.5, 12.6_

  - [x] 1.4 Implement config hot-reload
    - Add `reload()` method to `ConfigSystem` that re-reads and re-validates `config.yaml` without restarting the process
    - Use a file-watcher (watchdog) or a Celery periodic task to trigger reload on file change
    - Emit a `config_reloaded` event that all modules can subscribe to
    - _Requirements: 15.11_

  - [x]* 1.5 Write property test for Config Validation Completeness
    - **Property 20: Config Validation Completeness**
    - Use `hypothesis` to generate `config.yaml` dicts with randomly removed or type-corrupted required fields
    - Assert that `ConfigSystem` raises a descriptive error naming the parameter, expected type/range, and received value for every invalid input
    - Assert that no module initialization occurs before the error is raised
    - **Validates: Requirements 15.10, 12.6**

  - [x] 1.6 Create SQL schema and database layer
    - Working directory: `D:\workspace\trade-workspace\workspace\backend-workspace\`
    - Write `db/migrations/001_initial_schema.sql` with `CREATE TABLE IF NOT EXISTS` statements for `signal_log`, `trade_journal`, and `backtest_results` exactly as defined in the design document (compatible with both SQLite and PostgreSQL)
    - Write `db/connection.py` with SQLAlchemy engine factory: reads `DATABASE_URL` from environment variable; defaults to `sqlite:///./trading.db` if not set
    - Write `db/models.py` with SQLAlchemy ORM models matching the schema
    - Write a `db/init_db.py` script that applies `001_initial_schema.sql` to the configured database on first run
    - _Requirements: 17.7, 19.5_

  - [x] 1.7 Checkpoint — Verify infrastructure
    - Ensure `docker-compose up` starts Redis and Celery without errors
    - Ensure `python db/init_db.py` creates the SQLite database and all tables cleanly
    - Ensure `ConfigSystem` loads the example `config.yaml` without errors
    - Ensure all tests pass, ask the user if questions arise.

- [x] 2. Indicator Library
  - [x] 2.1 Implement `indicators/base.py` — `BaseIndicator` abstract class
    - Define `BaseIndicator` ABC with abstract method `compute(ohlcv: pd.DataFrame, period: int) -> Union[np.ndarray, pd.Series]`
    - Enforce the no-look-ahead constraint: add a `_assert_no_lookahead(ohlcv, T)` guard that raises `LookAheadError` if any index > T is accessed
    - _Requirements: 4.1, 4.3, 4.4, 5.1_

  - [x] 2.2 Implement ATR, RSI, EMA indicators (`indicators/atr.py`, `indicators/rsi.py`, `indicators/ema.py`)
    - `ATR`: N-period Average True Range using Wilder smoothing; return NaN for indices 0..N-2
    - `RSI`: N-period Relative Strength Index; return NaN for indices 0..N-2
    - `EMA`: N-period Exponential Moving Average; return NaN for indices 0..N-2
    - Each class implements `BaseIndicator.compute()`; accepts configurable period N
    - _Requirements: 4.2, 4.4, 4.5_

  - [x] 2.3 Implement ADX and Bollinger Bands indicators (`indicators/adx.py`, `indicators/bb.py`)
    - `ADX`: N-period Average Directional Index (DI+, DI-, ADX); return NaN for indices 0..N-2
    - `BollingerBands`: N-period, K standard deviations; return `(upper, middle, lower)` arrays; return NaN for indices 0..N-2
    - _Requirements: 4.2, 4.4, 4.5_

  - [x] 2.4 Implement candle measurement utilities (`indicators/candle.py`)
    - `body_length(candle)`: `abs(close - open)`
    - `upper_wick(candle)`: `high - max(open, close)`
    - `lower_wick(candle)`: `min(open, close) - low`
    - `tail_length(candle, direction)`: lower wick for long setups, upper wick for short setups
    - `is_bullish(candle)`, `is_bearish(candle)` helpers
    - _Requirements: 4.2_

  - [x]* 2.5 Write property test for Indicator No-Look-Ahead Invariant
    - **Property 1: Indicator No-Look-Ahead Invariant**
    - Use `hypothesis` to generate random OHLCV DataFrames and random index T
    - For each indicator (ATR, RSI, EMA, ADX, BB), assert that `compute(ohlcv[:T+1])[T] == compute(ohlcv)[T]`
    - Assert that extending the array with future candles does not change the value at T
    - **Validates: Requirements 4.3, 5.1**

  - [x]* 2.6 Write property test for Indicator NaN for Insufficient Data
    - **Property 2: Indicator NaN for Insufficient Data**
    - Use `hypothesis` to generate OHLCV arrays of length L and period N where L < N
    - Assert that all output values at indices 0..N-2 are NaN for every indicator
    - **Validates: Requirements 4.5**

  - [x]* 2.7 Write unit tests for all indicators
    - Test ATR against known hand-calculated values for a 5-candle series
    - Test RSI against known values (e.g., RSI=100 when all closes are rising)
    - Test EMA against known values
    - Test ADX against known values
    - Test BB upper/lower band symmetry around middle band
    - Test candle measurement functions with edge cases (doji, marubozu)
    - _Requirements: 4.1, 4.2_

- [x] 3. Data Pipeline
  - [ ] 3.1 Implement OHLCV WebSocket ingestion (`data/ws_ohlcv.py`)
    - Use `ccxt.pro` async WebSocket to subscribe to OHLCV streams for each configured asset and timeframe (15m, 30m, 1h)
    - Write each closed candle to Redis key `ohlcv:{symbol}:{timeframe}` as a JSON list (ring buffer of last 500 candles)
    - Ensure writes are atomic (Redis `SET` with serialized JSON); latency target < 0.1ms per tick
    - Handle reconnection with exponential backoff on disconnect
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.2 Implement gap detection and linear interpolation (`data/gap_filler.py`)
    - `detect_gaps(expected_timestamps, received_timestamps) -> List[Tuple[datetime, datetime]]`: compare expected vs received timestamp sequences and return all missing ranges
    - `fill_gaps(ohlcv_df: pd.DataFrame, timeframe: str) -> pd.DataFrame`: for each gap, generate interpolated candles with OHLCV fields linearly interpolated between the surrounding candles
    - Log each filled gap with asset, timeframe, and timestamp range
    - _Requirements: 2.4, 2.5_

  - [ ]* 3.3 Write property test for Gap Detection Completeness
    - **Property 3: Gap Detection Completeness**
    - Use `hypothesis` to generate expected timestamp sequences and received sequences with randomly removed timestamps
    - Assert that `detect_gaps()` identifies every missing timestamp — no gap may be silently skipped
    - **Validates: Requirements 2.4**

  - [ ]* 3.4 Write property test for Linear Interpolation Correctness
    - **Property 4: Linear Interpolation Correctness**
    - Use `hypothesis` to generate pairs of OHLCV candles A and B and a random number of interpolated candles between them
    - Assert that each interpolated OHLCV field value lies exactly on the linear path between A's value and B's value
    - **Validates: Requirements 2.5**

  - [ ] 3.5 Implement ccxt retry logic (`data/ccxt_client.py`)
    - Wrap ccxt REST calls with a `retry_with_backoff(fn, max_retries=3)` decorator that retries on API errors with exponential backoff (1s, 2s, 4s)
    - Raise a structured `DataFetchError` after all retries are exhausted
    - _Requirements: 2.6_

  - [ ] 3.6 Implement Order Book WebSocket ingestion (`data/ws_orderbook.py`)
    - Subscribe to order book WebSocket for each configured asset
    - Maintain a local order book snapshot; write to Redis key `ob:{symbol}:snap` on each update
    - Compute and store cumulative bid/ask stack sizes at configurable price levels
    - _Requirements: 6.2 (Order Flow component)_

  - [ ] 3.7 Implement trade tape / delta ingestion (`data/ws_trades.py`)
    - Subscribe to trade tape WebSocket for each configured asset
    - Accumulate `buy_volume - sell_volume` over rolling 5-candle window
    - Write delta to Redis key `delta:{symbol}:5m` on each candle close
    - _Requirements: 6.2 (Order Flow component)_

  - [ ] 3.8 Implement Funding Rate ingestion (`data/funding.py`)
    - Poll ccxt REST endpoint for funding rate at each funding interval (every 8h for most exchanges)
    - Store records in Redis key `funding:{symbol}` and persist to PostgreSQL `signal_log` funding_rate field
    - If funding rate unavailable, log a warning and use 0.0
    - _Requirements: 3.1, 3.2, 3.4_

  - [ ]* 3.9 Write unit tests for Data Pipeline
    - Test gap detection with a sequence missing 3 non-contiguous timestamps
    - Test linear interpolation produces values between endpoints for all OHLCV fields
    - Test retry logic: mock ccxt to fail twice then succeed; assert 3 total calls
    - Test funding rate fallback to 0.0 when API returns empty
    - _Requirements: 2.4, 2.5, 2.6, 3.4_

- [x] 4. Strategy Registry, BaseStrategy, and Signal dataclass
  - [ ] 4.1 Implement `Signal` dataclass (`strategies/signal.py`)
    - Define `Signal` dataclass exactly as specified in the design document with all fields: `strategy_name`, `asset`, `timeframe`, `direction`, `candle_index`, `candle_timestamp`, `entry_price`, `stop_loss`, `take_profit_1`, `take_profit_2`, `raw_score`, `final_score`, `score_breakdown`, `regime`, `regime_multiplier`, `funding_rate`, `portfolio_heat`, `correlated_group_risk`, `classification`, `expires_at_candle`, `created_at`, `user_action`, `skip_reason`
    - Add `__post_init__` validation: `direction` must be `"long"|"short"`, `final_score` must be in [0, 100], `classification` must be `"ALERT"|"WATCH"|"IGNORE"`
    - _Requirements: 5.4, 6.1, 17.2_

  - [ ] 4.2 Implement `BaseStrategy` abstract class (`strategies/base.py`)
    - Define `BaseStrategy` ABC with abstract methods `generate_signals(ohlcv: pd.DataFrame, context: dict) -> List[Signal]` and `name` property
    - Add a `_check_no_lookahead(ohlcv: pd.DataFrame, T: int)` guard method that raises `LookAheadError` if `ohlcv` contains candles beyond index T
    - Constructor accepts `config: dict`
    - _Requirements: 12.2, 16.1, 5.1, 5.3_

  - [ ] 4.3 Implement `StrategyRegistry` (`strategies/registry.py`)
    - Implement `@register(name: str)` class decorator that adds a `BaseStrategy` subclass to a module-level dict
    - Implement `StrategyRegistry` class with methods: `load_active(config)` (instantiates only strategies in `config.strategy.active`), `list_registered() -> List[str]`, `get(name: str) -> BaseStrategy`
    - Raise descriptive error if a name in `strategy.active` is not found in the registry
    - Pass the validated config object to each strategy constructor
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

  - [ ]* 4.4 Write unit tests for Strategy Registry
    - Test that `@register` adds a strategy to the registry
    - Test that `load_active` raises an error for an unknown strategy name
    - Test that `load_active` only instantiates strategies in the active list
    - Test that `list_registered` returns all registered names
    - _Requirements: 16.3, 16.4, 16.6_


---

## Phase 2 — AI Engine

- [-] 5. SMC Analysis module
  - [ ] 5.1 Implement Order Block detection (`engine/smc.py` — `find_order_block()`)
    - Implement `_find_order_block(ohlcv: pd.DataFrame, atr_multiplier: float = 1.5) -> dict | None`
    - Logic: scan backwards from the last candle; identify the last opposing candle before an impulse candle whose body >= `atr_multiplier * ATR(14)`; return OB dict with `type`, `high`, `low`, `mid`, `index`, `valid`
    - OB is invalidated when price closes beyond the OB zone
    - _Requirements: 1.2, 6.2 (SMC component)_

  - [ ] 5.2 Implement Fair Value Gap detection (`engine/smc.py` — `find_fvg()`)
    - Implement `_find_fvg(ohlcv: pd.DataFrame) -> dict | None`
    - Logic: three-candle imbalance — bullish FVG when `candle[i-2].high < candle[i].low`; bearish FVG when `candle[i-2].low > candle[i].high`
    - Return FVG dict with `type`, `top`, `bot`, `mid`, `filled`
    - Mark FVG as filled when price trades through the full gap
    - _Requirements: 1.2, 6.2 (SMC component)_

  - [ ] 5.3 Implement CHoCH detection and HTF bias (`engine/smc.py` — `detect_choch()`, `detect_htf_bias()`)
    - `detect_choch(ohlcv_15m)`: identify Change of Character — a break of the most recent swing low (bearish CHoCH) or swing high (bullish CHoCH)
    - `detect_htf_bias(ohlcv_1h)`: classify 1h trend as `"bullish"`, `"bearish"`, or `"neutral"` based on higher-high/higher-low structure
    - `_aligned_with_bias(choch_direction, htf_bias) -> bool`
    - _Requirements: 6.2 (SMC component)_

  - [ ] 5.4 Implement `compute_smc_score()` aggregator
    - Combine CHoCH (+10), OB retest (+10), FVG midpoint touch (+10) into a single score capped at 30
    - Expose `compute_smc_score(ohlcv_15m, ohlcv_1h) -> float`
    - _Requirements: 6.2_

  - [ ]* 5.5 Write unit tests for SMC Analysis
    - Test `find_order_block` with a synthetic OHLCV series containing a known OB
    - Test `find_fvg` with a synthetic three-candle imbalance (both bullish and bearish)
    - Test `detect_choch` with a series that has a clear swing break
    - Test `compute_smc_score` returns 0 when no patterns are present and 30 when all three are active
    - _Requirements: 1.2, 6.2_

- [x] 6. VSA and Volume Profile module
  - [ ] 6.1 Implement Volume Profile computation (`engine/volume_profile.py`)
    - `compute_volume_profile(ohlcv: pd.DataFrame, window: int = 100, bins: int = 50) -> dict`
    - Distribute volume across price bins; identify POC (bin with highest volume), VAH and VAL (boundaries of the 70% volume area)
    - Write POC to Redis key `poc:{symbol}` on each candle close
    - _Requirements: 6.2 (VSA+VolProfile component)_

  - [ ] 6.2 Implement VSA analysis (`engine/vsa.py`)
    - `detect_no_supply(ohlcv: pd.DataFrame) -> bool`: pullback volume < 40% of prior impulse volume
    - `detect_effort_vs_result(ohlcv: pd.DataFrame) -> bool`: low volume candle but price holds key level (range < 30% of ATR)
    - `detect_absorption(ohlcv: pd.DataFrame, delta: float) -> bool`: high volume but price did not move significantly (range < 20% of ATR)
    - _Requirements: 6.2 (VSA component)_

  - [ ] 6.3 Implement `compute_vsa_score()` aggregator
    - VSA: No Supply (+10), Effort vs Result (+10); Volume Profile: entry within 0.3% of POC (+10), entry at VAH/VAL (+6)
    - Cap at 30; expose `compute_vsa_score(ohlcv, poc, vah, val) -> float`
    - _Requirements: 6.2_

  - [ ]* 6.4 Write unit tests for VSA and Volume Profile
    - Test `compute_volume_profile` with a synthetic series; assert POC is the price level with highest volume
    - Test VAH and VAL contain exactly 70% of total volume
    - Test `detect_no_supply` returns True when pullback volume is 30% of impulse volume
    - Test `compute_vsa_score` returns 0 when no conditions are met and 30 when all are met
    - _Requirements: 6.2_

- [ ] 7. Order Flow Analysis module
  - [ ] 7.1 Implement `compute_order_flow_score()` (`engine/order_flow.py`)
    - `order_flow_score(delta, bid_stack, ask_stack, absorption, delta_threshold) -> float`
    - Delta > threshold: +15; bid_stack > ask_stack * 2: +10; absorption: +10; cap at 35
    - Read `delta:{symbol}:5m` and `ob:{symbol}:snap` from Redis
    - _Requirements: 6.2 (Order Flow component)_

  - [ ]* 7.2 Write unit tests for Order Flow Analysis
    - Test all three conditions independently and in combination
    - Test that score is capped at 35 even when all conditions are met with high values
    - _Requirements: 6.2_

- [-] 8. Regime Detector
  - [ ] 8.1 Implement `RegimeDetector` class (`engine/regime_detector.py`)
    - `classify(ohlcv_1h: pd.DataFrame, ohlcv_15m: pd.DataFrame) -> Tuple[str, float]`
    - TRENDING: ADX(14) on 1h > `adx_trending_threshold` (default 25) → multiplier 1.0
    - CHOPPY/RANGING: ADX(14) on 1h < `adx_choppy_threshold` (default 20) → multiplier 0.85
    - PARABOLIC: ATR(14) on 15m > `atr_parabolic_multiplier` × 20-period rolling mean ATR(14) on 15m → multiplier 0.6
    - PARABOLIC takes precedence over TRENDING/CHOPPY
    - Write regime state to Redis key `regime:{symbol}`
    - All thresholds sourced from `ConfigSystem`
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9_

  - [ ]* 8.2 Write property test for Regime Output Validity
    - **Property 12: Regime Output Validity**
    - Use `hypothesis` to generate valid OHLCV DataFrames (1h and 15m) with varying ADX and ATR values
    - Assert that `RegimeDetector.classify()` always returns exactly one of `{"TRENDING", "RANGING", "PARABOLIC", "CHOPPY"}` — never null, never an undefined state
    - **Validates: Requirements 13.1**

  - [ ]* 8.3 Write property test for PARABOLIC Short Suppression
    - **Property 13: PARABOLIC Short Suppression**
    - Use `hypothesis` to generate OHLCV data where ATR(14) on 15m exceeds 3× the 20-period rolling average ATR(14)
    - Assert that `SignalScorer` returns IGNORE for any short-direction signal in PARABOLIC regime
    - Assert that the regime multiplier equals 0.6
    - **Validates: Requirements 13.5**

  - [ ]* 8.4 Write unit tests for Regime Detector
    - Test TRENDING classification with ADX = 30
    - Test CHOPPY classification with ADX = 15
    - Test PARABOLIC classification with ATR spike > 3× rolling mean
    - Test that PARABOLIC takes precedence when both ADX > 25 and ATR spike are present
    - Test that all thresholds are read from config
    - _Requirements: 13.1–13.9_

- [x] 9. Correlation Manager and Portfolio Heat
  - [ ] 9.1 Implement `CorrelationManager` class (`engine/correlation_manager.py`)
    - `update(symbol: str, ohlcv_1h: pd.DataFrame)`: update rolling 24h Pearson correlation matrix for all asset pairs using 1h close prices; update at each 1h candle close
    - `get_correlated_group(symbol: str, threshold: float) -> List[str]`: return all assets whose correlation with `symbol` exceeds the threshold
    - `get_portfolio_heat(open_positions: List[dict]) -> float`: sum of all individual position risk percentages
    - Store correlation matrix in Redis key `correlation:matrix`
    - _Requirements: 14.1, 14.2, 14.3, 14.6_

  - [ ]* 9.2 Write property test for Pearson Correlation Bounds
    - **Property 14: Pearson Correlation Bounds**
    - Use `hypothesis` to generate pairs of price series of length >= 2
    - Assert that the Pearson correlation coefficient computed by `CorrelationManager` is always in [-1.0, 1.0]
    - **Validates: Requirements 14.1**

  - [ ]* 9.3 Write property test for Portfolio Heat Summation
    - **Property 15: Portfolio Heat Summation**
    - Use `hypothesis` to generate sets of open positions with associated risk percentages
    - Assert that `get_portfolio_heat()` equals exactly the sum of all individual position risk percentages
    - **Validates: Requirements 14.6**

  - [ ]* 9.4 Write property test for Portfolio Heat Enforcement
    - **Property 16: Portfolio Heat Enforcement**
    - Use `hypothesis` to generate portfolio states where Portfolio_Heat >= configured limit
    - Assert that `RiskManager` rejects every new signal regardless of score, asset, or direction
    - **Validates: Requirements 14.7**

  - [ ]* 9.5 Write unit tests for Correlation Manager
    - Test that two perfectly correlated series (identical) return correlation = 1.0
    - Test that two perfectly anti-correlated series return correlation = -1.0
    - Test `get_correlated_group` returns correct members above threshold
    - Test `get_portfolio_heat` with 3 positions of known risk percentages
    - _Requirements: 14.1, 14.2, 14.6_


---

## Phase 3 — Signal Pipeline

- [-] 10. Signal Scorer
  - [ ] 10.1 Implement `SignalScorer` class (`engine/signal_scorer.py`)
    - `score(order_flow: float, smc: float, vsa: float, context: float, bonus: float, regime_multiplier: float) -> int`
    - Formula: `raw = order_flow + smc + vsa + context + bonus`; `final = min(round(raw * regime_multiplier / 125 * 100), 100)`
    - `classify(final_score: int) -> str`: ALERT (≥ 75), WATCH (55–74), IGNORE (< 55)
    - All thresholds (ALERT, WATCH, module max points) configurable via `ConfigSystem`
    - In PARABOLIC regime: suppress all short signals (return IGNORE regardless of score)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 13.5_

  - [ ]* 10.2 Write property test for Score Normalization Invariant
    - **Property 5: Score Normalization Invariant**
    - Use `hypothesis` to generate module scores (OrderFlow ∈ [0,35], SMC ∈ [0,30], VSA ∈ [0,30], Context ∈ [0,15], Bonus ∈ [0,15]) and regime multiplier ∈ [0.6, 1.0]
    - Assert that `SignalScorer.score()` always returns an integer in [0, 100]
    - **Validates: Requirements 6.1, 6.3**

  - [ ]* 10.3 Write property test for Confluence Monotonicity
    - **Property 6: Confluence Monotonicity**
    - Use `hypothesis` to generate two positive module scores s1 and s2
    - Assert that the combined score when both factors are active is strictly greater than the score produced by either factor alone
    - **Validates: Requirements 6.4**

  - [ ]* 10.4 Write unit tests for Signal Scorer
    - Test ALERT classification at score = 75 and 100
    - Test WATCH classification at score = 55 and 74
    - Test IGNORE classification at score = 0 and 54
    - Test that short signals are suppressed in PARABOLIC regime
    - Test that ALERT/WATCH thresholds are read from config
    - _Requirements: 6.1, 6.5, 6.6_

- [-] 11. Risk Manager
  - [ ] 11.1 Implement `RiskManager` class (`risk/risk_manager.py`)
    - `compute_position_size(mode: str, equity: float, risk_pct: float, sl_distance: float, contract_value: float, leverage: int) -> float`
    - `fixed_usd` mode: return `config.position.fixed_usd`
    - `risk_pct` mode: `(equity * risk_pct) / (sl_distance * contract_value)`
    - `kelly` mode: Kelly fraction based on historical win rate and avg win/loss ratio from backtest results
    - Cap position size so max loss ≤ `equity * max_risk_pct`
    - Reject signal (return None + log) if ATR = 0 or computed size ≤ 0
    - Apply leverage only for Futures market type
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 11.2 Implement correlated risk enforcement in `RiskManager`
    - `check_correlated_risk(symbol, open_positions, correlation_manager) -> bool`
    - Reject signal if adding this position would cause correlated group risk > `max_correlated_risk_pct`
    - Reject signal if `portfolio_heat >= portfolio_heat_limit_pct`
    - Log rejection with asset, correlated group members, and current combined risk percentage
    - _Requirements: 14.3, 14.4, 14.5, 14.7_

  - [ ]* 11.3 Write property test for Risk Cap Invariant
    - **Property 7: Risk Cap Invariant**
    - Use `hypothesis` to generate account equity, risk percentage, entry price, and stop-loss distance
    - Assert that the maximum possible loss from the position size returned by `RiskManager` never exceeds `equity * max_risk_pct`
    - Test all three position sizing modes: `fixed_usd`, `risk_pct`, `kelly`
    - **Validates: Requirements 7.3**

  - [ ]* 11.4 Write unit tests for Risk Manager
    - Test `risk_pct` mode with known inputs produces expected position size
    - Test `fixed_usd` mode returns the configured USD amount
    - Test that ATR = 0 causes signal rejection with a log entry
    - Test correlated risk rejection when group risk would exceed limit
    - Test portfolio heat rejection when heat >= limit
    - _Requirements: 7.1–7.5, 14.4, 14.5, 14.7_

- [ ] 12. Alert Builder, Time Invalidation, and Redis pub/sub sender
  - [ ] 12.1 Implement `AlertBuilder` (`alert/alert_builder.py`)
    - `build_signal_card(signal: Signal, config: dict) -> dict`: construct the full Signal Card payload with all required fields: `asset`, `direction`, `final_score`, `entry_price`, `stop_loss`, `take_profit_1`, `take_profit_2`, `gross_rr`, `net_rr` (after fees and slippage), `score_breakdown` (all five sub-scores), `regime`, `expires_at_candle`
    - Compute `gross_rr = (take_profit_1 - entry_price) / (entry_price - stop_loss)` for longs
    - Compute `net_rr` by deducting `fee_rate * 2 + slippage_pct * 2` from gross R:R
    - _Requirements: 18.1, 17.2_

  - [ ] 12.2 Implement Time Invalidation (`alert/time_invalidation.py`)
    - `compute_expiry(candle_index: int, invalidation_candles: int) -> int`: `expires_at_candle = candle_index + invalidation_candles`
    - `is_expired(signal: Signal, current_candle_index: int) -> bool`
    - `record_expiry(signal: Signal, current_price: float)`: update signal with expiry reason and final price; write to Signal_Log
    - _Requirements: 18.5, 17.4_

  - [ ] 12.3 Implement Redis pub/sub sender (`alert/redis_sender.py`)
    - `publish_alert(signal_card: dict)`: serialize to JSON and publish to Redis channel `alerts:channel`
    - Only publish signals with `classification == "ALERT"` and `final_score >= 75`
    - _Requirements: 6.5, 18.10_

  - [ ]* 12.4 Write property test for Signal Card Required Fields
    - **Property 18: Signal Card Required Fields**
    - Use `hypothesis` to generate Signal objects with classification ALERT
    - Assert that `AlertBuilder.build_signal_card()` always produces a dict containing all required fields: `asset`, `direction`, `final_score`, `entry_price`, `stop_loss`, `take_profit_1`, `take_profit_2`, `gross_rr`, `net_rr`, `score_breakdown` (with all five sub-scores), `regime`, `expires_at_candle`
    - **Validates: Requirements 18.1**

  - [ ]* 12.5 Write unit tests for Alert Builder and Time Invalidation
    - Test `build_signal_card` produces correct `net_rr` given known fee and slippage rates
    - Test `compute_expiry` with `invalidation_candles = 15`
    - Test `is_expired` returns True when current candle index > `expires_at_candle`
    - Test that only ALERT-class signals are published to Redis
    - _Requirements: 18.1, 18.5, 17.4_

- [x] 13. Checkpoint — Signal pipeline integration
  - Wire together: `RegimeDetector` → `CorrelationManager` → `SignalScorer` → `RiskManager` → `AlertBuilder` → `redis_sender`
  - Write a `run_signal_scoring(symbol, timeframe)` Celery task in `engine/tasks.py` that executes the full pipeline for one symbol/timeframe
  - Ensure all tests pass, ask the user if questions arise.


---

## Phase 4 — Strategy Implementations

- [-] 14. Core strategies: SMC OB+FVG, Pinbar, Engulfing
  - [ ] 14.1 Implement `SMCOrderBlockFVGStrategy` (`strategies/smc_ob_fvg.py`)
    - Register with `@register("smc_ob_fvg")`
    - `generate_signals(ohlcv, context)`: detect CHoCH + OB retest + FVG confluence on 15m; require 1h HTF bias alignment
    - Entry: close of the candle that retests the OB/FVG zone; SL: below OB low (long) or above OB high (short); TP1: 1.5R, TP2: 2.5R
    - Enforce no-look-ahead: call `_check_no_lookahead(ohlcv, T)` before any pattern detection
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3_

  - [ ] 14.2 Implement `PinbarStrategy` (`strategies/pinbar.py`)
    - Register with `@register("pinbar")`
    - `generate_signals(ohlcv, context)`: detect candle where `tail_length >= 2 * body_length` at a key S/R level (OB zone or FVG midpoint)
    - Long pinbar: lower tail >= 2× body, close in upper 30% of range; Short pinbar: upper tail >= 2× body, close in lower 30% of range
    - Entry: close of pinbar candle; SL: beyond the tail tip; TP1: 1.5R, TP2: 2.5R
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 5.1, 5.2_

  - [ ] 14.3 Implement `EngulfingStrategy` (`strategies/engulfing.py`)
    - Register with `@register("engulfing")`
    - `generate_signals(ohlcv, context)`: detect two-candle pattern where `candle[T].body_length > candle[T-1].body_length` and candle[T] body fully contains candle[T-1] body
    - Bullish engulfing: candle[T] is bullish, candle[T-1] is bearish; bearish engulfing: vice versa
    - Entry: close of engulfing candle; SL: below/above the engulfed candle's wick; TP1: 1.5R, TP2: 2.5R
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 5.1, 5.2_

  - [ ]* 14.4 Write unit tests for core strategies
    - Test `SMCOrderBlockFVGStrategy` generates a long signal on a synthetic series with known OB + FVG + CHoCH
    - Test `PinbarStrategy` generates a signal when `tail >= 2 * body` and returns empty list when condition is not met
    - Test `EngulfingStrategy` generates a signal for a known two-candle engulfing pattern
    - Test that all strategies raise `LookAheadError` when given a DataFrame with future candles
    - _Requirements: 1.2, 1.3, 5.1, 5.3_

- [ ] 15. Additional strategies: Inside Bar, Quasimodo, Flag, RSI Momentum, EMA Cross
  - [ ] 15.1 Implement `InsideBarStrategy` (`strategies/inside_bar.py`)
    - Register with `@register("inside_bar")`
    - Detect: `candle[T].high < candle[T-1].high AND candle[T].low > candle[T-1].low`
    - Entry on breakout of the mother bar high (long) or low (short) on the next candle close
    - _Requirements: 1.2, 1.3, 5.1_

  - [ ] 15.2 Implement `QuasimodoStrategy` (`strategies/quasimodo.py`)
    - Register with `@register("quasimodo")`
    - Detect QM pattern: higher-high → lower-high → lower-low → return to prior S/R zone
    - Entry at the return to the prior support/resistance zone; SL beyond the lower-low (long QM)
    - _Requirements: 1.2, 1.3, 5.1_

  - [ ] 15.3 Implement `FlagStrategy` (`strategies/flag.py`)
    - Register with `@register("flag")`
    - Detect: strong impulse move (body >= 1.5 × ATR) followed by 3–7 candles of consolidation with declining volume
    - Entry on breakout of the flag channel in the direction of the impulse
    - _Requirements: 1.2, 1.3, 5.1_

  - [ ] 15.4 Implement `RSIMomentumStrategy` (`strategies/rsi_momentum.py`)
    - Register with `@register("rsi_momentum")`
    - Long: RSI(14) crosses above 50 from below while price is above EMA(50); Short: RSI crosses below 50 from above while price is below EMA(50)
    - Require 1h HTF bias alignment
    - _Requirements: 1.2, 1.3, 5.1_

  - [ ] 15.5 Implement `EMACrossStrategy` (`strategies/ema_cross.py`)
    - Register with `@register("ema_cross")`
    - Long: EMA(9) crosses above EMA(21) with ADX > 20; Short: EMA(9) crosses below EMA(21) with ADX > 20
    - _Requirements: 1.2, 1.3, 5.1_

  - [ ]* 15.6 Write unit tests for additional strategies
    - Test each strategy generates a signal on a synthetic series with the known pattern present
    - Test each strategy returns an empty list when the pattern is absent
    - _Requirements: 1.2, 5.1_

- [ ] 16. Strategy Spec documents
  - [ ] 16.1 Write Strategy_Spec Markdown files in `docs/`
    - Create one `.md` file per strategy: `pinbar.md`, `engulfing.md`, `inside_bar.md`, `order_block.md`, `breaker_block.md`, `fair_value_gap.md`, `quasimodo.md`, `double_top_bottom.md`, `flag.md`, `rsi_momentum.md`, `bollinger_band_squeeze.md`, `ema_cross.md`
    - Each file MUST include sections: Mathematical Logic (precise inequalities/formulas), Objective Entry/Exit (exact candle-close trigger, entry price, SL, TP for long and short), Context Filter (minimum 1h condition), Failure Scenario (price/structural condition that invalidates the pattern), and Glossary of terms used
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_


---

## Phase 5 — Backtesting

- [x] 17. Backtesting Engine — Trade Simulation
  - [ ] 17.1 Implement `TradeResult` dataclass (`backtest/models.py`)
    - Define `TradeResult` dataclass exactly as specified in the design document with all fields
    - Add `__post_init__` validation: `direction` must be `"long"|"short"`, `result` must be `"win"|"loss"|"be"`, `is_testnet` defaults to True
    - _Requirements: 8, 9, 19_

  - [ ] 17.2 Implement `BacktestingEngine` core simulation loop (`backtest/engine.py`)
    - `run(strategy: BaseStrategy, ohlcv: pd.DataFrame, funding_rates: pd.DataFrame, config: dict) -> List[TradeResult]`
    - Process candles in strictly ascending timestamp order; enforce no-look-ahead by passing `ohlcv[:T+1]` to `strategy.generate_signals()`
    - For each signal: compute position size via `RiskManager`, simulate fill at `entry_price * (1 + slippage_pct)` for longs
    - Check SL/TP intra-candle: if candle's low <= SL (long), fill at SL + slippage; if candle's high >= TP1, fill at TP1 - slippage
    - Apply funding rate payments at each 8h interval during the holding period
    - Deduct fees: 0.04% for Futures, 0.1% for Spot per fill
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 17.3 Write property test for Backtest Chronological Order
    - **Property 8: Backtest Chronological Order**
    - Use `hypothesis` to generate collections of OHLCV candles in random order
    - Assert that `BacktestingEngine` processes them in strictly ascending timestamp order
    - Assert that at simulation time T, no candle with timestamp > candles[T].timestamp is accessed
    - **Validates: Requirements 8.6, 5.1**

  - [ ]* 17.4 Write property test for Slippage Application Correctness
    - **Property 9: Slippage Application Correctness**
    - Use `hypothesis` to generate fill prices and slippage percentages in [0.0005, 0.001]
    - Assert that actual fill price = `fill_price * (1 + slippage_pct)` for long entries
    - Assert that actual fill price = `fill_price * (1 - slippage_pct)` for short entries
    - **Validates: Requirements 8.2**

  - [ ]* 17.5 Write unit tests for Backtesting Engine simulation
    - Test a single long trade: verify net_pnl = gross_pnl - fees - slippage - funding
    - Test intra-candle SL fill: candle low touches SL, verify fill at SL + slippage
    - Test intra-candle TP fill: candle high touches TP1, verify fill at TP1 - slippage
    - Test that candles are processed in ascending order even when input is shuffled
    - _Requirements: 8.1–8.6_

- [ ] 18. Performance Metrics and Walk-Forward Analysis
  - [ ] 18.1 Implement performance metrics computation (`backtest/metrics.py`)
    - `compute_metrics(trades: List[TradeResult]) -> dict`
    - Win rate: `count(result == "win") / len(trades)` → value in [0.0, 1.0]
    - Profit factor: `sum(net_pnl for wins) / abs(sum(net_pnl for losses))`
    - Max drawdown: maximum percentage decline from any equity peak to subsequent trough
    - Sharpe Ratio: `mean(daily_returns) / std(daily_returns) * sqrt(365)`
    - Recovery Factor: `net_profit / max_drawdown`
    - Write result record to `logs/backtest/` as JSON; flag as statistically insufficient if trade count < 30
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 11.1, 11.2_

  - [ ]* 18.2 Write property test for Win Rate Formula Invariant
    - **Property 10: Win Rate Formula Invariant**
    - Use `hypothesis` to generate lists of `TradeResult` objects with random result values
    - Assert that `compute_metrics()` win rate equals `count(result == "win") / len(results)` and is always in [0.0, 1.0]
    - **Validates: Requirements 9.2**

  - [ ]* 18.3 Write property test for Sharpe Ratio Formula Invariant
    - **Property 11: Sharpe Ratio Formula Invariant**
    - Use `hypothesis` to generate lists of daily returns with non-zero standard deviation
    - Assert that Sharpe Ratio equals `mean(returns) / std(returns) * sqrt(365)`
    - **Validates: Requirements 9.3**

  - [ ] 18.4 Implement Walk-Forward Analysis (`backtest/walk_forward.py`)
    - `run_walk_forward(strategy, ohlcv, config) -> List[dict]`
    - Partition dataset into sequential in-sample / out-of-sample windows using `in_sample_days`, `out_sample_days`, `step_days` from config
    - Optimize on in-sample window; evaluate on out-of-sample window; roll forward
    - Aggregate out-of-sample results into a combined performance report
    - Flag strategy as potentially overfit if out-of-sample performance degrades > `overfit_degradation_threshold` relative to in-sample
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 18.5 Write unit tests for Walk-Forward Analysis
    - Test that windows are non-overlapping and cover the full dataset
    - Test that optimization uses only in-sample data
    - Test that overfit flag is set when out-of-sample degrades > threshold
    - _Requirements: 10.1–10.5_

- [ ] 19. AI Feedback Loop and Benchmark Table
  - [ ] 19.1 Implement Underperformance Cluster detection (`backtest/ai_feedback.py`)
    - `find_underperformance_clusters(log_entries: List[dict]) -> List[dict]`
    - Identify contiguous date ranges where win rate < 45% or profit factor < 1.0
    - For each cluster: output structured suggestion record with cluster date range, affected strategy and asset, and at least one candidate logic filter
    - Exclude runs with < 30 trades from cluster analysis
    - Write suggestion records to `logs/` separately from raw backtest results
    - _Requirements: 11.3, 11.4, 11.5, 11.6_

  - [ ] 19.2 Implement Benchmark Table generator (`backtest/benchmark.py`)
    - `generate_benchmark_table(log_dir: str) -> pd.DataFrame`
    - Read all backtest result records from `logs/backtest/`
    - Produce a DataFrame with rows = strategy × timeframe and columns = win_rate, profit_factor, max_drawdown, sharpe_ratio, recovery_factor, trade_count
    - Mark rows with < 30 trades as statistically insufficient
    - _Requirements: 17.5, 17.6_

  - [ ]* 19.3 Write unit tests for AI Feedback Loop
    - Test cluster detection identifies a contiguous range with win_rate = 0.40 (below 45%)
    - Test that runs with < 30 trades are excluded from cluster analysis
    - Test benchmark table has correct shape and marks insufficient rows
    - _Requirements: 11.3, 11.4, 11.6, 17.5, 17.6_

- [ ] 20. Checkpoint — Backtesting pipeline
  - Ensure `BacktestingEngine.run()` produces correct metrics on a synthetic 100-trade dataset
  - Ensure walk-forward windows are correctly partitioned
  - Ensure all tests pass, ask the user if questions arise.


---

## Phase 6 — Dashboard

- [ ] 21. FastAPI backend
  - [ ] 21.1 Implement FastAPI app and REST endpoints (`api/main.py`, `api/routes/`)
    - Working directory: `D:\workspace\trade-workspace\workspace\backend-workspace\`
    - Create FastAPI app in `api/main.py` with CORS middleware configured for the React frontend at `http://localhost:5173`
    - `GET /api/signals`: return list of active ALERT-class signals from Redis
    - `GET /api/journal`: return paginated trade journal entries from PostgreSQL
    - `GET /api/analytics`: return aggregated performance metrics (win rate, profit factor, max drawdown, Sharpe, per-strategy breakdown) from `backtest_results` table
    - `GET /api/config`: return current non-sensitive config values
    - `POST /api/config/reload`: trigger `ConfigSystem.reload()`
    - _Requirements: 18.7, 18.8, 18.9_

  - [ ] 21.2 Implement WebSocket `/ws/alerts` endpoint
    - Subscribe to Redis `alerts:channel` pub/sub in a background task
    - Push new Signal Card JSON to all connected WebSocket clients on each Redis message
    - Handle client connect/disconnect gracefully
    - _Requirements: 18.10_

  - [ ] 21.3 Implement WebSocket `/ws/portfolio` endpoint
    - Push Portfolio_Heat and per-asset correlated group risk updates to all connected clients at each 1h candle close
    - Read data from Redis `correlation:matrix` and open positions
    - _Requirements: 14.8, 18.9, 18.10_

  - [ ] 21.4 Implement Signal Log writer (`dashboard/backend/signal_log_writer.py`)
    - `write_signal_log(signal: Signal)`: insert a row into the `signal_log` PostgreSQL table for every generated signal regardless of classification
    - `update_user_action(log_id: str, action: str, skip_reason: Optional[str])`: update the `user_action` and `skip_reason` fields when user confirms or skips
    - _Requirements: 17.1, 17.2, 17.3, 17.7_

  - [ ]* 21.5 Write property test for Signal Log Completeness
    - **Property 17: Signal Log Completeness**
    - Use `hypothesis` to generate batches of N signals with random classifications and user actions
    - Assert that after processing, exactly N `signal_log` rows exist in the database
    - **Validates: Requirements 17.1**

  - [ ]* 21.6 Write unit tests for FastAPI endpoints
    - Test `GET /api/signals` returns only ALERT-class signals
    - Test `GET /api/journal` returns paginated results
    - Test `POST /api/config/reload` triggers config reload
    - Test WebSocket `/ws/alerts` pushes a message when a signal is published to Redis
    - _Requirements: 18.1, 18.7, 18.10_

- [ ] 22. React frontend foundation
  - [ ] 22.1 Scaffold React + Vite + TypeScript project
    - Working directory: `D:\workspace\trade-workspace\workspace\frontend-workspace\`
    - The frontend-workspace directory is already the React project root — initialize directly: `npm create vite@latest . -- --template react-ts`
    - Install dependencies: `react-router-dom@6`, `@tanstack/react-query@5`, `recharts@2`, `lightweight-charts@4`, `tailwindcss@3`, `zustand@4`
    - Configure Tailwind CSS with dark mode support
    - Set up `vite.config.ts` with proxy: `'/api' → 'http://localhost:8000'` and `'/ws' → 'ws://localhost:8000'`
    - _Requirements: 18.1_

  - [ ] 22.2 Implement WebSocket providers and global state (`dashboard/frontend/src/providers/`)
    - `AlertsWebSocketProvider`: connect to `/ws/alerts`, parse incoming Signal Card JSON, store in Zustand `alertsStore`
    - `PortfolioWebSocketProvider`: connect to `/ws/portfolio`, store Portfolio_Heat and per-asset risk in Zustand `portfolioStore`
    - Implement reconnection logic with exponential backoff
    - _Requirements: 18.10, 14.8_

  - [ ] 22.3 Implement routing and layout (`dashboard/frontend/src/App.tsx`)
    - Set up React Router with routes: `/` (Signal Cards), `/journal` (Trade Journal), `/analytics` (Analytics), `/config` (Config UI)
    - Implement persistent header showing Portfolio_Heat and per-asset correlated group risk (read from `portfolioStore`)
    - _Requirements: 18.9_

- [ ] 23. Signal Card component and Confirm/Skip flow
  - [ ] 23.1 Implement `SignalCard` component (`dashboard/frontend/src/components/SignalCard.tsx`)
    - Display: asset pair, direction badge (Long/Short), final score, entry price, SL, TP1, TP2, gross R:R, net R:R after fees/slippage, score breakdown (all five sub-scores as a bar chart), current regime state
    - Include `CountdownTimer` sub-component that counts down remaining candles before expiry (reads `expires_at_candle` and current candle index)
    - When `CountdownTimer` reaches zero: mark card as EXPIRED, remove from active queue, call `PATCH /api/signals/{id}/expire`
    - _Requirements: 18.1, 18.5_

  - [ ] 23.2 Implement CONFIRM and SKIP actions
    - CONFIRM button: call `POST /api/trade/confirm` with signal ID; update card status to "Submitted"; disable both buttons
    - SKIP button: show optional skip reason modal; call `POST /api/signals/{id}/skip` with reason; remove card from queue
    - Both actions must complete within 2 seconds of user click (use optimistic UI update)
    - _Requirements: 18.2, 18.3, 18.4, 17.3_

  - [ ] 23.3 Implement `SignalCardList` page (`dashboard/frontend/src/pages/SignalsPage.tsx`)
    - Render a list of `SignalCard` components from `alertsStore`
    - New cards animate in from the top; expired/confirmed/skipped cards animate out
    - Empty state message when no active alerts
    - _Requirements: 18.1, 18.10_

  - [ ]* 23.4 Write unit tests for SignalCard component
    - Test that all required fields are rendered (asset, direction, score, entry, SL, TP1, TP2, R:R, regime)
    - Test that CONFIRM button calls the correct API endpoint
    - Test that SKIP button shows the skip reason modal
    - Test that CountdownTimer renders the correct remaining candle count
    - _Requirements: 18.1, 18.2, 18.3, 18.4_

- [ ] 24. Chart view, Trade Journal table, and Analytics page
  - [ ] 24.1 Implement real-time chart with overlays (`dashboard/frontend/src/components/TradingChart.tsx`)
    - Use `lightweight-charts` to render OHLCV candlestick chart for the selected asset
    - Overlay detected Order Blocks as shaded rectangles (green for bullish, red for bearish)
    - Overlay Fair Value Gaps as shaded rectangles
    - Overlay Fibonacci retracement levels as horizontal lines
    - Overlay POC, VAH, VAL as horizontal lines with labels
    - _Requirements: 18.6_

  - [ ] 24.2 Implement Trade Journal table (`dashboard/frontend/src/pages/JournalPage.tsx`)
    - Fetch from `GET /api/journal` with pagination
    - Columns: timestamp, pair, direction, score, entry, SL, TP, actual fill price, actual slippage, gross PnL, net PnL, result (Win/Loss/BE)
    - Color-code rows: green for Win, red for Loss, grey for BE
    - _Requirements: 18.7_

  - [ ] 24.3 Implement Analytics page (`dashboard/frontend/src/pages/AnalyticsPage.tsx`)
    - Fetch from `GET /api/analytics`
    - Display: overall win rate (net), profit factor (net), max drawdown, Sharpe Ratio
    - Per-strategy performance breakdown as a sortable table
    - Equity curve chart using `recharts`
    - _Requirements: 18.8_

  - [ ]* 24.4 Write unit tests for Journal and Analytics pages
    - Test Journal table renders correct columns and row count from mock API response
    - Test Analytics page displays correct overall metrics
    - Test per-strategy breakdown table is sortable
    - _Requirements: 18.7, 18.8_


---

## Phase 7 — Trade Execution

- [ ] 25. Trade Executor
  - [ ] 25.1 Implement `TradeExecutor` class (`trade/trade_executor.py`)
    - `execute(signal: Signal, config: dict) -> TradeResult`
    - Enforce testnet safety: if `config.exchange.testnet` is not explicitly `False`, route ALL orders to the exchange sandbox; never call live endpoints
    - Use `ccxt` to submit a limit or market order within 2 seconds of confirmation
    - After entry fill: automatically place SL order and TP1/TP2 orders
    - Apply leverage from `assets.<asset>.leverage` or global default for Futures orders
    - Retry order submission up to 3 times with exponential backoff on API error; notify user via Redis pub/sub and log failure if all retries fail
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.7, 19.8, 19.9_

  - [ ] 25.2 Implement testnet safety enforcement
    - Add a `_assert_testnet_safe(config)` guard at the top of `execute()` that raises `LiveTradingNotAllowedError` if `config.exchange.testnet` is not explicitly `False`
    - This guard MUST run before any ccxt call is made
    - _Requirements: 19.8, 19.9_

  - [ ]* 25.3 Write property test for Testnet Safety Enforcement
    - **Property 19: Testnet Safety Enforcement**
    - Use `hypothesis` to generate config dicts where `exchange.testnet` is any value other than `False` (including missing, `True`, `None`, `"false"`, `0`)
    - Assert that `TradeExecutor.execute()` never calls any live trading endpoint
    - Assert that all order submissions are routed to the exchange sandbox
    - **Validates: Requirements 19.8, 19.9**

  - [ ]* 25.4 Write unit tests for Trade Executor
    - Test that a confirmed signal results in an entry order + SL order + TP orders being submitted
    - Test retry logic: mock ccxt to fail twice then succeed; assert 3 total calls
    - Test that all retries failing triggers user notification and logs the failure
    - Test that leverage is applied correctly for Futures orders
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.7_

- [ ] 26. Trade Journal writer and position monitoring
  - [ ] 26.1 Implement Trade Journal writer (`trade/trade_journal.py`)
    - `record_entry(signal: Signal, fill_price: float, order_id: str)`: insert row into `trade_journal` with actual fill price, computed slippage, exchange order ID, timestamp
    - `record_exit(trade_id: str, exit_price: float, exit_order_id: str)`: update row with exit price, actual exit slippage, gross PnL, net PnL (after fees + slippage + funding), result (win/loss/be)
    - _Requirements: 19.5, 19.6, 19.10_

  - [ ] 26.2 Implement position monitoring (`trade/position_monitor.py`)
    - Background Celery task `monitor_positions()` that polls open positions via ccxt at each candle close
    - When a position is closed (SL or TP hit): call `record_exit()` with final fill price
    - Update `CorrelationManager` portfolio heat after each position close
    - _Requirements: 19.10, 14.6_

  - [ ]* 26.3 Write unit tests for Trade Journal
    - Test `record_entry` inserts a row with correct slippage = `actual_fill - signal_entry`
    - Test `record_exit` computes correct net_pnl = gross_pnl - fees - slippage - funding
    - Test that `result` is set to "win" when net_pnl > 0, "loss" when < 0, "be" when = 0
    - _Requirements: 19.5, 19.6, 19.10_

- [ ] 27. Checkpoint — Trade execution integration
  - Wire `POST /api/trade/confirm` FastAPI endpoint to `TradeExecutor.execute()`
  - Ensure testnet mode is active and all orders go to sandbox
  - Ensure all tests pass, ask the user if questions arise.


---

## Phase 8 — Integration and Property-Based Test Suite

- [ ] 28. End-to-end integration tests
  - [ ] 28.1 Write integration test: full signal pipeline (`tests/integration/test_signal_pipeline.py`)
    - Start Redis and PostgreSQL via `docker-compose` (or use `testcontainers`)
    - Feed synthetic OHLCV data for BTC/USDT 15m into Redis
    - Run `run_signal_scoring("BTC/USDT", "15m")` Celery task synchronously
    - Assert that a Signal_Log entry is written to PostgreSQL for every generated signal
    - Assert that ALERT-class signals are published to Redis `alerts:channel`
    - _Requirements: 17.1, 6.5_

  - [ ] 28.2 Write integration test: full backtest run (`tests/integration/test_backtest.py`)
    - Load 90 days of synthetic OHLCV data for BTC/USDT 1h
    - Run `BacktestingEngine.run()` with `SMCOrderBlockFVGStrategy`
    - Assert that result record is written to `logs/backtest/`
    - Assert that all computed metrics are present and within valid ranges
    - Assert that walk-forward windows are non-overlapping and cover the full dataset
    - _Requirements: 9.6, 10.1–10.4_

  - [ ] 28.3 Write integration test: config hot-reload (`tests/integration/test_config_reload.py`)
    - Start the system with initial `config.yaml`
    - Modify `strategy.score_threshold.alert` from 75 to 80 in `config.yaml`
    - Trigger `ConfigSystem.reload()`
    - Assert that the next signal scoring run uses the new threshold of 80
    - _Requirements: 15.11_

  - [ ]* 28.4 Write integration test: WebSocket signal delivery (`tests/integration/test_websocket.py`)
    - Connect a test WebSocket client to `/ws/alerts`
    - Publish a synthetic ALERT signal to Redis `alerts:channel`
    - Assert that the test client receives the signal within 1 second
    - _Requirements: 18.10_

- [x] 29. Property-based test suite — all 20 correctness properties
  - [ ] 29.1 Verify Property 1 — Indicator No-Look-Ahead Invariant
    - Confirm the property test from Task 2.5 covers all five indicators (ATR, RSI, EMA, ADX, BB)
    - Run `pytest tests/properties/test_indicators.py -v` and confirm all pass
    - _Requirements: 4.3, 5.1_

  - [ ] 29.2 Verify Property 2 — Indicator NaN for Insufficient Data
    - Confirm the property test from Task 2.6 covers all five indicators
    - Run and confirm all pass
    - _Requirements: 4.5_

  - [ ] 29.3 Verify Property 3 — Gap Detection Completeness
    - Confirm the property test from Task 3.3 covers all gap sizes (1 missing, N missing, all missing)
    - Run and confirm all pass
    - _Requirements: 2.4_

  - [ ] 29.4 Verify Property 4 — Linear Interpolation Correctness
    - Confirm the property test from Task 3.4 covers all five OHLCV fields
    - Run and confirm all pass
    - _Requirements: 2.5_

  - [ ] 29.5 Verify Property 5 — Score Normalization Invariant
    - Confirm the property test from Task 10.2 covers boundary values (all zeros, all maxes, mixed)
    - Run and confirm all pass
    - _Requirements: 6.1, 6.3_

  - [ ] 29.6 Verify Property 6 — Confluence Monotonicity
    - Confirm the property test from Task 10.3 covers all pairs of module scores
    - Run and confirm all pass
    - _Requirements: 6.4_

  - [ ] 29.7 Verify Property 7 — Risk Cap Invariant
    - Confirm the property test from Task 11.3 covers all three position sizing modes
    - Run and confirm all pass
    - _Requirements: 7.3_

  - [ ] 29.8 Verify Property 8 — Backtest Chronological Order
    - Confirm the property test from Task 17.3 covers shuffled, reversed, and random orderings
    - Run and confirm all pass
    - _Requirements: 8.6_

  - [ ] 29.9 Verify Property 9 — Slippage Application Correctness
    - Confirm the property test from Task 17.4 covers both long and short directions
    - Run and confirm all pass
    - _Requirements: 8.2_

  - [ ] 29.10 Verify Property 10 — Win Rate Formula Invariant
    - Confirm the property test from Task 18.2 covers edge cases (all wins, all losses, empty list)
    - Run and confirm all pass
    - _Requirements: 9.2_

  - [ ] 29.11 Verify Property 11 — Sharpe Ratio Formula Invariant
    - Confirm the property test from Task 18.3 covers positive, negative, and near-zero std dev cases
    - Run and confirm all pass
    - _Requirements: 9.3_

  - [ ] 29.12 Verify Property 12 — Regime Output Validity
    - Confirm the property test from Task 8.2 covers all ADX/ATR combinations
    - Run and confirm all pass
    - _Requirements: 13.1_

  - [ ] 29.13 Verify Property 13 — PARABOLIC Short Suppression
    - Confirm the property test from Task 8.3 covers all short-direction signals in PARABOLIC regime
    - Run and confirm all pass
    - _Requirements: 13.5_

  - [ ] 29.14 Verify Property 14 — Pearson Correlation Bounds
    - Confirm the property test from Task 9.2 covers series of length 2, 10, 100, and 1000
    - Run and confirm all pass
    - _Requirements: 14.1_

  - [ ] 29.15 Verify Property 15 — Portfolio Heat Summation
    - Confirm the property test from Task 9.3 covers 1, 5, and 20 open positions
    - Run and confirm all pass
    - _Requirements: 14.6_

  - [ ] 29.16 Verify Property 16 — Portfolio Heat Enforcement
    - Confirm the property test from Task 9.4 covers heat exactly at limit, above limit, and below limit
    - Run and confirm all pass
    - _Requirements: 14.7_

  - [ ] 29.17 Verify Property 17 — Signal Log Completeness
    - Confirm the property test from Task 21.5 covers ALERT, WATCH, and IGNORE classifications
    - Run and confirm all pass
    - _Requirements: 17.1_

  - [ ] 29.18 Verify Property 18 — Signal Card Required Fields
    - Confirm the property test from Task 12.4 covers all required field names and types
    - Run and confirm all pass
    - _Requirements: 18.1_

  - [ ] 29.19 Verify Property 19 — Testnet Safety Enforcement
    - Confirm the property test from Task 25.3 covers all non-False values for `exchange.testnet`
    - Run and confirm all pass
    - _Requirements: 19.8, 19.9_

  - [ ] 29.20 Verify Property 20 — Config Validation Completeness
    - Confirm the property test from Task 1.5 covers all required parameter namespaces
    - Run and confirm all pass
    - _Requirements: 15.10, 12.6_

- [ ] 30. Final checkpoint — Full test suite
  - Run `pytest tests/ -v --tb=short` and ensure all unit tests, integration tests, and property-based tests pass
  - Run `docker-compose up` and verify the full system starts without errors
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP build
- Each task references specific requirements for full traceability to `requirements.md`
- Property-based tests use the `hypothesis` library and are distributed throughout the build (not only in Task 29)
- Task 29 is a verification sweep — it confirms that all 20 correctness properties defined in `design.md` have been implemented and pass
- Testnet mode is enforced at the code level in Task 25.2 and is never optional
- Docker Compose (Redis + PostgreSQL + Celery) is set up in Task 1.2 as a prerequisite for all subsequent tasks
- The `exchange.testnet` flag must be explicitly set to `false` in `config.yaml` before any live order is submitted; any other value defaults to testnet
