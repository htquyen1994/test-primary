# Signal Validation Prompt — Crypto Trading System

> **Mục đích:** Đối chiếu ngược dự đoán của model với thực tế thị trường.
> Chạy sau audit hàng ngày hoặc sau mỗi 7 ngày tích lũy đủ signal.
> Copy toàn bộ vào Kiro chat.

---

## PROMPT

```
Tôi muốn thực hiện Signal Validation — kiểm tra xem những gì model dự đoán
có khớp với thực tế thị trường không.

Hãy thực hiện theo đúng thứ tự sau:

─────────────────────────────────────────────────────────
BƯỚC 1 — Lấy signals cần validate từ database
─────────────────────────────────────────────────────────

Chạy script:
  workspace/trade-audit-result/scripts/validate_signals.py --step=1

Script cần làm:
  Kết nối SQL Server (localhost:1433)
  Query signal_log với filter:
    - classification IN ('ALERT', 'WATCH')
    - timestamp >= NOW() - 7 ngày
    - entry_price IS NOT NULL
    - stop_loss IS NOT NULL
    - take_profit_1 IS NOT NULL

  Với mỗi signal, lấy đủ các field:
    log_id, timestamp, asset, timeframe, direction,
    entry_price, stop_loss, take_profit_1, take_profit_2,
    final_score, raw_score,
    score_order_flow, score_smc, score_vsa, score_context, score_bonus,
    regime, regime_multiplier,
    classification, user_action

  In ra: tổng số signals tìm thấy, date range, breakdown theo asset.

─────────────────────────────────────────────────────────
BƯỚC 2 — Fetch OHLCV thực tế sau thời điểm mỗi signal
─────────────────────────────────────────────────────────

Chạy script:
  workspace/trade-audit-result/scripts/validate_signals.py --step=2

Script cần làm:
  Với mỗi signal từ Bước 1, dùng Binance public API (không cần key):
    - Fetch OHLCV của asset đó, khung 5m
    - Từ thời điểm signal.timestamp
    - Lấy đủ 96 nến (96 × 5m = 8 giờ) — đủ để TP/SL hit trong hầu hết trường hợp

  Với mỗi nến trong 96 nến đó, kiểm tra:

    IF direction == 'long':
      - TP hit: nến nào có high >= take_profit_1 → ghi nhận "TP1_HIT" tại nến đó
      - SL hit: nến nào có low  <= stop_loss     → ghi nhận "SL_HIT"  tại nến đó
      - Lấy cái hit TRƯỚC (candle index nhỏ hơn)

    IF direction == 'short':
      - TP hit: nến nào có low  <= take_profit_1 → ghi nhận "TP1_HIT"
      - SL hit: nến nào có high >= stop_loss     → ghi nhận "SL_HIT"

    Kết quả outcome mỗi signal:
      "WIN"     — TP1 hit trước SL
      "LOSS"    — SL hit trước TP1
      "PENDING" — sau 8 giờ chưa hit cái nào (signal còn mới)
      "NO_DATA" — không fetch được OHLCV (Binance không có data)

  Tính thêm:
    candles_to_outcome: số nến 5m từ lúc entry đến lúc hit TP/SL
    max_adverse_excursion: giá đi ngược xa nhất trước khi hit outcome (%)
    max_favorable_excursion: giá đi thuận xa nhất (%)

  Lưu kết quả trung gian vào:
    workspace/trade-audit-result/temp/outcomes_{date}.json

─────────────────────────────────────────────────────────
BƯỚC 3 — Validate từng component dự đoán của model
─────────────────────────────────────────────────────────

Chạy script:
  workspace/trade-audit-result/scripts/validate_signals.py --step=3

Đây là bước quan trọng nhất: kiểm tra xem từng lý do model đưa ra
có đúng với diễn biến giá thực không.

Với mỗi signal có outcome WIN hoặc LOSS:

  [3A] Validate Order Block (nếu score_smc > 0)
    - Lấy vùng OB từ signal: entry_price ± 0.3% làm proxy OB zone
    - Kiểm tra trong 12 nến 5m sau signal:
      - Giá có retest về vùng OB không? (low chạm vùng OB)
      - Nếu có retest: giá có bounce không? (2 nến sau retest có close cao hơn không)
    - Kết luận: "OB_HELD" / "OB_BROKEN" / "OB_NOT_TESTED"

  [3B] Validate RSI context (nếu score_context > 0)
    - Fetch RSI(14) tại thời điểm signal từ OHLCV 15m thực tế
    - So sánh với điều kiện model đã dùng:
      - Long: RSI phải > 50 tại nến trigger
      - Short: RSI phải < 50 tại nến trigger
    - Kết luận: "RSI_CONFIRMED" / "RSI_WRONG" / "RSI_BORDERLINE" (48–52)

  [3C] Validate Regime
    - Tính ADX(14) từ OHLCV 1H thực tế tại thời điểm signal
    - So sánh với regime model ghi trong signal_log
    - Kết luận: "REGIME_MATCH" / "REGIME_MISMATCH"

  [3D] Validate MTF Direction
    - Fetch OHLCV 4H của asset tại thời điểm signal
    - Tính EMA20 và EMA50 trên 4H
    - Kiểm tra: 4H trend có cùng chiều với signal.direction không?
    - Kết luận: "MTF_ALIGNED" / "MTF_OPPOSING" / "MTF_NEUTRAL"

  [3E] Validate Price Action sau entry
    - Trong 6 nến 5m đầu tiên sau entry:
      - Giá đi đúng hướng ngay không? (3/6 nến đầu tiên đóng cửa đúng chiều)
    - Kết luận: "IMMEDIATE_FOLLOW_THROUGH" / "CHOP_AFTER_ENTRY" / "REVERSAL_AFTER_ENTRY"

  Lưu kết quả validation component vào:
    workspace/trade-audit-result/temp/component_validation_{date}.json

─────────────────────────────────────────────────────────
BƯỚC 4 — Tổng hợp phân tích thống kê
─────────────────────────────────────────────────────────

Chạy script:
  workspace/trade-audit-result/scripts/validate_signals.py --step=4

Tính các nhóm thống kê sau:

  [4A] Win rate tổng thể và theo score bucket
    Score 75–79:  win_rate, count
    Score 80–84:  win_rate, count
    Score 85–89:  win_rate, count
    Score 90+:    win_rate, count
    → Câu hỏi: Score cao hơn có thực sự win rate cao hơn không?

  [4B] Win rate theo từng module score
    Nhóm theo score_smc cao (>20) vs thấp (<10): win rate khác nhau bao nhiêu?
    Nhóm theo score_order_flow > 0 vs = 0: win rate khác nhau bao nhiêu?
    → Câu hỏi: Module nào thực sự predict được outcome?

  [4C] Win rate theo Regime
    TRENDING: win_rate, count
    RANGING:  win_rate, count
    CHOPPY:   win_rate, count
    → Câu hỏi: Model có hoạt động tốt hơn trong TRENDING không?

  [4D] Component validation accuracy
    Khi OB_HELD:        win_rate
    Khi OB_BROKEN:      win_rate
    Khi RSI_CONFIRMED:  win_rate
    Khi RSI_WRONG:      win_rate
    Khi MTF_ALIGNED:    win_rate
    Khi MTF_OPPOSING:   win_rate
    → Câu hỏi: Component nào có predictive value thực sự?

  [4E] Timing analysis
    Avg candles_to_outcome khi WIN vs LOSS
    % signals hit outcome trong 12 nến đầu (1 giờ)
    % signals hit outcome trong 24 nến (2 giờ)
    % signals còn PENDING sau 8 giờ
    → Câu hỏi: Time invalidation 15 nến có hợp lý không?

  [4F] MAE/MFE analysis (quan trọng cho SL/TP calibration)
    Avg max_adverse_excursion khi WIN (model set SL có dư room không?)
    Avg max_favorable_excursion khi LOSS (giá đã đi gần TP trước khi quay đầu?)
    → Câu hỏi: SL 0.3% dưới OB có đủ room không? TP 0.5% có thực tế không?

─────────────────────────────────────────────────────────
BƯỚC 5 — So sánh với thị trường hiện tại
─────────────────────────────────────────────────────────

Chạy script:
  workspace/trade-audit-result/scripts/validate_signals.py --step=5

Mục đích: kiểm tra xem điều kiện thị trường hiện tại có giống
với điều kiện của các winning signals không.

  Fetch OHLCV hiện tại của BTC/USDT, ETH/USDT, SOL/USDT (15m, 1H, 4H)
  Tính các indicator tương tự như model đang dùng:
    - ADX(14), RSI(14), EMA20, EMA50
    - Regime hiện tại
    - MTF direction hiện tại

  So sánh với profile của winning signals:
    - Winning signals thường có regime nào? Regime hiện tại có match không?
    - Winning signals thường có RSI khoảng bao nhiêu? RSI hiện tại có trong zone đó không?
    - MTF alignment của winning signals: hiện tại có aligned không?

  Output: "Current market conditions match winning signal profile: YES/NO/PARTIAL"
  Nếu PARTIAL hoặc NO: giải thích khác ở điểm nào.

─────────────────────────────────────────────────────────
BƯỚC 6 — Ghi kết quả và đề xuất cải thiện
─────────────────────────────────────────────────────────

Tạo folder: workspace/trade-audit-result/YYYY-MM-DD/validation/

Tạo file: signal_validation_report.md với cấu trúc:

  ## Summary
  - Tổng signals validated: N
  - Overall win rate: X%
  - WIN / LOSS / PENDING breakdown

  ## Score Accuracy
  - Bảng win rate theo score bucket
  - Kết luận: scoring có predictive value không?

  ## Component Analysis
  - Bảng win rate theo từng component validation
  - Component nào thực sự đóng góp vào winning? Cái nào không?

  ## Regime Analysis
  - Win rate tốt nhất ở regime nào?
  - Có nên block signal ở regime X không?

  ## Timing Insights
  - SL/TP calibration có hợp lý không?
  - Time invalidation threshold có nên điều chỉnh không?

  ## Current Market Match
  - Thị trường hiện tại có phù hợp để trade không?
  - Setup nào có xác suất cao nhất hôm nay?

  ## Recommended Config Changes
  - Những thay đổi config cụ thể (nếu có) dựa trên data
  - Ví dụ: "Tăng score_threshold.alert từ 75 lên 80 vì win rate ở 75–79 chỉ đạt 42%"

Tạo file: raw_data.csv với tất cả signals và outcomes để phân tích thêm sau.
```

---

## Script mới cần tạo

```
workspace/trade-audit-result/scripts/validate_signals.py
```

Script này chưa tồn tại. Kiro cần tạo mới với các yêu cầu sau:

```python
"""
validate_signals.py — Signal Validation Tool
Kết nối: SQL Server (localhost:1433) để đọc signal_log
         Binance public API để fetch OHLCV thực tế (không cần API key)
Chạy: python validate_signals.py --step=1|2|3|4|5|all
"""

# Dependencies cần có:
#   pyodbc hoặc pymssql       (SQL Server)
#   ccxt hoặc requests        (Binance OHLCV: GET /api/v3/klines)
#   pandas, numpy             (tính toán)
#   json, csv, pathlib        (output)
#   argparse                  (--step argument)
#   ta hoặc pandas_ta         (RSI, ADX, EMA — nếu chưa có thì tính thủ công)

# Binance public endpoint (không cần key):
#   GET https://api.binance.com/api/v3/klines
#   params: symbol=BTCUSDT, interval=5m, startTime=<ms>, limit=96

# Lưu ý quan trọng:
#   - symbol Binance: "BTC/USDT" → "BTCUSDT" (bỏ dấu /)
#   - startTime: timestamp Unix milliseconds
#   - Không rate limit quá nhanh: sleep 0.2s giữa các request
#   - Nếu signal quá mới (< 8 giờ): outcome = "PENDING", skip component validation
```

---

## Câu hỏi cốt lõi prompt này trả lời

| Câu hỏi | Bước |
|---|---|
| Signal score 80+ có thực sự win rate cao hơn 75 không? | 4A |
| Order Flow = 0 có làm giảm win rate không? | 4B |
| SMC score cao có thực sự predict winning trade không? | 4B |
| Model hoạt động tốt nhất ở regime nào? | 4C |
| OB zone có hold thực tế không sau khi signal tạo ra? | 4D |
| MTF aligned có thực sự tăng win rate không? | 4D |
| SL đặt 0.3% dưới OB có bị sweep trước khi giá đi đúng hướng không? | 4F |
| Time invalidation 15 nến có đủ không? | 4E |
| Thị trường hôm nay có phù hợp với profile winning signal không? | 5 |

---

## Lưu ý quan trọng

- **Không sửa signal_log**: script chỉ đọc, không ghi vào DB
- **Binance public API**: dùng endpoint `/api/v3/klines`, không cần key
- **Minimum sample**: cần ít nhất 20 signals có outcome WIN/LOSS để kết quả có ý nghĩa thống kê. Nếu chưa đủ, ghi rõ "insufficient sample" trong report
- **PENDING không tính**: không đưa PENDING vào win rate calculation
- **Lưu raw data**: luôn export raw_data.csv để có thể re-analyze sau
- **Timestamp**: mọi file output đều ghi timestamp tạo ra ở header

---

## Khi nào nên chạy

| Tình huống | Hành động |
|---|---|
| Sau 7 ngày đầu tiên hệ thống chạy | Chạy toàn bộ (--step=all) |
| Sau khi thay đổi config (threshold, scoring weight) | Chạy --step=4 với data cũ để compare |
| Khi win rate cảm giác đang giảm | Chạy --step=2,3,4 để diagnose |
| Trước khi go live từ testnet | Chạy toàn bộ, yêu cầu win rate ≥ 52% net |
| Hàng tuần định kỳ | Chạy --step=all, append vào report tuần |

*Tháng 5/2026*
