# Phần 8: Deployment & Operations Guide — Crypto Trading System

---

## 8.1 System Requirements

### Hardware Requirements

| Component | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| RAM | 4 GB | 8 GB | Redis + Python processes + SQL |
| CPU | 2 cores | 4 cores | asyncio scoring không cần nhiều cores |
| Disk | 10 GB | 50 GB | SQLite/SQL Server + logs |
| Network | 10 Mbps | 100 Mbps | REST polling đến exchange |

### Software Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| Docker | 20+ | Redis container |
| Redis | 7.x | Central buffer (via Docker) |
| SQLite | 3.x (bundled) | Local development database |
| SQL Server | 2019+ | Production database |

### Python Packages (Key)

```
fastapi>=0.104
uvicorn>=0.24
ccxt>=4.0
redis>=5.0
aioredis>=2.0
sqlalchemy>=2.0
pandas>=2.0
numpy>=1.24
pydantic>=2.0
asyncio (stdlib)
threading (stdlib)
```

### External Services

| Service | Required | Setup |
|---------|----------|-------|
| Redis | **Required** | `docker run -d -p 6379:6379 redis:7` |
| Crypto Exchange API | Optional (public endpoints cho OHLCV, private cho trading) | Config `exchange.name` trong config.yaml |
| SQL Server | Production only | `DATABASE_URL=mssql+pyodbc://...` |

---

## 8.2 Startup Sequence

### Thứ tự khởi động

```mermaid
sequenceDiagram
    participant Operator
    participant Docker
    participant main.py
    participant Redis
    participant SQL
    participant ConfigSystem
    participant OHLCVService
    participant ScoringService
    participant FastAPI
    participant Frontend

    Operator->>Docker: docker-compose up -d redis
    Docker-->>Operator: Redis container started on :6379

    Operator->>main.py: python main.py
    main.py->>Redis: PING health check
    Redis-->>main.py: PONG ✓

    main.py->>SQL: SQLAlchemy connect (DATABASE_URL)
    SQL-->>main.py: Connection OK ✓
    main.py->>SQL: Run migrations (001, 002, 003)
    SQL-->>main.py: Migrations complete ✓

    main.py->>ConfigSystem: load("config.yaml")
    ConfigSystem->>ConfigSystem: Validate all params
    ConfigSystem-->>main.py: Config object ✓

    Note over main.py,OHLCVService: Seed historical data (startup only)
    main.py->>OHLCVService: seed("BTC/USDT", "4h", 200)
    OHLCVService-->>Redis: LPUSH ohlcv:BTC/USDT:4h × 200
    main.py->>OHLCVService: seed("BTC/USDT", "1d", 250)
    OHLCVService-->>Redis: LPUSH ohlcv:BTC/USDT:1d × 250
    Note over OHLCVService: Seed tất cả configured symbols

    main.py->>ScoringService: start() — background thread subscribes candle_close
    main.py->>OHLCVService: start() — asyncio polling loop
    main.py->>FastAPI: uvicorn.run(:8000)
    FastAPI-->>Operator: Backend ready ✓

    Operator->>Frontend: npm run dev (or npm run build && serve)
    Frontend-->>Operator: Frontend ready on :5173 ✓
```

### Startup Commands

```bash
# 1. Khởi động Redis
docker run -d -p 6379:6379 --name trading-redis redis:7

# 2. Khởi động Backend
cd workspace/backend-workspace
pip install -r requirements.txt
python main.py

# 3. Khởi động Frontend (development)
cd workspace/frontend-workspace
npm install
npm run dev

# 4. Kiểm tra health
curl http://localhost:8000/api/config
```

---

## 8.3 Configuration Reference

Bảng đầy đủ tất cả `config.yaml` parameters:

| Parameter | Path | Type | Default | Valid Range | Description | Affects |
|-----------|------|------|---------|-------------|-------------|---------|
| Account balance | `account.balance` | float | `10000.0` | > 0 | Account equity USD | RiskManager |
| Account currency | `account.currency` | str | `"USDT"` | — | Base currency | Display |
| Position mode | `position.mode` | str | `"risk_pct"` | fixed_usd\|risk_pct\|kelly | Sizing mode | RiskManager |
| Fixed USD | `position.fixed_usd` | float | `100.0` | > 0 | USD per trade (mode=fixed_usd) | RiskManager |
| Risk percent | `position.risk_pct` | float | `0.02` | [0.001, 0.1] | Risk % per trade | RiskManager |
| Max concurrent | `position.max_concurrent` | int | `3` | [1, 10] | Max open positions | RiskManager |
| Leverage | `position.leverage` | int | `5` | [1, 125] | Default leverage | TradeExecutor |
| Regime enabled | `regime.enabled` | bool | `true` | — | Enable regime filter | ScoringService |
| ADX trending | `regime.adx_trending_threshold` | int | `25` | [15, 40] | ADX > N = TRENDING | RegimeDetector |
| ADX choppy | `regime.adx_choppy_threshold` | int | `20` | [10, 30] | ADX < N = CHOPPY | RegimeDetector |
| ATR parabolic mult | `regime.atr_parabolic_multiplier` | float | `3.0` | [2.0, 5.0] | ATR > N×avg = PARABOLIC | RegimeDetector |
| Parabolic score mult | `regime.parabolic_score_multiplier` | float | `0.6` | [0.3, 0.8] | Score multiplier PARABOLIC | SignalScorer |
| Ranging score mult | `regime.ranging_score_multiplier` | float | `0.85` | [0.5, 1.0] | Score multiplier RANGING/CHOPPY | SignalScorer |
| Trending score mult | `regime.trending_score_multiplier` | float | `1.0` | [0.8, 1.2] | Score multiplier TRENDING | SignalScorer |
| Max daily loss | `risk.max_daily_loss_pct` | float | `0.05` | [0.01, 0.20] | CB T3 trigger | CircuitBreaker |
| Max drawdown | `risk.max_drawdown_pct` | float | `0.15` | [0.05, 0.30] | Reference (not CB) | Display |
| Correlation threshold | `risk.correlation_threshold` | float | `0.8` | [0.5, 0.99] | Pearson corr threshold | CorrelationManager |
| Max corr risk | `risk.max_correlated_risk_pct` | float | `0.03` | [0.01, 0.10] | Max group risk % | CorrelationManager |
| Portfolio heat limit | `risk.portfolio_heat_limit_pct` | float | `0.06` | [0.02, 0.20] | Max total risk % | RiskManager |
| ATR SL multiplier | `risk.atr_sl_multiplier` | float | `1.5` | [1.0, 3.0] | SL = entry ± ATR×N | Strategies |
| Active strategies | `strategy.active` | list[str] | `["smc_ob_fvg"]` | registered names | Active strategies | StrategyRegistry |
| Alert threshold | `strategy.score_threshold.alert` | int | `75` | [60, 95] | Min score for ALERT | SignalScorer |
| Watch threshold | `strategy.score_threshold.watch` | int | `55` | [40, 74] | Min score for WATCH | SignalScorer |
| Trigger timeframe | `strategy.timeframes.trigger` | str | `"15m"` | 15m\|30m\|1h | Candle close trigger | OHLCVService |
| Context timeframe | `strategy.timeframes.context` | str | `"1h"` | 1h\|4h | HTF context | ContextFilter |
| Time invalidation | `strategy.time_invalidation_candles` | int | `15` | [5, 50] | Candles before expire | AlertBuilder |
| Exchange name | `exchange.name` | str | `"binance"` | ccxt IDs | Exchange | ccxt |
| Market type | `exchange.market_type` | str | `"futures"` | futures\|spot | Market | TradeExecutor |
| Fee rate | `exchange.fee_rate` | float | `0.001` | [0.0001, 0.01] | Taker fee | Backtest, net R:R |
| Slippage | `exchange.slippage_pct` | float | `0.0002` | [0.0001, 0.005] | Estimated slippage | Backtest |
| Testnet | `exchange.testnet` | bool | `true` | — | **MUST be false cho live** | TradeExecutor |
| Backtest start | `backtest.start_date` | str | `"2024-01-01"` | ISO date | Backtest period | BacktestEngine |
| Backtest end | `backtest.end_date` | str | `"2024-12-31"` | ISO date | Backtest period | BacktestEngine |
| Walk-forward | `backtest.walk_forward.enabled` | bool | `true` | — | Enable WF | BacktestEngine |
| In-sample days | `backtest.walk_forward.in_sample_days` | int | `90` | [30, 365] | WF in-sample window | BacktestEngine |
| Out-sample days | `backtest.walk_forward.out_sample_days` | int | `30` | [10, 90] | WF out-sample window | BacktestEngine |
| Step days | `backtest.walk_forward.step_days` | int | `30` | [7, 90] | WF step size | BacktestEngine |
| Min trades | `backtest.min_trades_threshold` | int | `30` | [10, 100] | Statistical significance | BacktestEngine |
| Overfit threshold | `backtest.overfit_degradation_threshold` | float | `0.20` | [0.05, 0.50] | Max in/out degradation | BacktestEngine |
| Log level | `logging.level` | str | `"INFO"` | DEBUG\|INFO\|WARNING\|ERROR | Log verbosity | All modules |
| Save all signals | `logging.save_all_signals` | bool | `true` | — | Ghi tất cả vào SQL | ScoringService |

---

## 8.4 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Production only | `sqlite:///./trading.db` | SQLAlchemy connection string. Local: `sqlite:///./trading.db`. Production: `mssql+pyodbc://admin:pwd@localhost:1433/trading?driver=ODBC+Driver+18+for+SQL+Server` |
| `REDIS_URL` | Optional | `redis://localhost:6379` | Redis connection URL. Override nếu Redis chạy trên host khác |
| `ALLOWED_ORIGINS` | Optional | `http://localhost:5173,http://localhost:3000` | Comma-separated CORS origins cho FastAPI |
| `EXCHANGE_API_KEY` | Live trading | — | Exchange API key — không lưu trong config.yaml |
| `EXCHANGE_API_SECRET` | Live trading | — | Exchange API secret |
| `CONFIG_ENCRYPTION_KEY` | Production | `dev_key_change_in_production_32b!` | **PHẢI đổi trong production.** AES-256 key để encrypt API credentials trong SQL DB (Group B ExchangeSettings). Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CONFIG_PATH` | Optional | `config.yaml` | Đường dẫn đến config.yaml |
| `LOG_LEVEL` | Optional | `INFO` | Override log level |

**Security note:** API key/secret KHÔNG lưu trong config.yaml. `CONFIG_ENCRYPTION_KEY` mặc định là dev key — **BẮT BUỘC đổi trước khi deploy production**.

### DB-stored Config Groups (ConfigService)

Ngoài `config.yaml`, hệ thống còn lưu 2 nhóm config trong SQL:

**Group A — TradingParams** (versioned, lịch sử đầy đủ)
Quản lý qua `PUT /api/config/trading`. Bao gồm: `atr_sl_multiplier`, `tp1_rr_ratio`, `tp2_rr_ratio`, `min_net_rr`, score thresholds, regime thresholds. **Đây là source of truth cho SL/TP params** — ScoringService đọc từ DB trước, fallback về config.yaml.

**Group B — ExchangeSettings** (không versioned, ghi đè)
Quản lý qua `PUT /api/config/exchange`. Bao gồm: exchange name, API key/secret (AES-256 encrypted), fee rate, leverage, assets list. API keys được mask khi đọc qua `GET /api/config/exchange`.

**Priority chain cho SL/TP params:**
```
DB TradingParams (Group A)
    ↓ nếu DB unavailable
config.yaml (risk.atr_sl_multiplier, risk.tp1_rr, ...)
    ↓ nếu ConfigSystem fail
Module constants: SL_ATR_MULT=1.5, TP1_RR=2.0, TP2_RR=3.0, MIN_NET_RR=1.5
```

---

## 8.5 Monitoring & Health Checks

### Các Metrics Quan Trọng

| Metric | Source | Ngưỡng cảnh báo | Ý nghĩa |
|--------|--------|-----------------|---------|
| Candle close latency | ScoringService logs | > 5s | OHLCVService có thể bị treo |
| Scoring pipeline time | `logs:channel` | > 2000ms | Scoring quá chậm |
| Redis memory usage | `redis-cli INFO memory` | > 80% maxmemory | Nguy cơ eviction |
| Signal ALERT rate | `signal_log` | 0 trong 24h | System có thể không score đúng |
| Circuit Breaker state | `GET /api/circuit-breaker/status` | is_locked=true | Trading đang bị khóa |
| Portfolio heat | `GET /api/portfolio` | > 80% of limit | Gần đầy positions |

### Log Levels và Ý nghĩa

| Level | Khi nào xuất hiện | Action |
|-------|------------------|--------|
| `DEBUG` | Mỗi indicator computation | Bật khi debug |
| `INFO` | Signal generated, score, CB events | Normal operation |
| `WARNING` | MTF Scenario B, data quality cap, BTC spike cooldown | Cần chú ý |
| `ERROR` | Exchange API fail, Redis disconnection, SQL error | Cần điều tra |
| `CRITICAL` | Startup failure, config validation error | System không thể chạy |

### Health Check Endpoints

```bash
# Backend health
curl http://localhost:8000/api/config

# Circuit Breaker status
curl http://localhost:8000/api/circuit-breaker/status

# Redis health
redis-cli -h localhost ping

# Check recent signals (ít nhất có 1 signal trong 2h qua)
curl "http://localhost:8000/api/signals"
```

### Phát Hiện Khi System Không Hoạt Động Đúng

| Triệu chứng | Nguyên nhân có thể | Kiểm tra |
|-------------|-------------------|---------|
| Không có signal nào trong 24h (dù thị trường active) | OHLCVService không poll, hoặc candle_close không publish | Check Redis pub/sub; check OHLCVService logs |
| Score luôn = 0 | DeltaService + OrderBookService chưa start | Kiểm tra OF score trong logs:channel |
| Score >= 75 nhưng không có ALERT | Circuit Breaker locked | `GET /api/circuit-breaker/status` |
| Frontend không nhận được signals | FastAPI WS handler bị disconnect | Reload React app, check WS connection |
| Trade Executor fail | Exchange API error hoặc testnet=true | Check trade_journal error logs |
| Redis memory đầy | OHLCV ring buffer quá lớn hoặc TTL không set | `redis-cli INFO memory`, `redis-cli DBSIZE` |

### Khởi Động Lại Services

```bash
# Restart backend (giữ Redis data)
Ctrl+C → python main.py

# Flush Redis và restart hoàn toàn (mất data buffer)
redis-cli FLUSHDB
python main.py

# Restart chỉ Frontend
Ctrl+C → npm run dev
```

---

## 8.6 Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    restart: unless-stopped

volumes:
  redis_data:
```

```bash
# Khởi động Redis với persistence
docker-compose up -d redis

# Xem Redis logs
docker-compose logs -f redis

# Dừng Redis
docker-compose down
```

---

## 8.7 Production Checklist

Trước khi chuyển sang live trading:

- [ ] `exchange.testnet: false` đã được đặt tường minh trong config.yaml
- [ ] `EXCHANGE_API_KEY` và `EXCHANGE_API_SECRET` đã được set trong env
- [ ] **`CONFIG_ENCRYPTION_KEY` đã được đổi** (không dùng dev default)
- [ ] `DATABASE_URL` trỏ đến SQL Server (không phải SQLite)
- [ ] `ALLOWED_ORIGINS` chỉ include production domains
- [ ] Redis maxmemory được set phù hợp (≥ 512MB)
- [ ] SQL Server migrations đã chạy (001, 002, 003_circuit_breaker.sql)
- [ ] DB TradingParams đã được setup qua `PUT /api/config/trading`
- [ ] DB ExchangeSettings đã được setup qua `PUT /api/config/exchange`
- [ ] Circuit Breaker thresholds đã được review (max_daily_loss_pct, drawdown)
- [ ] Đã chạy backtest và xác nhận strategy hoạt động
- [ ] OrderBookService và DeltaService đã được start (để có đủ data)
- [ ] AuditClient enabled (mock-exchange-workspace consuming `audit:pending_snapshots`)
- [ ] Monitoring đã được setup
