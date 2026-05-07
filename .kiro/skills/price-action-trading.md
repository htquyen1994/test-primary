# Price Action Trading — Knowledge Base

> Skill tổng hợp từ tài liệu price-action/
> Dùng để hỗ trợ phân tích, ra quyết định giao dịch, và xây dựng hệ thống trading

---

## 1. FRAMEWORK PHÂN TÍCH (3 CÂU HỎI CỐT LÕI)

Mọi giao dịch price action phải trả lời đủ 3 câu hỏi:

```
1. MARKET BIAS — Thị trường đang nghiêng về hướng nào?
2. TRADING SETUP — Điều kiện cụ thể để vào lệnh là gì?
3. TRADE EXIT — Stop-loss và target ở đâu?
```

> **Nguyên tắc vàng**: Market Bias > Price Pattern. Xác định đúng xu hướng quan trọng hơn tìm mô hình hoàn hảo.

---

## 2. XÁC ĐỊNH MARKET BIAS

### 2.1 Market Structure (Ưu tiên cao nhất)
- **Uptrend**: Higher Highs (HH) + Higher Lows (HL)
- **Downtrend**: Lower Highs (LH) + Lower Lows (LL)
- **Sideways**: Không có HH/HL hay LH/LL rõ ràng

### 2.2 Multiple Time-Frames
- Dùng khung cao hơn để xác định bias tổng thể
- Giao dịch theo hướng của khung cao hơn trên khung thấp hơn

### 2.3 Trend Lines
- Bull trend: Nối các pivot lows → trend line dốc lên
- Bear trend: Nối các pivot highs → trend line dốc xuống
- Phá vỡ quyết định (decisive break) = xu hướng mới

### 2.4 Support & Resistance
- Uptrend: Support giữ vững → chỉ xem xét long
- Downtrend: Resistance giữ vững → chỉ xem xét short

### 2.5 Volume
- Volume tăng theo hướng bias = xác nhận
- Volume cạn kiệt khi ngược chiều = cảnh báo

---

## 3. ĐỌC PRICE ACTION (BAR BY BAR)

### 3.1 Một Bar — 4 câu hỏi
| Thành phần | Câu hỏi |
|-----------|---------|
| **Range** | Thị trường đang biến động mạnh hay yếu? |
| **Body** | Đi lên hay xuống? Mạnh đến đâu? |
| **Bóng trên** | Áp lực bán mạnh đến đâu? |
| **Bóng dưới** | Áp lực mua mạnh đến đâu? |

### 3.2 Hai Bar — Context & Testing
- So sánh range: Biến động tăng hay giảm?
- Testing: Bar mới kiểm tra high/low bar trước như thế nào?
  - Vượt high nhưng bị từ chối → Bearish
  - Phá low và tiếp tục → Bearish
  - Phá low nhưng đảo chiều → Bullish

### 3.3 Ba Bar — Kỳ vọng & Xác nhận
- Thị trường có quán tính: Bullish tiếp nối bullish
- Bar thứ 3 xác nhận kỳ vọng → Momentum tiếp tục
- Bar thứ 3 phá vỡ kỳ vọng → Tín hiệu đảo chiều

---

## 4. SUPPORT & RESISTANCE

### 4.1 Nguyên tắc cơ bản
- S/R là **vùng (zone)**, không phải đường thẳng chính xác
- S/R có thể **flip** (đảo vai trò) sau khi bị phá vỡ
- Support cũ → Resistance mới (và ngược lại)

### 4.2 Cách tìm S/R (theo độ ưu tiên)
1. **Swing High/Low** — Luôn dùng, nền tảng cơ bản
2. **Higher Time-frame S/R** — Lọc ra mức quan trọng nhất
3. **Congestion Areas** — Vùng tích lũy lâu
4. **Round Numbers** — $100, $1K, $10K, $100K (crypto)
5. **Moving Average** — S/R động, tốt trong trending market
6. **Fibonacci** — 23.6%, 38.2%, 50%, 61.8%, 100%

### 4.3 Ứng dụng
- **Entry**: Tìm bullish pattern tại support, bearish pattern tại resistance
- **Filter**: Không mua khi giá ngay dưới resistance lớn
- **Exit**: S/R gần nhất = target xác suất cao nhất

---

## 5. BAR PATTERNS (10 PATTERNS)

### 5.1 Reversal Patterns

| Pattern | Điều kiện nhận biết | Giao dịch |
|---------|-------------------|-----------|
| **Reversal Bar** | Lower low + Higher close (bull) | Mua trên bar trong uptrend |
| **Key Reversal Bar** | Gap + Engulf toàn bộ bar trước | Mua/bán trên/dưới bar |
| **Exhaustion Bar** | Gap + Volume cao + Gap chưa lấp | Mua/bán trên/dưới bar |
| **Pin Bar** | Đuôi dài (≥2x thân), thân nhỏ | Mua/bán tại S/R quan trọng |
| **Two-Bar Reversal** | 2 bar mạnh ngược chiều | Mua/bán trên/dưới pattern |
| **Three-Bar Reversal** | 3 bar xác nhận đảo chiều | Mua/bán trên/dưới bar cuối |
| **Three-Bar Pullback** | 3 bar ngược trend → vào theo trend | Mua/bán trên/dưới bar xác nhận |

### 5.2 Volatility Patterns

| Pattern | Điều kiện nhận biết | Giao dịch |
|---------|-------------------|-----------|
| **Inside Bar** | Bar 2 nằm hoàn toàn trong Bar 1 | Breakout theo trend / Fade breakout |
| **Outside Bar** | Bar 2 nuốt Bar 1 (HH + LL) | Fade breakout / Trade breakout |
| **NR7** | Bar cuối có range nhỏ nhất trong 7 bar | Breakout theo trend |

### 5.3 Hybrid Patterns (Kết hợp)
- ID/NR4: Inside bar + NR4
- Reversal bar sau Three-Bar Pullback
- Two-Bar Reversal với Inside Bar là bar thứ hai

---

## 6. CANDLESTICK PATTERNS (10 PATTERNS)

### 6.1 Phổ Sức Mạnh
```
YẾU ←————————————————————→ MẠNH
Doji → Harami → Piercing/DCC → Engulfing → Marubozu
```

### 6.2 Basic Sentiment
| Pattern | Ý nghĩa | Giao dịch |
|---------|---------|-----------|
| **Doji** | Open=Close → Do dự | Reversal nếu có trend; Đứng ngoài nếu sideways |
| **Marubozu** | Không bóng → Sức mạnh tối đa | Continuation trong breakout mạnh |

### 6.3 Reversal Patterns (2 bar)
| Pattern | Điều kiện | Giao dịch |
|---------|-----------|-----------|
| **Harami** | Thân nhỏ trong thân lớn | Cuối retracement trong trend |
| **Engulfing** | Thân lớn nuốt thân nhỏ | Mua/bán trên/dưới pattern |
| **Piercing / DCC** | Gap + đóng cửa qua midpoint | Sau phá vỡ trend line |

### 6.4 Single-Bar Reversal
| Pattern | Vị trí | Giao dịch |
|---------|--------|-----------|
| **Hammer** | Sau downtrend | Mua trên Hammer |
| **Hanging Man** | Sau uptrend | Bán dưới sau xác nhận bearish |
| **Inverted Hammer** | Sau downtrend | Mua trên sau xác nhận bullish |
| **Shooting Star** | Sau uptrend | Bán dưới Shooting Star |

### 6.5 Multi-Bar Reversal
| Pattern | Cấu trúc | Giao dịch |
|---------|----------|-----------|
| **Morning Star** | Bearish + Star + Bullish (gap) | Mua trên bar cuối |
| **Evening Star** | Bullish + Star + Bearish (gap) | Bán dưới bar cuối |
| **Three White Soldiers** | 3 bar xanh liên tiếp, đóng gần high | Mua sau market decline lớn |
| **Three Black Crows** | 3 bar đỏ liên tiếp, đóng gần low | Bán sau market rise lớn |
| **Hikkake** | Inside bar + Failed breakout | Mua/bán khi breakout thất bại |

### 6.6 Liên kết Candlestick ↔ Bar Pattern
| Candlestick | Bar Pattern tương đương |
|-------------|------------------------|
| Hammer | Bullish Pin Bar |
| Shooting Star | Bearish Pin Bar |
| Harami | Inside Bar |
| Engulfing | Two-Bar Reversal |
| Morning/Evening Star | Three-Bar Reversal |
| Hikkake | Inside Bar + Failed Breakout |

---

## 7. TRADING CHANNELS

### 7.1 4 Cách Giao Dịch
| Cách | Điều kiện | Hành động |
|------|-----------|-----------|
| **Trend** | Channel dốc, trending | Mua/bán retracement về trend line |
| **Reversal** | Giá vượt channel + rejection mạnh | Giao dịch ngược chiều |
| **Range** | Channel nằm ngang | Mua đáy, bán đỉnh |
| **Breakout** | Phá vỡ channel + volume tăng | Giao dịch theo hướng breakout |

### 7.2 Tránh Overtrading
- Không tìm setup ở tất cả 4 cách cùng lúc
- Vẽ channel lớn hơn để có bức tranh rõ ràng
- Chỉ giao dịch theo một hướng của channel lớn

---

## 8. TRADE EXIT (THOÁT LỆNH)

### 8.1 Stop-Loss
- Đặt dưới đáy của bullish pattern
- Đặt trên đỉnh của bearish pattern
- Dùng S/R gần nhất làm điểm stop

### 8.2 Target — 2 Phương Pháp
**Phương pháp 1: Support/Resistance**
- Long: Resistance gần nhất = target xác suất cao nhất
- Short: Support gần nhất = target xác suất cao nhất

**Phương pháp 2: Measured Move**
- Lấy chiều dài impulse swing trước → chiếu cùng khoảng cách
- Tương đương Fibonacci extension 100%
- Dùng khi giá đang phá vỡ vùng giá mới

---

## 9. CHECKLIST TRƯỚC KHI VÀO LỆNH

```
✅ 1. Market Bias đã xác định? (HH/HL hay LH/LL?)
✅ 2. Đang giao dịch theo hướng bias?
✅ 3. Đã đánh dấu các vùng S/R quan trọng?
✅ 4. Pattern xuất hiện tại vùng S/R?
✅ 5. Volume xác nhận? (nếu có)
✅ 6. Stop-loss đã xác định rõ ràng?
✅ 7. Target hợp lý (R:R ≥ 1:1.5)?
✅ 8. Không mua ngay dưới resistance lớn?
✅ 9. Không bán ngay trên support lớn?
```

---

## 10. NGUYÊN TẮC CỐT LÕI

1. **Market Bias > Price Pattern** — Bias đúng, gần như pattern nào cũng cho kết quả
2. **S/R là vùng, không phải đường** — Và có thể flip sau breakout
3. **Volume xác nhận tất cả** — Breakout không có volume = nghi ngờ
4. **Bar patterns đơn thuần không tạo edge** — Phải kết hợp với bias + S/R + volume
5. **Vị trí quyết định ý nghĩa** — Cùng hình dạng, khác vị trí = khác ý nghĩa (Hammer vs Hanging Man)
6. **Thất bại kỳ vọng = Tín hiệu mạnh** — Khi thị trường không làm điều bạn kỳ vọng
7. **Tên gọi không quan trọng** — Hiểu cơ chế quan trọng hơn nhớ tên
8. **Chart patterns thất bại** — Không có phương pháp nào hoàn hảo 100%

---

## 11. QUICK REFERENCE — PATTERN LOOKUP

### Khi thấy pattern, hỏi:
1. **Trend hiện tại là gì?** (HH/HL hay LH/LL?)
2. **Pattern ở đâu?** (Tại S/R? Giữa không khí?)
3. **Volume như thế nào?** (Tăng hay giảm?)
4. **Stop-loss ở đâu?** (Đáy/đỉnh của pattern)
5. **Target ở đâu?** (S/R gần nhất hoặc Measured Move)

### Bullish Setups (Mua)
- Pin Bar / Hammer tại support trong uptrend
- Bullish Engulfing / Two-Bar Reversal tại support
- Three-Bar Pullback trong uptrend
- Inside Bar breakout lên trong uptrend
- Morning Star / Three White Soldiers sau decline lớn

### Bearish Setups (Bán)
- Pin Bar / Shooting Star tại resistance trong downtrend
- Bearish Engulfing / Two-Bar Reversal tại resistance
- Three-Bar Pullback trong downtrend
- Inside Bar breakout xuống trong downtrend
- Evening Star / Three Black Crows sau rise lớn

---

*Tổng hợp từ: price-action/ — "How to Trade with Price Action" (Galen Woods)*
*Dùng kèm với: requirements.md của crypto-trading-system*
