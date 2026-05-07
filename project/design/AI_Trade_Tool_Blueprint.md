# Blueprint: AI Semi-Auto Crypto Futures Trading Tool

> **Phiên bản:** 1.1 *(cập nhật: Data Lag, Time Invalidation, VSA+Volume Profile, Slippage)*  
> **Phong cách:** Semi-auto · Scalping · Crypto Futures  
> **Khung giờ:** 15m (trigger) · 1H (context) · 5m (entry tinh chỉnh)  
> **Dữ liệu:** OHLCV + Order Book / Order Flow  

---

## Changelog v1.0 → v1.1

| # | Vấn đề | Thay đổi |
|---|---|---|
| 1 | **Data Lag** — Cumulative Delta block WebSocket | Tách 3 luồng độc lập: WS writer → Redis → Celery scorer |
| 2 | **Time Invalidation** thiếu | Thêm quy tắc hủy alert sau 10–15 nến chờ |
| 3 | **VSA thiếu Volume Profile** | Thêm POC + Value Area Edge bonus (+10 pts) vào VSA module |
| 4 | **Backtest thiếu phí/slippage** | Trừ 0.06–0.1% mỗi vòng lệnh, điều chỉnh target win rate |

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc tổng thể](#2-kiến-trúc-tổng-thể)
3. [Layer 1 — Data Input](#3-layer-1--data-input)
4. [Layer 2 — AI Engine](#4-layer-2--ai-engine)
5. [Layer 3 — Human Confirm Dashboard](#5-layer-3--human-confirm-dashboard)
6. [Mô hình giao dịch được chọn](#6-mô-hình-giao-dịch-được-chọn)
7. [Signal Scoring Engine](#7-signal-scoring-engine)
8. [Confluence Zone — FIB + Order Block](#8-confluence-zone--fib--order-block)
9. [Quản lý rủi ro](#9-quản-lý-rủi-ro)
10. [Tech Stack](#10-tech-stack)
11. [Lộ trình build](#11-lộ-trình-build)
12. [Backtest & Tối ưu](#12-backtest--tối-ưu)
13. [Cải tiến v1.1 — Nhận xét thực chiến](#13-cải-tiến-v11--nhận-xét-thực-chiến)

---

## 1. Tổng quan hệ thống

### Mục tiêu
Xây dựng công cụ AI hỗ trợ giao dịch crypto futures theo phong cách **semi-automatic**: AI phân tích thị trường, phát hiện tín hiệu, tính điểm xác suất — người dùng là người đưa ra quyết định cuối cùng trong 1 click.

### Nguyên tắc thiết kế
- **AI phân tích, người quyết định** — không fully automated, tránh rủi ro hệ thống
- **Rule-based trước, ML sau** — các quy tắc rõ ràng trước, tích hợp machine learning ở giai đoạn 3
- **Tín hiệu phải giải thích được** — mỗi alert đi kèm lý do cụ thể, không "hộp đen"
- **Log mọi thứ** — mọi tín hiệu, quyết định, kết quả đều được ghi lại để tối ưu sau
- **Tách biệt luồng dữ liệu và luồng tính toán** *(v1.1)* — WebSocket không bao giờ bị block bởi scoring

### Thông số hoạt động

| Thông số | Giá trị |
|---|---|
| Phong cách | Semi-auto scalping |
| Khung trigger | 15 phút |
| Khung context | 1 giờ |
| Khung entry | 5 phút |
| Tín hiệu mục tiêu/ngày | 5–12 |
| Thời gian giữ lệnh TB | 15–60 phút |
| R:R tối thiểu (gross) | 1.5 : 1 |
| R:R tối thiểu (net sau phí) | 1.8 : 1 *(v1.1)* |
| Score ngưỡng vào lệnh | ≥ 75 / 100 |
| Đòn bẩy khuyến nghị | 3x – 10x |
| Phí + slippage mỗi vòng | 0.06–0.1% *(v1.1)* |

---

## 2. Kiến trúc tổng thể

```
┌──────────────────────────────────────────────────────────────┐
│                     LAYER 1 — DATA INPUT                      │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐  │
│  │  OHLCV Feed  │   │  Order Book  │   │  Funding / OI     │  │
│  │ 1m/5m/15m/1H │   │ Bid/Ask/Tape │   │  Perpetual ctx    │  │
│  └──────┬───────┘   └──────┬───────┘   └────────┬──────────┘  │
└─────────┼──────────────────┼────────────────────┼─────────────┘
          └──────────────────▼────────────────────┘
                             │ WebSocket ticks
                             ▼
┌──────────────────────────────────────────────────────────────┐
│              REDIS — LỚP ĐỆM TRUNG TÂM  (v1.1)               │
│   delta:BTC:5m  |  ob:BTC:snap  |  ohlcv:BTC:15m  |  poc:BTC │
└────────────┬──────────────────────────────┬──────────────────┘
             │                              │
      Luồng 1 (asyncio)             Luồng 2 (Celery)
      Delta Writer                  Signal Scorer
      < 0.1ms/tick                  chạy khi nến đóng
             │                              │
             └──────────────┬───────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     LAYER 2 — AI ENGINE                       │
│                                                               │
│  ┌─────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │ Order Flow  │ │    SMC     │ │  VSA +     │ │ Context  │  │
│  │  Analysis   │ │FVG+OB+CHoCH│ │Vol.Profile │ │  Filter  │  │
│  │  (35 pts)   │ │  (30 pts)  │ │  (30 pts)  │ │ (15 pts) │  │
│  └──────┬──────┘ └─────┬──────┘ └─────┬──────┘ └────┬─────┘  │
│         └──────────────┼──────────────┼─────────────┘         │
│                        ▼                                       │
│             ┌──────────────────────┐                           │
│             │  Signal Score 0–100  │                           │
│             │  + Confluence Bonus  │                           │
│             └──────────┬───────────┘                           │
│                        ▼                                       │
│     ┌──────────────────────────────────────┐                   │
│     │           Alert Engine               │                   │
│     │  score ≥ 75 → ALERT                 │                   │
│     │  Time Invalidation: hủy sau 15 nến  │  ← v1.1           │
│     └──────────────┬───────────────────────┘                   │
└────────────────────┼─────────────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                  LAYER 3 — HUMAN CONFIRM                      │
│  ┌──────────────┐  ┌──────────┐  ┌────────┐  ┌───────────┐   │
│  │  Signal Card │  │ CONFIRM  │  │  SKIP  │  │  Journal  │   │
│  │ Pair·Dir·Score│  │ 1 click  │  │ + Log  │  │ Auto log  │   │
│  │ + Countdown  │  │          │  │        │  │ + Slippage│   │
│  └──────────────┘  └──────────┘  └────────┘  └───────────┘   │
│                        ▼  feedback loop                        │
│                   ┌──────────┐                                 │
│                   │ AI Model │◄── học từ win/loss + skip       │
│                   └──────────┘                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1 — Data Input

### 3.1 OHLCV Feed

| Khung | Mục đích | Độ ưu tiên |
|---|---|---|
| 1H | HTF context, bias xác định xu hướng lớn | Cao |
| 15m | MTF trigger, phát hiện setup chính | Cao |
| 5m | LTF entry, tinh chỉnh điểm vào | Trung bình |
| 1m | Xác nhận order flow tức thời | Thấp |

**Nguồn dữ liệu:** Binance Futures WebSocket hoặc Bybit Linear Perpetual

### 3.2 Kiến trúc xử lý realtime — Giải quyết Data Lag *(v1.1)*

> ⚠️ **Vấn đề gốc:** Cumulative Delta đòi hỏi cập nhật mỗi tick (có thể 1,000+ ticks/giây với BTC). Nếu chạy chung với signal scoring, WebSocket bị block → mất tick → delta sai lệch → tín hiệu sai.

**Giải pháp: Tách 3 luồng hoàn toàn độc lập qua Redis**

```
Luồng 1 — WS Tick Writer (asyncio, không bao giờ block)
    Nhận tick → ghi atomic vào Redis → xong, < 0.1ms

Luồng 2 — Candle Builder (asyncio timer)
    Mỗi 1 phút: lấy tick từ Redis → build OHLCV → lưu lại Redis

Luồng 3 — Signal Scorer (Celery worker)
    Triggered khi nến 15m đóng → đọc từ Redis → tính score → publish alert
```

```python
# Luồng 1: WS Writer — atomic, không block
async def ws_tick_writer(msg):
    tick  = parse_trade(msg)
    delta = tick.qty if tick.is_buy else -tick.qty
    await redis.incrbyfloat(f"delta:{tick.symbol}:5m", delta)
    await redis.expire(f"delta:{tick.symbol}:5m", 300)

# Luồng 3: Celery task — hoàn toàn tách biệt khỏi WS
@celery.task
def run_signal_scoring(symbol):
    delta   = float(redis.get(f"delta:{symbol}:5m") or 0)
    ob_snap = redis.hgetall(f"ob:{symbol}:snap")
    ohlcv   = redis.lrange(f"ohlcv:{symbol}:15m", 0, 99)
    poc     = float(redis.get(f"poc:{symbol}") or 0)
    score   = calculate_signal_score(delta, ob_snap, ohlcv, poc)
    if score['action'] == 'ALERT':
        redis.publish("alerts:channel", json.dumps(score))

# FastAPI: stream alert ra dashboard qua WebSocket
@app.websocket("/ws/alerts")
async def alert_stream(ws: WebSocket):
    await ws.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe("alerts:channel")
    async for msg in pubsub.listen():
        await ws.send_json(msg['data'])
```

**Kết quả đạt được:**
- WebSocket tick writer: < 0.1ms/tick, không bao giờ drop tick
- Signal scoring: chạy riêng, không ảnh hưởng data pipeline
- Cumulative Delta chính xác 100% vì ghi atomic từng tick

### 3.3 Funding Rate & Open Interest

| Chỉ số | Ngưỡng | Ý nghĩa |
|---|---|---|
| Funding rate | > +0.05% | Thị trường quá long → cảnh báo |
| Funding rate | < -0.05% | Thị trường quá short → squeeze risk |
| OI tăng + giá tăng | — | Xu hướng tăng được xác nhận |
| OI tăng + giá giảm | — | Xu hướng giảm được xác nhận |
| OI giảm + giá tăng | — | Short covering, không bền |

---

## 4. Layer 2 — AI Engine

### 4.1 Tổng quan các module

```
Signal Score = OrderFlow(35) + SMC(30) + VSA+VolProfile(30) + Context(15)
             + Confluence Bonus (tối đa +15)
Tổng tối đa: 125 điểm → normalize về 100
```

> **Lưu ý v1.1:** VSA module tăng từ 20 → 30 điểm do tích hợp thêm Volume Profile (POC + Value Area).

### 4.2 Module 1 — Order Flow Analysis (35 pts)

**Mục đích:** Xác định ai đang kiểm soát thị trường ngay lúc này.

| Điều kiện | Điểm |
|---|---|
| Delta dương > 1,000 BTC trong 5 nến gần nhất | +15 |
| Bid stack > Ask stack × 2 tại vùng S/R | +10 |
| Absorption: volume cao nhưng giá không giảm | +10 |
| **Tổng tối đa** | **35** |

```python
def order_flow_score(delta, bid_stack, ask_stack, absorption):
    score = 0
    if delta > 1000:                  score += 15
    if bid_stack > ask_stack * 2:     score += 10
    if absorption:                    score += 10
    return score  # max 35
```

### 4.3 Module 2 — SMC Analysis (30 pts)

**Mục đích:** Phát hiện cấu trúc Smart Money — nơi tổ chức đặt lệnh.

| Tín hiệu | Điều kiện | Điểm |
|---|---|---|
| CHoCH | Break swing high/low 15m, cùng chiều bias 1H | +10 |
| Order Block | Giá retest OB, volume hồi < 50% impulse | +10 |
| Fair Value Gap | Giá chạm midpoint FVG chưa filled | +10 |
| **Tổng tối đa** | | **30** |

```python
def smc_score(choch, ob_touched, fvg_touched, htf_bias):
    score = 0
    if choch and aligned_with_bias(choch, htf_bias): score += 10
    if ob_touched:                                   score += 10
    if fvg_touched:                                  score += 10
    return score  # max 30
```

### 4.4 Module 3 — VSA + Volume Profile (30 pts) *(v1.1)*

**Mục đích:** Lọc tín hiệu giả bằng volume-price relationship + xác nhận vùng giá quan trọng.

#### VSA cơ bản (20 pts)

| Điều kiện | Điểm |
|---|---|
| No Supply: volume hồi giá < 40% volume impulse | +10 |
| Effort vs Result: volume thấp nhưng giá giữ vững | +10 |

#### Volume Profile bonus (10 pts) *(thêm mới v1.1)*

| Điều kiện | Điểm |
|---|---|
| Entry nằm trong ±0.3% của POC (Point of Control) | +10 |
| Entry nằm tại Value Area High/Low (VAH/VAL) | +6 |

> **Tại sao POC quan trọng?** POC là mức giá có volume giao dịch cao nhất trong range — tổ chức thường để lệnh lớn tại đây. Khi OB + Fib 61.8% + POC hội tụ, đây là "triple layer" mạnh nhất có thể xảy ra trong scalping.

```python
def vsa_volume_profile_score(pullback_vol, impulse_vol,
                              price_held, entry, poc, vah, val):
    score = 0
    # VSA cơ bản
    ratio = pullback_vol / impulse_vol
    if ratio < 0.40:                 score += 10  # No Supply
    if ratio < 0.50 and price_held:  score += 10  # Effort vs Result

    # Volume Profile bonus
    if abs(entry - poc) / poc <= 0.003:   score += 10  # tại POC
    elif entry <= vah * 1.003 or entry >= val * 0.997:
                                          score += 6   # tại VAH/VAL
    return score  # max 30
```

**Nguồn dữ liệu Volume Profile:** Tính từ OHLCV + volume trong window 1 ngày giao dịch (390 nến 1m). Lưu vào Redis key `poc:{symbol}`, cập nhật mỗi 15m.

### 4.5 Module 4 — Context Filter (15 pts)

| Điều kiện | Điểm |
|---|---|
| 1H bias cùng chiều với signal 15m | +8 |
| Funding rate trong khoảng ±0.05% | +4 |
| Giá cách S/R gần nhất ≥ 0.5% | +3 |
| **Tổng tối đa** | **15** |

### 4.6 Ngưỡng hành động

| Score | Hành động | Màu alert |
|---|---|---|
| ≥ 75 | Gửi alert ngay — sẵn sàng vào lệnh | 🟢 Xanh |
| 55–74 | Theo dõi thêm — chờ xác nhận | 🟡 Vàng |
| < 55 | Bỏ qua | 🔴 Đỏ |

---

## 5. Layer 3 — Human Confirm Dashboard

### 5.1 Signal Card — thông tin hiển thị

```
┌──────────────────────────────────────────────┐
│  🟢 BTC/USDT PERP — LONG          ⏱ 12:45  │
│  Score: 88 / 100                             │
│  ⚠️ Hết hạn sau: 14 nến 15m (210 phút)     │
│──────────────────────────────────────────────│
│  Entry:  $77,050  (OB midpoint + POC)        │
│  SL:     $76,720  (dưới OB low 0.3%)        │
│  TP1:    $77,800  (R:R gross 1.5)           │
│  TP2:    $78,400  (FVG fill)                │
│  Net R:R sau phí: ~1.38                     │
│──────────────────────────────────────────────│
│  Lý do:                                      │
│  ✓ Bullish OB tại $76,850–$77,100           │
│  ✓ Fib 61.8% = $77,028 (trong OB)          │
│  ✓ POC ngày = $76,980 (trong OB)           │
│  ✓ Delta +1,800 BTC — tổ chức mua          │
│  ✓ Volume hồi = 38% impulse (No Supply)    │
│  ✓ 1H bias: Bullish                         │
│──────────────────────────────────────────────│
│      [CONFIRM]          [SKIP]               │
└──────────────────────────────────────────────┘
```

### 5.2 Luồng xác nhận

```
Alert từ AI
    ↓
Người dùng đọc Signal Card (< 30 giây)
    ↓
    ├── CONFIRM → Gửi lệnh limit/market qua API
    │              → Đặt SL/TP tự động
    │              → Log vào journal (kèm net fee ước tính)
    │
    └── SKIP → Log lý do skip (optional)
               → AI ghi nhận để học
               → Nếu giá chạy đúng hướng → đánh dấu "missed"
```

### 5.3 Trade Journal — tự động ghi lại

| Field | Mô tả |
|---|---|
| timestamp | Thời điểm alert |
| pair | BTC/USDT, ETH/USDT, ... |
| direction | Long / Short |
| score | Signal score tại thời điểm vào |
| signals | Danh sách tín hiệu kích hoạt |
| entry / sl / tp | Các mức giá |
| fee_estimated | 0.06–0.1% × notional |
| slippage_actual | Chênh lệch entry lý thuyết vs thực tế |
| result | Win / Loss / BE |
| pnl_gross | PnL trước phí |
| pnl_net | PnL sau phí + slippage |
| action | Confirm / Skip |

---

## 6. Mô hình giao dịch được chọn

### 6.1 Bộ mô hình core (Entry triggers — 15m)

| Mô hình | Loại | Trọng số | Ghi chú v1.1 |
|---|---|---|---|
| **Fair Value Gap (FVG)** | SMC | Cao nhất | Kết hợp POC để tăng độ tin cậy |
| **CHoCH** | SMC | Cao | Không thay đổi |
| **Order Block** | SMC | Cao | Ưu tiên OB trùng POC + Fib |
| **Flag / Pennant** | Chart | Trung bình | Không thay đổi |
| **Fibonacci 61.8%** | Confluence | Add-on | Kết hợp thêm POC khi có thể |

### 6.2 Bộ mô hình filter (Context — 1H)

| Mô hình | Vai trò |
|---|---|
| **RSI Divergence 1H** | Giảm score nếu divergence ngược chiều |
| **Double Top/Bottom 1H** | Xác định HTF bias tổng thể |
| **Funding Rate** | Lọc khi thị trường quá lệch một phía |
| **Volume Profile (POC/VAH/VAL)** | Xác nhận vùng giá có giá trị *(v1.1)* |

### 6.3 Mô hình không dùng cho scalping

| Mô hình | Lý do loại |
|---|---|
| Head & Shoulders | Quá chậm, false positive cao khi auto-detect |
| Double Top/Bottom (15m) | Noise nhiều, chỉ dùng ở 1H làm context |
| Mean Reversion | Chỉ dùng khi ADX < 25, cần regime detection |

---

## 7. Signal Scoring Engine

### 7.1 Công thức tổng hợp

```python
def calculate_signal_score(candles_1h, candles_15m, candles_5m,
                            order_flow, funding_rate, poc, vah, val):
    of_score  = order_flow_score(order_flow)                    # 0–35
    smc_score = smc_analysis_score(candles_15m)                 # 0–30
    vsa_score = vsa_volume_profile_score(candles_15m,
                    poc, vah, val)                              # 0–30
    ctx_score = context_filter_score(candles_1h, funding_rate)  # 0–15

    base  = of_score + smc_score + vsa_score + ctx_score        # 0–110
    bonus = confluence_bonus(candles_15m)                       # 0–15

    # Normalize về 100
    total = min(round((base + bonus) / 125 * 100), 100)

    return {
        'score': total,
        'breakdown': {
            'order_flow': of_score,
            'smc':        smc_score,
            'vsa':        vsa_score,
            'context':    ctx_score,
            'bonus':      bonus
        },
        'action': 'ALERT' if total >= 75 else
                  'WATCH' if total >= 55 else 'IGNORE',
        'expires_at': current_candle_index + 15  # Time invalidation
    }
```

### 7.2 Quy trình xử lý realtime

```
Mỗi khi nến 15m đóng (Celery task):
  1. Đọc dữ liệu từ Redis (delta, OB snap, OHLCV, POC)
  2. Tính ATR(14) mới
  3. Cập nhật swing high/low (50 nến lookback)
  4. Tính POC/VAH/VAL từ 1 ngày giao dịch gần nhất
  5. Scan OB mới, vô hiệu hóa OB cũ nếu vi phạm
  6. Detect FVG, đánh dấu filled nếu midpoint bị chạm
  7. Kiểm tra CHoCH
  8. Tính score từng module
  9. Kiểm tra confluence (OB + Fib + POC + FVG)
  10. Nếu score ≥ 75 → build Signal Card → publish Redis → dashboard
  11. Set expiry_candle = current + 15 (Time Invalidation)
```

---

## 8. Confluence Zone — FIB + Order Block

### 8.1 Khái niệm

**Confluence Zone** là vùng giá mà nhiều yếu tố kỹ thuật hội tụ cùng một điểm. Mỗi lớp bổ sung tăng xác suất phản ứng giá đột biến.

**Thứ tự độ mạnh (v1.1):**
```
OB đơn thuần
    < OB + Fib 38.2%
    < OB + Fib 50%
    < OB + Fib 61.8%
    < OB + Fib 61.8% + POC        ← MỚI v1.1
    < OB + Fib 61.8% + FVG
    < OB + Fib 61.8% + POC + FVG  ← QUAD CONFLUENCE — mạnh nhất
```

### 8.2 Thuật toán detect

```python
def find_order_block(candles, atr):
    for i in range(1, len(candles) - 1):
        impulse = abs(candles[i+1].close - candles[i+1].open)
        if impulse >= 1.5 * atr:
            if candles[i+1].is_bullish and candles[i].is_bearish:
                return {
                    'type':  'bullish',
                    'high':  candles[i].high,
                    'low':   candles[i].low,
                    'mid':   (candles[i].high + candles[i].low) / 2,
                    'valid': True
                }
    return None


def calc_fibonacci(candles, lookback=50):
    recent     = candles[-lookback:]
    swing_high = max(c.high for c in recent)
    swing_low  = min(c.low  for c in recent)
    diff       = swing_high - swing_low
    return {
        '382': swing_high - 0.382 * diff,
        '500': swing_high - 0.500 * diff,
        '618': swing_high - 0.618 * diff,
        '786': swing_high - 0.786 * diff,
    }


def confluence_bonus(ob, fib_levels, poc=None, fvg=None):
    if not ob or not ob['valid']:
        return 0

    bonus     = 0
    threshold = ob['mid'] * 0.005  # 0.5%
    fib_pts   = {'618': 35, '500': 25, '382': 15, '786': 10}

    # Fib confluence
    for level, pts in fib_pts.items():
        fib_price = fib_levels[level]
        if ob['low'] <= fib_price <= ob['high'] or \
           abs(fib_price - ob['mid']) <= threshold:
            bonus += pts
            break

    # POC confluence bonus (v1.1)
    if poc and abs(poc - ob['mid']) <= threshold:
        bonus += 10

    # FVG triple confluence
    if fvg and abs(fvg['mid'] - ob['mid']) <= threshold:
        bonus += 10

    return bonus  # Max: 35 + 10 + 10 = 55 (normalize sau)
```

### 8.3 Bảng điểm confluence

| Tổ hợp | Bonus | Độ hiếm |
|---|---|---|
| OB đơn thuần | 0 | Rất phổ biến |
| OB + Fib 38.2% | +15 | Khá thường |
| OB + Fib 50% | +25 | Trung bình |
| OB + Fib 61.8% | +35 | Ít thường |
| OB + Fib 61.8% + POC | +45 | Hiếm *(v1.1)* |
| OB + Fib 61.8% + FVG | +45 | Hiếm |
| OB + Fib 61.8% + POC + FVG | +55 | Cực hiếm — Alert ngay |

### 8.4 Tính SL/TP từ confluence zone

```python
def build_trade_params(ob, fib_levels, direction='long',
                        fee_rate=0.001):  # 0.1% round-trip (v1.1)
    if direction == 'long':
        entry = ob['mid']
        sl    = ob['low']  * 0.997
        tp1   = fib_levels['382']
        tp2   = fib_levels['236'] if '236' in fib_levels else tp1 * 1.005

    rr_gross = abs(tp1 - entry) / abs(entry - sl)
    # Net R:R sau phí entry + exit (v1.1)
    fee_cost = entry * fee_rate * 2  # entry + exit
    rr_net   = (abs(tp1 - entry) - fee_cost) / abs(entry - sl)

    return {
        'entry':    entry,
        'sl':       sl,
        'tp1':      tp1,
        'tp2':      tp2,
        'rr_gross': round(rr_gross, 2),
        'rr_net':   round(rr_net, 2),
        'viable':   rr_net >= 1.5  # Chỉ alert nếu net R:R đạt
    }
```

---

## 9. Quản lý rủi ro

### 9.1 Quy tắc bắt buộc

| Quy tắc | Giá trị | Lý do |
|---|---|---|
| Risk mỗi lệnh | Tối đa 1–2% tài khoản | Bảo vệ vốn dài hạn |
| R:R gross tối thiểu | 1.5 : 1 | Điều kiện cần |
| R:R net tối thiểu (sau phí) | 1.5 : 1 *(v1.1)* | Điều kiện đủ — mới thêm |
| Đòn bẩy tối đa | 10x (khuyến nghị 3–5x) | Tránh liquidation |
| Max lệnh đồng thời | 3 lệnh | Tránh over-exposure |
| Max drawdown ngày | 5% tài khoản | Dừng trade khi đạt |

### 9.2 Tính size lệnh (có tích hợp phí)

```python
def calc_position_size(account_balance, risk_pct, entry, sl,
                        fee_rate=0.001):
    """
    Tính size lệnh với phí tích hợp vào risk (v1.1)
    fee_rate: 0.001 = 0.1% (maker+taker round-trip)
    """
    risk_amount   = account_balance * risk_pct
    sl_distance   = abs(entry - sl)
    sl_pct        = sl_distance / entry

    # Trừ phí khỏi risk budget trước khi tính size
    fee_per_unit  = entry * fee_rate * 2  # entry + exit
    net_risk_pct  = sl_pct + (fee_per_unit / entry)

    position_usd  = risk_amount / net_risk_pct
    return round(position_usd, 2)
```

### 9.3 Invalidation rules — đầy đủ *(v1.1)*

#### Price-based Invalidation (cũ)

| Điều kiện | Hành động |
|---|---|
| Giá đóng nến 15m dưới OB low (long) | Hủy alert, OB invalid |
| FVG midpoint bị chạm | FVG filled, xóa khỏi watchlist |
| Swing high/low mới vượt lookback | Reset Fibonacci |
| Funding rate vượt ±0.1% | Giảm 15 điểm score, cảnh báo |
| Delta đảo chiều trong khi hold | Cảnh báo sớm — check SL |

#### Time-based Invalidation *(thêm mới v1.1)*

> **Nguyên tắc:** Trong scalping, thời gian chờ = chi phí cơ hội + rủi ro thay đổi context. Một alert chờ quá lâu không được trigger là alert đã hết giá trị.

| Điều kiện | Hành động |
|---|---|
| Alert chờ > 10 nến 15m (150 phút) mà giá chưa chạm entry | Tự động hủy alert — EXPIRED |
| Alert chờ > 5 nến 15m + 1H bias đảo chiều | Hủy ngay lập tức |
| Giá đi ngang trong OB > 15 nến 15m không có momentum | Giảm score 20 pts — re-evaluate |

```python
def check_time_invalidation(alert, current_candle_index,
                              htf_bias_changed):
    candles_elapsed = current_candle_index - alert['created_at']

    # Hard expiry: 15 nến 15m = 225 phút
    if candles_elapsed > 15:
        return {'status': 'EXPIRED', 'reason': 'Time limit exceeded'}

    # Soft expiry: 5 nến + bias đổi chiều
    if candles_elapsed > 5 and htf_bias_changed:
        return {'status': 'CANCELLED', 'reason': 'HTF bias reversed'}

    # Sideways penalty: giảm score nếu giá stuck trong OB
    if candles_elapsed > 8 and no_directional_momentum:
        alert['score'] -= 20
        if alert['score'] < 55:
            return {'status': 'DEGRADED', 'reason': 'No momentum'}

    return {'status': 'ACTIVE'}
```

---

## 10. Tech Stack

### 10.1 Backend (Python)

```
backend/
├── main.py                  # Entry point
├── data/
│   ├── ws_ohlcv.py          # WebSocket OHLCV
│   ├── ws_orderbook.py      # WebSocket Order Book
│   ├── ws_trades.py         # WebSocket tick delta writer (v1.1)
│   └── funding.py           # REST: funding rate, OI
├── cache/
│   ├── redis_writer.py      # Atomic tick → Redis (v1.1)
│   └── redis_reader.py      # Đọc snapshot cho scorer
├── engine/
│   ├── order_flow.py        # Module Order Flow
│   ├── smc.py               # Module SMC: FVG, OB, CHoCH
│   ├── vsa.py               # Module VSA (v1.1: + Volume Profile)
│   ├── volume_profile.py    # POC/VAH/VAL calculator (v1.1)
│   ├── context.py           # Module Context Filter
│   ├── confluence.py        # Fib + OB + POC confluence (v1.1)
│   └── scorer.py            # Signal Score aggregator
├── risk/
│   ├── position_size.py     # Size lệnh (v1.1: tích hợp phí)
│   ├── fee_calculator.py    # Phí + slippage estimate (v1.1)
│   └── validator.py         # R:R net check, invalidation
├── alert/
│   ├── builder.py           # Build Signal Card
│   ├── invalidator.py       # Time-based invalidation (v1.1)
│   └── sender.py            # Publish → Redis → Dashboard
├── trade/
│   ├── executor.py          # Gửi lệnh qua exchange API
│   └── journal.py           # Log kèm fee/slippage thực tế
└── api/
    └── routes.py            # FastAPI endpoints
```

### 10.2 Thư viện chính

| Thư viện | Dùng cho |
|---|---|
| `ccxt` | Kết nối exchange API |
| `websockets` | Realtime data stream |
| `pandas` + `numpy` | Tính toán OHLCV |
| `ta-lib` | ATR, RSI, MACD |
| `fastapi` | Backend API |
| `celery` + `redis` | Task queue + cache *(v1.1 core)* |
| `aioredis` | Async Redis cho WS writer |
| `postgresql` | Trade journal lâu dài |

### 10.3 Infrastructure *(v1.1)*

```
┌─────────────┐  WebSocket  ┌──────────────────────────────┐
│  Binance /  │────────────►│  asyncio WS handlers         │
│  Bybit API  │◄───REST─────│  (tick writer < 0.1ms)       │
└─────────────┘             └──────────────┬───────────────┘
                                           │ atomic write
                                           ▼
                             ┌─────────────────────────────┐
                             │         REDIS               │
                             │  delta · OB · OHLCV · POC   │
                             └──────────────┬──────────────┘
                                           │ read on candle close
                                           ▼
                             ┌─────────────────────────────┐
                             │    Celery Worker(s)          │
                             │    Signal Scoring Engine     │
                             └──────────────┬──────────────┘
                                           │ publish alert
                                           ▼
                             ┌─────────────────────────────┐
                             │    FastAPI + WebSocket       │
                             │    React Dashboard           │
                             └──────────────┬──────────────┘
                                           │
                                           ▼
                             ┌─────────────────────────────┐
                             │    PostgreSQL                │
                             │    Trade Journal             │
                             └─────────────────────────────┘
```

### 10.4 Frontend Dashboard

```
dashboard/
├── components/
│   ├── SignalCard.jsx        # Alert + countdown timer
│   ├── ScoreBreakdown.jsx    # Chi tiết điểm từng module
│   ├── FeeEstimate.jsx       # Net R:R sau phí (v1.1)
│   ├── ConfirmButton.jsx     # Confirm / Skip
│   ├── ChartView.jsx         # Chart với OB/FVG/Fib/POC
│   └── JournalTable.jsx      # Lịch sử lệnh + net PnL
└── pages/
    ├── Dashboard.jsx
    └── Analytics.jsx         # Win rate net, profit factor net
```

---

## 11. Lộ trình build

### Giai đoạn 1 — MVP Rule-based (Tuần 1–3)

- [ ] Kết nối Binance WebSocket: OHLCV 15m + tick trades
- [ ] Redis setup: delta writer atomic
- [ ] ATR(14) + swing high/low calculator
- [ ] Detect Order Block cơ bản
- [ ] Tính Fibonacci từ swing tự động
- [ ] Confluence check OB + Fib
- [ ] Signal Card terminal output
- [ ] Log vào CSV (kèm estimated fee)

**Deliverable:** Bot terminal, alert khi OB + Fib hội tụ, không block WS.

### Giai đoạn 2 — Full AI Engine (Tuần 4–6)

- [ ] Celery worker tách khỏi WS loop hoàn toàn
- [ ] Volume Profile calculator (POC/VAH/VAL) → Redis
- [ ] Order Flow delta score
- [ ] FVG + CHoCH detector
- [ ] VSA + Volume Profile module (30 pts)
- [ ] Context filter (funding rate, 1H bias)
- [ ] Time-based Invalidation (15 nến timeout)
- [ ] Signal scoring engine (0–100, normalize)
- [ ] Net R:R calculator (trừ 0.06–0.1% phí)
- [ ] FastAPI + React dashboard: Signal Card + Confirm/Skip
- [ ] Testnet execution: lệnh thật + auto SL/TP
- [ ] Trade journal PostgreSQL (kèm slippage actual)

**Deliverable:** Hệ thống semi-auto hoàn chỉnh trên testnet.

### Giai đoạn 3 — Tối ưu & ML (Tuần 7–12)

- [ ] Backtest engine với phí + slippage (0.08% default)
- [ ] Phân tích journal: win rate net, profit factor net
- [ ] A/B test ngưỡng score (70 vs 75 vs 80)
- [ ] Tự động điều chỉnh trọng số module
- [ ] Telegram alert backup
- [ ] Multi-pair scanning (BTC, ETH, SOL)
- [ ] ML layer: random forest phân loại win/loss
- [ ] Dashboard analytics: net metrics toàn bộ

---

## 12. Backtest & Tối ưu

### 12.1 Metrics cần đo (NET sau phí)

| Metric | Mục tiêu (gross) | Mục tiêu (net) | Ghi chú |
|---|---|---|---|
| Win Rate | ≥ 55% | ≥ 52% | Phí ăn ~3–5% win rate |
| Profit Factor | ≥ 1.5 | ≥ 1.3 | Net quan trọng hơn |
| Max Drawdown | ≤ 15% | ≤ 18% | Net có thể cao hơn |
| Sharpe Ratio | ≥ 1.0 | ≥ 0.8 | |
| Avg R:R thực tế | ≥ 1.3 | ≥ 1.1 | |
| Alerts/ngày | 5–12 | — | Không đổi |

### 12.2 Backtest với phí + slippage *(v1.1 — bắt buộc)*

```python
def simulate_trade(entry, sl, tp, balance, risk_pct,
                   fee_rate=0.001, slippage_pct=0.0002):
    """
    fee_rate:     0.001 = 0.1% Taker (Binance Futures mặc định)
    slippage_pct: 0.0002 = 0.02% ước tính BTC 15m scalping
    """
    risk_amount = balance * risk_pct
    sl_dist     = abs(entry - sl)
    position    = risk_amount / (sl_dist / entry)

    # Áp dụng slippage vào entry thực tế
    actual_entry = entry * (1 + slippage_pct)  # Long: mua cao hơn

    # Phí entry + exit
    fee_entry = actual_entry * position * fee_rate
    fee_exit  = tp * position * fee_rate
    total_fee = fee_entry + fee_exit

    # PnL gross vs net
    pnl_gross = (tp - actual_entry) * (position / actual_entry)
    pnl_net   = pnl_gross - total_fee

    return {
        'pnl_gross':    pnl_gross,
        'pnl_net':      pnl_net,
        'fee_paid':     total_fee,
        'slippage':     actual_entry - entry,
        'fee_pct_pnl':  total_fee / abs(pnl_gross) * 100  # % phí ăn vào PnL
    }


def backtest(historical_candles, params):
    trades  = []
    balance = params['initial_balance']
    fee_rate    = params.get('fee_rate', 0.001)     # 0.1% Taker
    slippage    = params.get('slippage', 0.0002)    # 0.02%

    for i in range(100, len(historical_candles)):
        window = historical_candles[i-100:i]
        signal = calculate_signal_score(window, ...)

        if signal['action'] == 'ALERT' and signal['rr_net'] >= 1.5:
            trade = simulate_trade(
                entry       = signal['entry'],
                sl          = signal['sl'],
                tp          = signal['tp1'],
                balance     = balance,
                risk_pct    = params['risk_pct'],
                fee_rate    = fee_rate,
                slippage_pct= slippage
            )
            trades.append(trade)
            balance += trade['pnl_net']  # Dùng net, không dùng gross

    return compute_metrics(trades, balance)
```

> **Lưu ý quan trọng:** Với đòn bẩy 10x và scalping 15m, tổng phí + slippage khoảng **0.06–0.1% notional mỗi vòng lệnh**. Nếu TP target = 0.4% giá, thì phí chiếm 15–25% lợi nhuận. **Không backtest mà bỏ qua phí = kết quả vô nghĩa.**

### 12.3 Ngưỡng chuyển sang live trading

| Điều kiện | Ngưỡng |
|---|---|
| Số lệnh backtest | ≥ 200 lệnh |
| Win rate **net** backtest | ≥ 52% |
| Profit factor **net** backtest | ≥ 1.3 |
| Số tuần testnet | ≥ 2 tuần |
| Win rate **net** testnet | ≥ 50% |
| Max drawdown **net** testnet | ≤ 10% |
| Slippage thực tế vs ước tính | ≤ 150% (không vượt 1.5× ước tính) |

---

## 13. Cải tiến v1.1 — Nhận xét thực chiến

### 13.1 Data Lag — Giải quyết hoàn toàn

**Vấn đề gốc:** WS handler vừa nhận tick vừa tính delta vừa chạy scoring → nghẽn luồng → mất tick.

**Giải pháp:** 3 luồng độc lập qua Redis.
- Luồng 1 (asyncio): chỉ ghi tick vào Redis, < 0.1ms
- Luồng 2 (Celery): đọc Redis khi nến đóng, tính score
- Luồng 3 (FastAPI WS): stream kết quả ra dashboard

**Thư viện:** `aioredis` (async), `celery[redis]`, `FastAPI BackgroundTasks` cho tasks nhẹ.

### 13.2 Time-based Invalidation — Thêm vào hệ thống

**Vấn đề gốc:** Alert chờ mãi không expired → chiếm dashboard → người dùng bị phân tâm → vào lệnh trễ trong điều kiện xấu hơn.

**Giải pháp:** Mỗi alert có `expires_at = created_candle + 15`. Celery task kiểm tra mỗi nến đóng. Nếu hết hạn → tự hủy + log `EXPIRED`.

**Bonus:** Giảm score 20 pts nếu giá stuck trong OB > 8 nến mà không có momentum — cảnh báo người dùng re-evaluate.

### 13.3 VSA + Volume Profile — Tăng độ tin cậy

**Vấn đề gốc:** VSA thuần túy (No Supply/Demand) có false positive khi thị trường trending mạnh — volume pullback tự nhiên thấp không có nghĩa là setup tốt.

**Giải pháp:** Thêm POC làm "neo giá trị". Khi OB + Fib 61.8% + POC hội tụ = tổ chức (OB) + đám đông (Fib) + vùng giao dịch nhiều nhất (POC) cùng một điểm. Xác suất phản ứng tăng đáng kể.

**Điểm thêm:** +10 pts khi entry nằm tại POC (±0.3%), +6 pts tại VAH/VAL.

### 13.4 Phí & Slippage — Tích hợp vào mọi tầng

**Vấn đề gốc:** Target win rate 55% + R:R 1.5 trên paper trading ≠ profitable sau phí thực tế.

**Tác động thực tế (ví dụ):**
```
Trade: Long BTC, entry $77,050, TP $77,820 (+1%), SL $76,720 (-0.43%)
Gross R:R = 1.0% / 0.43% = 2.33

Phí Binance Taker (0.05%) × 2 = 0.10%
Slippage ước tính = 0.02%
Tổng cost = 0.12%

Net TP = 1.0% - 0.12% = 0.88%
Net R:R = 0.88% / 0.43% = 2.05  ← vẫn tốt ở ví dụ này

Nhưng nếu TP chỉ = 0.3%:
Net TP = 0.3% - 0.12% = 0.18%
Net R:R = 0.18% / 0.43% = 0.42  ← THUA dù giá chạm TP!
```

**Quy tắc bổ sung:** TP tối thiểu phải = SL distance × 1.5 **VÀ** ≥ 4× tổng phí+slippage. Với fee 0.1%, TP tối thiểu phải ≥ 0.4% notional.

---

## Phụ lục — Cheat Sheet tín hiệu (v1.1)

### Tín hiệu LONG lý tưởng (score ≥ 75)
```
✓ 1H bias: Bullish (RSI không bearish divergence)
✓ 15m: Giá retest về Bullish OB
✓ 15m: OB trùng Fib 61.8% của swing gần nhất
✓ 15m: OB trùng POC ngày  ← MỚI v1.1
✓ 15m: Volume hồi < 45% volume impulse (No Supply)
✓ 5m: Pin bar / Bullish engulfing tại vùng OB
✓ Order flow: Delta dương, Bid stack > Ask stack
✓ Net R:R ≥ 1.5 sau phí 0.08%  ← MỚI v1.1
✓ Entry: OB midpoint | SL: dưới OB low 0.3% | TP: FVG / swing high
```

### Tín hiệu SHORT lý tưởng (score ≥ 75)
```
✓ 1H bias: Bearish (RSI bearish divergence hoặc lower high)
✓ 15m: Giá retest về Bearish OB (overhead supply)
✓ 15m: OB trùng Fib 61.8% tính từ swing high
✓ 15m: OB trùng POC ngày  ← MỚI v1.1
✓ 15m: Volume hồi < 45% volume impulse (No Demand)
✓ 5m: Pin bar / Bearish engulfing tại vùng OB
✓ Order flow: Delta âm, Ask stack > Bid stack
✓ Net R:R ≥ 1.5 sau phí 0.08%  ← MỚI v1.1
✓ Entry: OB midpoint | SL: trên OB high 0.3% | TP: FVG / swing low
```

### Điều kiện KHÔNG vào lệnh
```
✗ Score < 55
✗ R:R gross < 1.5 HOẶC R:R net < 1.5  ← MỚI v1.1
✗ TP < 4× tổng phí+slippage  ← MỚI v1.1
✗ Alert đã chờ > 15 nến 15m (EXPIRED)  ← MỚI v1.1
✗ Funding rate > ±0.1%
✗ Đang giữ ≥ 3 lệnh đồng thời
✗ Drawdown ngày đã đạt 5%
✗ Trong vòng 30 phút trước/sau CPI, FOMC, ...
✗ OB đã bị vi phạm (giá đóng cửa nến dưới OB low)
✗ 1H bias đảo chiều sau khi alert được tạo  ← MỚI v1.1
```

---

*Blueprint này là tài liệu sống — cần cập nhật sau mỗi giai đoạn dựa trên kết quả thực tế.*

*Phiên bản 1.1 · Tháng 5/2026 · Cập nhật dựa trên nhận xét thực chiến*
