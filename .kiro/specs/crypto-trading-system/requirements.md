# Requirements Document

## Introduction

A modular, data-driven Python trading system targeting cryptocurrency futures and spot markets on centralized exchanges (CEX). The system identifies high-probability entry and exit signals across 15m, 30m, and 1h timeframes for top-tier assets (BTC, ETH, SOL, and others), validates strategies through rigorous backtesting, and enforces strict constraints against overfitting, repainting, and look-ahead bias.

The architecture follows a three-layer design: **Layer 1 — Data Input** (OHLCV, Order Book, Funding Rate via Redis/Celery), **Layer 2 — AI Engine** (Signal Scoring with Regime Detection, Correlation Risk Management, and Strategy Registry), and **Layer 3 — Human Confirm Dashboard** (Signal Cards, one-click trade execution, Trade Journal, and Analytics). All tunable parameters are controlled through a single `config.yaml` file without requiring source code changes. The system operates in Testnet Mode before any live trading is enabled.

---

## Glossary

- **System**: The overall crypto trading system application.
- **Strategy**: A named set of rules that defines entry and exit conditions for a trade.
- **Signal**: A discrete buy or sell recommendation produced by a Strategy at a specific candle close.
- **Score**: A normalized integer in [0, 100] representing the combined confidence of all active confirmation factors for a Signal.
- **Indicator**: A computed value derived from OHLCV data used as input to a Strategy.
- **OHLCV**: Open, High, Low, Close, Volume candlestick data.
- **Candle**: A single OHLCV record representing one time period.
- **Closed Candle**: A Candle whose time period has fully elapsed and whose values are final.
- **Timeframe**: The duration of a single Candle; one of 15m, 30m, or 1h.
- **Asset**: A tradable cryptocurrency pair (e.g., BTC/USDT).
- **Data_Pipeline**: The module responsible for fetching, validating, and storing OHLCV and funding rate data.
- **Backtesting_Engine**: The module that simulates trade execution against historical data and computes performance metrics.
- **Signal_Scorer**: The module that aggregates confirmation factors and assigns a Score to each Signal.
- **Risk_Manager**: The module that computes position size and enforces risk limits.
- **Strategy_Spec**: A Markdown document in `/docs/` describing the mathematical logic, entry/exit rules, context filter, and failure scenario for one Strategy.
- **Order Block (OB)**: A price zone representing institutional supply or demand, identified by the last opposing candle before a strong directional move.
- **Breaker Block**: A former Order Block that has been violated and flipped to the opposing role.
- **Fair Value Gap (FVG)**: A three-candle imbalance where the wicks of candle 1 and candle 3 do not overlap.
- **Pinbar**: A Candle whose tail is at least 2× the length of its body.
- **Engulfing**: A two-candle pattern where the second candle's body fully contains the first candle's body.
- **Inside Bar**: A Candle whose high and low are fully within the high and low of the preceding candle.
- **Quasimodo (QM)**: A reversal pattern defined by a sequence of higher-high, lower-high, lower-low, and a return to the prior support/resistance zone.
- **ATR**: Average True Range; a measure of market volatility over N periods.
- **Funding Rate**: A periodic payment between long and short futures holders on a perpetual contract.
- **Walk-Forward Analysis**: A validation method that trains on an in-sample window and tests on a subsequent out-of-sample window, rolling forward in time.
- **Slippage**: The difference between the expected fill price and the actual fill price.
- **Profit Factor**: Gross profit divided by gross loss across all trades.
- **Sharpe Ratio**: Mean return divided by standard deviation of returns, annualized.
- **Max Drawdown**: The largest peak-to-trough decline in portfolio equity.
- **Recovery Factor**: Net profit divided by Max Drawdown.
- **CEX**: Centralized cryptocurrency exchange.
- **ccxt**: An open-source Python library for connecting to cryptocurrency exchange APIs.
- **Regime**: The current macro state of the market for a given Asset, classified as one of: TRENDING, RANGING, PARABOLIC, or CHOPPY.
- **Regime_Detector**: The module that classifies the current Regime for each Asset and outputs a Score multiplier.
- **Score_Multiplier**: A float factor applied to the raw Signal Score to adjust for the current Regime (e.g., 0.6 in PARABOLIC reduces the score by 40%).
- **ADX**: Average Directional Index; a measure of trend strength. ADX > 25 indicates a trending market; ADX < 20 indicates a choppy or ranging market.
- **Portfolio_Heat**: The total percentage of account equity currently exposed across all open positions.
- **Correlation_Manager**: The module that computes rolling 24-hour correlations between Assets and enforces correlated-risk limits.
- **Correlated_Risk_Limit**: The maximum combined risk percentage allowed for a group of Assets whose pairwise rolling correlation exceeds the configured threshold (default: 0.8).
- **Config_System**: The module that loads, validates, and exposes all tunable parameters from a single configuration file (`config.yaml`) to all other modules.
- **Strategy_Registry**: A runtime registry that maps strategy names to their implementing classes, enabling dynamic loading and switching of strategies without modifying source code.
- **BaseStrategy**: The abstract interface that every Strategy class must implement, exposing at minimum `generate_signals(ohlcv: DataFrame) -> List[Signal]`.
- **Signal_Card**: The UI component displayed in the Human Confirm Dashboard that presents all relevant information for a single Signal, including pair, direction, Score, entry/SL/TP levels, net R:R after fees, score breakdown, and a countdown timer.
- **Countdown_Timer**: A visual timer on the Signal_Card that counts down the remaining candles before the Signal expires due to Time Invalidation.
- **Dashboard**: The Human Confirm Dashboard web application (Layer 3) where the user reviews Signal_Cards and confirms or skips trades.
- **Trade_Executor**: The module that sends orders to the exchange via ccxt after the user confirms a Signal, and automatically places SL/TP orders.
- **Trade_Journal**: The persistent log of all confirmed trades, including entry/exit prices, fees, actual slippage, gross PnL, and net PnL.
- **Testnet_Mode**: An operating mode in which all order execution is directed to the exchange's paper-trading or testnet environment instead of the live market.
- **Signal_Log**: A structured log entry recording every generated Signal (including SKIP and IGNORE signals) with its full score breakdown, regime state, funding rate, and correlation state at the time of generation.
- **Benchmark_Table**: A comparison table produced after running backtests across multiple strategies and timeframes, showing all performance metrics side by side.
- **POC**: Point of Control; the price level with the highest traded volume within a given Volume Profile window.
- **VAH**: Value Area High; the upper boundary of the price range containing 70% of traded volume in a Volume Profile window.
- **VAL**: Value Area Low; the lower boundary of the price range containing 70% of traded volume in a Volume Profile window.

---

## Requirements

### Requirement 1: Strategy Specification Documents

**User Story:** As a quant developer, I want a complete technical specification document for each strategy, so that I can implement rule-based Python logic from an unambiguous, single source of truth.

#### Acceptance Criteria

1. THE System SHALL produce one Strategy_Spec Markdown file per strategy in the `/docs/` directory, covering: Pinbar, Engulfing, Inside Bar, Order Block, Breaker Block, Fair Value Gap, Quasimodo, Double Top/Bottom, Flag, RSI Momentum, Bollinger Band Squeeze, and EMA Cross.
2. WHEN a Strategy_Spec is created, THE System SHALL include a Mathematical Logic section that expresses all pattern conditions as precise inequalities or formulas (e.g., `tail_length >= 2 * body_length` for Pinbar).
3. WHEN a Strategy_Spec is created, THE System SHALL include an Objective Entry/Exit section that specifies the exact candle-close trigger, entry price level, stop-loss level, and take-profit level for each direction (long and short).
4. WHEN a Strategy_Spec is created, THE System SHALL include a Context Filter section that defines the minimum 1h timeframe condition that must be satisfied before a 15m or 30m Signal is considered valid.
5. WHEN a Strategy_Spec is created, THE System SHALL include a Failure Scenario section that defines the precise price or structural condition that invalidates the pattern before entry is triggered.
6. THE System SHALL define all mathematical terms and thresholds in the Glossary of each Strategy_Spec before they are referenced in that document.

---

### Requirement 2: Data Pipeline — OHLCV Ingestion

**User Story:** As a quant developer, I want reliable OHLCV data for all supported assets and timeframes, so that strategies and the backtesting engine operate on complete, accurate historical and live data.

#### Acceptance Criteria

1. THE Data_Pipeline SHALL fetch OHLCV data for each configured Asset and Timeframe using the ccxt library.
2. THE Data_Pipeline SHALL support the following Timeframes: 15m, 30m, and 1h.
3. THE Data_Pipeline SHALL support at minimum the following Assets: BTC/USDT, ETH/USDT, SOL/USDT.
4. WHEN OHLCV data is fetched, THE Data_Pipeline SHALL detect missing Candles by comparing the expected sequence of timestamps against the received sequence.
5. WHEN missing Candles are detected, THE Data_Pipeline SHALL fill gaps using linear interpolation for OHLCV fields and log each filled gap with the Asset, Timeframe, and timestamp range.
6. IF the ccxt API returns an error response, THEN THE Data_Pipeline SHALL retry the request up to 3 times with exponential backoff before raising a structured error.
7. THE Data_Pipeline SHALL store fetched OHLCV data in a structured format that preserves Asset, Timeframe, and timestamp as unique composite keys.

---

### Requirement 3: Data Pipeline — Funding Rate Ingestion

**User Story:** As a futures trader, I want funding rate data integrated into the system, so that PnL calculations and strategy filters accurately reflect the cost of holding perpetual futures positions.

#### Acceptance Criteria

1. THE Data_Pipeline SHALL fetch historical and current Funding Rate data for each configured futures Asset using the ccxt library.
2. THE Data_Pipeline SHALL store Funding Rate records with Asset, timestamp, and rate value as fields.
3. WHEN a futures trade is simulated in the Backtesting_Engine, THE Backtesting_Engine SHALL apply the Funding Rate payments that occurred during the holding period to the trade's PnL.
4. IF Funding Rate data is unavailable for a given Asset and timestamp range, THEN THE Data_Pipeline SHALL log a warning and proceed with a Funding Rate of 0.0 for that period.

---

### Requirement 4: Indicator Library

**User Story:** As a strategy developer, I want a library of reusable, independently testable indicator functions, so that strategies can be composed from verified building blocks without duplicating computation logic.

#### Acceptance Criteria

1. THE System SHALL implement each Indicator as a pure function or stateless class method that accepts an OHLCV array and returns a numeric array or scalar of the same length.
2. THE System SHALL implement the following Indicators: ATR (N-period), RSI (N-period), Bollinger Bands (N-period, K standard deviations), EMA (N-period), and candle body/tail/wick measurements.
3. WHEN an Indicator is computed, THE System SHALL use only data at index T or earlier; data at index T+1 or later SHALL NOT be accessed during computation of index T.
4. THE System SHALL expose each Indicator through a consistent interface that accepts a configurable period parameter N.
5. IF an OHLCV array contains fewer than N elements, THEN THE System SHALL return NaN for all output positions that require more data than is available.

---

### Requirement 5: Signal Generation — No Repainting and No Look-Ahead Bias

**User Story:** As a quant developer, I want all signals generated exclusively on closed candles without access to future data, so that backtest results are not inflated by repainting or look-ahead bias.

#### Acceptance Criteria

1. WHEN a Strategy evaluates a Candle at index T, THE Strategy SHALL access only Candles at indices 0 through T.
2. THE System SHALL generate a Signal only after the Candle at index T has fully closed.
3. IF a Strategy references a Candle that has not yet closed, THEN THE System SHALL raise a runtime error identifying the Strategy name and the offending index.
4. THE System SHALL record the Timeframe and index T of each generated Signal to enable post-hoc audit of data access.

---

### Requirement 6: Signal Scoring

**User Story:** As a trader, I want each signal assigned a confidence score based on the number and weight of confirming factors, so that I can filter low-quality setups and prioritize high-probability trades.

#### Acceptance Criteria

1. THE Signal_Scorer SHALL assign a Score as a normalized integer in [0, 100] to each Signal.
2. THE Signal_Scorer SHALL compute the raw score as the sum of four module scores: Order Flow Analysis (max 35 pts), SMC Analysis (max 30 pts), VSA + Volume Profile (max 30 pts), and Context Filter (max 15 pts), plus a Confluence Bonus (max 15 pts), normalized to 100.
3. THE Signal_Scorer SHALL apply a Score_Multiplier from the Regime_Detector to the raw score before normalization; the final Score SHALL equal `min(round(raw_score * multiplier / 125 * 100), 100)`.
4. WHEN two or more confirmation factors are active simultaneously (e.g., SMC Order Block + VSA No Supply), THE Signal_Scorer SHALL produce a Score that is strictly greater than the Score produced by either factor alone.
5. THE Signal_Scorer SHALL classify each Signal as ALERT (Score ≥ 75), WATCH (Score 55–74), or IGNORE (Score < 55).
6. THE System SHALL allow all module point allocations and the ALERT/WATCH thresholds to be overridden via the Config_System without modifying source code.

---

### Requirement 7: Risk Management — Position Sizing

**User Story:** As a trader, I want position sizes calculated dynamically based on current volatility, so that risk per trade remains consistent regardless of market conditions.

#### Acceptance Criteria

1. THE Risk_Manager SHALL compute position size using the formula: `position_size = (account_equity * risk_per_trade_pct) / (stop_loss_distance_in_price * contract_value)`.
2. THE Risk_Manager SHALL derive stop_loss_distance_in_price from the ATR value at the time of Signal generation, using a configurable ATR multiplier.
3. THE Risk_Manager SHALL cap position size so that the maximum loss on any single trade does not exceed a configurable percentage of account equity (default: 2%).
4. IF the computed position size is zero or negative due to an ATR value of zero, THEN THE Risk_Manager SHALL reject the Signal and log the rejection with the Asset, Timeframe, and Signal timestamp.
5. THE Risk_Manager SHALL support both Spot and Futures position sizing, applying leverage only when the trade type is Futures.

---

### Requirement 8: Backtesting Engine — Trade Simulation

**User Story:** As a quant developer, I want a backtesting engine that simulates realistic trade execution, so that strategy performance metrics reflect actual trading costs and market conditions.

#### Acceptance Criteria

1. THE Backtesting_Engine SHALL simulate trade entry and exit using Closed Candle prices only.
2. THE Backtesting_Engine SHALL apply a configurable Slippage of 0.05%–0.1% to each fill price.
3. THE Backtesting_Engine SHALL deduct exchange commission from each trade: 0.04% for Futures trades and 0.1% for Spot trades.
4. THE Backtesting_Engine SHALL apply Funding Rate payments to open Futures positions at each funding interval during the holding period.
5. WHEN a stop-loss or take-profit level is reached within a Candle, THE Backtesting_Engine SHALL fill the order at the stop-loss or take-profit price plus Slippage, not at the Candle close.
6. THE Backtesting_Engine SHALL process Candles in strictly ascending timestamp order and SHALL NOT access any Candle with a timestamp greater than the current simulation time.

---

### Requirement 9: Backtesting Engine — Performance Metrics

**User Story:** As a quant developer, I want comprehensive performance metrics computed after each backtest run, so that I can objectively compare strategies and identify underperforming configurations.

#### Acceptance Criteria

1. THE Backtesting_Engine SHALL compute the following metrics after each run: win rate (%), profit factor, maximum drawdown (%), Sharpe Ratio, and Recovery Factor.
2. THE Backtesting_Engine SHALL compute win rate as the number of profitable trades divided by the total number of closed trades, expressed as a percentage.
3. THE Backtesting_Engine SHALL compute Sharpe Ratio using daily returns, annualized by multiplying by the square root of 365.
4. THE Backtesting_Engine SHALL compute Max Drawdown as the maximum percentage decline from any equity peak to the subsequent trough over the full backtest period.
5. THE Backtesting_Engine SHALL compute Recovery Factor as net profit divided by Max Drawdown.
6. WHEN a backtest run completes, THE Backtesting_Engine SHALL write a structured result record to `/logs/` containing the strategy name, Asset, Timeframe, date range, all computed metrics, and the configuration parameters used.

---

### Requirement 10: Walk-Forward Analysis

**User Story:** As a quant developer, I want walk-forward analysis to validate that strategy parameters generalize beyond the training window, so that I can detect and prevent overfitting.

#### Acceptance Criteria

1. THE Backtesting_Engine SHALL support a walk-forward analysis mode that partitions the full historical dataset into sequential in-sample and out-of-sample windows.
2. WHEN walk-forward analysis is executed, THE Backtesting_Engine SHALL optimize strategy parameters using only the in-sample window and evaluate performance on the subsequent out-of-sample window.
3. THE Backtesting_Engine SHALL roll the in-sample and out-of-sample windows forward by a configurable step size until the end of the dataset is reached.
4. THE Backtesting_Engine SHALL aggregate out-of-sample results across all walk-forward windows into a single combined performance report.
5. IF out-of-sample performance degrades by more than a configurable threshold relative to in-sample performance, THEN THE Backtesting_Engine SHALL flag the strategy as potentially overfit in the result record.

---

### Requirement 11: AI Feedback Loop and Optimization Logging

**User Story:** As a quant developer, I want all backtest results persisted and analyzed for underperformance patterns, so that the system can suggest targeted logic improvements over time.

#### Acceptance Criteria

1. THE System SHALL persist every backtest result record to `/logs/` in a structured, machine-readable format (JSON or CSV) immediately after each run completes.
2. THE System SHALL record in each log entry: strategy name, Asset, Timeframe, date range, all performance metrics, configuration parameters, and a timestamp of when the run completed.
3. WHEN the optimization analysis is triggered, THE System SHALL read all log entries and identify Underperformance Clusters defined as contiguous date ranges where win rate falls below 45% or profit factor falls below 1.0.
4. WHEN an Underperformance Cluster is identified, THE System SHALL output a structured suggestion record that identifies the cluster date range, the affected strategy and Asset, and at least one candidate logic filter to investigate.
5. THE System SHALL store optimization suggestion records in `/logs/` separately from raw backtest result records.
6. IF a backtest run produces fewer than 30 closed trades, THEN THE Backtesting_Engine SHALL flag the result as statistically insufficient and SHALL NOT include it in Underperformance Cluster analysis.

---

### Requirement 12: Modular Architecture and Interfaces

**User Story:** As a developer, I want the system organized into well-defined modules with explicit interfaces, so that components can be developed, tested, and replaced independently.

#### Acceptance Criteria

1. THE System SHALL organize source code into the following top-level directories: `docs/`, `strategies/`, `indicators/`, `data/`, `engine/`, `risk/`, `alert/`, `trade/`, `backtest/`, `dashboard/`, `logs/`, with `main.py` as the entry point.
2. THE System SHALL define each Strategy as a class that implements the BaseStrategy interface exposing at minimum `generate_signals(ohlcv: DataFrame) -> List[Signal]`.
3. THE System SHALL define each Indicator as a callable that conforms to a common `Indicator` interface accepting an OHLCV array and returning a numeric array.
4. THE System SHALL define the Data_Pipeline, Backtesting_Engine, Signal_Scorer, Risk_Manager, Regime_Detector, Correlation_Manager, Strategy_Registry, Trade_Executor, and Dashboard as separate classes with no circular dependencies between modules.
5. THE System SHALL provide a `config.yaml` configuration file (the Config_System) that controls all tunable parameters — including Timeframes, Assets, risk percentage, ATR multiplier, Slippage, fees, walk-forward window sizes, regime thresholds, correlation thresholds, and strategy activation list — without requiring source code changes.
6. IF a required configuration parameter is missing or invalid at startup, THEN THE System SHALL raise a descriptive error identifying the missing parameter name and expected type before any data is fetched or any trade is simulated.

---

### Requirement 13: Regime Detection

**User Story:** As a trader, I want the system to automatically classify the current market state for each asset, so that signal scoring and strategy selection adapt to trending, ranging, parabolic, and choppy conditions.

#### Acceptance Criteria

1. THE Regime_Detector SHALL classify the current Regime for each Asset at every Closed Candle as one of four states: TRENDING, RANGING, PARABOLIC, or CHOPPY.
2. THE Regime_Detector SHALL classify the Regime as TRENDING when ADX(14) > 25 on the 1h timeframe.
3. THE Regime_Detector SHALL classify the Regime as CHOPPY or RANGING when ADX(14) < 20 on the 1h timeframe.
4. THE Regime_Detector SHALL classify the Regime as PARABOLIC when the current ATR(14) on the 15m timeframe exceeds 3× the 20-period rolling average of ATR(14) on the same timeframe.
5. WHEN the Regime is PARABOLIC, THE Regime_Detector SHALL output a Score_Multiplier of 0.6 (reducing the final Score by 40%) and THE Signal_Scorer SHALL suppress all Short Signals for that Asset.
6. WHEN the Regime is TRENDING, THE Regime_Detector SHALL output a Score_Multiplier of 1.0 (no adjustment).
7. WHEN the Regime is RANGING or CHOPPY, THE Regime_Detector SHALL output a Score_Multiplier of 0.85.
8. THE Regime_Detector SHALL expose the current Regime state and Score_Multiplier for each Asset through a consistent interface consumable by the Signal_Scorer and the Signal_Card.
9. THE thresholds for ADX TRENDING (default: 25), ADX CHOPPY (default: 20), and ATR PARABOLIC multiplier (default: 3.0) SHALL be configurable via the Config_System without modifying source code.

---

### Requirement 14: Correlation Risk Management

**User Story:** As a risk manager, I want the system to track rolling correlations between assets and enforce correlated-risk limits, so that the portfolio is not over-exposed to a single market move affecting multiple correlated positions simultaneously.

#### Acceptance Criteria

1. THE Correlation_Manager SHALL compute a rolling 24-hour Pearson correlation coefficient between every pair of active Assets using 1h OHLCV close prices.
2. THE Correlation_Manager SHALL update correlation coefficients at the close of each 1h Candle.
3. WHEN the rolling correlation between two Assets exceeds the configured threshold (default: 0.8), THE Risk_Manager SHALL treat those Assets as a correlated group for risk aggregation purposes.
4. THE Risk_Manager SHALL ensure that the combined risk percentage of all open and pending positions within any correlated group does not exceed the configured Correlated_Risk_Limit (default: 3% of account equity).
5. IF opening a new position would cause the combined risk of its correlated group to exceed the Correlated_Risk_Limit, THEN THE Risk_Manager SHALL reject the Signal and log the rejection with the Asset, the correlated group members, and the current combined risk percentage.
6. THE Correlation_Manager SHALL compute and expose the Portfolio_Heat as the sum of risk percentages across all currently open positions.
7. WHEN Portfolio_Heat exceeds the configured maximum (default: 6% of account equity), THE Risk_Manager SHALL reject all new Signals until Portfolio_Heat falls below the threshold.
8. THE System SHALL display the current Portfolio_Heat and per-group correlated risk on the Dashboard in real time.
9. THE correlation threshold (default: 0.8), Correlated_Risk_Limit (default: 3%), and Portfolio_Heat limit (default: 6%) SHALL be configurable via the Config_System without modifying source code.

---

### Requirement 15: Configuration System

**User Story:** As a developer and trader, I want all system parameters controlled through a single configuration file, so that I can switch strategies, adjust risk rules, change exchange settings, and tune regime thresholds without touching source code.

#### Acceptance Criteria

1. THE Config_System SHALL load all parameters from a single `config.yaml` file at startup and expose them to all modules through a validated configuration object.
2. THE Config_System SHALL support the following parameter namespaces: `position`, `regime`, `risk`, `strategy`, `exchange`, `assets`, and `backtest`.
3. THE Config_System SHALL support the following `position` parameters: `mode` (one of `fixed_usd`, `risk_pct`, or `kelly`), `fixed_usd` (USD amount per trade when mode is `fixed_usd`), and `risk_pct` (percentage of account equity risked per trade when mode is `risk_pct`).
4. THE Config_System SHALL support the following `regime` parameters: `adx_trending_threshold` (default: 25), `adx_choppy_threshold` (default: 20), `atr_parabolic_multiplier` (default: 3.0), and `parabolic_score_multiplier` (default: 0.6).
5. THE Config_System SHALL support the following `risk` parameters: `correlation_threshold` (default: 0.8), `max_correlated_risk_pct` (default: 3.0), `portfolio_heat_limit_pct` (default: 6.0), and `max_concurrent_positions` (default: 3).
6. THE Config_System SHALL support the following `strategy` parameters: `active` (a list of strategy names to load from the Strategy_Registry).
7. THE Config_System SHALL support the following `exchange` parameters: `name` (exchange identifier for ccxt), `market_type` (one of `futures` or `spot`), `fee_rate` (default: 0.001), `slippage_pct` (default: 0.0002), and `testnet` (boolean, default: true).
8. THE Config_System SHALL support per-Asset overrides under the `assets` namespace, including `enabled` (boolean) and `leverage` (integer override for that Asset).
9. THE Config_System SHALL support the following `backtest` parameters: `start_date`, `end_date`, `in_sample_days`, `out_of_sample_days`, and `walk_forward_step_days`.
10. IF a required parameter is absent or its value is outside the allowed range or type, THEN THE Config_System SHALL raise a descriptive validation error naming the parameter, its expected type or range, and the received value before any module is initialized.
11. THE Config_System SHALL support reloading parameters at runtime without restarting the process, applying changes to all modules on the next Candle close.

---

### Requirement 16: Strategy Registry and Plugin Architecture

**User Story:** As a developer, I want a strategy registry that loads and manages strategy classes by name, so that I can add new strategies by creating a single file and registering it, without modifying any existing code.

#### Acceptance Criteria

1. THE Strategy_Registry SHALL maintain a mapping from strategy name strings to their corresponding BaseStrategy subclass implementations.
2. THE System SHALL provide a registration mechanism (e.g., a decorator or explicit `register()` call) that adds a BaseStrategy subclass to the Strategy_Registry under a given name.
3. WHEN the system starts, THE Strategy_Registry SHALL load and instantiate only the strategies whose names appear in the `strategy.active` list in the Config_System.
4. IF a strategy name in `strategy.active` is not found in the Strategy_Registry, THEN THE System SHALL raise a descriptive error identifying the missing strategy name before any data is fetched.
5. THE System SHALL allow a new strategy to be added by creating a new Python file that defines a BaseStrategy subclass and registers it, without modifying any existing strategy file, registry file, or configuration schema.
6. THE Strategy_Registry SHALL expose a method to list all registered strategy names, enabling runtime introspection and dashboard display.
7. WHEN a strategy is loaded from the Strategy_Registry, THE System SHALL pass the validated configuration object to the strategy's constructor so that all strategy-level parameters are sourced from the Config_System.

---

### Requirement 17: Rich Logging for AI Learning

**User Story:** As a quant developer, I want every signal — including skipped and ignored ones — logged with its full context, so that the AI feedback loop can learn from all market events, not just confirmed trades.

#### Acceptance Criteria

1. THE System SHALL write a Signal_Log entry for every Signal generated, regardless of its classification (ALERT, WATCH, or IGNORE) or the user's action (CONFIRM, SKIP, or no action).
2. EACH Signal_Log entry SHALL include: timestamp, Asset, Timeframe, strategy name, signal direction, raw score, final Score after Score_Multiplier, per-module score breakdown (Order Flow, SMC, VSA+VolProfile, Context, Confluence Bonus), current Regime state, Score_Multiplier applied, current Funding Rate, current Portfolio_Heat, correlated group risk at time of signal, and the user action taken (CONFIRM / SKIP / EXPIRED / IGNORE).
3. WHEN the user selects SKIP on a Signal_Card, THE Dashboard SHALL prompt for an optional skip reason and THE System SHALL record the reason in the Signal_Log entry.
4. IF a Signal expires due to Time Invalidation before the user acts, THEN THE System SHALL record the expiry reason and the final price at expiry in the Signal_Log entry.
5. WHEN a backtest is run across multiple strategies and multiple Timeframes, THE Backtesting_Engine SHALL produce a Benchmark_Table that displays all strategies × timeframes as rows and all performance metrics (win rate, profit factor, max drawdown, Sharpe Ratio, recovery factor, trade count) as columns in a single structured output.
6. IF a backtest configuration produces fewer than 30 closed trades, THEN THE Backtesting_Engine SHALL mark that row in the Benchmark_Table as statistically insufficient and exclude it from automated optimization suggestions.
7. THE System SHALL store all Signal_Log entries in `/logs/signals/` in a machine-readable format (JSON Lines) and SHALL NOT overwrite existing entries.

---

### Requirement 18: Human Confirm Dashboard

**User Story:** As a trader, I want a web dashboard that presents each signal as a clear, actionable card with all relevant information and a countdown timer, so that I can make an informed confirm-or-skip decision within 30 seconds.

#### Acceptance Criteria

1. THE Dashboard SHALL display each ALERT-class Signal as a Signal_Card containing: Asset pair, direction (Long/Short), final Score, entry price, stop-loss price, take-profit levels (TP1 and TP2), gross R:R, net R:R after estimated fees and slippage, a human-readable score breakdown listing each active confirmation factor, the current Regime state, and a Countdown_Timer showing the number of 15m candles remaining before the Signal expires.
2. THE Signal_Card SHALL display a CONFIRM button and a SKIP button; no other action is required to execute or dismiss the trade.
3. WHEN the user clicks CONFIRM, THE Dashboard SHALL immediately send the confirmed Signal to the Trade_Executor and update the Signal_Card status to "Submitted".
4. WHEN the user clicks SKIP, THE Dashboard SHALL prompt for an optional skip reason, record the action in the Signal_Log, and remove the Signal_Card from the active queue.
5. WHEN a Signal's Countdown_Timer reaches zero, THE Dashboard SHALL automatically mark the Signal_Card as EXPIRED, remove it from the active queue, and record the expiry in the Signal_Log.
6. THE Dashboard SHALL display an embedded real-time chart for the Asset with overlays for detected Order Blocks, Fair Value Gaps, Fibonacci levels, and POC/VAH/VAL.
7. THE Dashboard SHALL include a Trade Journal table showing all confirmed trades with columns for: timestamp, pair, direction, score, entry, SL, TP, actual fill price, actual slippage, gross PnL, net PnL, and result (Win/Loss/BE).
8. THE Dashboard SHALL include an Analytics page displaying: overall win rate (net), profit factor (net), max drawdown, Sharpe Ratio, and per-strategy performance breakdown.
9. THE Dashboard SHALL display the current Portfolio_Heat and per-asset correlated group risk in a persistent header visible on all pages.
10. THE Dashboard SHALL receive Signal_Cards and trade updates in real time via WebSocket without requiring a page refresh.

---

### Requirement 19: Semi-Automatic Trade Execution

**User Story:** As a trader, I want the system to automatically place the order, set stop-loss and take-profit levels, and log actual slippage after I confirm a signal, so that execution is fast and consistent without requiring manual order entry.

#### Acceptance Criteria

1. WHEN the user confirms a Signal, THE Trade_Executor SHALL submit a limit or market order to the exchange via ccxt within 2 seconds of the confirmation action.
2. AFTER the entry order is filled, THE Trade_Executor SHALL automatically place a stop-loss order and at least one take-profit order on the exchange at the levels specified in the Signal_Card.
3. THE Trade_Executor SHALL support both Futures and Spot market types as configured in the `exchange.market_type` parameter of the Config_System.
4. THE Trade_Executor SHALL apply the leverage configured for the Asset (from `assets.<asset>.leverage` or the global default) when placing Futures orders.
5. WHEN the entry order is filled, THE Trade_Executor SHALL record the actual fill price in the Trade_Journal and compute actual Slippage as the difference between the Signal's entry price and the actual fill price.
6. THE Trade_Executor SHALL log the actual Slippage, actual fill price, exchange order ID, and timestamp for every filled order in the Trade_Journal.
7. IF the exchange API returns an error when submitting an order, THEN THE Trade_Executor SHALL retry the submission up to 3 times with exponential backoff, and IF all retries fail, THEN THE Trade_Executor SHALL notify the user via the Dashboard and log the failure with the full error response.
8. WHEN `exchange.testnet` is set to `true` in the Config_System, THE Trade_Executor SHALL direct all order submissions to the exchange's testnet or paper-trading environment and SHALL NOT submit any order to the live market.
9. THE System SHALL require `exchange.testnet` to be explicitly set to `false` in the Config_System before any live order is submitted; a missing or `true` value SHALL default to testnet mode.
10. THE Trade_Executor SHALL monitor open positions and update the Trade_Journal with the final result (Win/Loss/BE), gross PnL, and net PnL (after fees and actual slippage) when the position is closed.
