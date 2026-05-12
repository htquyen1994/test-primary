# Phần 10: Glossary & Reference — Crypto Trading System

---

## 10.1 Technical Glossary

### Trading Terms

**OHLCV**
Open, High, Low, Close, Volume — dữ liệu nến cơ bản. Mỗi nến đại diện cho một khoảng thời gian (15m, 1H, 4H, Daily). Open = giá mở cửa, High = giá cao nhất, Low = giá thấp nhất, Close = giá đóng cửa, Volume = khối lượng giao dịch.

**Order Block (OB)**
Vùng giá mà tổ chức (smart money) đặt lệnh lớn, thường là nến bearish ngay trước một impulse bullish lớn (bullish OB) hoặc nến bullish ngay trước impulse bearish (bearish OB). Khi giá retest về OB, tổ chức thường đặt thêm lệnh → xác suất bounce cao.

**Fair Value Gap (FVG)**
Khoảng trống giá trên 3 nến: nến 1 high < nến 3 low (bullish FVG) hoặc nến 1 low > nến 3 high (bearish FVG). Thị trường có xu hướng "lấp" FVG. Entry tại midpoint FVG = entry tốt.

**Change of Character (CHoCH)**
Giá phá vỡ swing high hoặc swing low gần nhất, thể hiện đảo chiều xu hướng (từ downtrend sang uptrend hoặc ngược lại). Bullish CHoCH: close > last swing high. Bearish CHoCH: close < last swing low.

**SMC (Smart Money Concepts)**
Trường phái phân tích kỹ thuật tập trung vào dấu vết của "smart money" (tổ chức, institutional traders). Gồm: Order Blocks, FVG, CHoCH, Liquidity Zones. Nguyên tắc: follow the institutional footprint.

**VSA (Volume Spread Analysis)**
Phân tích mối quan hệ giữa spread (high - low) và volume để xác định hành động của tổ chức. Key concepts: No Supply (volume pullback thấp = không có áp lực bán), Effort vs Result (volume lớn mà giá không di chuyển = absorption).

**POC (Point of Control)**
Mức giá có volume giao dịch cao nhất trong một khoảng thời gian (thường 1 ngày). Đây là "giá công bằng nhất" — tổ chức hay đặt lệnh tại đây. Entry tại POC ±0.3% → +10 pts VSA.

**VAH (Value Area High)**
Biên trên của Value Area — vùng bao gồm 70% tổng volume của ngày. Giá thường bounce tại VAH.

**VAL (Value Area Low)**
Biên dưới của Value Area. Giá thường bounce tại VAL.

**Funding Rate**
Phí định kỳ (mỗi 8h) giữa long và short trong futures perpetual. Rate > +0.05% → quá nhiều long → thị trường overheated. Rate < -0.05% → quá nhiều short → squeeze risk. Rate ≈ 0% → cân bằng → tốt cho trading.

**Perpetual**
Hợp đồng futures không có ngày hết hạn (perpetual contract). Được giữ bằng cơ chế Funding Rate — long trả short (hoặc ngược lại) mỗi 8 tiếng.

**Delta (Cumulative)**
Tổng (buy_volume - sell_volume) qua nhiều giao dịch. Delta dương = net buying pressure. Delta âm = net selling pressure. Dùng để detect institutional accumulation.

**Absorption**
Tổ chức "hấp thụ" lệnh bán: volume lớn nhưng giá không giảm (hoặc giảm rất ít). Dấu hiệu tổ chức đang accumulate lặng lẽ.

**Regime**
Trạng thái thị trường hiện tại, được phân loại dựa trên ADX và ATR:
- TRENDING: ADX > 25 — xu hướng rõ ràng
- RANGING: 20 ≤ ADX ≤ 25 — dao động trong khoảng
- CHOPPY: ADX < 20 — thị trường lộn xộn
- PARABOLIC: ATR > 3× rolling avg ATR — biến động cực lớn

**ATR (Average True Range)**
Chỉ báo đo biến động trung bình trong N nến gần nhất. ATR cao = volatility cao. Dùng để tính SL distance (SL = entry ± ATR × 1.5).

**ADX (Average Directional Index)**
Chỉ báo đo sức mạnh xu hướng (0–100). ADX > 25 = xu hướng mạnh. ADX < 20 = không có xu hướng. Không cho biết hướng, chỉ cho biết độ mạnh.

**RSI (Relative Strength Index)**
Oscillator đo momentum (0–100). RSI > 70 = overbought. RSI < 30 = oversold. Dùng trong Context Filter để identify extreme conditions.

**EMA (Exponential Moving Average)**
Moving average ưu tiên giá gần hơn. EMA200 = "trend filter" — giá > EMA200 = uptrend tổng thể. Dùng trong MTFBiasDetector để classify Daily bias.

**Fibonacci Retracement**
Các mức thoái lui dựa trên tỷ lệ Fibonacci: 23.6%, 38.2%, 50%, 61.8% (Golden Ratio), 78.6%. Entry tại Fib 61.8% của swing → vùng buy/sell quan trọng nhất. Dùng trong Confluence Bonus.

**Confluence Zone**
Vùng giá mà nhiều phương pháp phân tích cùng chỉ ra cùng một điểm vào lệnh. Ví dụ: OB + Fib 61.8% + FVG cùng tại 45000 → confluence mạnh → Bonus 15 pts.

### System Terms

**Signal**
Một tín hiệu giao dịch được generate bởi Strategy. Chứa: asset, direction, entry/SL/TP prices, score, classification. Là đầu vào của toàn bộ pipeline.

**Score**
Điểm số [0–100] đại diện cho chất lượng tín hiệu. Tổng hợp từ 5 modules, áp regime multiplier, normalize. ≥ 75 = ALERT, 55–74 = WATCH, < 55 = IGNORE.

**Alert**
Signal Card với score ≥ 75, được gửi đến React Dashboard để trader xem xét. Có countdown timer (expires sau N candles).

**Watch**
Signal với score 55–74. Không được gửi đến Dashboard — chỉ log vào logs:channel để debug.

**Ignore**
Signal với score < 55. Log only.

**Circuit Breaker**
Cơ chế tự động khóa trading khi vượt ngưỡng thua lỗ. 4 triggers với lock duration khác nhau. Tương tự circuit breaker điện — ngắt khi quá tải.

**Portfolio Heat**
Tổng % rủi ro của tất cả lệnh đang mở so với equity. Heat = Σ(position_risk %). Heat limit = 6% — nếu đạt, không mở thêm lệnh mới.

**Correlated Risk**
Risk của nhóm assets có correlation cao (> 0.8). BTC và ETH thường correlation > 0.8 → group risk = risk_BTC + risk_ETH. Max group risk = 3%.

**MTF Bias (Multi-Timeframe Bias)**
Xu hướng của thị trường ở khung 4H và Daily. Dùng để lọc signals — tránh trade ngược xu hướng lớn.

**BTC Spike Guard**
Cơ chế bảo vệ Alt positions khi BTC có biến động > 2% trong 1 nến 15m. BTC dump → cancel tất cả Alt alerts. BTC pump → size × 0.5.

**Time Invalidation**
Signal hết hạn sau N candles (mặc định 15 candles = 3.75 giờ cho 15m). Nếu trader không action trong thời gian này, signal bị đánh dấu EXPIRED.

**Walk-Forward Analysis**
Phương pháp backtest tránh overfitting: chia dữ liệu thành nhiều windows (in-sample + out-of-sample), optimize trên in-sample, evaluate trên out-of-sample, roll forward. Kết quả out-of-sample mới đáng tin cậy.

### Technical Terms

**Redis pub/sub**
Publish/Subscribe pattern trong Redis. Publisher gửi message vào channel. Tất cả subscribers nhận message ngay lập tức. Dùng: candle_close trigger, alerts:channel, logs:channel.

**asyncio**
Python library cho concurrent I/O với single-threaded event loop. Dùng cho: OHLCVService polling, FastAPI WebSocket handlers, ScoringService coroutines.

**ccxt**
Python/JavaScript library thống nhất API của 100+ crypto exchanges. Dùng: fetch_ohlcv, fetch_order_book, create_order. Hỗ trợ cả REST và WebSocket.

**FastAPI**
Modern Python web framework dựa trên ASGI. Supports async/await natively, auto-generates OpenAPI docs, built-in Pydantic validation.

**WebSocket**
Protocol cho two-way real-time communication giữa browser và server. Dùng trong: /ws/alerts (push Signal Cards), /ws/logs (debug stream), /ws/portfolio (heat updates).

**SQLAlchemy**
Python ORM (Object-Relational Mapper). Cho phép cùng code chạy với SQLite (dev) và SQL Server (production) qua DATABASE_URL.

**Pydantic**
Python library cho data validation với type hints. Dùng trong FastAPI request/response models.

**Ring Buffer**
Data structure có kích thước cố định. Khi đầy, item cũ nhất bị xóa. Dùng trong Redis: LPUSH + LTRIM → giữ 500 nến gần nhất.

**Pearson Correlation**
Hệ số đo mức độ tương quan tuyến tính giữa 2 biến, range [-1.0, 1.0]. 1.0 = hoàn toàn tương quan cùng chiều. Dùng trong CorrelationManager để detect correlated assets.

---

## 10.2 Abbreviations Table

| Abbreviation | Full Form | Context |
|--------------|-----------|---------|
| OHLCV | Open, High, Low, Close, Volume | Market data format |
| OB | Order Block | SMC analysis |
| FVG | Fair Value Gap | SMC analysis |
| CHoCH | Change of Character | SMC analysis |
| SMC | Smart Money Concepts | Trading methodology |
| VSA | Volume Spread Analysis | Volume methodology |
| POC | Point of Control | Volume Profile |
| VAH | Value Area High | Volume Profile |
| VAL | Value Area Low | Volume Profile |
| ATR | Average True Range | Volatility indicator |
| ADX | Average Directional Index | Trend strength indicator |
| RSI | Relative Strength Index | Momentum oscillator |
| EMA | Exponential Moving Average | Trend indicator |
| MTF | Multi-Timeframe | Analysis across multiple timeframes |
| CB | Circuit Breaker | Risk management system |
| WF | Walk-Forward | Backtest methodology |
| PnL | Profit and Loss | Trading result |
| R:R | Risk:Reward ratio | Trade evaluation |
| SL | Stop Loss | Risk management order |
| TP | Take Profit | Target order |
| OF | Order Flow | Scoring module |
| CTX | Context | Context Filter module |
| TF | Timeframe | Candle interval |
| P75 | 75th Percentile | Statistical measure |
| API | Application Programming Interface | Software interface |
| WS | WebSocket | Real-time protocol |
| ORM | Object-Relational Mapper | Database abstraction |
| ASGI | Asynchronous Server Gateway Interface | Python web server spec |
| CORS | Cross-Origin Resource Sharing | Browser security policy |
| SPA | Single-Page Application | Frontend architecture |
| UUID | Universally Unique Identifier | ID format |
| TTL | Time To Live | Redis expiry |
| ACID | Atomicity, Consistency, Isolation, Durability | Database guarantees |

---

## 10.3 File Structure Reference

```
D:\workspace\trade-workspace\workspace\
│
├── backend-workspace\               # Python backend
│   ├── main.py                      # Entry point: khởi động tất cả services (asyncio.gather)
│   ├── config.yaml                  # Single config file — tất cả parameters
│   ├── requirements.txt             # Python dependencies
│   ├── docker-compose.yml           # Redis service definition
│   │
│   ├── db\                          # Database layer
│   │   ├── migrations\
│   │   │   ├── 001_initial_schema.sql  # signal_log, trade_journal, backtest_results tables
│   │   │   ├── 002_config_versions.sql # Config version history table
│   │   │   └── 003_circuit_breaker.sql # circuit_breaker_state table (Phase 9)
│   │   ├── connection.py            # SQLAlchemy engine (DATABASE_URL env var switching)
│   │   └── models.py                # SQLAlchemy ORM models mapping to SQL schema
│   │
│   ├── docs\                        # Strategy specification documents
│   │   ├── order_block.md           # Order Block strategy spec
│   │   ├── fair_value_gap.md        # FVG strategy spec
│   │   ├── pinbar.md                # Pinbar strategy spec
│   │   └── ...                      # Other strategy specs
│   │
│   ├── config\
│   │   └── system.py                # ConfigSystem: load, validate, hot-reload config.yaml
│   │
│   ├── data\                        # Data Pipeline (Layer 1)
│   │   ├── ohlcv_service.py         # OHLCVService: REST polling, ring buffer, candle_close publish
│   │   ├── orderbook_service.py     # OrderBookService: OB snapshot polling (⚠️ not started)
│   │   ├── delta_service.py         # DeltaService: trade tape, cumulative delta (⚠️ not started)
│   │   ├── funding.py               # FundingService: funding rate poll every 8h
│   │   ├── redis_writer.py          # Utility: atomic Redis writes
│   │   ├── redis_reader.py          # Utility: read OHLCV/delta/OB from Redis
│   │   └── gap_filler.py            # Linear interpolation for missing candles
│   │
│   ├── indicators\                  # Pure indicator functions (no side effects)
│   │   ├── base.py                  # BaseIndicator abstract class
│   │   ├── atr.py                   # ATR(14) computation
│   │   ├── adx.py                   # ADX(14) computation
│   │   ├── rsi.py                   # RSI(14) computation
│   │   ├── ema.py                   # EMA(N) computation
│   │   ├── bollinger.py             # Bollinger Bands(20, 2)
│   │   └── candle_measurements.py   # Spread, body, wick measurements
│   │
│   ├── strategies\                  # Strategy Registry + Implementations
│   │   ├── base.py                  # Signal dataclass + BaseStrategy abstract class
│   │   ├── registry.py              # @StrategyRegistry.register decorator pattern
│   │   ├── smc_ob_fvg.py            # SMC: OB + FVG + CHoCH strategy
│   │   ├── pinbar.py                # Pinbar reversal strategy
│   │   ├── engulfing.py             # Engulfing candle strategy
│   │   └── ...                      # Other strategy implementations
│   │
│   ├── engine\                      # AI Engine (Layer 2)
│   │   ├── scoring_service.py       # ScoringService: orchestrator, pub/sub, asyncio+threading
│   │   ├── scorer.py                # SignalScorer: aggregate 5 modules, normalize, classify
│   │   ├── order_flow.py            # OrderFlowAnalysis: delta + bid/ask + absorption (max 35)
│   │   ├── smc.py                   # SMCAnalysis: CHoCH + OB + FVG (max 30)
│   │   ├── vsa.py                   # VSAModule: No Supply + EvR (max 20)
│   │   ├── volume_profile.py        # VolumeProfile: POC/VAH/VAL computation (max 10)
│   │   ├── context.py               # ContextFilter: 1H bias + funding + S/R (max 15)
│   │   ├── confluence.py            # ConfluenceBonus: OB + Fib + FVG (max 15)
│   │   ├── regime_detector.py       # RegimeDetector: ADX + ATR → 4 regimes
│   │   ├── correlation_manager.py   # CorrelationManager: Pearson 24h, portfolio heat
│   │   ├── mtf_bias.py              # MTFBiasDetector: 4H + Daily bias, 3 scenarios (Phase 9)
│   │   └── btc_guard.py             # BTCVolatilityGuard: spike detection + cooldown (Phase 9)
│   │
│   ├── risk\                        # Risk Management
│   │   ├── manager.py               # RiskManager: position sizing, heat check, corr check
│   │   ├── position_sizer.py        # Position sizing calculations (3 modes)
│   │   ├── circuit_breaker.py       # CircuitBreaker: 4 triggers + smart unlock (Phase 9)
│   │   └── validator.py             # Risk limit validation helpers
│   │
│   ├── alert\                       # Alert Building
│   │   ├── builder.py               # AlertBuilder: Signal → SignalCard JSON
│   │   ├── invalidator.py           # Time invalidation checker
│   │   └── sender.py                # Redis publish helper
│   │
│   ├── trade\                       # Trade Execution
│   │   ├── executor.py              # TradeExecutor: ccxt order submission, SL/TP placement
│   │   ├── journal.py               # Journal writer: INSERT trade_journal
│   │   └── position_monitor.py      # Monitor open positions, update portfolio heat
│   │
│   ├── backtest\                    # Backtesting Engine
│   │   ├── engine.py                # BacktestEngine: main simulation loop
│   │   ├── models.py                # TradeResult dataclass
│   │   ├── metrics.py               # Win rate, profit factor, Sharpe, max drawdown
│   │   ├── walk_forward.py          # Walk-Forward Analysis
│   │   ├── benchmark.py             # Benchmark Table generation
│   │   └── ai_feedback.py           # Underperformance cluster detection, optimization suggestions
│   │
│   ├── api\                         # FastAPI Application (Layer 3 backend)
│   │   ├── main.py                  # FastAPI app instance, CORS, startup
│   │   ├── routes\
│   │   │   ├── signals.py           # /api/signals/* endpoints
│   │   │   ├── journal.py           # /api/journal endpoint
│   │   │   ├── analytics.py         # /api/analytics endpoint
│   │   │   ├── config.py            # /api/config/* endpoints
│   │   │   └── trade.py             # Trade execution routes
│   │   ├── schemas.py               # Pydantic request/response models
│   │   └── websockets.py            # /ws/alerts, /ws/logs, /ws/portfolio handlers
│   │
│   └── tests\
│       ├── unit\                    # Unit tests per module
│       ├── integration\             # End-to-end pipeline tests
│       └── properties\              # hypothesis property-based tests (20 properties)
│
└── frontend-workspace\              # React Dashboard (Layer 3 frontend)
    ├── package.json
    ├── vite.config.ts               # Proxy /api → :8000, /ws → :8000
    ├── tsconfig.json
    └── src\
        ├── App.tsx                  # Root component, Router, WebSocket Providers
        ├── providers\
        │   ├── AlertsWebSocketProvider.tsx   # WebSocket /ws/alerts management
        │   └── PortfolioWebSocketProvider.tsx # WebSocket /ws/portfolio management
        ├── store\
        │   ├── alertsStore.ts       # Zustand store: active Signal Cards
        │   └── portfolioStore.ts    # Zustand store: portfolio heat + positions
        ├── components\
        │   ├── SignalCard.tsx        # Signal Card UI component
        │   ├── ScoreBreakdown.tsx    # Per-module score visualization
        │   ├── ChartView.tsx         # TradingView Lightweight Charts + overlays
        │   ├── CountdownTimer.tsx    # Candle countdown timer
        │   ├── ConfirmButton.tsx     # POST /api/signals/{id}/confirm
        │   ├── SkipButton.tsx        # POST /api/signals/{id}/skip
        │   ├── PortfolioHeader.tsx   # Persistent portfolio heat header
        │   ├── JournalTable.tsx      # Trade history table
        │   └── AnalyticsPage.tsx     # Performance metrics
        ├── pages\
        │   ├── SignalsPage.tsx       # Main dashboard: active Signal Cards
        │   ├── JournalPage.tsx       # /journal route
        │   └── AnalyticsPage.tsx     # /analytics route
        ├── hooks\
        │   ├── useAlertWebSocket.ts  # WebSocket hook for alerts
        │   └── usePortfolioWebSocket.ts # WebSocket hook for portfolio
        └── types\
            └── index.ts             # TypeScript type definitions
```

---

## 10.4 Quick Reference: Scoring Formula

```
Step 1: Raw Score
  raw = OrderFlow(0-35) + SMC(0-30) + VSA(0-30) + Context(0-15) + Confluence(0-15)
  Max raw = 125

Step 2: Normalize
  final = min(round(raw × regime_multiplier / 125 × 100), 100)

Step 3: Phase 9 adjustments
  final += mtf_score_adjustment  # +10 (A), -10 (B), N/A (C = blocked earlier)
  if not order_book_available:
      final = min(final, 60)

Step 4: Classify
  ALERT  ≥ 75  → Signal Card → Dashboard
  WATCH  55-74 → Log only
  IGNORE < 55  → Log only
```

## 10.5 Quick Reference: Circuit Breaker Triggers

```
T1: 3 consecutive losses in 24h         → lock 12h
T2: Single loss > 4% equity             → lock 6h
T3: Daily loss > 5% equity              → lock until 00:00 UTC
T4: Drawdown > 10% from 7-day peak      → lock 24h + manual review required

Smart Unlock (after lock expires):
  Regime changed? → auto unlock
  Regime same?    → extend 6h + notify
  T4 always?      → manual review_note ≥ 10 chars required
```

## 10.6 Quick Reference: MTF Scenarios

```
Scenario A (Aligned):   4H + 1H same direction → size × 1.0, score +10
Scenario B (Diverging): 4H ranging/mixed       → size × 0.5, score -10
Scenario C (Opposing):  4H strong opposing (ADX>25) → BLOCK

Daily bias modifier:
  BEAR daily + long signal → additional × 0.75
  BULL daily + long signal → × 1.0 (no reduction)
```
