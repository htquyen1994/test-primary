# Phần 3: Data Flow Diagrams — Crypto Trading System

---

## 3.1 Realtime Signal Flow (End-to-End)

```mermaid
sequenceDiagram
    participant Exchange
    participant OHLCVService
    participant Redis
    participant ScoringService
    participant RegimeDetector
    participant MTFBiasDetector
    participant BTCGuard
    participant CircuitBreaker
    participant SignalScorer
    participant RiskManager
    participant AlertBuilder
    participant FastAPI
    participant ReactDashboard
    participant TradeExecutor

    Note over Exchange,OHLCVService: Layer 1 — Data Input (REST Polling)

    loop Every 60s (15m candles)
        OHLCVService->>Exchange: fetch_ohlcv("BTC/USDT", "15m")
        Exchange-->>OHLCVService: [[ts, o, h, l, c, v], ...]
        OHLCVService->>Redis: LPUSH ohlcv:BTC/USDT:15m + LTRIM 500
        OHLCVService->>Redis: PUBLISH candle_close {symbol, timeframe, ts}
    end

    Note over Redis,ScoringService: Layer 2 — AI Engine (pub/sub trigger)

    Redis->>ScoringService: candle_close event received
    ScoringService->>Redis: LRANGE ohlcv:BTC/USDT:15m 0 499
    ScoringService->>Redis: LRANGE ohlcv:BTC/USDT:1h 0 199
    ScoringService->>Redis: LRANGE ohlcv:BTC/USDT:4h 0 199
    ScoringService->>Redis: LRANGE ohlcv:BTC/USDT:1d 0 249
    ScoringService->>Redis: GET delta:BTC/USDT:5m
    ScoringService->>Redis: GET ob:BTC/USDT:snap
    ScoringService->>Redis: GET funding:BTC/USDT
    ScoringService->>Redis: GET poc:BTC/USDT

    ScoringService->>RegimeDetector: detect(ohlcv_1h, ohlcv_15m)
    RegimeDetector-->>ScoringService: RegimeState(TRENDING, mult=1.0)

    ScoringService->>MTFBiasDetector: detect_4h_bias(ohlcv_4h)
    ScoringService->>MTFBiasDetector: get_mtf_alignment(bias_4h, bias_1h, direction)
    MTFBiasDetector-->>ScoringService: MTFAlignment(scenario=A, size_mult=1.0, score_adj=+10)

    alt BTC spike check (Alt symbols only)
        ScoringService->>BTCGuard: check_btc_spike(ohlcv_btc_15m)
        BTCGuard-->>ScoringService: BTCSpikeState(spike=False)
    end

    Note over ScoringService: Filter Pipeline (FilterRegistry)
    ScoringService->>ScoringService: FilterRegistry.load_active(["mtf_bias","btc_guard","circuit_breaker","daily_bias"])
    ScoringService->>ScoringService: MTFBiasFilter.apply(context) → scenario A/B/C
    alt Scenario C (BLOCK)
        ScoringService->>Redis: PUBLISH logs:channel (blocked)
        ScoringService->>ScoringService: _emit_audit(blocked)
        Note over ScoringService: Return early — no scoring
    else Scenario B (warning)
        Note over ScoringService: combined_size_mult *= 0.5, score_adj = -10
    else Scenario A (aligned)
        Note over ScoringService: combined_size_mult *= 1.0, score_adj = +10
    end

    ScoringService->>ScoringService: BTCGuardFilter.apply(context) → check btc spike
    ScoringService->>ScoringService: CircuitBreakerFilter.apply(context) → is_locked()
    ScoringService->>ScoringService: DailyBiasFilter.apply(context) → BEAR daily × 0.75

    ScoringService->>SignalScorer: score(ScoreInput(of, smc, vsa, ctx, bonus, regime, order_book_available))
    SignalScorer-->>ScoringService: ScoreOutput(raw=87, final=70, data_quality={...})
    Note over ScoringService: OB cap applied INSIDE scorer (not outside)
    Note over ScoringService: Apply sum of filter score_adjustments → final=80

    ScoringService->>ScoringService: _compute_sl_tp(entry, atr, direction) → sl, tp1, tp2, net_rr
    Note over ScoringService: ALERT suppressed if atr==0 OR net_rr < 1.5

    ScoringService->>SQL: write_signal_log(Signal(...)) via api/signal_log_writer.py
    ScoringService->>ScoringService: _emit_audit("signal_snapshot", {...})

    alt classification == ALERT AND atr > 0 AND net_rr >= 1.5
        ScoringService->>Redis: PUBLISH alerts:channel signal_card_json
        Redis->>FastAPI: alert message received
        FastAPI->>ReactDashboard: WebSocket push signal_card
    end

    ScoringService->>Redis: PUBLISH logs:channel full_log_json

    Note over ReactDashboard,TradeExecutor: Layer 3 — Human Confirm Dashboard

    ReactDashboard->>ReactDashboard: Render SignalCard + Countdown Timer
    ReactDashboard->>FastAPI: POST /api/signals/{id}/confirm (User clicks CONFIRM)
    FastAPI->>CircuitBreaker: is_locked() — double-check
    alt Circuit Breaker locked
        FastAPI-->>ReactDashboard: HTTP 423 Locked
    else Not locked
        FastAPI->>TradeExecutor: execute(signal_card)
        TradeExecutor->>Exchange: ccxt.create_limit_order(entry)
        Exchange-->>TradeExecutor: order_id, fill_price
        TradeExecutor->>Exchange: ccxt.create_order(stop_loss)
        TradeExecutor->>Exchange: ccxt.create_order(take_profit_1)
        TradeExecutor->>Exchange: ccxt.create_order(take_profit_2)
        TradeExecutor->>SQL: INSERT trade_journal(...)
        FastAPI-->>ReactDashboard: HTTP 200 {trade_id, fill_price}
    end
```

---

## 3.2 Candle Close Trigger Flow

```mermaid
sequenceDiagram
    participant OHLCVService
    participant Redis
    participant ScoringThread
    participant AsyncioLoop

    OHLCVService->>OHLCVService: Phát hiện timestamp mới trong fetch_ohlcv response
    OHLCVService->>Redis: LPUSH ohlcv:{sym}:{tf} new_candle_json
    OHLCVService->>Redis: LTRIM ohlcv:{sym}:{tf} 0 499
    OHLCVService->>Redis: PUBLISH candle_close {"symbol": "BTC/USDT", "timeframe": "15m", "close": 45230.5}

    Note over Redis,ScoringThread: Threading model: pub/sub subscribe trong daemon thread

    Redis-->>ScoringThread: Message received (blocking LISTEN in thread)
    ScoringThread->>ScoringThread: Parse {"symbol", "timeframe", "close"}
    ScoringThread->>AsyncioLoop: asyncio.run_coroutine_threadsafe(_run_cycle(sym, tf), loop)

    Note over AsyncioLoop: _run_cycle() coroutine

    AsyncioLoop->>AsyncioLoop: [1] Read OHLCV (15m/1h/4h/1d), OB snap, delta, funding từ Redis
    AsyncioLoop->>AsyncioLoop: [1b] ob_age check: stale nếu updated_at > 60s ago
    AsyncioLoop->>AsyncioLoop: [1c] Snapshot delta → delta_history (RPUSH+LTRIM 96), reset delta="0"
    AsyncioLoop->>AsyncioLoop: [2] Compute ATR(14), ADX(14); regime = RegimeDetector.classify()
    AsyncioLoop->>AsyncioLoop: [3] compute_volume_profile(last 96 candles)
    AsyncioLoop->>AsyncioLoop: [3b] 2-Pass SMC: Pass1 detect direction, Pass2 direction-aware OB
    AsyncioLoop->>AsyncioLoop: [3c] compute_vsa_score(ohlcv, vp, atr, delta)
    AsyncioLoop->>AsyncioLoop: [4] Build filter_context dict
    AsyncioLoop->>AsyncioLoop: [4b] FilterRegistry.load_active → run 4 filters sequentially

    alt Any filter BLOCK
        AsyncioLoop->>Redis: PUBLISH logs:channel (blocked)
        AsyncioLoop->>AsyncioLoop: _emit_audit(blocked_snapshot)
        AsyncioLoop->>AsyncioLoop: Return early
    else All filters pass
        AsyncioLoop->>AsyncioLoop: [5] Compute OF, CTX, Bonus scores
        AsyncioLoop->>AsyncioLoop: [5b] SignalScorer.score(ScoreInput) — OB cap inside scorer
        AsyncioLoop->>AsyncioLoop: [5c] Apply sum filter score_adjustments
        AsyncioLoop->>AsyncioLoop: [6] _compute_sl_tp(entry, atr) → sl, tp1, tp2, net_rr
        AsyncioLoop->>SQL: write_signal_log(Signal) — api/signal_log_writer.py
        AsyncioLoop->>AsyncioLoop: _emit_audit("signal_snapshot")

        alt classification == ALERT AND atr > 0 AND net_rr >= 1.5
            AsyncioLoop->>Redis: PUBLISH alerts:channel (ALERT)
        else score 55-74
            AsyncioLoop->>Redis: PUBLISH logs:channel (WATCH)
        else score < 55
                    AsyncioLoop->>Redis: PUBLISH logs:channel (IGNORE)
                end
            end
            
            AsyncioLoop->>SQL: INSERT signal_log
        end
    end
```

---

## 3.3 Circuit Breaker State Machine

```mermaid
stateDiagram-v2
    [*] --> UNLOCKED : System startup

    state UNLOCKED {
        [*] --> Monitoring
        Monitoring --> Monitoring : Normal trade results
    }

    state LOCKED {
        [*] --> WaitingExpiry
        WaitingExpiry --> CheckUnlock : lock_at timestamp passed
    }

    state PENDING_REVIEW {
        [*] --> AwaitingReviewNote
        AwaitingReviewNote --> AwaitingReviewNote : review_note missing or < 10 chars
    }

    UNLOCKED --> LOCKED : Trigger 1\n3 consecutive losses in 24h\n→ lock 12h
    UNLOCKED --> LOCKED : Trigger 2\nSingle loss > 4% equity\n→ lock 6h
    UNLOCKED --> LOCKED : Trigger 3\nDaily loss > 5% equity\n→ lock until 00:00 UTC
    UNLOCKED --> PENDING_REVIEW : Trigger 4\nDrawdown > 10% from 7-day peak\n→ lock 24h + requires review

    LOCKED --> UNLOCKED : Smart Unlock\nRegime changed since trigger\n→ auto unlock
    LOCKED --> LOCKED : Smart Unlock\nRegime unchanged\n→ extend 6h + notify
    LOCKED --> UNLOCKED : Manual Unlock\nUser calls POST /api/circuit-breaker/unlock

    PENDING_REVIEW --> UNLOCKED : Manual Unlock\nWith valid review_note (≥ 10 chars)
    PENDING_REVIEW --> PENDING_REVIEW : Manual Unlock\nreview_note invalid

    note right of LOCKED
        Redis: circuit_breaker:locked = "1"
        SQL: circuit_breaker_state.is_locked = 1
        HTTP 423 on POST /api/signals/{id}/confirm
    end note

    note right of PENDING_REVIEW
        Same as LOCKED state
        Plus: unlock_requires_review = 1 in SQL
    end note
```

**Mô tả transitions:**

| Transition | Guard | Action |
|------------|-------|--------|
| UNLOCKED → LOCKED (T1) | 3 losses trong Redis `circuit_breaker:recent_losses` list | SQL INSERT, Redis SET TTL=12h+60s, PUBLISH cb:events |
| UNLOCKED → LOCKED (T2) | `loss_pct > config.risk.max_single_loss` | SQL INSERT, Redis SET TTL=6h+60s |
| UNLOCKED → LOCKED (T3) | `daily_loss_pct > config.risk.max_daily_loss_pct` | SQL INSERT, Redis SET TTL đến 00:00 UTC |
| UNLOCKED → PENDING_REVIEW (T4) | `drawdown > 0.10` from 7-day peak | SQL INSERT (unlock_requires_review=1), Redis SET TTL=24h+60s |
| LOCKED → UNLOCKED (Smart) | Lock expired + regime changed | SQL UPDATE (unlocked_by='auto_regime_change'), Redis DEL |
| LOCKED → LOCKED (Extend) | Lock expired + regime unchanged | SQL UPDATE (unlock_at += 6h), Redis SETEX TTL=6h+60s |
| LOCKED → UNLOCKED (Manual) | T1/T2/T3: any review_note | SQL UPDATE (unlocked_by='manual_user'), Redis DEL |
| PENDING_REVIEW → UNLOCKED (Manual) | review_note ≥ 10 chars | SQL UPDATE review_note + unlocked_by |

---

## 3.4 MTF Bias Decision Tree

```mermaid
flowchart TD
    A[Signal Generated\nsymbol, direction, timeframe] --> B{Is it BTC/USDT?}
    
    B -->|Yes| D[Detect 4H bias\nEMA200 + higher lows/lower highs + ADX]
    B -->|No, Alt| C[Check BTC spike first\nBTCVolatilityGuard]
    C -->|No spike| D

    D --> E{4H Bias?}
    E -->|BULLISH| F[Detect 1H bias]
    E -->|BEARISH| F
    E -->|RANGING| F

    F --> G{Alignment check}

    G -->|4H BULLISH\n+ 1H BULLISH\n+ Signal LONG| H[Scenario A\nFull alignment]
    G -->|4H BEARISH\n+ 1H BEARISH\n+ Signal SHORT| H
    G -->|4H BULLISH\n+ 1H BEARISH\n+ Signal SHORT| H

    G -->|4H RANGING\n+ any bias\n+ any direction| I[Scenario B\nPartial alignment]

    G -->|4H BEARISH ADX>25\n+ Signal LONG| J[Scenario C\nOpposing trend]
    G -->|4H BULLISH ADX>25\n+ Signal SHORT| J

    H --> K[size × 1.0\nscore +10\nContinue pipeline]
    I --> L[size × 0.5\nscore -10\nLog WARNING\nContinue pipeline]
    J --> M[size × 0.0\nBLOCK signal\nLog BLOCKED\nReturn early]

    K --> N{Daily Bias Check}
    L --> N
    N -->|BEAR daily + LONG signal| O[Additional × 0.75\nsize reduction]
    N -->|BULL daily + LONG signal\nor BEAR daily + SHORT| P[× 1.0 no reduction]
    O --> Q[Apply to RiskManager\nfinal_size = base × mtf_mult × daily_mult × btc_mult]
    P --> Q
```

---

## 3.5 Trade Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant ReactDashboard
    participant FastAPI
    participant CircuitBreaker
    participant TradeExecutor
    participant Exchange
    participant SQL

    User->>ReactDashboard: Click CONFIRM button on Signal Card
    ReactDashboard->>FastAPI: POST /api/signals/{signal_id}/confirm
    Note over FastAPI: Request contains signal_id in URL

    FastAPI->>FastAPI: Lookup signal by ID from active signals store
    alt Signal not found or already expired
        FastAPI-->>ReactDashboard: HTTP 404 Not Found
    else Signal found
        FastAPI->>CircuitBreaker: is_locked() — fast-path check
        CircuitBreaker->>CircuitBreaker: Redis GET circuit_breaker:locked

        alt Circuit Breaker LOCKED
            FastAPI-->>ReactDashboard: HTTP 423 Locked\n{"reason": "circuit_breaker", "unlock_at": "..."}
        else Not locked
            FastAPI->>TradeExecutor: execute_signal(signal_card)

            TradeExecutor->>TradeExecutor: _assert_testnet_safe()\nCheck exchange.testnet flag

            alt testnet = True (default)
                Note over TradeExecutor: Route to testnet/sandbox endpoint
            else testnet = False (explicit)
                Note over TradeExecutor: Route to live trading endpoint
            end

            TradeExecutor->>Exchange: ccxt.create_limit_order(\n  symbol, "buy"/"sell", size, entry_price)

            loop Retry up to 3x with backoff (1s, 2s, 4s)
                Exchange-->>TradeExecutor: order_id, status, fill_price
            end

            TradeExecutor->>Exchange: ccxt.create_order(stop_loss_price, "stop_market")
            Exchange-->>TradeExecutor: sl_order_id

            TradeExecutor->>Exchange: ccxt.create_order(tp1_price, "limit")
            Exchange-->>TradeExecutor: tp1_order_id

            TradeExecutor->>Exchange: ccxt.create_order(tp2_price, "limit")
            Exchange-->>TradeExecutor: tp2_order_id

            TradeExecutor->>SQL: INSERT trade_journal(\n  trade_id, signal_id, entry_price, sl, tp1, tp2,\n  actual_fill_price, slippage, order_ids, is_testnet)

            TradeExecutor-->>FastAPI: TradeResult(trade_id, fill_price, slippage)
            FastAPI->>SQL: UPDATE signal_log SET user_action='CONFIRM'
            FastAPI-->>ReactDashboard: HTTP 200 {"trade_id": "...", "fill_price": 45230.5}
        end
    end
```

---

## 3.6 Backtest Flow

```mermaid
flowchart TD
    A[POST /api/backtest/run\nbody: strategy, asset, timeframe, start_date, end_date] --> B[Load config.yaml\nbacktest section]
    
    B --> C[Load historical OHLCV\nfrom SQL / CSV\nstart_date → end_date]
    C --> D[Load historical Funding Rates\nfrom SQL / CSV]
    
    D --> E{Walk-Forward enabled?}
    
    E -->|Yes| F[Partition data\nIn-sample / Out-of-sample windows\nin_sample_days: 90\nout_sample_days: 30\nstep_days: 30]
    E -->|No| G[Single run\nfull date range]
    
    F --> H[For each WF window]
    G --> H
    
    H --> I[For each candle T\nin ascending order]
    
    I --> J[Compute indicators\nATR/RSI/ADX/EMA/BB\non ohlcv index 0..T only]
    
    J --> K[Regime Detector\nADX + ATR on closed candles]
    
    K --> L[Strategy Registry\ngenerate_signals ohlcv index 0..T\nStrict no look-ahead bias]
    
    L --> M{Signal generated?}
    
    M -->|No| N[Next candle T+1]
    M -->|Yes| O[Signal Scorer\ncompute score]
    
    O --> P{Score >= 75?}
    
    P -->|No: WATCH/IGNORE| Q[Log signal\nNext candle T+1]
    P -->|Yes: ALERT| R[Risk Manager\nCheck portfolio heat\nCalculate position size]
    
    R --> S[Simulate fill\nentry_price = ohlcv[T].close\nactual_entry = entry × 1 + slippage_pct]
    
    S --> T[Apply funding rate payments\nDuring hold period]
    
    T --> U{Check SL/TP within candle\nIntra-candle fill check}
    
    U -->|SL hit| V[Record TradeResult\nresult = loss\nexit_price = stop_loss]
    U -->|TP1 hit| W[Record TradeResult\nresult = win\nexit_price = tp1_price]
    U -->|TP2 hit| X[Record TradeResult\nresult = win\nexit_price = tp2_price]
    U -->|Neither| Y[Hold to next candle\nUpdate position monitor]
    
    V --> N
    W --> N
    X --> N
    Y --> N
    
    N --> Z{Last candle?}
    Z -->|No| I
    Z -->|Yes| AA[Compute Metrics]
    
    AA --> AB[Win Rate = wins / total\nProfit Factor = gross_win / gross_loss\nMax Drawdown = max peak-to-trough\nSharpe Ratio = mean returns / std × sqrt365\nRecovery Factor = net_pnl / max_drawdown]
    
    AB --> AC{Walk-Forward?}
    AC -->|Yes, more windows| H
    AC -->|No or last window| AD[Write backtest_results to SQL\nGenerate Benchmark_Table]
    
    AD --> AE[AI Feedback\nIdentify Underperformance Clusters\nWrite optimization suggestions to /logs/]
    
    AE --> AF[Return results\nGET /api/backtest/results]
```

---

## 3.7 System Startup Sequence

```mermaid
sequenceDiagram
    participant main.py
    participant Redis
    participant SQL
    participant ConfigSystem
    participant OHLCVService
    participant ScoringService
    participant FastAPI

    main.py->>Redis: PING (health check)
    alt Redis not running
        main.py->>main.py: Exit with error "Redis required"
    end
    Redis-->>main.py: PONG

    main.py->>SQL: Connect (DATABASE_URL env var)
    SQL-->>main.py: Connection established
    main.py->>SQL: Run pending migrations (003_circuit_breaker.sql etc.)
    SQL-->>main.py: Migrations complete

    main.py->>ConfigSystem: load_and_validate("config.yaml")
    ConfigSystem->>ConfigSystem: Validate all required params\nRaise ConfigValidationError if invalid
    ConfigSystem-->>main.py: Config object

    main.py->>OHLCVService: init(config, redis, exchange)
    main.py->>OHLCVService: seed_historical("BTC/USDT", "4h", limit=200)
    OHLCVService->>Exchange: fetch_ohlcv("BTC/USDT", "4h", limit=200)
    Exchange-->>OHLCVService: 200 candles
    OHLCVService->>Redis: LPUSH ohlcv:BTC/USDT:4h × 200

    main.py->>OHLCVService: seed_historical("BTC/USDT", "1d", limit=250)
    OHLCVService->>Exchange: fetch_ohlcv("BTC/USDT", "1d", limit=250)
    Exchange-->>OHLCVService: 250 candles
    OHLCVService->>Redis: LPUSH ohlcv:BTC/USDT:1d × 250

    Note over OHLCVService: Seed all configured symbols (15m, 1h, 4h, 1d)

    main.py->>ScoringService: init(redis, db, config)
    main.py->>ScoringService: start() — subscribe candle_close in background thread

    main.py->>OHLCVService: start() — asyncio polling loop

    main.py->>FastAPI: uvicorn.run(app, host="0.0.0.0", port=8000)
    FastAPI-->>main.py: Server started

    Note over main.py: System fully operational\nAll services running concurrently via asyncio.gather()
```
