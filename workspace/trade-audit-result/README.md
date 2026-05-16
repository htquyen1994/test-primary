# Trade Audit Result

Mỗi lần audit tạo một folder theo ngày: `YYYY-MM-DD/`

## Cấu trúc

```
trade-audit-result/
├── README.md                    ← file này
├── AUDIT_PROMPT.md              ← prompt chuẩn để chạy mỗi lần audit
├── scripts/                     ← các script audit dùng chung (không thay đổi)
│   ├── audit_signals.py         ← query signal_log từ SQL Server
│   ├── market_analysis.py       ← fetch live OHLCV + tính indicators
│   ├── debug_smc.py             ← debug SMC scoring pipeline
│   └── check_config.py          ← kiểm tra trading_params, exchange_settings
└── YYYY-MM-DD/                  ← folder mỗi ngày audit
    ├── findings.md              ← những gì phát hiện
    ├── fixes_applied.md         ← những gì đã fix
    └── outputs/                 ← output từ scripts (optional)
```

## Quy trình audit

1. Đọc `AUDIT_PROMPT.md`
2. Chạy scripts trong `scripts/`
3. Ghi kết quả vào `YYYY-MM-DD/findings.md`
4. Ghi fix vào `YYYY-MM-DD/fixes_applied.md`
5. Commit folder ngày đó

## Database

**SQL Server** (production) — luôn dùng SQL Server, không dùng SQLite.
```
DATABASE_URL=mssql+pyodbc://admin:***@localhost:1433/trading?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```
