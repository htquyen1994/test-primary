# Divergence Patterns — Skill

> Tổng hợp từ: project/docs/divergence-patterns.md
> Dùng để phát hiện sự suy yếu của momentum trước khi giá đảo chiều hoặc tiếp diễn

---

## 1. NGUYÊN LÝ CỐT LÕI

```
Divergence = Giá và Indicator đi NGƯỢC CHIỀU nhau
→ Momentum đang thay đổi → Cơ hội giao dịch
```

- **Regular Divergence** → Tín hiệu **đảo chiều** (ngược xu hướng)
- **Hidden Divergence** → Tín hiệu **tiếp diễn** (theo xu hướng)
- Dùng với **oscillator** (RSI, MACD, Stochastic, CCI, OBV)

---

## 2. BẢNG NHẬN DIỆN 4 LOẠI DIVERGENCE

| Loại | Giá | Indicator | Tín Hiệu | Xu Hướng Hiện Tại |
|------|-----|-----------|----------|-------------------|
| **Regular Bullish** | Lower Low ↘ | Higher Low ↗ | Đảo chiều TĂNG | Downtrend |
| **Regular Bearish** | Higher High ↗ | Lower High ↘ | Đảo chiều GIẢM | Uptrend |
| **Hidden Bullish** | Higher Low ↗ | Lower Low ↘ | Tiếp diễn TĂNG | Uptrend |
| **Hidden Bearish** | Lower High ↘ | Higher High ↗ | Tiếp diễn GIẢM | Downtrend |

### Sơ đồ nhanh:
```
REGULAR BULLISH:          REGULAR BEARISH:
  Giá:  LL₂ < LL₁ ↘        Giá:  HH₂ > HH₁ ↗
  RSI:  HL₂ > HL₁ ↗        RSI:  LH₂ < LH₁ ↘
  → BUY signal              → SELL signal

HIDDEN BULLISH:           HIDDEN BEARISH:
  Giá:  HL₂ > HL₁ ↗        Giá:  LH₂ < LH₁ ↘
  RSI:  LL₂ < LL₁ ↘        RSI:  HH₂ > HH₁ ↗
  → BUY (continuation)      → SELL (continuation)
```

---

## 3. 5 INDICATOR PHỔ BIẾN

| Indicator | Overbought | Oversold | Phù hợp nhất |
|-----------|-----------|---------|--------------|
| **RSI** | > 70 | < 30 | Mọi thị trường |
| **MACD** | EMA lines xa | EMA lines xa | Trending market |
| **Stochastic** | > 80 | < 20 | Range-bound market |
| **CCI** | Dương cao | Âm thấp | Forex, Commodity |
| **OBV** | Phân kỳ volume | Phân kỳ volume | Xác nhận volume |

> **Lưu ý:** Bất kỳ oscillator nào cũng có thể dùng để phát hiện divergence

---

## 4. QUY TRÌNH GIAO DỊCH DIVERGENCE

```
Bước 1: Xác định xu hướng trên Higher Timeframe
         ↓
Bước 2: Tìm Significant Highs/Lows (bỏ qua minor)
         ↓
Bước 3: So sánh Giá vs Indicator
         → Cùng chiều? → Không có divergence
         → Ngược chiều? → Có divergence
         ↓
Bước 4: Xác định loại divergence (Regular hay Hidden)
         ↓
Bước 5: Xuống Lower Timeframe
         ↓
Bước 6: Chờ Break of Structure (BOS) hoặc Market Structure Shift (MSS)
         ↓
Bước 7: Vào lệnh sau khi có BOS/MSS xác nhận
         ↓
Bước 8: Stop Loss dưới swing low (BUY) / trên swing high (SELL)
         Take Profit: Tối thiểu 1:1 R:R
```

---

## 5. VÍ DỤ THỰC HÀNH

### Ví dụ 1: Regular Bearish Divergence (GBPUSD + RSI)
```
Timeframe: H1
Quan sát:
  - Giá: HH₂ > HH₁ (Higher High)
  - RSI: LH₂ < LH₁ (Lower High)
  → Regular Bearish Divergence → Kỳ vọng giảm

Quy trình:
  1. Xác nhận cả 2 đỉnh là Significant Highs
  2. Xuống M15
  3. Chờ Market Structure Shift (MSS) xác nhận
  4. Vào SELL sau MSS
  5. Target: 1:1 R:R tối thiểu
```

### Ví dụ 2: Hidden Bullish Divergence (GBPJPY + Stochastic)
```
Timeframe: Daily/H4
Quan sát:
  - Giá: HL₂ > HL₁ (Higher Low) — trong uptrend
  - Stochastic: LL₂ < LL₁ (Lower Low)
  → Hidden Bullish Divergence → Tiếp diễn tăng

Quy trình:
  1. Xác nhận đang trong uptrend
  2. Chờ Market Structure Shift xác nhận
  3. Vào BUY
  4. Stop Loss: Dưới swing low gần nhất
  5. Target: 1:1 R:R
```

---

## 6. 3 TIPS QUAN TRỌNG

### Tip 1: Chỉ dùng Significant Highs/Lows
```
✅ Significant = Đỉnh/đáy rõ ràng, được thị trường tôn trọng
❌ Minor = Đỉnh/đáy nhỏ, không đáng kể

Ít tín hiệu hơn nhưng chất lượng cao hơn
```

### Tip 2: Người mới → Dùng Hidden Divergence
```
Hidden Divergence = Giao dịch THEO xu hướng
→ An toàn hơn, xác suất cao hơn

Regular Divergence = Giao dịch NGƯỢC xu hướng
→ Cần kinh nghiệm và quản lý rủi ro tốt hơn
```

### Tip 3: Bắt buộc chờ BOS/MSS trên LTF
```
Divergence trên HTF → Xuống LTF → Chờ BOS/MSS
Không có BOS/MSS = Không vào lệnh

Lý do: Giá có thể tiếp tục theo hướng cũ lâu hơn dự kiến
```

---

## 7. CHECKLIST TRƯỚC KHI VÀO LỆNH

```
✅ Đã xác định xu hướng trên HTF?
✅ Divergence hình thành tại Significant High/Low?
✅ Đã xác định loại divergence (Regular hay Hidden)?
✅ Đã xuống LTF chưa?
✅ Có BOS hoặc MSS xác nhận chưa?
✅ Stop loss đã xác định?
✅ R:R ≥ 1:1?
```

---

## 8. KẾT HỢP VỚI CÁC CÔNG CỤ KHÁC

| Công cụ | Cách kết hợp |
|---------|-------------|
| **ChoCh** | Dùng ChoCh thay cho BOS/MSS để xác nhận entry |
| **Order Blocks** | Divergence tại OB = tín hiệu rất mạnh |
| **FVG** | Tìm entry chính xác trong vùng divergence |
| **Fibonacci** | Divergence tại mức Fib 61.8% = confluence mạnh |
| **S/R Zones** | Divergence tại S/R = xác suất cao nhất |

---

## 9. NGUYÊN TẮC VÀNG

1. **Divergence dễ thấy, khó giao dịch** — Không biết khi nào bias phát huy
2. **Bắt buộc chờ BOS/MSS** — Xác nhận thị trường đang di chuyển theo hướng của bạn
3. **Significant highs/lows only** — Bỏ qua minor để tránh false signals
4. **Người mới: Hidden Divergence** — Giao dịch theo xu hướng an toàn hơn
5. **Oscillator nào cũng được** — RSI, MACD, Stochastic đều hoạt động

---

*Nguồn: project/docs/divergence-patterns.md*
