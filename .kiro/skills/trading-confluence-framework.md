# Trading Confluence Framework — Skill Tổng Hợp

> Kết nối tất cả các lý thuyết: Price Action + FVG + Order Blocks + ChoCh + Divergence + Fibonacci + Mean Reversion + Chart Patterns
> Dùng để xây dựng setup giao dịch chất lượng cao bằng cách kết hợp nhiều confluence

---

## 1. NGUYÊN LÝ CONFLUENCE

```
Một tín hiệu đơn lẻ = Xác suất thấp
Nhiều tín hiệu cùng hướng = Confluence = Xác suất cao

Mục tiêu: Tìm điểm giao nhau của nhiều công cụ
```

---

## 2. BẢN ĐỒ CÁC CÔNG CỤ

| Công cụ | Mục đích chính | Skill file |
|---------|---------------|------------|
| **Price Action** | Market bias, S/R, patterns | `price-action-trading.md` |
| **Advanced Chart Patterns** | Nhận diện mô hình nến/chart | `advanced-chart-patterns.md` |
| **Order Blocks** | Vùng tích lũy của big player | `order-blocks.md` |
| **Fair Value Gap** | Vùng imbalance cần lấp | `fair-value-gap.md` |
| **Change of Character** | Xác nhận đảo chiều xu hướng | `change-of-character.md` |
| **Divergence** | Phát hiện momentum yếu | `divergence-patterns.md` |
| **Fibonacci** | Mức S/R động, target intraday | `fibonacci-retracement.md` |
| **Mean Reversion** | Giao dịch khi giá lệch xa mean | `mean-reversion-trading.md` |

---

## 3. QUY TRÌNH PHÂN TÍCH TOP-DOWN

```
Bước 1: HIGHER TIMEFRAME (Daily/H4) — XÁC ĐỊNH BIAS
         → Uptrend hay Downtrend? (HH/HL hay LH/LL)
         → Đánh dấu S/R quan trọng
         → Có Order Block nào không?
         → Có Divergence trên HTF không?
         
Bước 2: MIDDLE TIMEFRAME (H1/H4) — XÁC ĐỊNH SETUP
         → Giá đang tiếp cận vùng nào? (S/R, OB, Fibonacci)
         → Có FVG nào trong vùng đó không?
         → Có Chart Pattern đang hình thành không?
         → Mean Reversion: Giá có lệch xa MA không?
         
Bước 3: LOWER TIMEFRAME (M15/M5) — TÌM ENTRY
         → Chờ ChoCh xác nhận đảo chiều
         → Tìm FVG để đặt limit order
         → Xác nhận bằng Divergence (RSI/MACD)
         → Kiểm tra Fibonacci level
```

---

## 4. SETUP CHẤT LƯỢNG CAO — CHECKLIST CONFLUENCE

### Setup BUY (Tối thiểu 3/5 điều kiện):
```
✅ Uptrend trên HTF (HH/HL)
✅ Giá tại vùng Demand / Support quan trọng
✅ Bullish Order Block trong vùng đó
✅ Bullish FVG tại vùng entry
✅ Bullish ChoCh trên LTF
✅ Bullish Divergence (RSI/MACD)
✅ Fibonacci level 61.8% hoặc 1.618 downside
✅ Bullish Chart Pattern (Hammer, Engulfing, Double Bottom...)
✅ RSI oversold (< 30) — Mean Reversion
```

### Setup SELL (Tối thiểu 3/5 điều kiện):
```
✅ Downtrend trên HTF (LH/LL)
✅ Giá tại vùng Supply / Resistance quan trọng
✅ Bearish Order Block trong vùng đó
✅ Bearish FVG tại vùng entry
✅ Bearish ChoCh trên LTF
✅ Bearish Divergence (RSI/MACD)
✅ Fibonacci level 61.8% hoặc 1.618 upside
✅ Bearish Chart Pattern (Shooting Star, Engulfing, Double Top...)
✅ RSI overbought (> 70) — Mean Reversion
```

---

## 5. CÁC COMBO CONFLUENCE PHỔ BIẾN

### Combo 1: Smart Money Setup (Mạnh nhất)
```
HTF: Downtrend + Bearish OB
MTF: Giá retracement về OB + Bearish FVG trong OB
LTF: Bearish ChoCh + Bearish Divergence RSI

Entry: Limit order tại FVG
SL: Trên OB
TP: Swing low tiếp theo
```

### Combo 2: Mean Reversion + Divergence
```
Điều kiện: Thị trường sideway
Setup: Giá chạm Bollinger Band ngoài + RSI overbought/oversold
       + Regular Divergence xuất hiện
       + ChoCh xác nhận trên LTF

Entry: Sau ChoCh
SL: Ngoài Bollinger Band
TP: Đường MA (mean)
```

### Combo 3: Fibonacci + Chart Pattern
```
HTF: Xác định xu hướng
MTF: Giá retracement về Fibonacci 61.8%
     + Chart Pattern hình thành tại đó (Hammer, Engulfing)
     + Volume giảm trong retracement
LTF: Breakout xác nhận

Entry: Trên/dưới pattern
SL: Dưới/trên Fibonacci level
TP: Fibonacci extension 1.618
```

### Combo 4: Wyckoff + Order Block
```
HTF: Nhận diện Wyckoff Accumulation/Distribution
     Chờ Spring (Accumulation) hoặc UTAD (Distribution)
MTF: Spring/UTAD tại Order Block
LTF: ChoCh xác nhận đảo chiều

Entry: Sau ChoCh
SL: Dưới Spring low / Trên UTAD high
TP: SOS/SOW target
```

---

## 6. QUẢN LÝ RỦI RO TỔNG HỢP

### Stop Loss:
```
Ưu tiên đặt SL tại:
  1. Dưới/trên Order Block
  2. Dưới/trên nến đầu tiên của FVG
  3. Dưới/trên swing low/high gần nhất
  4. Dưới/trên Fibonacci level
  
Nguyên tắc: SL phải có lý do kỹ thuật, không đặt tùy tiện
```

### Take Profit:
```
Target 1 (50% vị thế): S/R gần nhất
Target 2 (50% còn lại): S/R tiếp theo / Fibonacci extension

Hoặc:
  Fixed R:R: 1:2 hoặc 1:3
  Trail stop: Theo swing high/low
```

### Position Sizing:
```
Rủi ro mỗi lệnh: 1-2% tài khoản
Số lệnh cùng lúc: Tối đa 3 lệnh
Tổng rủi ro: Không quá 5% tài khoản
```

---

## 7. ĐIỀU KIỆN THỊ TRƯỜNG VÀ CHIẾN LƯỢC PHÙ HỢP

| Điều kiện thị trường | Chiến lược tốt nhất | Tránh |
|---------------------|--------------------|----|
| **Uptrend mạnh** | Trend following, Hidden Bullish Divergence, Bullish FVG | Mean Reversion, Regular Bearish Divergence |
| **Downtrend mạnh** | Trend following, Hidden Bearish Divergence, Bearish FVG | Mean Reversion, Regular Bullish Divergence |
| **Sideway / Range** | Mean Reversion, Regular Divergence, Order Blocks | Trend following |
| **Breakout** | Chart Patterns (Flag, Triangle), Fibonacci extension | Mean Reversion |
| **Reversal** | ChoCh + FVG, Wyckoff Spring/UTAD, Regular Divergence | Hidden Divergence |

---

## 8. CHECKLIST TỔNG TRƯỚC KHI VÀO LỆNH

```
PHÂN TÍCH:
✅ Bias HTF đã xác định? (Uptrend/Downtrend/Sideways)
✅ Đang giao dịch thuận chiều bias?
✅ Đã đánh dấu S/R, OB, FVG quan trọng?
✅ Có ít nhất 3 confluence cùng hướng?

ENTRY:
✅ ChoCh hoặc BOS/MSS đã xác nhận?
✅ Entry tại FVG, OB, hoặc Fibonacci level?
✅ Không vào lệnh giữa không khí?

QUẢN LÝ:
✅ Stop loss có lý do kỹ thuật rõ ràng?
✅ R:R ≥ 1:2?
✅ Rủi ro ≤ 2% tài khoản?
✅ Take profit đã xác định?

TÂM LÝ:
✅ Setup đủ điều kiện, không FOMO?
✅ Không revenge trade?
✅ Tuân thủ kế hoạch giao dịch?
```

---

## 9. NGUYÊN TẮC VÀNG TỔNG HỢP

1. **Confluence > Single Signal** — Nhiều tín hiệu cùng hướng = xác suất cao hơn
2. **Bias > Pattern** — Xác định đúng xu hướng quan trọng hơn tìm pattern hoàn hảo
3. **Vị trí > Hình dạng** — Pattern tại S/R quan trọng > Pattern giữa không khí
4. **Volume xác nhận tất cả** — Breakout không có volume = nghi ngờ
5. **Chờ xác nhận** — ChoCh, BOS/MSS, Sustenance trước khi vào lệnh
6. **Quản lý rủi ro trước** — SL trước TP, không bao giờ ngược lại
7. **Demo trước live** — Backtest mọi chiến lược trước khi dùng thực
8. **Kỷ luật > Kỹ thuật** — Tuân thủ kế hoạch quan trọng hơn tìm setup hoàn hảo

---

## 10. LIÊN KẾT SKILLS

```
Khi phân tích thị trường, đọc theo thứ tự:
  1. price-action-trading.md       → Bias + S/R + Market Structure
  2. advanced-chart-patterns.md    → Nhận diện patterns
  3. order-blocks.md               → Vùng tích lũy big player
  4. fair-value-gap.md             → Vùng imbalance
  5. change-of-character.md        → Xác nhận đảo chiều
  6. divergence-patterns.md        → Momentum analysis
  7. fibonacci-retracement.md      → Levels và targets
  8. mean-reversion-trading.md     → Sideway market strategy
```

---

*Tổng hợp từ tất cả docs trong project/docs/*
*Dùng kèm với: .kiro/specs/crypto-trading-system/requirements.md*
