# AI System Review Prompt

Dùng prompt này để yêu cầu một AI khác (ChatGPT, Claude, Gemini...) review toàn bộ hệ thống.

---

## Cách dùng

1. Copy toàn bộ nội dung trong phần **"PROMPT"** bên dưới
2. Paste vào AI bạn muốn dùng
3. Đính kèm thêm các file code cụ thể nếu muốn review sâu hơn

---

## PROMPT

---

Bạn là một **Senior Software Architect** và **Quantitative Trading Systems Engineer** với kinh nghiệm thiết kế hệ thống giao dịch tần suất cao (HFT), crypto trading bots, và distributed systems.

Tôi sẽ mô tả chi tiết một hệ thống trading mà tôi đang xây dựng. Hãy review toàn diện và cho tôi phản hồi thực chất — không cần khen ngợi, chỉ cần chỉ ra vấn đề và đề xuất cải thiện.

---

## Mô tả hệ thống

### Tổng quan

Đây là một **AI Semi-Auto Crypto Futures Trading Tool** (v2.0, Phase 9 — May 2026), hoạt động theo phong cách scalping trên crypto futures perpetual. Triết lý cốt lõi: **AI phân tích, người quyết định** — không fully automated.

- Khung trigger: 15 phút
- Khung context: 1H, 4H, Daily
- Score ngưỡng ALERT: ≥ 75/100
- R:R tối thiểu (net sau phí): 1.5:1
- Đòn bẩy: 3x–10x

---

### Kiến trúc 3 lớp

**Layer 1 — Data Input**

Thu thập dữ liệu từ exchange (Binance/Bybit) qua **REST polling** (ccxt, không cần API key):
- `OHLCVService` — poll nến 15m/1h/4h/1d
- `OrderBookService` — poll order book mỗi 5 giây
- `DeltaService` — poll trade tape, tính cumulative delta
- `FundingService` — poll funding rate mỗi 8 giờ

Tất cả ghi atomic vào **Redis** làm central buffer.

**Layer 2 — AI Engine (ScoringService)**

Chạy mỗi khi nến 15m đóng (asyncio + threading, không dùng Celery):

```
[1] Regime Detector (ADX + ATR)
[2] MTF Bias Filter (4H + Daily) → 3 scenarios A/B/C
[3] BTC Spike Guard → block/reduce Alt alerts
[4] Circuit Breaker check → block nếu locked
[5] Signal Scoring (4 modules + bonus)
[6] Risk Manager → position size + portfolio heat
[7] Publish alert / log
```

**Layer 3 — Human Confirm Dashboard**

FastAPI (port 8000) → WebSocket → React (port 5173). Trader thấy Signal Card và bấm CONFIRM hoặc SKIP.

---

### Signal Scoring Engine

```
Score = OrderFlow(35) + SMC(30) + VSA+VolProfile(30) + Context(15) + Bonus(15)
Max raw = 125 → normalize về 100
```

**Module 1 — Order Flow (35 pts)**
- Cumulative Delta > `percentile_75(|delta_24h|) × 1.5` → +15
- Bid stack > Ask stack × 2 → +10
- Absorption detected → +10
- **Data quality cap:** nếu Order Book unavailable → score bị cap tại 60

**Module 2 — SMC Analysis (30 pts)**
- CHoCH aligned với 1H bias → +10
- Order Block retest (trả về List tối đa 3 OB, ưu tiên Fib 61.8%) → +10
- Fair Value Gap midpoint touched → +10

**Module 3 — VSA + Volume Profile (30 pts)**
- No Supply: pullback volume < 40% impulse → +10
- Effort vs Result: volume thấp, giá giữ → +10
- Entry trong ±0.3% của POC → +10 (hoặc tại VAH/VAL → +6)

**Module 4 — Context Filter (15 pts)**
- 1H bias aligned → +8
- Funding rate trong ±0.05% → +4
- Giá cách S/R ≥ 0.5% → +3

**Confluence Bonus (max 15 pts)**
- OB + Fib 61.8% + FVG → max bonus
- POC đã được chuyển sang VSA module (tránh double-count)

**Formula:**
```python
raw = OF + SMC + VSA + CTX + bonus          # 0–125
final = min(round(raw × regime_mult / 125 × 100), 100)
final += mtf_score_adjustment               # +10 (A) hoặc -10 (B)
if not order_book_available:
    final = min(final, 60)                  # data quality cap
```

---

### Bộ lọc bảo vệ (Phase 9)

**Regime Detector**
- PARABOLIC (ATR > 3× avg): multiplier 0.6, tắt Short
- TRENDING (ADX > 25): multiplier 1.0
- RANGING/CHOPPY (ADX < 25): multiplier 0.85

**MTF Bias Filter**
- Scenario A (4H aligned): size × 1.0, score +10
- Scenario B (4H diverging): size × 0.5, score -10, warning
- Scenario C (4H opposing): BLOCK signal
- Daily BEAR + long signal: size × 0.75 thêm

**BTC Spike Guard**
- BTC move > 2%/15m (dump): cancel tất cả Alt alerts, cooldown 30 phút
- BTC move > 2%/15m (pump): Alt size × 0.5
- Alt gain < 0.3× BTC gain trong cooldown: block (relative weakness)

**Circuit Breaker (4 triggers)**
- 3 thua liên tiếp trong 24h → lock 12h
- 1 lệnh thua > 4% equity → lock 6h
- Thua ngày > 5% equity → lock đến 00:00 UTC
- Drawdown > 10% từ đỉnh 7 ngày → lock 24h + manual review
- Smart unlock: regime changed → auto unlock; unchanged → extend 6h

---

### Risk Management

- Risk mỗi lệnh: tối đa 2% tài khoản
- Portfolio Heat limit: 6%
- Correlated group risk: 3% (Pearson correlation > 0.8 → same group)
- Max lệnh đồng thời: 3
- Position sizing: `fixed_usd` / `risk_pct` / `kelly`
- Testnet safety: `_assert_testnet_safe()` guard trước mọi ccxt call

---

### Tech Stack

- **Backend:** Python 3.11, FastAPI, asyncio + threading, Redis 7, SQLAlchemy 2.0
- **Database:** SQL Server (prod) / SQLite (dev)
- **Exchange:** ccxt 4.3
- **Frontend:** React + TypeScript + Tailwind + Zustand + Vite
- **Testing:** pytest + Hypothesis (property-based testing) — 319 tests, 20 correctness properties
- **Infra:** Docker (Redis only), Celery + Celery Beat (task queue)

---

### Trạng thái hiện tại

**Đã implement:**
- Toàn bộ scoring engine, MTF filter, Circuit Breaker, BTC Guard
- FastAPI backend + React dashboard
- Trade Journal + Signal Log (SQL)
- 319 tests với Hypothesis PBT

**Chưa hoàn thành:**
- Order Book Feed chưa start → Order Flow score = 0/35 → score cap tại 60 → khó đạt ALERT (75)
- Trade Tape / Delta chưa start → delta luôn = 0
- Trade Executor chỉ testnet, chưa test live

---

## Yêu cầu review

Hãy review hệ thống này theo các góc độ sau. Với mỗi mục, hãy cho điểm **(1–10)** và giải thích ngắn gọn:

### 1. Kiến trúc tổng thể
- Thiết kế 3 lớp có hợp lý không?
- Việc dùng REST polling thay vì WebSocket cho data feed có phải trade-off tốt không?
- Redis làm central buffer — có bottleneck nào tiềm ẩn không?
- asyncio + threading thay vì Celery — đánh đổi gì?

### 2. Signal Scoring Logic
- Công thức scoring có hợp lý về mặt trading không?
- Trọng số các module (35/30/30/15) có cân bằng không?
- Data quality cap (score ≤ 60 khi không có OB) — có đủ bảo vệ không?
- Dynamic delta threshold (`percentile_75 × 1.5`) — có robust không?
- Có nguy cơ overfitting vào một loại market condition không?

### 3. Risk Management
- Circuit Breaker với 4 triggers — có đủ không? Có trigger nào bị thiếu không?
- MTF Bias Filter 3 scenarios — logic có chặt chẽ không?
- BTC Spike Guard — có edge case nào bị bỏ sót không?
- Portfolio Heat 6% + correlated group 3% — có phù hợp với scalping không?

### 4. Độ tin cậy hệ thống (Reliability)
- Single point of failure ở đâu?
- Nếu Redis down thì sao?
- Nếu exchange API rate limit thì sao?
- Có cơ chế reconnect/retry đủ không?

### 5. Backtesting & Correctness
- 20 correctness properties với Hypothesis PBT — có đủ coverage không?
- Look-ahead bias được enforce bằng `LookAheadError` — có đủ không?
- Walk-forward analysis có được implement đúng không?

### 6. Security
- Testnet safety guard — có đủ không?
- API key management — có rủi ro nào không?
- CORS explicit origins — đủ chưa?

### 7. Scalability
- Hệ thống có thể scale lên 20+ assets không?
- Bottleneck khi thêm nhiều timeframes?
- Database schema có phù hợp cho long-term không?

### 8. Những gì còn thiếu / Rủi ro lớn nhất
- Liệt kê **top 5 rủi ro** quan trọng nhất theo thứ tự ưu tiên
- Những feature nào nên implement tiếp theo?
- Có anti-pattern nào trong thiết kế hiện tại không?

---

## Format output mong muốn

```
## Tổng điểm: X/10

### 1. Kiến trúc tổng thể: X/10
[nhận xét]

### 2. Signal Scoring Logic: X/10
[nhận xét]

...

### Top 5 Rủi ro
1. [rủi ro quan trọng nhất]
2. ...

### Đề xuất ưu tiên tiếp theo
1. [việc cần làm ngay]
2. ...
```

Hãy thẳng thắn và cụ thể. Nếu có điểm nào trong thiết kế là sai hoặc nguy hiểm, hãy nói thẳng.

---

*Nếu bạn muốn review sâu hơn một phần cụ thể (ví dụ: scoring formula, circuit breaker logic, database schema), hãy hỏi thêm và tôi sẽ cung cấp code.*
