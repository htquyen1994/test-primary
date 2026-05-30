# Log Analysis & Model Tuning Prompt
# Phiên bản: v1.0 | Ngày: 2026-05-30
# Mục đích: Phân tích log + Tối ưu model scoring dựa trên outcome thực tế

> **Khi nào dùng prompt này?**
> - Sau 7+ ngày hệ thống chạy → đủ data để tune
> - Khi win rate thấp hơn kỳ vọng (< 50%)
> - Khi nghi ngờ có module đang inflate/deflate score sai
> - Định kỳ hàng tháng để giữ model sharp
>
> **Yêu cầu tối thiểu:** ≥ 20 signals có outcome WIN/LOSS (ALERT + WATCH đã resolved)

---

## PROMPT — COPY TOÀN BỘ VÀO KIRO CHAT

```
Tôi muốn thực hiện Log Analysis và Model Tuning cho hệ thống trading.

Ngữ cảnh hệ thống:
  - Exchange: Gate.io (trading), Binance public API (market data)
  - Assets: BTC/USDT, ETH/USDT, SOL/USDT
  - Scoring: OF(max 35) + SMC(max 30) + VSA(max 30) + Context(max 15) + Bonus(max 15) = max 125 → normalize 0–100
  - Alert threshold: 75 | Watch threshold: 55
  - SL = ATR(14) × 1.5 | TP1 = SL_dist × 2.0 | TP2 = SL_dist × 3.0
  - Weights và thresholds được lưu trong DB (bảng trading_params), KHÔNG hardcode
  - Script tuning: workspace/trade-audit-result/scripts/threshold_optimizer.py
  - Script audit: workspace/trade-audit-result/scripts/run_step1_audit.py

Hãy thực hiện theo đúng thứ tự sau:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHẦN 1 — PHÂN TÍCH LOG (Log Analysis)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

─────────────────────────────────────────────────────
BƯỚC 1A — Tổng quan signal log hôm nay
─────────────────────────────────────────────────────

Chạy:
  python workspace/trade-audit-result/scripts/run_step1_audit.py

Phân tích output và trả lời:

  □ Tổng số signals hôm nay là bao nhiêu?
  □ Tỷ lệ ALERT / WATCH / IGNORE như thế nào?
  □ Score trung bình, max, min là bao nhiêu?
  □ Component score nào đang thấp bất thường?
     → Nếu SMC avg < 5: CHoCH không fire → kiểm tra OHLCV buffer có đủ không
     → Nếu OF avg < 3: OrderBook không có data → kiểm tra ob:{sym}:snap
     → Nếu VSA avg > 20 nhưng SMC = 0: VSA đang inflate score sai, cần xem lại
  □ Regime phân bố như thế nào? CHOPPY nhiều quá (> 60%) là bất thường
  □ Có duplicate signals không? (cùng asset/timeframe/score trong 1 phút)
  □ VELO/USDT có còn xuất hiện không? (đã disabled, không được có)

Cờ đỏ cần điều tra:
  ⚠ ALERT = 0 sau 7+ ngày → xem Bước 1B
  ⚠ Score max < 50 liên tục → SMC hoặc OF pipeline bị lỗi
  ⚠ Tổng signals > 5000/ngày → pipeline loop firing quá nhanh (bug dedup)
  ⚠ Cùng score xuất hiện hàng chục lần trong 1 phút → restart main.py

─────────────────────────────────────────────────────
BƯỚC 1B — Chẩn đoán tại sao không có ALERT (nếu ALERT = 0)
─────────────────────────────────────────────────────

Kết nối SQL Server và chạy các query sau:

  -- [Q1] Score distribution trong 7 ngày
  SELECT
      CASE
          WHEN final_score < 40 THEN '00-39'
          WHEN final_score < 50 THEN '40-49'
          WHEN final_score < 55 THEN '50-54'
          WHEN final_score < 60 THEN '55-59'
          WHEN final_score < 65 THEN '60-64'
          WHEN final_score < 70 THEN '65-69'
          WHEN final_score < 75 THEN '70-74'
          WHEN final_score < 80 THEN '75-79'
          ELSE '80+'
      END as bucket,
      COUNT(*) as cnt,
      AVG(CAST(final_score AS FLOAT)) as avg_score
  FROM dbo.signal_log
  WHERE timestamp >= DATEADD(DAY, -7, GETUTCDATE())
  GROUP BY
      CASE
          WHEN final_score < 40 THEN '00-39'
          WHEN final_score < 50 THEN '40-49'
          WHEN final_score < 55 THEN '50-54'
          WHEN final_score < 60 THEN '55-59'
          WHEN final_score < 65 THEN '60-64'
          WHEN final_score < 70 THEN '65-69'
          WHEN final_score < 75 THEN '70-74'
          WHEN final_score < 80 THEN '75-79'
          ELSE '80+'
      END
  ORDER BY bucket

  -- [Q2] Top scores — gần ngưỡng nhất
  SELECT TOP 20
      CONVERT(VARCHAR(16), timestamp, 120) as ts,
      asset, timeframe, direction, final_score,
      score_order_flow, score_smc, score_vsa, score_context, score_bonus,
      regime, regime_multiplier
  FROM dbo.signal_log
  WHERE timestamp >= DATEADD(DAY, -7, GETUTCDATE())
  ORDER BY final_score DESC

  -- [Q3] Component trung bình theo ngày (trend)
  SELECT
      CONVERT(DATE, timestamp) as day,
      COUNT(*) as n_signals,
      AVG(CAST(score_order_flow AS FLOAT)) as avg_of,
      AVG(CAST(score_smc        AS FLOAT)) as avg_smc,
      AVG(CAST(score_vsa        AS FLOAT)) as avg_vsa,
      AVG(CAST(score_context    AS FLOAT)) as avg_ctx,
      MAX(final_score)                     as max_score
  FROM dbo.signal_log
  WHERE timestamp >= DATEADD(DAY, -14, GETUTCDATE())
  GROUP BY CONVERT(DATE, timestamp)
  ORDER BY day DESC

Diễn giải kết quả Q1:
  → Nếu 95%+ signals nằm ở bucket 00-39: SMC không fire (CHoCH missing)
  → Nếu scores tập trung ở 40-55 nhưng không có 55+: Context filter đang chặn
  → Nếu scores đang tăng dần theo ngày (Q3): hệ thống đang warm up bình thường

Diễn giải kết quả Q2:
  → Signal có score cao nhất đang "thiếu" gì?
     Ví dụ: score=68, SMC=0 → nếu SMC không bằng 0 thì đã ALERT
     → Cần điều kiện: CHoCH trên 1H + OB retest + FVG touch
  → Regime nào chiếm nhiều trong top scores? TRENDING tốt hơn CHOPPY

─────────────────────────────────────────────────────
BƯỚC 1C — Phân tích market hiện tại
─────────────────────────────────────────────────────

Chạy:
  python workspace/trade-audit-result/scripts/market_analysis.py

Đọc output và trả lời:
  □ Regime của từng coin? (TRENDING là tốt nhất cho signals)
  □ MTF Scenario? (A = full size, B = half size -10pts, C = BLOCKED)
  □ Max score estimate có thể đạt được hôm nay là bao nhiêu?
  □ Điều kiện thị trường có match với profile winning signals không?

Điều kiện lý tưởng cho ALERT:
  ✓ Regime: TRENDING (ADX > 25)
  ✓ MTF Scenario A: 4H + 1H cùng chiều
  ✓ RSI 15m: 40–60 (không overbought/oversold)
  ✓ Price gần EMA200 1H (retest zone)
  ✓ OB Feed: valid (age < 60s, bid_stack > 0)

─────────────────────────────────────────────────────
BƯỚC 1D — Tóm tắt chẩn đoán
─────────────────────────────────────────────────────

Sau Bước 1A-1C, hãy đưa ra:

  CHẨN ĐOÁN CHÍNH: [1-2 câu tóm tắt vấn đề cốt lõi]

  NGUYÊN NHÂN GỐC RỄ: [cụ thể — không phải "market không tốt"]
    Ví dụ:
    - "SMC score = 0 vì OHLCV 1H buffer chỉ có 45 candles, cần ≥ 200 để compute EMA200"
    - "4H ranging khiến toàn bộ signals bị Scenario B, giảm 10 điểm, score max 65"
    - "OF = 0 vì OrderBook stale (age = 180s), score bị cap tại 60"

  CÁC ĐIỀU KIỆN CẦN ĐỂ CÓ ALERT TIẾP THEO:
    1. [điều kiện 1]
    2. [điều kiện 2]
    3. [điều kiện 3]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHẦN 2 — MODEL TUNING (chỉ chạy khi có ≥ 20 labeled signals)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Kiểm tra sample size trước:
  python workspace/trade-audit-result/scripts/threshold_optimizer.py --step=analyze

  → Nếu output: "No labeled signals" → DỪNG, không chạy tiếp Phần 2
  → Nếu "Only N labeled signal(s)": chạy tiếp nhưng ghi rõ "PRELIMINARY — insufficient sample"
  → Nếu N ≥ 20: tiếp tục đầy đủ

─────────────────────────────────────────────────────
BƯỚC 2A — Phân tích đầy đủ (threshold + weights + regime)
─────────────────────────────────────────────────────

Chạy:
  python workspace/trade-audit-result/scripts/threshold_optimizer.py --step=all

  (Mặc định là dry-run — KHÔNG ghi vào DB)

Đọc output và phân tích:

  [THRESHOLD ANALYSIS]
  □ Optimal threshold T* là bao nhiêu? (so với current = 75)
  □ EV tại T* so với EV tại T=75 chênh nhau bao nhiêu?
     → Chênh > 0.10 per trade = đáng cân nhắc thay đổi
     → Chênh < 0.05 = không cần thay đổi
  □ CI của EV tại T* có dương hoàn toàn không?
     → CI phải dương (ev_ci_low > 0) mới đáng tin cậy
  □ Win rate theo score bucket:
     → Bucket nào có win_rate thấp nhất? Threshold có nên cao hơn bucket đó không?
     → Có khoảng "dip" (win_rate giảm ở score cao hơn) không? → dấu hiệu overfitting

  [WEIGHT ANALYSIS]
  □ Module nào có AUC-ROC cao nhất? (module đó quan trọng nhất)
  □ Module nào có AUC ~ 0.50? (module đó là noise — random không tốt hơn)
  □ Module nào có correlation âm? (module đó đang hại win rate!)
  □ AUC improvement sau optimize là bao nhiêu?
     → < 0.01: không đáng thay đổi weights
     → 0.01–0.03: nhỏ nhưng có ý nghĩa
     → > 0.03: thay đổi weights có giá trị rõ ràng

  [REGIME ANALYSIS]
  □ Regime nào có win_rate thấp nhất?
  □ Có regime nào nên BLOCK không? (win_rate < 40%)

─────────────────────────────────────────────────────
BƯỚC 2B — Ra quyết định: Apply hay không?
─────────────────────────────────────────────────────

Dùng bảng quyết định sau:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                    DECISION MATRIX                                   │
  ├──────────────────────┬────────────────┬──────────────────────────── ┤
  │ Điều kiện            │ Quyết định     │ Hành động                   │
  ├──────────────────────┼────────────────┼─────────────────────────────┤
  │ N < 20               │ ❌ KHÔNG APPLY  │ Ghi note, chờ thêm data    │
  │ Confidence = LOW     │ ❌ KHÔNG APPLY  │ Chờ N ≥ 50                 │
  │ EV delta < 0.05      │ ❌ KHÔNG APPLY  │ Params đang OK             │
  │ EV ci_low < 0        │ ❌ KHÔNG APPLY  │ Không đủ confidence        │
  │ Threshold jump > 10  │ ⚠ APPLY 1 bước │ Chỉ thay đổi ±5 lần này   │
  │ AUC improvement<0.02 │ ❌ KHÔNG đổi W  │ Giữ weights = 1.0          │
  │ N ≥ 20 + conf=MEDIUM │ ✅ DRY-RUN xem  │ Review rồi quyết định      │
  │ N ≥ 50 + conf=HIGH   │ ✅ APPLY        │ Chạy với --apply           │
  └──────────────────────┴────────────────┴─────────────────────────────┘

  Với mỗi recommendation, giải thích:
    "Recommendation này [NÊN / KHÔNG NÊN] apply vì: [lý do cụ thể]"

─────────────────────────────────────────────────────
BƯỚC 2C — Thực hiện apply (chỉ khi quyết định = ✅ APPLY)
─────────────────────────────────────────────────────

Chạy:
  python workspace/trade-audit-result/scripts/threshold_optimizer.py --step=all --apply

Verify sau khi apply:
  1. Kiểm tra DB đã có row mới trong trading_params:

     SELECT TOP 3
         id, version_tag, version_note, is_active,
         score_alert_threshold, score_watch_threshold,
         weight_of, weight_smc, weight_vsa, weight_ctx, weight_bonus,
         tuning_win_rate, tuning_sample_size, activated_at
     FROM dbo.trading_params
     ORDER BY created_at DESC

  2. Confirm: row mới có is_active = 1, row cũ có is_active = 0
  3. Confirm: các giá trị mới đúng với recommendation
  4. Ghi lại version_tag để rollback nếu cần

  Nếu cần ROLLBACK:
     UPDATE dbo.trading_params SET is_active = 0 WHERE version_tag = '[new_tag]'
     UPDATE dbo.trading_params SET is_active = 1 WHERE version_tag = '[old_tag]'
     -- Sau đó restart pipeline

  5. Restart pipeline để nhận params mới:
     → Dừng process main.py đang chạy
     → Chạy lại: python workspace/backend-workspace/main.py
     → Confirm log: "TradingParams cache refresh" với giá trị mới

─────────────────────────────────────────────────────
BƯỚC 2D — Đo hiệu quả sau tuning (chạy sau 7 ngày)
─────────────────────────────────────────────────────

Sau 7 ngày kể từ khi apply, chạy lại phân tích để so sánh:

  -- [Q4] So sánh trước/sau tuning
  SELECT
      CASE
          WHEN activated_at < '[tuning_date]' THEN 'BEFORE'
          ELSE 'AFTER'
      END as period,
      COUNT(*) as total_signals,
      SUM(CASE WHEN classification = 'ALERT' THEN 1 ELSE 0 END) as alerts,
      AVG(CAST(final_score AS FLOAT)) as avg_score,
      MAX(final_score) as max_score
  FROM dbo.signal_log sl
  LEFT JOIN dbo.trading_params tp ON tp.is_active = 1
  WHERE sl.timestamp >= DATEADD(DAY, -14, GETUTCDATE())
  GROUP BY
      CASE
          WHEN sl.timestamp < '[tuning_date]' THEN 'BEFORE'
          ELSE 'AFTER'
      END

  So sánh kết quả:
  □ Alert count có tăng không? (phải tăng nếu hạ threshold)
  □ Win rate của ALERT signals có cải thiện không?
  □ AUC của scoring có tốt hơn không?
  □ Có cần fine-tune thêm không?


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHẦN 3 — KẾT QUẢ VÀ LƯU TRỮ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tạo file báo cáo tại:
  workspace/trade-audit-result/YYYY-MM-DD/log_and_tuning_report.md

Nội dung báo cáo:

  ## 1. Log Analysis Summary
  - Tổng signals: N | ALERT: A | WATCH: W | IGNORE: I
  - Score: avg=X max=Y
  - Component bottleneck: [module bị thấp nhất và lý do]
  - Market conditions: [TRENDING/CHOPPY, MTF scenario]
  - Issues found: [list any anomalies]

  ## 2. Root Cause (nếu không có ALERT)
  - [Phân tích cụ thể tại sao không có ALERT]

  ## 3. Tuning Analysis (nếu có data)
  - Labeled signals: WIN=X LOSS=Y Win_rate=Z%
  - Optimal threshold: T* = [value] (current = 75)
  - Top predictive modules: [ranked list]
  - Recommended changes: [list]

  ## 4. Decision & Actions Taken
  - [ ] Applied threshold change: 75 → [new]
  - [ ] Applied weight changes: [list]
  - [ ] DB version_tag: [tag]
  - [ ] Pipeline restarted: YES / NO / NOT_NEEDED

  ## 5. Next Steps
  - [3-5 action items cụ thể]
```

---

## Hướng dẫn sử dụng

### Khi nào chạy từng phần?

| Tình huống | Chạy phần |
|---|---|
| Check hàng ngày (< 5 phút) | Phần 1A + 1C |
| Debugging: không có ALERT | Phần 1A + 1B + 1C + 1D |
| Sau 7 ngày đầu chạy | Phần 1 đầy đủ + Phần 2 (analyze only) |
| Có ≥ 20 WIN/LOSS signals | Phần 1 + Phần 2 đầy đủ |
| Monthly review | Phần 1 + 2 + 3 đầy đủ |

### Thứ tự ưu tiên khi fix vấn đề

```
Không có ALERT?
  │
  ├─ SMC avg = 0? → CHoCH không fire
  │    → Kiểm tra OHLCV buffer (min 200 candles)
  │    → Kiểm tra swing_lookback trong trading_params
  │
  ├─ OF avg = 0? → OrderBook stale
  │    → Kiểm tra OrderBookService đang chạy
  │    → Kiểm tra ob:{sym}:snap age < 60s
  │
  ├─ Score max ~ 55-65? → MTF filter chặn (Scenario B/C)
  │    → Đợi 4H bias align với 1H
  │    → Xem xét giảm MTF penalty nếu win_rate OK
  │
  └─ Regime 70% CHOPPY? → Thị trường đang sideway
       → Bình thường — chờ trend quay lại
       → Threshold có thể quá cao cho choppy market
```

### Workflow tuning theo thời gian

```
Tuần 1-2: Chỉ log analysis (chưa đủ data)
Tuần 3-4: Analyze only, không apply
Tháng 2+: Analyze + apply nếu confidence HIGH
Quarterly: Full review, compare trước/sau
```

---

## Scripts reference

| Script | Lệnh | Mục đích |
|--------|------|---------|
| Log audit | `python run_step1_audit.py` | Signal counts, score stats, regime |
| Market analysis | `python market_analysis.py` | Live market conditions |
| Outcome labeling | `python validate_signals.py --step=2` | Label WIN/LOSS từ Binance |
| Analyze only | `python threshold_optimizer.py --step=analyze` | Stats, không recommend |
| Full dry-run | `python threshold_optimizer.py --step=all` | Recommend, không ghi DB |
| Apply changes | `python threshold_optimizer.py --step=all --apply` | Ghi vào DB |
| Custom lookback | `python threshold_optimizer.py --lookback=60` | Dùng 60 ngày lịch sử |

> **Tất cả scripts chạy từ:** `workspace/trade-audit-result/scripts/`
> **Python:** `workspace/backend-workspace/.venv/Scripts/python.exe`

---

## Câu hỏi cốt lõi prompt này trả lời

| Câu hỏi | Bước |
|---------|------|
| Hôm nay hệ thống có đang chạy đúng không? | 1A |
| Tại sao không có ALERT signal? | 1B |
| Market đang ở đâu, có nên trade không? | 1C |
| Score 68 WIN thực tế — threshold có quá cao không? | 2A Threshold |
| Score 78 LOSS — module nào đang inflate sai? | 2A Weight |
| CHOPPY regime có win rate quá thấp, có nên block không? | 2A Regime |
| Nên thay đổi threshold bao nhiêu? Có đủ confidence không? | 2B |
| Thay đổi đã có tác dụng sau 7 ngày chưa? | 2D |

---

## Lưu ý quan trọng

- **Không bao giờ apply** khi N < 20 WIN/LOSS signals
- **Chỉ thay đổi threshold ±5** mỗi lần — không nhảy lớn
- **Weights chỉ thay khi AUC improvement > 0.02** — dưới mức đó là noise
- **Luôn kiểm tra rollback procedure** trước khi apply
- **Sau mỗi apply: monitor 48h** trước khi apply thêm thay đổi
- **DB version history bảo toàn tất cả** — mọi thay đổi đều reversible

*Tháng 5/2026*
