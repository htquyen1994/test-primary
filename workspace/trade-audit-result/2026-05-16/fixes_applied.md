# Fixes Applied — 2026-05-16

**Audit session:** 2026-05-16 ~14:07 UTC
**Thuc hien fixes:** 2026-05-16 ~14:30 UTC

---

## A. FIX DA THUC HIEN TRONG PHIEN NAY

---

### [FIX-A1] CRITICAL — Them 3 assets vao exchange_assets (DB)

**Thoi gian:** 2026-05-16 14:30 UTC
**Van de:** Chi co VELO/USDT trong exchange_assets.
BTC/USDT (6,048 signals hom nay) khong duoc OrderBookService/DeltaService poll
vi assets list chi lay tu exchange_assets table.
Ket qua: tat ca BTC signals co OF=0, score bi cap 60.

**Phan tich truoc khi fix:**
  - Gate.io fetch_order_book test:
    - BTC/USDT  OK  mid=$78,034
    - ETH/USDT  OK  mid=$2,178
    - SOL/USDT  OK  mid=$86.22
    - Tat ca format 'SYMBOL/USDT' deu OK tren Gate.io public API

**Fix thuc hien:**
  - Them vao DB bang exchange_assets (INSERT truc tiep qua Python/SQLAlchemy):
    - BTC/USDT  enabled=True  leverage_override=10
    - ETH/USDT  enabled=True  leverage_override=7
    - SOL/USDT  enabled=True  leverage_override=5
  - VELO/USDT giu nguyen (leverage=None, dung default 5x)

**Tac dong sau fix:**
  - Data Pipeline restart -> assets = [BTC/USDT, ETH/USDT, SOL/USDT, VELO/USDT]
  - OB poll moi 5s cho ca 4 symbols
  - Delta poll moi 10s cho ca 4 symbols
  - BTC signals se co OB data -> score cap 60 se duoc giai phong
  - Du kien: BTC score co the dat 37-47 hien tai (chua co ALERT),
    khi OB feed co data tot hon va cac conditions met -> co the dat 55-75

**Action tiep theo:**
  Restart Data Pipeline: Ctrl+C python main.py -> chay lai

---

### [FIX-A2] LOW — Wire SMC params tu DB trading_params vao code

**Thoi gian:** 2026-05-16 14:35 UTC
**Van de:** Ba parameters trong trading_params KHONG duoc su dung boi smc.py:
  - fvg_touch_tolerance_pct = 0.001 (trong DB) <- khong duoc doc
  - ob_atr_multiplier = 1.5 (trong DB)         <- khong duoc doc
  - swing_lookback = 20 (trong DB)              <- khong duoc doc
  smc.py chi dung hardcoded module constants.

**Root cause:**
  compute_smc_score() khong nhan config params, FairValueGap.is_price_at_midpoint()
  chi dung FVG_TOUCH_TOLERANCE constant (0.003).

**Fix thuc hien (commit e66d42c):**

  1. engine/smc.py:
     - compute_smc_score() them params: fvg_tolerance, swing_lookback
     - FairValueGap.is_price_at_midpoint() them param: tolerance
     - Fallback ve module constants khi caller khong truyen

  2. engine/scoring_service.py:
     - Load ob_atr_multiplier, fvg_touch_tolerance_pct, swing_lookback
       tu DB trading_params (via get_active_trading_params)
     - Truyen vao ca 2 luc goi compute_smc_score() (Pass 1 va Pass 2)
     - Fallback gracefully neu DB unavailable

**Ket qua test:**
  fvg.is_price_at_midpoint(77920, tol=0.003) -> False (dung, distance=0.33%)
  fvg.is_price_at_midpoint(77920, tol=0.005) -> True
  fvg.is_price_at_midpoint(78100, tol=0.003) -> True
  Imports OK, logic dung.

**Tac dong:**
  - fvg_touch_tolerance_pct trong DB (hien tai 0.001) se duoc su dung
  - De tang FVG hit rate: vao /config/trading -> tang fvg_touch_tolerance_pct
    tu 0.001 len 0.003 (khong can restart, hot-reload)
  - Khong thay doi hành vi hien tai vi DB value 0.001 < module constant 0.003

---

## B. FIX DA THUC HIEN TRUOC PHIEN NAY (lich su)

### [PRE-FIX-1] trigger_timeframe 5m -> 15m (2026-05-16 12:44 UTC)
- Version DB: v2026.05.16-fix-timeframe
- Van de: 5m trigger lam scoring chay tren data chua du
- Fix: doi trigger_timeframe = '15m' trong trading_params qua /config/trading

### [PRE-FIX-2] circuit_breaker_state table (truoc do)
- migration 003 duoc fix (SQL Server syntax) va chay thanh cong
- Table circuit_breaker_state da ton tai

### [PRE-FIX-3] scoring_service score_adjustment bug
- Bug: r.score_adjustment tren dict object (phai dung r.get())
- Fix: engine/scoring_service.py line 357

### [PRE-FIX-4] migration 004 (trading_params patch)
- Them column min_net_rr (truoc do khong co trong DB)
- Fix tp1_rr_ratio/tp2_rr_ratio defaults (1.5/2.5 -> 2.0/3.0)

---

## C. HANH DONG CON LAI (chua thuc hien)

### [TODO-1] Restart Data Pipeline — BAN PHAI LAM THU CONG
  Sau khi da them assets vao DB, can restart main.py:
    Ctrl+C   (dung data pipeline hien tai)
    python main.py  (chay lai, se load 4 assets moi)
  
  Sau restart, OrderBookService va DeltaService se poll:
    gate exchange: BTC/USDT, ETH/USDT, SOL/USDT, VELO/USDT

### [TODO-2] Tang fvg_touch_tolerance_pct trong /config/trading
  Hien tai DB = 0.001 (0.1%), module constant = 0.003 (0.3%)
  De tang: /config/trading -> fvg_touch_tolerance_pct = 0.003
  -> Se duoc ap dung ngay (hot-reload, khong can restart)
  LUU Y: Nen chay backtest sau khi tang de xac nhan impact

### [TODO-3] Theo doi SOL/USDT SHORT setup
  Khi OB feed chay voi 4 assets moi:
  SOL: Daily=BEAR, 4H=BEARISH, 1H=BEARISH -> Scenario A (+10 score)
  Day la setup tot nhat trong 3 assets theo audit hom nay.

---

## D. SCORE PROJECTION SAU KHI RESTART

| Symbol   | Hien tai (no OB) | Du kien sau restart | Notes |
|----------|------------------|---------------------|-------|
| BTC/USDT | max 37/100       | 55-70/100           | Can CHoCH de tang SMC |
| ETH/USDT | max 37/100       | 55-70/100           | Tuong tu BTC |
| SOL/USDT | max 34/100       | 65-80/100           | Scenario A +10, co the ALERT! |
| VELO/USDT| max 38/100       | 50-65/100           | Thanh khoan thap |

SOL/USDT co co hoi ALERT cao nhat khi:
  - OB feed cung cap bid/ask data
  - CHoCH break xay ra
  - FVG midpoint duoc cham
  - Tat ca Scenario A conditions met
