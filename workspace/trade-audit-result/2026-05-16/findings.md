# Trading System Audit — 2026-05-16

**Thoi gian audit:** 2026-05-16 ~14:07 UTC
**Scripts:** audit_signals, market_analysis, check_config, debug_smc

---

## BUOC 1 — Signal Log (SQL Server)

### Tong quan database
- Tong signals: 12,159
- Date range: 2026-05-13 -> 2026-05-16
- Unique assets: 2 (VELO/USDT, BTC/USDT)
- Unique strategies: 1 (scoring_engine)
- Tong ALERT all-time: **0**
- Tong trades da dong: **0**

### Phan tich hom nay (2026-05-16)
- Tong signals: 10,116
- ALERT: 0 | WATCH: 0 | IGNORE: 10,116 (100%)
- Score avg: 6.3/100 | Score max: 38/100

### [FINDING 1] Khong co ALERT nao tu truoc den nay
Score max = 38/100, nguong ALERT = 75.
Khoang cach 37 diem khong dat duoc do 3 nguyen nhan chinh.

---

## BUOC 2 — Phan tich thi truong live (14:07 UTC)

| Symbol    | Price     | Regime          | Daily   | 4H      | 1H      | RSI  | MaxScore |
|-----------|-----------|-----------------|---------|---------|---------|------|----------|
| BTC/USDT  | $77,894   | TRENDING ADX=52 | NEUTRAL | RANGING | BEARISH | 38.9 | 60/100   |
| ETH/USDT  | $2,173    | TRENDING ADX=52 | BEAR    | RANGING | BEARISH | 37.1 | 60/100   |
| SOL/USDT  | $86.08    | TRENDING ADX=55 | BEAR    | BEARISH | BEARISH | 34.9 | 60/100   |

### [FINDING 2] Tat ca assets bi cap tai 60/100 (duoi ALERT threshold 75)
Nguyen nhan: OrderBookService + DeltaService chua chay
-> order_book_available = False -> score bi cap 60/100
Impact: Ngay ca khi SMC/VSA perfect, score van khong bao gio >= 75

### [FINDING 3] MTF Scenario cho SHORT signals
- BTC, ETH: 4H=RANGING, 1H=BEARISH -> SHORT -> Scenario B (size x0.5, score -10)
- SOL: Daily=BEAR, 4H=BEARISH, 1H=BEARISH -> SHORT -> Scenario A (score +10)
- SOL SHORT la setup tot nhat neu OB feed hoat dong

---

## BUOC 3 — Config Check

| Parameter         | Value | Status |
|-------------------|-------|--------|
| trigger_timeframe | 15m   | OK (da fix tu 5m sang 15m luc 12:44 hom nay) |
| alert_threshold   | 75    | OK     |
| tp1_rr_ratio      | 2.0   | OK     |
| tp2_rr_ratio      | 3.0   | OK     |
| min_net_rr        | 1.5   | OK     |
| testnet           | True  | OK (dang test mode) |
| exchange          | gate  | OK     |

### [FINDING 4] Chi co 1 asset active: VELO/USDT
Exchange = gate, asset active duy nhat = VELO/USDT.
BTC/USDT xuat hien trong signal_log nhung khong co trong exchange_assets.

### Config version history (important)
- v1.0 (2026-05-05): trigger_timeframe = 15m  <- dung
- v2026.05.07 + v2026.05.08: trigger_timeframe = 5m <- SAI, 10,051 signals bi anh huong
- v2026.05.16-fix-timeframe: trigger_timeframe = 15m <- da fix hom nay 12:44

---

## BUOC 4 — Debug SMC (avg = 1.8/30)

BTC/USDT live debug luc 14:07 UTC:

| Component | Ket qua | Ly do |
|-----------|---------|-------|
| CHoCH     | NONE    | Price trong swing range $77,730-$78,163, can break out |
| OB retest | FALSE   | 1 OB bearish tai $79,394-$79,532 nhung cach xa 1.98% |
| FVG       | FALSE   | FVG mid=$78,177, cach 0.330% nhung tolerance chi 0.300% |

### [FINDING 5] FVG miss do tolerance qua chat
fvg_touch_tolerance_pct = 0.001 (0.1%) -> chi 0.3% distance nhung van khong qua
De nghi tang len 0.003 (0.3%) -> FVG se duoc tinh diem hon
Luu y: SMC = 0 do thi truong consolidating - day la hanh vi binh thuong

---

## Module Score Summary

| Module     | Avg hom nay | Max  | % dat | Nguyen nhan |
|------------|-------------|------|-------|-------------|
| Order Flow | 2.2/35      | 35   | 6%    | OB + Delta feed OFF |
| SMC        | 1.8/30      | 30   | 6%    | Price consolidating |
| VSA        | 9.8/30      | 30   | 33%   | Hoat dong, hop ly |
| Context    | 6.1/15      | 15   | 41%   | OK |
| Bonus      | 1.3/15      | 15   | 9%    | Can SMC working truoc |

---

## Circuit Breaker
OK - Khong co lock event nao (chua co trade nao)

---

## CHECKLIST

| Item                             | Status | Notes |
|----------------------------------|--------|-------|
| signal_log co data hom nay?      | OK     | 10,116 signals |
| Co ALERT signal nao khong?       | NONE   | Score max=38, can >=75 |
| Order Flow = 0?                  | WARN   | 89% signals OF=0, OB feed chua chay |
| trigger_timeframe = 15m?         | OK     | Da fix sang 15m |
| SMC avg > 5/30?                  | FAIL   | SMC=1.8 - consolidating |
| Circuit breaker locked?          | OK     | Khong locked |
| Thi truong regime?               | OK     | TRENDING manh ADX 52-55 |
| Setup trade tot nhat hom nay?    | SOL    | SOL/USDT SHORT khi OB feed chay, Scenario A |
