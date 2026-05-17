# Master Audit Prompt — Crypto Trading System
# Phiên bản: v2.0 | Ngày: 2026-05-16
# Thay thế: AUDIT_PROMPT.md + SIGNAL_VALIDATION_PROMPT.md

> **Mục đích kép:**
> 1. **Kiểm tra hệ thống hàng ngày** (services, pipeline, data quality)
> 2. **Đối chiếu ngược dự đoán của model** với diễn biến giá thực tế
>
> **Tài sản theo dõi:** BTC/USDT, ETH/USDT, SOL/USDT (Gate.io trading, Binance data)
> **Chạy:** mỗi ngày (daily check) + mỗi 7 ngày (validation đầy đủ)

---

## PROMPT — COPY TOÀN BỘ VÀO KIRO CHAT

```
Tôi muốn thực hiện audit và signal validation hệ thống trading hôm nay.

Ngữ cảnh hệ thống:
  - Exchange: Gate.io (trading), Binance public API (market data analysis)
  - Assets: BTC/USDT, ETH/USDT, SOL/USDT
  - Scoring: OF(35) + SMC(30) + VSA(30) + Context(15) + Bonus(15) = max 125 → normalize 0–100
  - SL = entry ± ATR(14) × 1.5 | TP1 = entry ± SL_dist × 2.0 | TP2 = ± SL_dist × 3.0
  - MTF filter: 4H EMA200 + ADX(14) → Scenario A/B/C
  - Context: 1H bias (EMA200-based) + funding rate + S/R distance
  - Score cap: 60 khi không có Order Book data

Hãy thực hiện theo đúng thứ tự sau:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 0 — PRE-CHECK (luôn chạy đầu tiên)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy: workspace/trade-audit-result/scripts/master_audit.py --step=0

Kiểm tra:
  □ Tất cả 4 services đang chạy? (Redis, Backend:8000, MockExchange:8001, Frontend:5173)
  □ Order Book có data cho BTC/ETH/SOL? (ob:{sym}:snap age < 60s)
  □ Delta có data flowing? (delta > 0 cho ít nhất 1 symbol)
  □ OHLCV buffer đủ? (BTC/ETH/SOL: 15m n≥200, 4h n≥200, 1d n≥250)
  □ Last signal < 20 phút? (pipeline còn active)

  Đếm signal khả dụng để validate:
    - classification IN ('ALERT','WATCH') AND entry_price IS NOT NULL
    - asset IN ('BTC/USDT','ETH/USDT','SOL/USDT')
    - timestamp >= NOW() - 7 ngày
  → Nếu < 20 signals: ghi "INSUFFICIENT SAMPLE" và chỉ chạy Bước 1–3
  → Nếu ≥ 20 signals: chạy đầy đủ Bước 1–7

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 1 — DAILY SIGNAL LOG AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy: workspace/trade-audit-result/scripts/master_audit.py --step=1

[1A] Tổng quan hôm nay (asset=BTC/ETH/SOL, timestamp=TODAY):
  - ALERT / WATCH / IGNORE breakdown + tổng
  - Avg scores: OF, SMC, VSA, Context, Bonus, Final
  - % signals bị score cap tại 60 (OF=0)
  - Top 5 highest scoring signals (hiển thị đủ breakdown)

[1B] Filter Pipeline Analysis:
  Đếm signals bị block TRƯỚC khi scoring (từ log hoặc filter_extras):
    MTF_BLOCK    : N signals (4H opposing signal direction)
    BTC_GUARD    : N signals (BTC spike detected)
    CB_LOCKED    : N signals (circuit breaker active)
    DAILY_BIAS   : N signals (size reduced, not blocked)
  → Tính block rate = blocked / total attempted
  → Nếu MTF_BLOCK rate > 60%: cảnh báo "4H trend mạnh ngược chiều"

[1C] Regime Distribution hôm nay:
  TRENDING / RANGING / PARABOLIC / CHOPPY — count và avg score mỗi regime
  → Regime nào đang dominant?

[1D] Score Trend (so sánh với hôm qua và 7 ngày trước):
  - Avg final score hôm nay vs D-1 vs 7-day avg
  - Avg OF score (chỉ số OB feed health)
  - Nếu OF avg tăng so với hôm qua: OB feed cải thiện

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 2 — LIVE MARKET ANALYSIS (3 assets)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy: workspace/trade-audit-result/scripts/master_audit.py --step=2

Với mỗi asset trong [BTC/USDT, ETH/USDT, SOL/USDT]:
  Fetch Binance public API: /api/v3/klines
    symbol = BTCUSDT / ETHUSDT / SOLUSDT
    15m: limit=200, 1H: limit=200, 4H: limit=200, 1D: limit=50

  [2A] Regime Detection (đúng logic hệ thống):
    ATR(14) trên 15m: cur vs rolling_mean_20
    PARABOLIC nếu: cur_ATR > rolling_mean_ATR × 3.0
    ADX(14) trên 1H:
      TRENDING nếu ADX > 25
      CHOPPY   nếu ADX < 20
      RANGING  nếu 20 ≤ ADX ≤ 25
    → Score multiplier: TRENDING=1.0, RANGING/CHOPPY=0.85, PARABOLIC=0.6

  [2B] MTF Bias (đúng logic hệ thống — EMA200 + ADX):
    4H bias:
      bullish = price > EMA200(4H) AND ADX(4H) > 20 AND higher lows (last 3 swings)
      bearish = price < EMA200(4H) AND ADX(4H) > 20 AND lower highs
      ranging = otherwise
    Daily bias:
      BULL = close > EMA200(1D) AND close > EMA50(1D) AND 3+ higher lows in 10 days
      BEAR = close < EMA200(1D) AND close < EMA50(1D) AND 3+ lower highs
      NEUTRAL = otherwise
    → Scenario A/B/C dựa trên 4H bias vs expected direction

  [2C] Key Indicators:
    RSI(14) trên 15m, 1H
    EMA200 trên 1H, 4H (trend filter)
    Bollinger Band width: (upper-lower)/mid (đo volatility)

  [2D] SMC Structure hiện tại:
    Order Block: nến bearish/bullish ngay trước impulse mạnh (ATR × 1.0)
    FVG: 3-candle gap, midpoint, distance từ current price (%)
    CHoCH: giá có break swing high/low gần nhất chưa?

  [2E] Score Projection:
    Tính estimated score nếu:
      Scenario A (MTF aligned): + context aligned + có OB retest + có FVG
    Format: "Max possible: X/100 | Likely range: Y–Z/100"
    Điều kiện cần thêm để đạt ALERT (≥75): liệt kê cụ thể

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 3 — SIGNAL OUTCOME SIMULATION
(Chạy nếu có ≥ 20 signals khả dụng)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy: workspace/trade-audit-result/scripts/master_audit.py --step=3

Mục đích: Vì hệ thống đang testnet (chưa có trade thực), simulate outcome
từ price action để kiểm tra model prediction có đúng không.

  Lấy signals: classification IN ('ALERT','WATCH') AND entry_price IS NOT NULL
    AND asset IN ('BTC/USDT','ETH/USDT','SOL/USDT')
    AND timestamp <= NOW() - 8 giờ (đủ thời gian để TP/SL hit)

  Với mỗi signal, fetch Binance klines 5m:
    symbol = BTCUSDT / ETHUSDT / SOLUSDT
    startTime = signal.timestamp (milliseconds)
    limit = 96 (8 giờ = 96 × 5m)
    sleep 0.2s giữa các request

  Simulate outcome:
    IF direction == 'long':
      TP_hit = first candle where high >= take_profit_1 → "WIN"
      SL_hit = first candle where low  <= stop_loss     → "LOSS"
      Lấy outcome của candle index nhỏ hơn (hit trước)
    IF direction == 'short':
      TP_hit = first candle where low  <= take_profit_1 → "WIN"
      SL_hit = first candle where high >= stop_loss     → "LOSS"

    Nếu sau 96 nến không hit: "PENDING" (giữ nguyên, không tính vào win rate)
    Nếu không fetch được data: "NO_DATA"

  Tính thêm cho mỗi signal:
    candles_to_outcome : số nến 5m từ entry đến khi hit TP/SL
    max_adverse_excursion (MAE): giá đi ngược xa nhất (% từ entry)
      long MAE  = max((entry - low)  / entry × 100) trong các nến trước khi hit
      short MAE = max((high - entry) / entry × 100)
    max_favorable_excursion (MFE): giá đi thuận xa nhất (%)
      long MFE  = max((high - entry) / entry × 100)
      short MFE = max((entry - low)  / entry × 100)

  Lưu vào: workspace/trade-audit-result/temp/outcomes_{date}.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 4 — COMPONENT VALIDATION
(Chạy song song với Bước 3, chỉ với signals có WIN hoặc LOSS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy: workspace/trade-audit-result/scripts/master_audit.py --step=4

Đây là bước cốt lõi: kiểm tra từng lý do model đưa ra có phản ánh đúng
diễn biến giá thực tế không.

  [4A] Validate SMC — Order Block (nếu score_smc > 0)
    Fetch OHLCV 15m, lấy 20 nến trước signal để reconstruct OB zone
    Tìm candle bearish (bullish OB) ngay trước swing impulse mạnh nhất
    Tính OB zone: [ob_candle.low, ob_candle.high]
    Trong 12 nến 5m sau signal:
      Giá có pullback về OB zone không? (low chạm ob_candle.high)
      Nếu có: 2 nến tiếp theo có close > open không? (bounce confirmation)
    Kết luận:
      "OB_HELD"       — giá retest OB và bounce, OB zone giữ vững
      "OB_BROKEN"     — giá xuyên qua OB zone không bounce
      "OB_NOT_TESTED" — giá không pullback về OB trong 12 nến đầu

  [4B] Validate SMC — FVG (nếu score_smc > 0)
    Từ OHLCV 15m, tìm FVG gần nhất (3-candle gap)
    FVG midpoint = (top + bot) / 2
    Kiểm tra: giá có chạm midpoint ± 0.3% trong 8 nến 5m đầu tiên?
    Kết luận: "FVG_TOUCHED" / "FVG_MISSED" / "FVG_NOT_FOUND"

  [4C] Validate Context — 1H Bias (đúng logic hệ thống)
    Fetch OHLCV 1H, tính EMA200 trên 1H tại thời điểm signal
    1H bias = "bullish" nếu close > EMA200(1H), "bearish" nếu close < EMA200(1H)
    So với signal.direction: aligned?
    Kết luận: "1H_ALIGNED" / "1H_OPPOSING" / "1H_NEUTRAL"
    [KHÔNG dùng RSI threshold — hệ thống không dùng RSI cho context filter]

  [4D] Validate MTF — 4H Bias (đúng logic hệ thống)
    Fetch OHLCV 4H, tính EMA200(4H) và ADX(14) tại thời điểm signal
    4H bias:
      bullish = close > EMA200(4H) AND ADX > 20 AND recent higher lows
      bearish = close < EMA200(4H) AND ADX > 20 AND recent lower highs
      ranging = otherwise
    So với signal.direction:
      aligned  → Scenario A prediction
      opposing → Scenario C prediction (signal đã bị block?)
    Kết luận: "MTF_ALIGNED" / "MTF_OPPOSING" / "MTF_RANGING"
    [KHÔNG dùng EMA20/50 — hệ thống dùng EMA200 + ADX]

  [4E] Validate Price Action ngay sau entry
    Trong 6 nến 5m đầu tiên sau entry:
      long : đếm số nến có close > open (bullish candles)
      short: đếm số nến có close < open (bearish candles)
    Kết luận:
      "IMMEDIATE_FOLLOW_THROUGH" nếu ≥ 4/6 nến theo chiều signal
      "CHOP_AFTER_ENTRY"         nếu 2–3/6 nến theo chiều
      "REVERSAL_AFTER_ENTRY"     nếu ≤ 1/6 nến theo chiều

  [4F] Validate Filter Decisions (QUAN TRỌNG — không có trong audit cũ)
    Lấy signals bị MTF_BLOCK trong 7 ngày (từ log hoặc filter_extras field)
    Với mỗi blocked signal, simulate outcome (giống Bước 3):
      Nếu signal đó KHÔNG bị block, nó có WIN không?
    Tính:
      filter_correct_rate = (blocked signals that would have LOSS) / total_blocked
      → Nếu > 60%: filter đang hoạt động đúng
      → Nếu < 40%: filter quá aggressive, đang block winning trades

  Lưu vào: workspace/trade-audit-result/temp/component_validation_{date}.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 5 — STATISTICAL ANALYSIS
(Chạy sau Bước 3 + 4, cần ≥ 20 WIN/LOSS outcomes)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy: workspace/trade-audit-result/scripts/master_audit.py --step=5

Nếu WIN + LOSS < 20: bỏ qua bước này, ghi "INSUFFICIENT SAMPLE (N={count})"

  [5A] Win rate tổng thể và theo score bucket
    Tổng: win_rate, count, WIN, LOSS, PENDING, NO_DATA
    Theo bucket:
      Score 55–64  (WATCH cap): win_rate, count
      Score 65–74  (WATCH):     win_rate, count
      Score 75–79  (ALERT min): win_rate, count
      Score 80–89  (ALERT mid): win_rate, count
      Score 90+    (ALERT top): win_rate, count
    → Câu hỏi: Score cao hơn có thực sự win rate cao hơn không?
    → Nếu score 75–79 win_rate < 45%: cân nhắc tăng alert threshold lên 80

  [5B] Win rate theo module score (predictive value analysis)
    Score_OF > 0 vs = 0: win_rate mỗi nhóm
    Score_SMC > 15 vs ≤ 15: win_rate mỗi nhóm
    Score_VSA > 15 vs ≤ 15: win_rate mỗi nhóm
    Score_Context ≥ 11 vs < 11: win_rate mỗi nhóm
    → Module nào thực sự predict được outcome?
    → Module nào có win_rate tương đương → không add value?

  [5C] Win rate theo Regime
    TRENDING: win_rate, count
    RANGING:  win_rate, count
    CHOPPY:   win_rate, count
    → Nếu CHOPPY win_rate < 35%: xem xét block CHOPPY hoàn toàn

  [5D] Win rate theo Component Validation
    OB_HELD vs OB_BROKEN vs OB_NOT_TESTED: win_rate mỗi nhóm
    FVG_TOUCHED vs FVG_MISSED: win_rate mỗi nhóm
    1H_ALIGNED vs 1H_OPPOSING: win_rate mỗi nhóm
    MTF_ALIGNED vs MTF_OPPOSING: win_rate mỗi nhóm
    IMMEDIATE_FOLLOW_THROUGH vs CHOP vs REVERSAL: win_rate mỗi nhóm
    → Kết hợp nào có win_rate cao nhất? (ví dụ: OB_HELD + MTF_ALIGNED)

  [5E] Timing Analysis
    Avg candles_to_outcome: WIN vs LOSS (số nến 5m đến khi hit)
    % hit outcome trong 12 nến đầu (= 1 giờ đầu)
    % hit outcome trong 24 nến (= 2 giờ)
    % còn PENDING sau 96 nến (= 8 giờ)
    → Nếu > 60% hit trong 12 nến đầu: time invalidation 15 nến (15m) là hợp lý
    → Nếu < 30% hit trong 12 nến đầu: time invalidation cần tăng lên 30 nến

  [5F] SL/TP Calibration (dựa trên ATR, không phải % cố định)
    ATR tại thời điểm signal vs MAE khi WIN:
      Avg ATR × 1.5 (SL distance): X%
      Avg MAE khi WIN: Y%
      Nếu Y > X: SL đang bị sweep trước khi giá đi đúng hướng!
      → Cân nhắc tăng sl_atr_multiplier từ 1.5 lên 1.8 hoặc 2.0
    MFE khi LOSS vs TP1 distance:
      Avg MFE khi LOSS: Z% (giá đã đi bao xa theo chiều tốt trước khi quay đầu)
      TP1 distance = SL × 2.0
      Nếu avg MFE khi LOSS > TP1 × 0.7: giá thường gần TP nhưng không hit
      → Cân nhắc giảm tp1_rr_ratio từ 2.0 xuống 1.5

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 6 — MARKET PROFILE MATCHING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy: workspace/trade-audit-result/scripts/master_audit.py --step=6

Mục đích: thị trường hiện tại có phù hợp với profile của winning signals không?

  Từ Step 5: lấy "winning signal profile":
    Regime phổ biến nhất trong WIN: R_win
    Avg score_smc khi WIN: SMC_win
    MTF scenario phổ biến khi WIN: MTF_win
    Avg candles_to_outcome khi WIN: timing_win

  Với mỗi asset [BTC, ETH, SOL]:
    Regime hiện tại (từ Bước 2) = R_now
    MTF alignment hiện tại = MTF_now
    SMC score estimate hiện tại = SMC_estimate
    Match score = (R_now == R_win) + (MTF_now == MTF_win) + (SMC_estimate > SMC_win×0.7)

  Output cho mỗi asset:
    "BTC/USDT: Market match = HIGH/MEDIUM/LOW (N/3 conditions met)"
    Liệt kê điều kiện đang thiếu để đạt ALERT
    "Best setup hôm nay: {asset} {direction} — cần thêm {condition}"

  Nếu INSUFFICIENT SAMPLE:
    So sánh market hiện tại với signal_log 7 ngày (dùng regime + MTF_scenario như proxy)
    "Trong 7 ngày qua, {regime} regime có avg_score cao nhất = X"
    "Hiện tại {asset} đang ở {regime} → phù hợp / không phù hợp"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 7 — TẠO REPORT VÀ ĐỀ XUẤT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tạo folder: workspace/trade-audit-result/{YYYY-MM-DD}/

Tạo file: {YYYY-MM-DD}/master_report.md với cấu trúc:

  # Trading System Audit — {date}
  Generated: {timestamp UTC}

  ## System Status
  | Service | Status | Notes |
  |---------|--------|-------|
  | Redis   | OK/FAIL | |
  | Backend API | OK/FAIL | |
  | OB Feed | OK/MISS | age=Xs |
  | Delta   | OK/ZERO | |
  | Pipeline | ACTIVE/IDLE | last signal Xmin ago |

  ## Today's Signal Summary
  - Total: N | ALERT: N | WATCH: N | IGNORE: N
  - Score cap (OF=0): X% — nếu > 50% cảnh báo
  - Filter blocks: MTF_BLOCK=N, BTC_GUARD=N, CB=N
  - Dominant regime: {regime}
  - Avg scores: OF={x}/35, SMC={x}/30, VSA={x}/30, CTX={x}/15

  ## Validation Results (nếu đủ sample)
  - Validated signals: N (WIN: N, LOSS: N, PENDING: N)
  - Overall win rate: X% [insufficient / sufficient sample]

  ## Score Accuracy
  | Score Range | Win Rate | Count | Assessment |
  |-------------|----------|-------|------------|
  | 55–74 (WATCH) | X% | N | |
  | 75–89 (ALERT) | X% | N | |
  | 90+ | X% | N | |
  Kết luận: scoring có predictive value không?

  ## Component Analysis
  | Component | Condition | Win Rate | Conclusion |
  |-----------|-----------|----------|------------|
  | OB | OB_HELD | X% | |
  | OB | OB_BROKEN | X% | |
  | 1H Bias | Aligned | X% | |
  | MTF | Scenario A | X% | |
  | Price Action | Follow-through | X% | |
  Module có predictive value cao nhất: {module}
  Module không add value (win rate tương đương random): {module}

  ## SL/TP Calibration
  - Avg SL distance (ATR×1.5): X% | Avg MAE khi WIN: Y%
  - SL sweep risk: {HIGH/LOW}
  - Avg candles to outcome: WIN={N}×5m, LOSS={N}×5m
  - Time invalidation 15 nến: {HỢP LÝ / CẦN TĂNG lên N nến}

  ## Filter Effectiveness
  - MTF_BLOCK filter correct rate: X% (blocked signals that would have LOSS)
  - Verdict: {CORRECT / TOO_AGGRESSIVE / INSUFFICIENT_DATA}

  ## Best Setup Today
  Asset: {asset} | Direction: {long/short}
  Conditions met: {list}
  Missing for ALERT: {list}
  Score projection: {estimated range}/100

  ## Recommended Config Changes
  Chỉ đề xuất nếu có ≥ 20 outcomes và evidence rõ ràng:
  - {Thay đổi cụ thể} vì {evidence từ data}
  - Ví dụ: "Tăng sl_atr_multiplier từ 1.5 → 1.8 vì avg MAE khi WIN = 1.7% > SL = 1.5%"
  Nếu không đủ data: "Chưa đủ sample — theo dõi thêm {N} ngày"

Tạo file: {YYYY-MM-DD}/raw_signals.csv
  log_id, timestamp, asset, direction, final_score, entry_price, sl, tp1,
  score_of, score_smc, score_vsa, score_ctx, score_bonus, regime,
  simulated_outcome, candles_to_outcome, mae_pct, mfe_pct,
  ob_validation, fvg_validation, bias_1h_validation, mtf_validation, pa_validation

Tạo file: {YYYY-MM-DD}/filter_analysis.csv
  signal_id, timestamp, asset, direction, block_reason,
  would_have_been: WIN/LOSS/PENDING, filter_correct: True/False
```

---

## SCRIPT: workspace/trade-audit-result/scripts/master_audit.py

Script cần tạo mới. Yêu cầu:

```python
"""
master_audit.py — Master Audit & Signal Validation Tool
=========================================================
Kết hợp daily audit + signal validation vào 1 script.

Chạy: python master_audit.py --step=0|1|2|3|4|5|6|7|all
      python master_audit.py --step=all  (chạy toàn bộ)
      python master_audit.py --step=0,1,2  (chạy subset)

Dependencies: sqlalchemy, ccxt, pandas, numpy, pathlib, argparse
              (tất cả đã có trong backend-workspace .venv)

Database: SQL Server via _db.py (không dùng SQLite)
Exchange: Binance public API cho BTC/ETH/SOL price data
          (không cần API key, endpoint /api/v3/klines)

QUAN TRỌNG:
  - Binance symbol format: "BTC/USDT" → "BTCUSDT" (bỏ dấu /)
  - startTime cho Binance API: Unix milliseconds
  - Rate limit: sleep 0.2s giữa mỗi request
  - 1H bias = EMA200(1H) based, KHÔNG phải RSI threshold
  - MTF bias = EMA200(4H) + ADX(14), KHÔNG phải EMA20/50
  - SL = ATR × 1.5, TP1 = SL_dist × 2.0 — KHÔNG phải % cố định
  - Chỉ validate BTC/USDT, ETH/USDT, SOL/USDT
"""
```

---

## CHECKLIST sau mỗi lần chạy

### Daily (Bước 0–2):
- [ ] Tất cả 4 services đang chạy?
- [ ] OB feed có data < 60s cho cả 3 assets?
- [ ] OHLCV buffer đủ (BTC/ETH/SOL n≥200)?
- [ ] Last signal < 20 phút? (pipeline active)
- [ ] Có ALERT signal nào hôm nay? Nếu không: tại sao?
- [ ] MTF_BLOCK rate < 60%?
- [ ] Regime đang là gì? Setup tốt nhất hôm nay?

### Weekly (Bước 3–7, cần ≥20 signals):
- [ ] Simulated win rate ≥ 50%? (minimum viable)
- [ ] Score có predictive value? (higher score → higher win rate?)
- [ ] OB_HELD có win rate cao hơn OB_BROKEN?
- [ ] MTF_ALIGNED có win rate cao hơn MTF_OPPOSING?
- [ ] SL distance (ATR×1.5) có lớn hơn avg MAE khi WIN?
- [ ] MTF filter có correct rate > 60%?
- [ ] Có config change nào được recommend không?

---

## Khi nào chạy

| Tình huống | Steps | Frequency |
|---|---|---|
| Hàng ngày | 0, 1, 2 | Mỗi ngày |
| Sau 7 ngày (đủ sample) | 0, 1, 2, 3, 4, 5, 6, 7 | Mỗi tuần |
| Sau thay đổi config | 1, 5 (với data cũ để compare) | Sau mỗi thay đổi |
| Win rate giảm | 3, 4, 5 | Khi cần diagnose |
| Trước go-live | 0→7 toàn bộ, yêu cầu win_rate ≥ 52% | Một lần trước live |

---

## Lưu ý quan trọng

- **Database**: SQL Server (localhost:1433), không dùng SQLite
- **Market data**: Binance public API cho BTC/ETH/SOL
- **Không sửa signal_log**: script chỉ đọc, không ghi vào DB gốc
- **Outcome = simulated**: Hệ thống đang testnet — outcomes là mô phỏng từ price, không phải P&L thực
- **Minimum sample**: 20 WIN+LOSS cho kết quả có ý nghĩa thống kê
- **PENDING không tính vào win rate**
- **Raw data luôn được lưu** để re-analyze sau
- **Timestamp UTC** trên mọi file output

*Phiên bản v2.0 — Thay thế AUDIT_PROMPT.md + SIGNAL_VALIDATION_PROMPT.md*
*Cập nhật: 2026-05-16 — Loại VELO/USDT, sửa MTF/Context validation logic*
