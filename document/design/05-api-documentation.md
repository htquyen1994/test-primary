# Phần 5: API Documentation — Crypto Trading System

---

## 5.1 API Overview

### Base URL
```
http://localhost:8000
```

### Authentication
Hiện tại không có authentication (internal tool). Các request từ React frontend được CORS-whitelist.

### CORS
```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
# Comma-separated list — không dùng wildcard "*"
```

### Common Response Format

**Success:**
```json
{
  "data": { ... },
  "timestamp": "2024-01-15T09:15:00Z"
}
```

**Error:**
```json
{
  "detail": "Error message here",
  "code": "ERROR_CODE"
}
```

### HTTP Error Codes

| Code | Ý nghĩa | Khi nào xảy ra |
|------|---------|----------------|
| 200 | Success | Request thành công |
| 400 | Bad Request | Request body/params không hợp lệ |
| 404 | Not Found | Signal ID, trade ID không tồn tại |
| 422 | Unprocessable Entity | Validation error (FastAPI/Pydantic) |
| 423 | Locked | Circuit Breaker đang active |
| 500 | Internal Server Error | Unexpected server error |

### Rate Limiting
Không có rate limiting hiện tại.

---

## 5.2 WebSocket Endpoints

### WS /ws/alerts

**Mục đích:** Stream Signal Cards real-time khi AI Engine phát hiện tín hiệu score ≥ 75.

**Message Format:**
```json
{
  "signal_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset": "BTC/USDT",
  "timeframe": "15m",
  "direction": "long",
  "entry_price": 45230.5,
  "stop_loss": 44800.0,
  "take_profit_1": 46000.0,
  "take_profit_2": 47500.0,
  "gross_rr": 1.71,
  "net_rr": 1.68,
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
  "expires_at_candle": 12465,
  "created_at": "2024-01-15T09:15:00Z",
  "mtf_scenario": "A",
  "mtf_warning": null,
  "bias_4h": "BULLISH",
  "daily_bias": "BULL",
  "size_multiplier": 1.0,
  "data_quality": "full",
  "ob_warning": null
}
```

**Trigger:** ScoringService publish `alerts:channel` khi signal score ≥ 75 và risk checks pass.

**Phase 9 fields:**
- `mtf_scenario`: "A" | "B" — Scenario C bị block trước, không bao giờ xuất hiện đây
- `mtf_warning`: null hoặc warning message khi Scenario B
- `bias_4h`: "BULLISH" | "BEARISH" | "RANGING"
- `daily_bias`: "BULL" | "BEAR" | "NEUTRAL"
- `size_multiplier`: Combined size multiplier (MTF × Daily × BTC)
- `data_quality`: "full" | "limited" (limited khi OB unavailable)
- `ob_warning`: null hoặc warning message khi score bị cap

---

### WS /ws/logs

**Mục đích:** Stream tất cả scoring events (ALERT + WATCH + IGNORE) với đầy đủ debug breakdown.

**Message Format:**
```json
{
  "signal_id": "uuid",
  "timestamp": "2024-01-15T09:15:00Z",
  "asset": "BTC/USDT",
  "timeframe": "15m",
  "direction": "long",
  "final_score": 45,
  "classification": "IGNORE",
  "score_breakdown": {
    "order_flow": 0.0,
    "smc": 20.0,
    "vsa": 10.0,
    "context": 8.0,
    "bonus": 5.5
  },
  "regime": "CHOPPY",
  "regime_multiplier": 0.85,
  "mtf_scenario": "B",
  "mtf_score_adjustment": -10,
  "btc_spike_active": false,
  "circuit_breaker_locked": false,
  "rejection_reason": null,
  "portfolio_heat": 0.04,
  "risk_allowed": true
}
```

**Trigger:** Mỗi candle close được score (không phụ thuộc vào kết quả).

---

### WS /ws/portfolio

**Mục đích:** Stream Portfolio Heat và correlated group risk cập nhật real-time.

**Message Format:**
```json
{
  "total_heat": 0.04,
  "heat_limit": 0.06,
  "heat_percentage": 66.7,
  "positions": [
    {
      "asset": "BTC/USDT",
      "direction": "long",
      "risk_pct": 0.02,
      "entry_price": 45230.5,
      "current_price": 45500.0,
      "unrealized_pnl": 29.7
    }
  ],
  "correlated_groups": [
    {
      "assets": ["BTC/USDT", "ETH/USDT"],
      "combined_risk_pct": 0.04,
      "correlation": 0.87
    }
  ],
  "timestamp": "2024-01-15T09:16:00Z"
}
```

**Trigger:** Cập nhật mỗi 1 giây từ ScoringService.

---

## 5.3 REST Endpoints

### GET /api/signals

**Mục đích:** Lấy danh sách active ALERT signals hiện tại (chưa expire, chưa confirm/skip).

**Request:**
- Headers: không cần
- Query params: không có

**Response 200:**
```json
{
  "signals": [
    {
      "signal_id": "550e8400-e29b-41d4-a716-446655440000",
      "asset": "BTC/USDT",
      "direction": "long",
      "entry_price": 45230.5,
      "stop_loss": 44800.0,
      "take_profit_1": 46000.0,
      "take_profit_2": 47500.0,
      "final_score": 80,
      "classification": "ALERT",
      "expires_at_candle": 12465,
      "candles_remaining": 12,
      "created_at": "2024-01-15T09:15:00Z"
    }
  ],
  "count": 1
}
```

**Side Effects:** Không có.

---

### POST /api/signals/{signal_id}/confirm

**Mục đích:** Trader xác nhận Signal → TradeExecutor đặt lệnh.

**Request:**
- Path params: `signal_id` (UUID)
- Body: không cần

**Response 200:**
```json
{
  "trade_id": "660e8400-e29b-41d4-a716-446655440000",
  "signal_id": "550e8400-e29b-41d4-a716-446655440000",
  "fill_price": 45232.1,
  "slippage": 1.6,
  "sl_order_id": "12345678901",
  "tp1_order_id": "12345678902",
  "tp2_order_id": "12345678903",
  "position_size_usd": 100.0,
  "is_testnet": false
}
```

**Response 423 Locked (Circuit Breaker):**
```json
{
  "detail": "Trading locked by Circuit Breaker",
  "code": "CIRCUIT_BREAKER_LOCKED",
  "trigger_type": "CONSECUTIVE_LOSSES",
  "unlock_at": "2024-01-15T21:00:00Z",
  "requires_review": false
}
```

**Response 404:**
```json
{
  "detail": "Signal not found or already expired",
  "code": "SIGNAL_NOT_FOUND"
}
```

**Side Effects:**
- INSERT `trade_journal`
- UPDATE `signal_log.user_action = 'CONFIRM'`
- Exchange orders created (entry + SL + TP1 + TP2)

---

### POST /api/signals/{signal_id}/skip

**Mục đích:** Trader bỏ qua signal.

**Request:**
- Path params: `signal_id` (UUID)
- Body (optional): `{"reason": "Too risky"}`

**Response 200:**
```json
{
  "signal_id": "550e8400-...",
  "action": "skipped",
  "reason": "Too risky"
}
```

**Side Effects:**
- UPDATE `signal_log.user_action = 'SKIP'`
- UPDATE `signal_log.skip_reason = reason`

---

### PATCH /api/signals/{signal_id}/expire

**Mục đích:** Đánh dấu signal đã expired (timeout).

**Request:**
- Path params: `signal_id` (UUID)

**Response 200:**
```json
{
  "signal_id": "550e8400-...",
  "action": "expired",
  "expiry_price": 45800.0
}
```

**Side Effects:**
- UPDATE `signal_log.user_action = 'EXPIRED'`
- UPDATE `signal_log.expiry_price`

---

### GET /api/journal

**Mục đích:** Lấy lịch sử giao dịch từ trade_journal (paginated).

**Request:**
- Query params:
  - `asset` (optional): Filter by symbol
  - `strategy` (optional): Filter by strategy
  - `start_date` (optional): ISO date, e.g., `"2024-01-01"`
  - `end_date` (optional): ISO date
  - `page` (default: 1): Page number
  - `page_size` (default: 20): Items per page

**Response 200:**
```json
{
  "trades": [
    {
      "trade_id": "660e8400-...",
      "asset": "BTC/USDT",
      "direction": "long",
      "entry_timestamp": "2024-01-15T09:16:00Z",
      "exit_timestamp": "2024-01-15T11:30:00Z",
      "actual_entry_price": 45232.1,
      "actual_exit_price": 46001.5,
      "net_pnl": 76.76,
      "result": "win",
      "signal_score": 80,
      "is_testnet": false
    }
  ],
  "total": 48,
  "page": 1,
  "page_size": 20
}
```

---

### GET /api/analytics

**Mục đích:** Tổng hợp performance metrics từ trade_journal.

**Response 200:**
```json
{
  "overall": {
    "total_trades": 48,
    "win_rate": 0.625,
    "profit_factor": 2.15,
    "max_drawdown": 0.085,
    "sharpe_ratio": 1.82,
    "net_pnl_usd": 1245.5,
    "avg_net_pnl": 25.94,
    "avg_win": 85.2,
    "avg_loss": -42.1
  },
  "by_strategy": [
    {
      "strategy_name": "smc_ob_fvg",
      "total_trades": 30,
      "win_rate": 0.667,
      "profit_factor": 2.5,
      "net_pnl_usd": 850.0
    }
  ],
  "by_asset": [
    {
      "asset": "BTC/USDT",
      "total_trades": 25,
      "win_rate": 0.68,
      "net_pnl_usd": 750.0
    }
  ]
}
```

---

### GET /api/portfolio

**Mục đích:** Trả về Portfolio Heat hiện tại và per-asset correlated group risk.

**Response 200:**
```json
{
  "total_heat": 0.04,
  "heat_limit": 0.06,
  "heat_available": 0.02,
  "positions": [
    {
      "asset": "BTC/USDT",
      "direction": "long",
      "risk_pct": 0.02,
      "size_usd": 100.0
    }
  ],
  "correlated_groups": [
    {
      "assets": ["BTC/USDT", "ETH/USDT"],
      "group_risk_pct": 0.02,
      "max_group_risk": 0.03,
      "correlation": 0.87
    }
  ]
}
```

---

### GET /api/config

**Mục đích:** Lấy config hiện tại (không bao gồm sensitive fields như API keys).

**Response 200:**
```json
{
  "account": { "balance": 10000.0, "currency": "USDT" },
  "position": { "mode": "risk_pct", "risk_pct": 0.02, "max_concurrent": 3 },
  "regime": { "enabled": true, "adx_trending_threshold": 25 },
  "risk": { "portfolio_heat_limit_pct": 6.0 },
  "strategy": { "score_threshold": { "alert": 75, "watch": 55 } },
  "exchange": { "name": "binance", "market_type": "futures", "testnet": true }
}
```

---

### POST /api/config/reload

**Mục đích:** Hot-reload config.yaml mà không cần restart process.

**Request:** Body không cần.

**Response 200:**
```json
{
  "status": "reloaded",
  "timestamp": "2024-01-15T09:20:00Z",
  "version": 3
}
```

**Response 400 (config invalid):**
```json
{
  "detail": "Config validation failed: position.risk_pct must be between 0.001 and 0.1",
  "code": "CONFIG_VALIDATION_ERROR"
}
```

**Side Effects:** ConfigSystem.reload() — tất cả modules đọc config mới ở lần tiếp theo.

---

### GET /api/config/exchange

**Mục đích:** Lấy exchange settings (API keys bị mask).

**Response 200:**
```json
{
  "name": "binance",
  "market_type": "futures",
  "testnet": true,
  "api_key": "****5678",
  "api_secret": "****ABCD",
  "fee_rate": 0.001,
  "slippage_pct": 0.0002
}
```

---

### PUT /api/config/exchange

**Mục đích:** Cập nhật exchange settings.

**Request Body:**
```json
{
  "name": "binance",
  "market_type": "futures",
  "testnet": false,
  "api_key": "actual_api_key",
  "api_secret": "actual_api_secret",
  "fee_rate": 0.001
}
```

**Response 200:**
```json
{
  "status": "saved",
  "testnet": false
}
```

---

### GET /api/config/trading

**Mục đích:** Lấy trading parameters version mới nhất.

**Response 200:**
```json
{
  "version": 3,
  "updated_at": "2024-01-15T09:00:00Z",
  "position": { "mode": "risk_pct", "risk_pct": 0.02 },
  "risk": { "max_daily_loss_pct": 0.05 },
  "strategy": { "score_threshold": { "alert": 75 } }
}
```

---

### PUT /api/config/trading

**Mục đích:** Cập nhật trading parameters, tạo version mới.

**Request Body:** Partial trading config object.

**Response 200:**
```json
{
  "status": "saved",
  "version": 4,
  "updated_at": "2024-01-15T10:00:00Z"
}
```

---

### GET /api/config/trading/history

**Mục đích:** Lấy lịch sử các version của trading config.

**Response 200:**
```json
{
  "history": [
    {
      "version": 3,
      "updated_at": "2024-01-15T09:00:00Z",
      "changed_fields": ["risk.max_daily_loss_pct"],
      "snapshot": { ... }
    }
  ]
}
```

---

### GET /api/circuit-breaker/status

**Mục đích:** Lấy trạng thái hiện tại của Circuit Breaker.

**Response 200 (not locked):**
```json
{
  "is_locked": false,
  "trigger_type": null,
  "triggered_at": null,
  "unlock_at": null,
  "time_remaining_seconds": null,
  "requires_review": false,
  "regime_at_trigger": null,
  "last_unlock": {
    "unlocked_at": "2024-01-14T21:00:00Z",
    "unlocked_by": "auto_regime_change"
  }
}
```

**Response 200 (locked):**
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

### POST /api/circuit-breaker/unlock

**Mục đích:** Manual unlock Circuit Breaker. Trigger 4 yêu cầu `review_note`.

**Request Body:**
```json
{
  "review_note": "Reviewed market conditions. BTC regime changed to CHOPPY. Safe to resume.",
  "unlocked_by": "trader_john"
}
```

**Response 200:**
```json
{
  "status": "unlocked",
  "unlocked_at": "2024-01-15T10:00:00Z",
  "unlocked_by": "manual_user"
}
```

**Response 400 (review_note too short for Trigger 4):**
```json
{
  "detail": "review_note must be at least 10 characters for Trigger 4 unlock",
  "code": "REVIEW_NOTE_REQUIRED"
}
```

---

### GET /api/backtest/results

**Mục đích:** Lấy danh sách backtest results và Benchmark Table.

**Response 200:**
```json
{
  "results": [
    {
      "run_id": "770e8400-...",
      "strategy_name": "smc_ob_fvg",
      "asset": "BTC/USDT",
      "timeframe": "15m",
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "win_rate": 0.625,
      "profit_factor": 2.15,
      "max_drawdown": 0.085,
      "sharpe_ratio": 1.82,
      "total_trades": 48,
      "is_walk_forward": true,
      "is_in_sample": false,
      "completed_at": "2024-01-15T10:00:00Z"
    }
  ],
  "benchmark_table": {
    "headers": ["strategy", "BTC/USDT 15m", "ETH/USDT 15m"],
    "rows": [
      ["smc_ob_fvg", "WR:62.5% PF:2.15", "WR:58.3% PF:1.87"]
    ]
  }
}
```

---

### POST /api/backtest/run

**Mục đích:** Trigger async backtest run.

**Request Body:**
```json
{
  "strategy_name": "smc_ob_fvg",
  "asset": "BTC/USDT",
  "timeframe": "15m",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "walk_forward": true
}
```

**Response 202 Accepted:**
```json
{
  "run_id": "770e8400-...",
  "status": "running",
  "estimated_duration_seconds": 120
}
```

**Side Effects:**
- Background task chạy BacktestEngine
- INSERT `backtest_results` khi hoàn thành
- Write optimization suggestions to `/logs/`
