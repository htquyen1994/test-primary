# Audit Prompt — Crypto Trading System

> Dùng prompt này mỗi lần audit. Copy toàn bộ vào Kiro chat.

---

## PROMPT

```
Tôi muốn thực hiện audit hệ thống trading hôm nay.

Hãy thực hiện theo thứ tự sau:

### BƯỚC 1 — Kiểm tra database (SQL Server)
Chạy script `workspace/trade-audit-result/scripts/audit_signals.py` để:
- Xem tổng quan signal_log (tổng số, date range, assets, strategies)
- Phân tích signals hôm nay: ALERT/WATCH/IGNORE breakdown
- Score distribution và avg module scores
- Data quality check (Order Flow = 0?, score cap violation?)
- Top 10 highest scoring signals
- Circuit breaker state

### BƯỚC 2 — Phân tích thị trường live
Chạy script `workspace/trade-audit-result/scripts/market_analysis.py` để:
- Fetch OHLCV từ Binance (BTC/USDT, ETH/USDT, SOL/USDT)
- Tính Regime (TRENDING/RANGING/PARABOLIC/CHOPPY)
- MTF Bias (Daily/4H/1H)
- Key indicators (RSI, ADX, EMA, BB)
- SMC structures (FVG, OB)
- Estimated max score với current data quality

### BƯỚC 3 — Kiểm tra config
Chạy script `workspace/trade-audit-result/scripts/check_config.py` để:
- Active trading_params (trigger_timeframe, thresholds)
- Exchange settings (exchange, testnet mode)
- Active assets

### BƯỚC 4 — Debug SMC nếu score thấp
Nếu SMC avg score < 5/30, chạy `workspace/trade-audit-result/scripts/debug_smc.py`
để diagnose từng function: CHoCH, OB, FVG

### BƯỚC 5 — Tổng hợp và ghi kết quả
Tạo folder `workspace/trade-audit-result/YYYY-MM-DD/` với:
- `findings.md`: những gì phát hiện
- `fixes_applied.md`: những gì đã fix (nếu có)

### CHECKLIST sau mỗi audit:
- [ ] signal_log có data hôm nay không?
- [ ] Có ALERT signal nào không? Nếu không, tại sao?
- [ ] Order Flow score = 0? (OB feed chưa chạy)
- [ ] trigger_timeframe = 15m? (không phải 5m)
- [ ] SMC avg score > 5/30?
- [ ] Circuit breaker có locked không?
- [ ] Thị trường đang ở regime nào?
- [ ] Setup trade tốt nhất hôm nay là gì?
```

---

## Cách chạy scripts

```bash
# Từ thư mục workspace/backend-workspace
python "D:\workspace\trade-workspace\workspace\trade-audit-result\scripts\audit_signals.py"
python "D:\workspace\trade-workspace\workspace\trade-audit-result\scripts\market_analysis.py"
python "D:\workspace\trade-workspace\workspace\trade-audit-result\scripts\check_config.py"
python "D:\workspace\trade-workspace\workspace\trade-audit-result\scripts\debug_smc.py"
```

## Lưu ý quan trọng

- **Database**: Luôn dùng SQL Server (`localhost:1433`), không dùng SQLite
- **Exchange**: Binance public API (không cần key) cho market data
- **Scripts**: Không sửa scripts trong `scripts/` — nếu cần thay đổi, tạo version mới
- **Findings**: Ghi rõ timestamp, data range, và context của từng finding
