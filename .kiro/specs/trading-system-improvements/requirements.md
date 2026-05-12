# Requirements Document

## Introduction

This document specifies six targeted improvements to the existing crypto trading system. The system currently operates with a semi-automatic signal pipeline: OHLCV data is ingested via WebSocket, scored across four modules (Order Flow 35 pts, SMC 30 pts, VSA+VolProfile 30 pts, Context 15 pts) plus a Confluence Bonus, filtered through Regime Detection, and surfaced as Signal Cards on the Human Confirm Dashboard.

The six improvements address the following areas:

1. **Critical Bug Fixes** — Four correctness defects in CORS configuration, Order Block detection, Confluence Bonus double-counting, and Alert suppression when Order Flow data is absent.
2. **MTF 4H Filter** — A 4-hour timeframe layer added above the existing 1H context, with three alignment scenarios that modulate position size and score.
3. **Enhanced Circuit Breaker** — Expansion from a single loss trigger to five independent triggers with smart unlock conditions and persistent state in SQL Server.
4. **BTC Correlation Guard** — Real-time monitoring of BTC/USDT 15m candles to cancel or reduce Alt coin signals during BTC spike events.
5. **Dynamic Delta Threshold** — Replacement of the hardcoded 1000 BTC delta threshold with a rolling percentile-75 value computed from 24-hour history.
6. **Daily Bias Filter** — A Daily timeframe macro filter that reduces position size for long signals when the daily trend is bearish.

Improvement 7 (USDT Dominance) is explicitly out of scope for this sprint and SHALL NOT be implemented.

---

## Glossary

- **CORS**: Cross-Origin Resource Sharing; the HTTP mechanism that controls which origins may call the API.
- **Allowed_Origins**: The explicit list of frontend origins permitted to make cross-origin requests to the FastAPI backend.
- **Order_Block (OB)**: A price zone representing institutional supply or demand, identified by the last opposing candle before a strong directional move. Defined in the base system glossary.
- **OB_List**: An ordered collection of valid Order Blocks for a given symbol and timeframe, sorted by recency (most recent first).
- **Fib_Level**: A Fibonacci retracement price level (38.2%, 50%, 61.8%, 78.6%) computed from the most recent swing high and swing low.
- **POC**: Point of Control; the price level with the highest traded volume within a given Volume Profile window.
- **Confluence_Bonus**: The bonus score component awarded when multiple technical layers (OB, Fibonacci, POC, FVG) converge at the same price zone.
- **VSA_Module**: The VSA + Volume Profile scoring module (max 30 pts) that includes No Supply, Effort vs Result, and Volume Profile sub-scores.
- **OF_Score**: The Order Flow Analysis module score (max 35 pts), derived from delta, bid/ask stack, and absorption signals.
- **Alert_Threshold**: The minimum final score (default 75) required for a signal to be classified as ALERT.
- **MTF_Filter**: The Multi-Timeframe Filter component that evaluates 4H, 1H, and 15m timeframes together before producing a signal.
- **4H_Bias**: The directional classification of the 4-hour timeframe as BULLISH, BEARISH, or RANGING, derived from EMA200, swing structure, and ADX(14).
- **EMA200**: Exponential Moving Average with period 200.
- **ADX**: Average Directional Index; a measure of trend strength. ADX > 20 indicates a trending market; ADX < 20 indicates a ranging market.
- **Alignment_Bonus**: A score bonus of +10 pts awarded when 4H, 1H, and 15m timeframes are all directionally aligned.
- **Circuit_Breaker**: The risk protection module that locks the system from generating new ALERT signals when predefined loss or volatility conditions are met.
- **CB_State**: The current state of the Circuit Breaker, stored persistently in the `circuit_breaker_log` SQL Server table.
- **Lock_Period**: The duration for which the Circuit Breaker prevents new ALERT signals after a trigger condition is met.
- **Manual_Override**: A user-initiated action that unlocks the Circuit Breaker before the Lock_Period expires, requiring a written reason stored in the journal.
- **BTC_Spike**: A BTC/USDT 15m candle where `|close - open| / open > 0.02` (a 2% or greater move in a single 15-minute candle).
- **BTC_Dump**: A BTC_Spike where `close < open` (bearish spike).
- **BTC_Pump**: A BTC_Spike where `close > open` (bullish spike).
- **Alt_Alert**: Any ALERT-class signal for a non-BTC asset (e.g., ETH/USDT, SOL/USDT).
- **Relative_Weakness**: A condition where BTC pumps 2%+ in a 15m candle but the Alt asset gains less than 0.5% in the same period.
- **Cooldown_Period**: A 30-minute window after a BTC_Spike during which Alt_Alerts are suppressed or reduced.
- **Delta_Threshold**: The minimum cumulative buy-sell delta required to award the 15-point Order Flow delta bonus. Currently hardcoded at 1000; to be replaced by a dynamic value.
- **Dynamic_Threshold**: The rolling percentile-75 of absolute delta values over the past 24 hours for a given symbol, used as the Delta_Threshold.
- **Daily_Bias**: The directional classification of the Daily timeframe as BULL, BEAR, or NEUTRAL, derived from MA50 and MA200.
- **MA50**: Simple Moving Average with period 50 on the Daily timeframe.
- **MA200**: Simple Moving Average with period 200 on the Daily timeframe.
- **OHLCVService**: The data ingestion service responsible for fetching and storing OHLCV candles for all configured symbols and timeframes.
- **Redis**: The in-memory data store used as the central buffer layer for OHLCV data, delta values, order book snapshots, and spike event timestamps.
- **Signal_Card**: The UI component in the Human Confirm Dashboard that presents all relevant information for a single ALERT signal.

---

## Requirements

### Requirement 1: CORS Origin Restriction

**User Story:** As a system operator, I want the API to accept cross-origin requests only from explicitly configured frontend origins, so that the trading dashboard is not accessible from unauthorized third-party websites.

#### Acceptance Criteria

1. THE FastAPI_Backend SHALL restrict CORS allowed origins to a list of origins defined in the application configuration, replacing any wildcard (`"*"`) value.
2. WHEN a cross-origin request arrives from an origin not present in the Allowed_Origins list, THE FastAPI_Backend SHALL reject the request with an HTTP 403 response.
3. THE Allowed_Origins list SHALL be configurable via the `config.yaml` file under the `exchange.allowed_origins` key without requiring source code changes.
4. IF the `exchange.allowed_origins` key is absent or empty in `config.yaml`, THEN THE FastAPI_Backend SHALL default to `["http://localhost:5173", "http://localhost:3000"]` and log a warning at startup.
5. THE FastAPI_Backend SHALL continue to allow all HTTP methods and headers for requests from permitted origins.

---

### Requirement 2: Order Block List Detection

**User Story:** As a signal analyst, I want the SMC module to return all valid Order Blocks rather than only the first one found, so that the scoring engine can evaluate OB confluence with Fibonacci levels and select the most relevant zone.

#### Acceptance Criteria

1. THE SMC_Module SHALL return an OB_List containing all valid Order Blocks found in the lookback window, ordered from most recent to oldest.
2. WHEN computing the SMC score, THE SMC_Module SHALL evaluate each Order Block in the OB_List and select the one whose midpoint is closest to the current price for the retest check.
3. WHERE a Fib_Level is present, THE SMC_Module SHALL prefer the Order Block whose midpoint falls within 0.5% of any Fib_Level over a closer but non-confluent Order Block.
4. WHEN no valid Order Block is found in the lookback window, THE SMC_Module SHALL return an empty OB_List and award zero points for the Order Block retest criterion.
5. THE OB_List SHALL contain only Order Blocks whose `valid` flag is `True`; invalidated Order Blocks (price closed beyond the zone) SHALL be excluded.
6. THE SMC_Module SHALL preserve backward compatibility by exposing the highest-priority Order Block as a single `order_block` field on the SMCResult for use by the Confluence_Bonus calculator.

---

### Requirement 3: Confluence Bonus POC Double-Count Fix

**User Story:** As a signal analyst, I want the POC proximity bonus to be counted exactly once in the scoring pipeline, so that the final score accurately reflects the strength of each confirmation factor without inflation.

#### Acceptance Criteria

1. THE VSA_Module SHALL NOT award score points for price proximity to the POC; the POC proximity check SHALL be removed from the VSA_Module scoring logic.
2. THE Confluence_Bonus calculator SHALL remain the sole location where POC proximity is evaluated and awarded bonus points.
3. WHEN the entry price is within 0.3% of the POC and an Order Block is present at the same zone, THE Confluence_Bonus calculator SHALL award the POC confluence bonus as defined in the existing bonus table.
4. WHEN the entry price is within 0.3% of the POC but no Order Block is present, THE Confluence_Bonus calculator SHALL award zero bonus points for POC proximity.
5. THE VSA_Module score ceiling SHALL remain at 30 pts after removing the POC sub-score; the No Supply (+10 pts) and Effort vs Result (+10 pts) sub-scores SHALL be retained, and the Value Area Edge sub-score (+6 pts) SHALL be retained.
6. THE System SHALL update all unit tests for the VSA_Module and Confluence_Bonus calculator to reflect the corrected scoring logic.

---

### Requirement 4: Order Flow Score Zero Alert Suppression

**User Story:** As a trader, I want the system to suppress ALERT signals when Order Book data is unavailable, so that I am not misled into acting on signals that are missing the most important confirmation module.

#### Acceptance Criteria

1. WHEN the OF_Score equals zero due to absent or stale Order Book data, THE Signal_Scorer SHALL cap the final score at a maximum of 60 points, regardless of the scores from other modules.
2. THE Signal_Scorer SHALL determine that Order Book data is absent when the `ob:{symbol}:snap` Redis key is missing OR when the Order Book snapshot age exceeds 30 seconds.
3. WHEN the final score is capped at 60 due to absent Order Book data, THE Signal_Scorer SHALL classify the signal as WATCH or IGNORE (never ALERT), since 60 is below the Alert_Threshold of 75.
4. WHEN the final score is capped, THE Signal_Scorer SHALL include a `cap_reason` field set to `"no_order_book_data"` in the signal log entry.
5. THE cap behavior SHALL be configurable: the cap value (default 60) and the Order Book staleness threshold (default 30 seconds) SHALL be adjustable via `config.yaml` without source code changes.

---

### Requirement 5: MTF 4H Filter

**User Story:** As a trader, I want a 4-hour timeframe layer added to the signal pipeline, so that long signals are only taken at full size when the 4H, 1H, and 15m timeframes are all directionally aligned, reducing exposure to counter-trend entries.

#### Acceptance Criteria

1. THE OHLCVService SHALL fetch and store 4H OHLCV candles for all configured symbols in Redis under the key `ohlcv:{symbol}:4h`, with a rolling buffer of at least 250 candles.
2. THE MTF_Filter SHALL classify the 4H_Bias for each symbol as BULLISH, BEARISH, or RANGING using the following rules:
   - BEARISH: `close < EMA200` AND lower highs in the last 20 candles AND `ADX(14) > 20`
   - BULLISH: `close > EMA200` AND higher lows in the last 20 candles AND `ADX(14) > 20`
   - RANGING: `ADX(14) < 20` OR price oscillating around EMA200 (neither BULLISH nor BEARISH conditions met)
3. WHEN the 4H_Bias is BULLISH AND the 1H bias is bullish AND the 15m signal is long (Scenario A — Fully Aligned), THE MTF_Filter SHALL apply a position size multiplier of 1.0 (full size) and award an Alignment_Bonus of +10 pts to the final score.
4. WHEN the 4H_Bias is RANGING AND the 1H bias is bullish AND the 15m signal is long (Scenario B — Partial Conflict), THE MTF_Filter SHALL apply a position size multiplier of 0.5 and deduct 10 pts from the final score before classification.
5. WHEN the 4H_Bias is BEARISH AND the 15m signal is long (Scenario C — Direct Opposition), THE MTF_Filter SHALL block the signal completely and SHALL NOT publish an ALERT regardless of the final score.
6. WHEN a signal is blocked by Scenario C, THE Signal_Scorer SHALL log the signal with classification `"BLOCKED_4H"` and include the 4H_Bias value in the log entry.
7. WHEN a signal is reduced by Scenario B, THE Signal_Card SHALL display a warning label `"4H not confirmed"` alongside the score breakdown.
8. THE MTF_Filter SHALL be applied after all module scores are computed and before the final ALERT classification decision.
9. THE 4H_Bias classification thresholds (EMA period default 200, ADX period default 14, ADX ranging threshold default 20) SHALL be configurable via `config.yaml` without source code changes.

---

### Requirement 6: Enhanced Circuit Breaker

**User Story:** As a risk manager, I want the Circuit Breaker to trigger on five independent loss and volatility conditions, so that the system automatically pauses trading during adverse market conditions and prevents compounding losses.

#### Acceptance Criteria

1. THE Circuit_Breaker SHALL trigger a 12-hour lock when 3 or more consecutive losing trades are recorded within any rolling 24-hour window (Trigger 1 — Consecutive Losses).
2. THE Circuit_Breaker SHALL trigger a 6-hour lock when any single trade results in a loss exceeding 4% of account equity at the time of trade entry (Trigger 2 — Loss Magnitude).
3. THE Circuit_Breaker SHALL trigger a lock until 00:00 UTC of the following day when the cumulative realized loss within the current UTC calendar day exceeds 5% of account equity (Trigger 3 — Daily Loss Cap).
4. THE Circuit_Breaker SHALL trigger a 24-hour lock when account equity declines more than 10% from the highest equity value recorded in the preceding 7 calendar days (Trigger 4 — Peak Drawdown).
5. THE Circuit_Breaker SHALL trigger a 4-hour lock when the ATR(14) on the 1H timeframe for any monitored symbol increases more than 200% above its 7-day rolling average ATR (Trigger 5 — Volatility Spike).
6. WHILE the Circuit_Breaker is locked, THE Signal_Scorer SHALL suppress all ALERT-class signals and SHALL NOT publish to the `alerts:channel` Redis channel.
7. WHEN a Lock_Period expires, THE Circuit_Breaker SHALL evaluate the current market regime before unlocking: if the regime that was active when the lock was triggered is still active (same TRENDING/RANGING/PARABOLIC/CHOPPY state), THE Circuit_Breaker SHALL extend the lock by one additional hour and re-evaluate.
8. WHERE a Manual_Override is provided by the user, THE Circuit_Breaker SHALL unlock immediately and record the override reason, the unlocking timestamp, and the user identifier in the `circuit_breaker_log` table.
9. THE Circuit_Breaker SHALL persist its state (lock status, trigger type, lock start time, lock end time, trigger details) in a SQL Server table named `circuit_breaker_log` so that state survives process restarts.
10. WHEN a Circuit_Breaker trigger fires, THE System SHALL push a notification to the Dashboard indicating the trigger type, the lock duration, and the unlock condition.
11. THE Circuit_Breaker thresholds (consecutive losses count default 3, loss magnitude pct default 4%, daily loss cap pct default 5%, peak drawdown pct default 10%, volatility spike multiplier default 200%) SHALL be configurable via `config.yaml` without source code changes.

---

### Requirement 7: BTC Correlation Guard

**User Story:** As a risk manager, I want the system to automatically cancel or reduce Alt coin signals when BTC makes a sudden large move, so that Alt positions are not entered during periods of high BTC-driven market disruption.

#### Acceptance Criteria

1. THE BTC_Correlation_Guard SHALL monitor the BTC/USDT 15m candle stream and detect a BTC_Spike when `|close - open| / open > 0.02` on any single 15m candle.
2. WHEN a BTC_Dump is detected (BTC_Spike where `close < open`), THE BTC_Correlation_Guard SHALL immediately cancel all pending Alt_Alerts from the `alerts:channel` Redis channel and from the in-memory signal store.
3. WHEN a BTC_Dump is detected, THE BTC_Correlation_Guard SHALL push a notification to the Dashboard with the message `"BTC dump detected — review open Alt SL positions immediately"`.
4. WHEN a BTC_Dump is detected, THE BTC_Correlation_Guard SHALL reset the delta accumulator for all non-BTC symbols by setting `delta:{symbol}:5m` to `"0"` in Redis, since pre-spike delta values no longer reflect current order flow.
5. WHEN a BTC_Dump is detected, THE BTC_Correlation_Guard SHALL enter a Cooldown_Period of 30 minutes during which no new Alt_Alerts SHALL be published.
6. WHEN a BTC_Pump is detected (BTC_Spike where `close > open`), THE BTC_Correlation_Guard SHALL NOT cancel existing Alt_Alerts but SHALL apply a 50% position size reduction to all new Alt long signals generated during the Cooldown_Period.
7. WHEN a BTC_Pump is detected AND an Alt symbol's price gain in the same 15m candle is less than 0.5% (Relative_Weakness), THE BTC_Correlation_Guard SHALL block new Alt long signals for that symbol for the duration of the Cooldown_Period.
8. WHEN the Cooldown_Period expires, THE BTC_Correlation_Guard SHALL restore normal Alt_Alert behavior without requiring manual intervention.
9. THE BTC_Correlation_Guard SHALL store the timestamp of the most recent BTC_Spike in Redis under the key `btc:spike:last` with a TTL equal to the Cooldown_Period duration.
10. THE BTC_Spike detection threshold (default 2%), Cooldown_Period duration (default 30 minutes), and Relative_Weakness threshold (default 0.5%) SHALL be configurable via `config.yaml` without source code changes.

---

### Requirement 8: Dynamic Delta Threshold

**User Story:** As a signal analyst, I want the Order Flow delta threshold to adapt to current market liquidity conditions, so that the delta bonus is awarded based on what constitutes a significant delta for the current trading environment rather than a fixed absolute value.

#### Acceptance Criteria

1. THE Order_Flow_Module SHALL compute the Dynamic_Threshold for each symbol as the 75th percentile of the absolute delta values recorded over the preceding 24 hours.
2. THE Order_Flow_Module SHALL use the Dynamic_Threshold in place of the hardcoded 1000 BTC-equivalent value when evaluating whether `delta > threshold` for the 15-point delta bonus.
3. WHEN fewer than 20 delta samples are available in the 24-hour history for a symbol, THE Order_Flow_Module SHALL fall back to the hardcoded default threshold of 1000 and log a debug message indicating insufficient history.
4. THE Order_Flow_Module SHALL update the Dynamic_Threshold for each symbol every 60 minutes and store the result in Redis under the key `delta_threshold:{symbol}` with a TTL of 90 minutes.
5. WHEN the Dynamic_Threshold is retrieved from Redis and the key is absent (TTL expired or not yet computed), THE Order_Flow_Module SHALL fall back to the hardcoded default threshold of 1000 and trigger an asynchronous recomputation.
6. THE Dynamic_Threshold computation SHALL use the 75th percentile (not the mean) of the absolute delta distribution, because delta distributions are right-skewed and the mean would underweight high-activity periods.
7. THE fallback threshold value (default 1000) and the update interval (default 60 minutes) SHALL be configurable via `config.yaml` without source code changes.

---

### Requirement 9: Daily Bias Filter

**User Story:** As a trader, I want a Daily timeframe macro filter applied to all long signals, so that position sizes are automatically reduced when the daily trend is bearish, protecting against extended downtrends that technical setups on lower timeframes cannot anticipate.

#### Acceptance Criteria

1. THE OHLCVService SHALL fetch and store Daily OHLCV candles for all configured symbols in Redis under the key `ohlcv:{symbol}:1d`, with a rolling buffer of at least 250 candles.
2. THE Daily_Bias_Filter SHALL classify the Daily_Bias for each symbol as BULL, BEAR, or NEUTRAL using the following rules:
   - BEAR: `close < MA200` AND `close < MA50`
   - BULL: `close > MA200` AND `close > MA50`
   - NEUTRAL: all other cases (e.g., `close` between MA50 and MA200)
3. WHEN the Daily_Bias is BEAR, THE Daily_Bias_Filter SHALL apply a 25% reduction to the position size for all long signals, regardless of 4H or 1H alignment.
4. WHEN the Daily_Bias is BULL or NEUTRAL, THE Daily_Bias_Filter SHALL apply no position size adjustment.
5. THE Daily_Bias_Filter SHALL be applied after the MTF_Filter position size multiplier; the two multipliers SHALL be applied multiplicatively (e.g., Scenario B 0.5× combined with BEAR 0.75× yields a final multiplier of 0.375×).
6. THE Signal_Card SHALL display the current Daily_Bias value (BULL / BEAR / NEUTRAL) as a field in the score breakdown section.
7. THE Daily_Bias classification SHALL be recomputed at the close of each Daily candle and cached in Redis under the key `daily_bias:{symbol}`.
8. THE MA periods used for Daily_Bias classification (MA50 period default 50, MA200 period default 200) SHALL be configurable via `config.yaml` without source code changes.

---
