# Advanced Chart Patterns

> Nguồn: Advanced Chart Patterns Cheat Sheet + Chart Patterns Cheat Sheet — HowToTrade
> Tài liệu tham khảo lý thuyết cho hệ thống giao dịch

---

## Tổng Quan

Tài liệu này tổng hợp toàn bộ chart patterns từ 2 cheat sheet của HowToTrade, bao gồm:

- **Candlestick Patterns** (Mô hình nến đơn/đa nến)
- **Chart Patterns — Reversal** (Mô hình đảo chiều)
- **Chart Patterns — Continuation** (Mô hình tiếp diễn)
- **Wyckoff Pattern** (Phân tích chu kỳ thị trường)

### Cấu Trúc File

| Phần | Nội dung |
|------|----------|
| Phần 1 | Candlestick Patterns (15 patterns) |
| Phần 2 | Chart Patterns — Reversal (5 patterns) |
| Phần 3 | Chart Patterns — Continuation (5 patterns) |
| Phần 4 | Wyckoff Pattern |
| Phần 5 | Rectangle Pattern |

---

## PHẦN 1: CANDLESTICK PATTERNS

---

## 1.1 Engulfing Candle Patterns (Mô Hình Nến Nhấn Chìm)

### Hình Dạng

```
BULLISH ENGULFING:
  Bar 1: [Đỏ nhỏ] — Bearish
  Bar 2: [Xanh lớn] — Thân Bar 2 NUỐT CHỬNG hoàn toàn thân Bar 1

BEARISH ENGULFING:
  Bar 1: [Xanh nhỏ] — Bullish
  Bar 2: [Đỏ lớn] — Thân Bar 2 NUỐT CHỬNG hoàn toàn thân Bar 1
```

### Ý Nghĩa
- Tín hiệu đảo chiều **mạnh**
- Nến thứ hai hoàn toàn nuốt chửng nến đầu tiên → phe đối lập chiếm hoàn toàn quyền kiểm soát

### Cách Giao Dịch
- **Bullish Engulfing**: Mua trên high của nến thứ hai, stop dưới low của pattern
- **Bearish Engulfing**: Bán dưới low của nến thứ hai, stop trên high của pattern

---

## 1.2 Bullish and Bearish Island Reversal Patterns

### Hình Dạng

```
BULLISH ISLAND REVERSAL:
  Xu hướng giảm → Gap xuống → Vùng giá đảo (Island) → Gap lên → Đảo chiều tăng

BEARISH ISLAND REVERSAL:
  Xu hướng tăng → Gap lên → Vùng giá đảo (Island) → Gap xuống → Đảo chiều giảm
```

### Ý Nghĩa
- Vùng giá bị **tách biệt hoàn toàn** khỏi phần còn lại của chart bởi 2 gap
- Gap đầu tiên (Exhaustion Gap): Động thái cực đoan theo xu hướng cũ
- Gap thứ hai (Breakaway Gap): Xác nhận đảo chiều
- Tín hiệu đảo chiều **rất mạnh**

### Cách Giao Dịch
- **Bullish**: Mua khi giá gap lên khỏi Island, stop dưới đáy Island
- **Bearish**: Bán khi giá gap xuống khỏi Island, stop trên đỉnh Island

---

## 1.3 Three Inside Up Chart Pattern

### Hình Dạng

```
THREE INSIDE UP:
  Bar 1: [Đỏ lớn] — Bearish mạnh
  Bar 2: [Xanh nhỏ] — Nằm trong thân Bar 1 (Harami)
  Bar 3: [Xanh] — Đóng cửa TRÊN high của Bar 1 → Xác nhận bullish
```

### Ý Nghĩa
- Biến thể của Harami + xác nhận
- Bar 3 đóng cửa trên Bar 1 = xác nhận đảo chiều tăng hoàn toàn
- Tín hiệu **bullish reversal** đáng tin cậy

### Cách Giao Dịch
- Mua khi Bar 3 đóng cửa trên high của Bar 1
- Stop dưới low của Bar 1

---

## 1.4 Three Black Crows & Three White Soldiers

### Hình Dạng

```
THREE WHITE SOLDIERS (Bullish):
  Bar 1: [Xanh] — Mở trong thân bar trước, đóng gần high
  Bar 2: [Xanh] — Mở trong thân Bar 1, đóng gần high
  Bar 3: [Xanh] — Mở trong thân Bar 2, đóng gần high
  → 3 nến xanh liên tiếp, mỗi nến cao hơn nến trước

THREE BLACK CROWS (Bearish):
  Bar 1: [Đỏ] — Mở trong thân bar trước, đóng gần low
  Bar 2: [Đỏ] — Mở trong thân Bar 1, đóng gần low
  Bar 3: [Đỏ] — Mở trong thân Bar 2, đóng gần low
  → 3 nến đỏ liên tiếp, mỗi nến thấp hơn nến trước
```

### Ý Nghĩa
- **Three White Soldiers**: Tín hiệu đảo chiều tăng mạnh sau downtrend
- **Three Black Crows**: Tín hiệu đảo chiều giảm mạnh sau uptrend
- 3 lần liên tiếp xác nhận → momentum rõ ràng

### Cách Giao Dịch
- **Three White Soldiers**: Mua sau khi bar thứ 3 đóng cửa, tốt nhất sau downtrend đáng kể
- **Three Black Crows**: Bán sau khi bar thứ 3 đóng cửa, tốt nhất sau uptrend đáng kể

---

## 1.5 Bullish and Bearish Breakaway Pattern

### Hình Dạng

```
BULLISH BREAKAWAY (5 bar):
  Bar 1: [Đỏ lớn] — Bearish mạnh
  Bar 2: [Đỏ] — Gap xuống, tiếp tục giảm
  Bar 3: [Đỏ/Xanh nhỏ] — Tiếp tục giảm nhẹ
  Bar 4: [Đỏ/Xanh nhỏ] — Tiếp tục giảm nhẹ
  Bar 5: [Xanh lớn] — Đóng cửa trong gap của Bar 1-2 → Đảo chiều

BEARISH BREAKAWAY (5 bar):
  Bar 1: [Xanh lớn] — Bullish mạnh
  Bar 2: [Xanh] — Gap lên, tiếp tục tăng
  Bar 3-4: [Nhỏ] — Tiếp tục tăng nhẹ
  Bar 5: [Đỏ lớn] — Đóng cửa trong gap của Bar 1-2 → Đảo chiều
```

### Ý Nghĩa
- Pattern 5 nến phức tạp
- Gap tạo ra "khoảng trống" → khi giá quay lại lấp gap = tín hiệu đảo chiều
- Tín hiệu đảo chiều **trung bình đến mạnh**

### Cách Giao Dịch
- **Bullish**: Mua khi Bar 5 đóng cửa, stop dưới low của pattern
- **Bearish**: Bán khi Bar 5 đóng cửa, stop trên high của pattern

---

## 1.6 Bearish and Bullish Harami Chart Patterns

### Hình Dạng

```
BULLISH HARAMI:
  Bar 1: [Đỏ lớn] — Bearish mạnh
  Bar 2: [Xanh nhỏ] — Thân nằm HOÀN TOÀN trong thân Bar 1

BEARISH HARAMI:
  Bar 1: [Xanh lớn] — Bullish mạnh
  Bar 2: [Đỏ nhỏ] — Thân nằm HOÀN TOÀN trong thân Bar 1
```

### Ý Nghĩa
- Tín hiệu đảo chiều **yếu** (cần xác nhận thêm)
- Thân nhỏ = momentum giảm, thị trường do dự
- Harami = "mang thai" trong tiếng Nhật cổ

### Cách Giao Dịch
- **Bullish Harami**: Mua khi có xác nhận bullish tiếp theo, stop dưới low của Bar 1
- **Bearish Harami**: Bán khi có xác nhận bearish tiếp theo, stop trên high của Bar 1

> ⚠️ **Lưu ý**: Harami yếu hơn Engulfing. Luôn chờ xác nhận trước khi vào lệnh.

---

## 1.7 Abandoned Baby Bullish Candle Pattern

### Hình Dạng

```
ABANDONED BABY (Bullish):
  Bar 1: [Đỏ lớn] — Bearish mạnh
  Bar 2: [Doji] — Gap xuống, tách biệt hoàn toàn (không chồng lên Bar 1 và Bar 3)
  Bar 3: [Xanh lớn] — Gap lên, đóng cửa mạnh

ABANDONED BABY (Bearish):
  Bar 1: [Xanh lớn] — Bullish mạnh
  Bar 2: [Doji] — Gap lên, tách biệt hoàn toàn
  Bar 3: [Đỏ lớn] — Gap xuống, đóng cửa mạnh
```

### Ý Nghĩa
- Biến thể đặc biệt của Morning/Evening Star với **Doji** ở giữa
- Doji bị "bỏ rơi" (abandoned) — tách biệt hoàn toàn bởi 2 gap
- Tín hiệu đảo chiều **rất mạnh** (hiếm gặp)

### Cách Giao Dịch
- **Bullish**: Mua khi Bar 3 đóng cửa, stop dưới low của Doji
- **Bearish**: Bán khi Bar 3 đóng cửa, stop trên high của Doji

---

## 1.8 Piercing Line Pattern

### Hình Dạng

```
PIERCING LINE (Bullish):
  Bar 1: [Đỏ lớn]
  Bar 2: Mở cửa dưới Low Bar 1 (gap xuống) → Đóng cửa TRÊN midpoint Bar 1

DARK CLOUD COVER (Bearish):
  Bar 1: [Xanh lớn]
  Bar 2: Mở cửa trên High Bar 1 (gap lên) → Đóng cửa DƯỚI midpoint Bar 1
```

### Ý Nghĩa
- Nến thứ hai xóa bỏ hơn 50% nến đầu tiên
- Tín hiệu đảo chiều **trung bình** (yếu hơn Engulfing)
- Hiếm gặp trong intraday vì cần gap

### Cách Giao Dịch
- **Piercing Line**: Mua trên high của Bar 2, stop dưới low của Bar 2
- **Dark Cloud Cover**: Bán dưới low của Bar 2, stop trên high của Bar 2

---

## 1.9 Tweezer Top Pattern

### Hình Dạng

```
TWEEZER TOP (Bearish):
  Bar 1: [Xanh] — Bullish, đẩy lên high
  Bar 2: [Đỏ] — Bearish, cùng high với Bar 1 (hoặc rất gần)
  → 2 nến có cùng high → kháng cự mạnh

TWEEZER BOTTOM (Bullish):
  Bar 1: [Đỏ] — Bearish, đẩy xuống low
  Bar 2: [Xanh] — Bullish, cùng low với Bar 1 (hoặc rất gần)
  → 2 nến có cùng low → hỗ trợ mạnh
```

### Ý Nghĩa
- Hai lần thất bại tại cùng một mức giá = vùng S/R mạnh
- **Tweezer Top**: Kháng cự mạnh → đảo chiều giảm
- **Tweezer Bottom**: Hỗ trợ mạnh → đảo chiều tăng

### Cách Giao Dịch
- **Tweezer Top**: Bán dưới low của Bar 2, stop trên high chung
- **Tweezer Bottom**: Mua trên high của Bar 2, stop dưới low chung

---

## 1.10 Upside Gap Three Methods Pattern

### Hình Dạng

```
UPSIDE GAP THREE METHODS (Bullish Continuation):
  Bar 1: [Xanh lớn] — Bullish mạnh
  Bar 2: [Xanh] — Gap lên, tiếp tục tăng
  Bar 3: [Đỏ] — Giảm lấp gap, nhưng đóng cửa TRONG thân Bar 1
  → Pullback thất bại → tiếp tục tăng

DOWNSIDE GAP THREE METHODS (Bearish Continuation):
  Bar 1: [Đỏ lớn] — Bearish mạnh
  Bar 2: [Đỏ] — Gap xuống, tiếp tục giảm
  Bar 3: [Xanh] — Tăng lấp gap, nhưng đóng cửa TRONG thân Bar 1
  → Pullback thất bại → tiếp tục giảm
```

### Ý Nghĩa
- Mô hình **tiếp diễn (continuation)**
- Pullback (Bar 3) thất bại trong việc lấp đầy gap → xu hướng chính vẫn mạnh
- Xác nhận momentum theo xu hướng

### Cách Giao Dịch
- **Upside Gap**: Mua khi Bar 3 đóng cửa trong thân Bar 1, stop dưới low Bar 3
- **Downside Gap**: Bán khi Bar 3 đóng cửa trong thân Bar 1, stop trên high Bar 3

---

## 1.11 Falling Three Methods Pattern

### Hình Dạng

```
FALLING THREE METHODS (Bearish Continuation):
  Bar 1: [Đỏ lớn] — Bearish mạnh
  Bar 2-4: [Xanh nhỏ] — 3 nến tăng nhỏ, nằm trong range Bar 1
  Bar 5: [Đỏ lớn] — Đóng cửa dưới low Bar 1 → Tiếp tục giảm

RISING THREE METHODS (Bullish Continuation):
  Bar 1: [Xanh lớn] — Bullish mạnh
  Bar 2-4: [Đỏ nhỏ] — 3 nến giảm nhỏ, nằm trong range Bar 1
  Bar 5: [Xanh lớn] — Đóng cửa trên high Bar 1 → Tiếp tục tăng
```

### Ý Nghĩa
- Mô hình **tiếp diễn** 5 nến
- 3 nến giữa là giai đoạn nghỉ ngắn (consolidation)
- Bar 5 xác nhận xu hướng tiếp tục

### Cách Giao Dịch
- **Falling Three Methods**: Bán khi Bar 5 đóng cửa dưới low Bar 1
- **Rising Three Methods**: Mua khi Bar 5 đóng cửa trên high Bar 1

---

## 1.12 3 Bar Play Pattern

### Hình Dạng

```
BULLISH 3 BAR PLAY:
  Bar 1: [Xanh lớn] — Bullish mạnh, range rộng
  Bar 2: [Nhỏ] — Inside bar hoặc narrow range (consolidation)
  Bar 3: [Xanh] — Breakout lên trên high Bar 1 → Vào lệnh

BEARISH 3 BAR PLAY:
  Bar 1: [Đỏ lớn] — Bearish mạnh, range rộng
  Bar 2: [Nhỏ] — Inside bar hoặc narrow range
  Bar 3: [Đỏ] — Breakout xuống dưới low Bar 1 → Vào lệnh
```

### Ý Nghĩa
- Mô hình **tiếp diễn** đơn giản và hiệu quả
- Bar 1 = momentum mạnh
- Bar 2 = tích lũy ngắn
- Bar 3 = tiếp tục theo hướng Bar 1

### Cách Giao Dịch
- **Bullish**: Mua khi Bar 3 breakout trên high Bar 1, stop dưới low Bar 2
- **Bearish**: Bán khi Bar 3 breakout dưới low Bar 1, stop trên high Bar 2

---

## 1.13 Hanging Man Chart Pattern

### Hình Dạng

```
HANGING MAN (Bearish):
  Xuất hiện sau UPTREND
  Thân nhỏ ở TRÊN
  Bóng dưới dài (~2x thân)
  Không có (hoặc rất ít) bóng trên

HAMMER (Bullish):
  Xuất hiện sau DOWNTREND
  Hình dạng GIỐNG HỆT Hanging Man
  → Vị trí quyết định ý nghĩa
```

### Ý Nghĩa
- **Hanging Man**: Xuất hiện ở đỉnh uptrend → tín hiệu bearish reversal
- Bóng dưới dài = bears đã đẩy giá xuống mạnh trong phiên, nhưng bulls kéo lại
- Tuy nhiên, sự xuất hiện của bears ở đỉnh = cảnh báo đảo chiều

### Cách Giao Dịch
- **Hanging Man**: Bán dưới low của nến sau khi có xác nhận bearish
- **Hammer**: Mua trên high của nến, stop dưới low của Hammer

> 📌 **Quy tắc nhớ**: Cùng hình dạng, khác vị trí → khác ý nghĩa
> - Sau downtrend → **Hammer** (bullish)
> - Sau uptrend → **Hanging Man** (bearish)

---

## 1.14 Bullish Hammer Pattern

### Hình Dạng

```
BULLISH HAMMER:
  Xuất hiện sau DOWNTREND
  Thân nhỏ ở TRÊN
  Bóng dưới dài (ít nhất 2x thân)
  Không có (hoặc rất ít) bóng trên
  Màu sắc thân không quan trọng (xanh tốt hơn đỏ)
```

### Ý Nghĩa
- Bears đẩy giá xuống mạnh trong phiên → Bulls kéo giá trở lại gần mức mở cửa
- Bẫy các trader đã bán ở vùng thấp → buộc họ đóng short → tạo áp lực mua
- Tín hiệu **bullish reversal** tại vùng hỗ trợ

### Cách Giao Dịch
- Mua trên high của Hammer, stop dưới low của Hammer
- Tốt nhất khi xuất hiện tại vùng S/R quan trọng hoặc sau downtrend rõ ràng

---

## 1.15 Three Inside Up Pattern

### Hình Dạng

```
THREE INSIDE UP:
  Bar 1: [Đỏ lớn] — Bearish mạnh
  Bar 2: [Xanh nhỏ] — Harami (thân trong thân Bar 1)
  Bar 3: [Xanh] — Đóng cửa TRÊN high Bar 1 → Xác nhận hoàn toàn

(Lưu ý: Giống mục 1.3 nhưng nhấn mạnh thêm về cấu trúc Harami + xác nhận)
```

### Ý Nghĩa
- Harami (Bar 1-2) = tín hiệu đảo chiều yếu ban đầu
- Bar 3 đóng cửa trên Bar 1 = xác nhận đảo chiều mạnh
- Kết hợp 2 tín hiệu → độ tin cậy cao hơn

---

## PHẦN 2: CHART PATTERNS — REVERSAL PATTERNS

---

## 2.1 Double Top / Double Bottom (Đỉnh Đôi / Đáy Đôi)

### Hình Dạng

```
BEARISH DOUBLE TOP:
  Xuất hiện sau UPTREND
  Đỉnh 1 → Pullback xuống (Neckline) → Đỉnh 2 (cùng mức Đỉnh 1)
  Breakout: Giá phá xuống dưới Neckline → Đảo chiều giảm

BULLISH DOUBLE BOTTOM:
  Xuất hiện sau DOWNTREND
  Đáy 1 → Pullback lên (Neckline) → Đáy 2 (cùng mức Đáy 1)
  Breakout: Giá phá lên trên Neckline → Đảo chiều tăng
```

### Ý Nghĩa
- **Double Top**: 2 lần thất bại phá lên trên resistance → phe mua kiệt sức → đảo chiều giảm
- **Double Bottom**: 2 lần thất bại phá xuống dưới support → phe bán kiệt sức → đảo chiều tăng
- Neckline là mức giá then chốt — breakout qua đây xác nhận pattern

### Cách Giao Dịch
- **Double Top**: Bán khi giá breakout dưới Neckline, hoặc chờ pullback về Neckline (nay là resistance)
- **Double Bottom**: Mua khi giá breakout trên Neckline, hoặc chờ pullback về Neckline (nay là support)
- **Stop**: Trên đỉnh cao nhất (Double Top) / Dưới đáy thấp nhất (Double Bottom)
- **Target**: Chiều cao từ đỉnh/đáy đến Neckline, chiếu từ điểm breakout

### Volume
- Volume **giảm** ở đỉnh/đáy thứ 2 (xác nhận kiệt sức)
- Volume **tăng** khi breakout qua Neckline

---

## 2.2 Head & Shoulders / Inverted Head & Shoulders

### Hình Dạng

```
BEARISH HEAD & SHOULDERS:
  Xuất hiện sau UPTREND
  Left Shoulder (đỉnh trái) → Head (đỉnh cao nhất) → Right Shoulder (đỉnh phải, thấp hơn Head)
  Neckline: Nối 2 đáy giữa các đỉnh
  Breakout: Giá phá xuống dưới Neckline → Đảo chiều giảm

BULLISH INVERTED HEAD & SHOULDERS:
  Xuất hiện sau DOWNTREND
  Left Shoulder (đáy trái) → Head (đáy thấp nhất) → Right Shoulder (đáy phải, cao hơn Head)
  Neckline: Nối 2 đỉnh giữa các đáy
  Breakout: Giá phá lên trên Neckline → Đảo chiều tăng
```

### Ý Nghĩa
- Một trong những mô hình đảo chiều **đáng tin cậy nhất**
- Head = đỉnh/đáy cực đoan cuối cùng của xu hướng cũ
- Right Shoulder thấp hơn Head (H&S) hoặc cao hơn Head (Inverted) = momentum suy yếu
- Breakout qua Neckline = xác nhận đảo chiều hoàn toàn

### Cách Giao Dịch
- **H&S**: Bán khi breakout dưới Neckline, stop trên Right Shoulder
- **Inverted H&S**: Mua khi breakout trên Neckline, stop dưới Right Shoulder
- **Target**: Đo khoảng cách từ Head đến Neckline, chiếu từ điểm breakout

### Volume
- Volume **giảm dần** từ Left Shoulder → Head → Right Shoulder
- Volume **tăng mạnh** khi breakout qua Neckline

> 💡 **Lưu ý**: Neckline có thể dốc lên hoặc dốc xuống, không nhất thiết phải nằm ngang.

---

## 2.3 Rising Wedge / Falling Wedge — Reversal Context

### Hình Dạng

```
BEARISH RISING WEDGE (Reversal):
  Xuất hiện sau UPTREND
  2 đường trend line hội tụ, cả 2 dốc LÊN
  Swing high và swing low đều tăng, nhưng biên độ thu hẹp
  Breakout: Giá phá xuống dưới đường support → Đảo chiều giảm

BULLISH FALLING WEDGE (Reversal):
  Xuất hiện sau DOWNTREND
  2 đường trend line hội tụ, cả 2 dốc XUỐNG
  Swing high và swing low đều giảm, nhưng biên độ thu hẹp
  Breakout: Giá phá lên trên đường resistance → Đảo chiều tăng
```

### Ý Nghĩa
- **Rising Wedge** sau uptrend: Giá tăng nhưng momentum yếu dần → đảo chiều giảm
- **Falling Wedge** sau downtrend: Giá giảm nhưng áp lực bán yếu dần → đảo chiều tăng
- Biên độ thu hẹp = phe đang kiểm soát đang mất dần sức mạnh

### Cách Giao Dịch
- **Rising Wedge**: Bán khi breakout dưới đường support, stop trên đỉnh gần nhất
- **Falling Wedge**: Mua khi breakout trên đường resistance, stop dưới đáy gần nhất
- **Target**: Chiều cao toàn bộ Wedge chiếu từ điểm breakout

### Volume
- Volume **giảm** trong quá trình hình thành Wedge
- Volume **tăng** khi breakout

> ⚠️ **Wedge có 2 ngữ cảnh**: Reversal (xuất hiện cuối trend) và Continuation (xuất hiện giữa trend). Xem thêm mục 3.3.

---

## 2.4 Expanding Triangle — Reversal Context (Tam Giác Mở Rộng)

### Hình Dạng

```
BEARISH EXPANDING TRIANGLE (Reversal):
  Xuất hiện sau UPTREND
  2 đường trend line PHÂN KỲ (diverge) — mở rộng ra
  Swing high ngày càng CAO hơn
  Swing low ngày càng THẤP hơn
  Breakout: Giá phá xuống dưới đường support → Đảo chiều giảm

BULLISH EXPANDING TRIANGLE (Reversal):
  Xuất hiện sau DOWNTREND
  Tương tự nhưng ngược lại
  Breakout: Giá phá lên trên đường resistance → Đảo chiều tăng
```

### Ý Nghĩa
- Ngược với Triangle thông thường (hội tụ) — đây là **phân kỳ**
- Biên độ dao động ngày càng lớn = thị trường mất kiểm soát, biến động tăng cao
- Thường xuất hiện ở đỉnh/đáy của xu hướng lớn
- Tín hiệu đảo chiều khi giá phá ra khỏi một trong 2 đường

### Cách Giao Dịch
- **Bearish**: Bán khi giá phá xuống dưới đường support thấp nhất
- **Bullish**: Mua khi giá phá lên trên đường resistance cao nhất
- **Stop**: Bên trong vùng Expanding Triangle
- **Target**: Chiều cao phần rộng nhất của Triangle

### Volume
- Volume **tăng** theo biên độ dao động (không giảm như Triangle thông thường)
- Volume **tăng mạnh** khi breakout

---

## 2.5 Triple Top / Triple Bottom (Đỉnh Ba / Đáy Ba)

### Hình Dạng

```
BEARISH TRIPLE TOP:
  Xuất hiện sau UPTREND
  3 đỉnh (swing high) ở cùng mức giá
  Neckline: Đường support nối các đáy giữa
  Breakout: Giá phá xuống dưới Neckline → Đảo chiều giảm

BULLISH TRIPLE BOTTOM:
  Xuất hiện sau DOWNTREND
  3 đáy (swing low) ở cùng mức giá
  Neckline: Đường resistance nối các đỉnh giữa
  Breakout: Giá phá lên trên Neckline → Đảo chiều tăng
```

### Ý Nghĩa
- Phiên bản mạnh hơn của Double Top/Bottom — **3 lần thất bại** tại cùng mức giá
- Mỗi lần thất bại = xác nhận thêm vùng S/R quan trọng
- Tín hiệu đảo chiều **đáng tin cậy cao**

### Cách Giao Dịch
- **Triple Top**: Bán khi breakout dưới Neckline, stop trên đỉnh cao nhất
- **Triple Bottom**: Mua khi breakout trên Neckline, stop dưới đáy thấp nhất
- **Re-entry**: Chờ pullback về Neckline sau breakout
- **Target**: Chiều cao từ đỉnh/đáy đến Neckline, chiếu từ điểm breakout

### Volume
- Volume **giảm dần** qua mỗi lần đẩy lên/xuống
- Volume **tăng** khi breakout qua Neckline

---

## PHẦN 3: CHART PATTERNS — CONTINUATION PATTERNS

---

## 3.1 Flag & Pennant (Cờ & Cờ Đuôi Nheo)

### Hình Dạng

```
BULLISH FLAG (Continuation):
  Flag Pole: Cú thrust tăng mạnh (nhiều nến xanh, volume lớn)
  Flag: 2 đường song song dốc XUỐNG (pullback ngắn)
  Breakout: Giá phá lên trên đường resistance của Flag → Tiếp tục tăng

BEARISH FLAG (Continuation):
  Flag Pole: Cú thrust giảm mạnh (nhiều nến đỏ, volume lớn)
  Flag: 2 đường song song dốc LÊN (pullback ngắn)
  Breakout: Giá phá xuống dưới đường support của Flag → Tiếp tục giảm

BULLISH PENNANT (Continuation):
  Flag Pole: Cú thrust tăng mạnh
  Pennant: 2 đường hội tụ (Symmetrical Triangle nhỏ)
  Breakout: Giá phá lên trên đường resistance → Tiếp tục tăng

BEARISH PENNANT (Continuation):
  Flag Pole: Cú thrust giảm mạnh
  Pennant: 2 đường hội tụ
  Breakout: Giá phá xuống dưới đường support → Tiếp tục giảm
```

### Ý Nghĩa
- Flag Pole = momentum mạnh theo xu hướng chính
- Flag/Pennant = giai đoạn nghỉ ngắn (consolidation) — phe đối lập không đủ mạnh để đảo chiều
- Khi breakout = xu hướng chính tiếp tục với momentum mới
- **Pennant** là biến thể của Flag với phần consolidation hình tam giác thay vì song song

### Cách Giao Dịch
- **Bullish Flag/Pennant**: Mua khi breakout trên đường resistance, stop dưới đáy Flag/Pennant
- **Bearish Flag/Pennant**: Bán khi breakout dưới đường support, stop trên đỉnh Flag/Pennant
- **Target**: Đo chiều cao **Flag Pole** → chiếu từ điểm thấp nhất của Flag (bullish) hoặc cao nhất (bearish)

### Volume
- Volume **lớn** trong Flag Pole
- Volume **giảm** trong quá trình hình thành Flag/Pennant
- Volume **tăng** khi breakout

> ⚠️ **Target của Flag khác các mô hình khác**: Dùng chiều cao Flag Pole, không phải chiều cao Flag.

---

## 3.2 Descending Triangle (Tam Giác Giảm Dần)

### Hình Dạng

```
DESCENDING TRIANGLE (Bearish Continuation):
  Xuất hiện trong DOWNTREND
  Resistance: Dốc XUỐNG (lower highs)
  Support: Nằm NGANG (horizontal)
  → Swing high ngày càng thấp, swing low giữ nguyên
  Breakout: Giá phá xuống dưới đường support nằm ngang → Tiếp tục giảm

(Lưu ý: Descending Triangle cũng có thể là Reversal nếu xuất hiện sau uptrend)
```

### Ý Nghĩa
- Phe mua cố giữ vùng support nằm ngang, nhưng phe bán liên tục tạo lower highs
- Áp lực bán ngày càng tăng → khi support vỡ = breakout mạnh
- Mô hình **tiếp diễn bearish** trong downtrend

### Cách Giao Dịch
- **Entry**: Bán khi giá breakout xuống dưới đường support nằm ngang
- **Re-entry**: Bán khi pullback về đường support (nay là resistance)
- **Stop**: Trên đỉnh gần nhất (lower high)
- **Target**: Chiều cao phần rộng nhất của Triangle chiếu từ điểm breakout

### Volume
- Volume **giảm** trong quá trình hình thành
- Volume **tăng** khi breakout

---

## 3.3 Wedge — Continuation Context

### Hình Dạng

```
BULLISH FALLING WEDGE (Continuation trong Uptrend):
  Xuất hiện GIỮA uptrend (pullback tạm thời)
  2 đường hội tụ, cả 2 dốc XUỐNG
  Breakout: Giá phá lên trên đường resistance → Tiếp tục uptrend

BEARISH RISING WEDGE (Continuation trong Downtrend):
  Xuất hiện GIỮA downtrend (pullback tạm thời)
  2 đường hội tụ, cả 2 dốc LÊN
  Breakout: Giá phá xuống dưới đường support → Tiếp tục downtrend
```

### Ý Nghĩa
- Wedge trong ngữ cảnh continuation = giai đoạn pullback/retracement ngắn
- Biên độ thu hẹp = pullback đang mất dần sức mạnh
- Khi breakout theo hướng xu hướng chính = tiếp tục xu hướng

### Cách Giao Dịch
- Giống Wedge Reversal nhưng **thuận chiều xu hướng chính**
- **Bullish Falling Wedge**: Mua khi breakout trên resistance, stop dưới đáy Wedge
- **Bearish Rising Wedge**: Bán khi breakout dưới support, stop trên đỉnh Wedge

> 📌 **Phân biệt Wedge Reversal vs Continuation**:
> - **Reversal**: Xuất hiện ở **cuối** xu hướng (Rising Wedge sau uptrend, Falling Wedge sau downtrend)
> - **Continuation**: Xuất hiện **giữa** xu hướng (Falling Wedge trong uptrend, Rising Wedge trong downtrend)

---

## 3.4 Symmetrical Expanding Triangle (Tam Giác Mở Rộng Đối Xứng)

### Hình Dạng

```
SYMMETRICAL EXPANDING TRIANGLE (Continuation):
  2 đường trend line PHÂN KỲ đối xứng
  Swing high ngày càng CAO hơn
  Swing low ngày càng THẤP hơn
  Breakout: Theo hướng xu hướng chính

BULLISH (trong uptrend):
  Breakout lên trên đường resistance → Tiếp tục tăng

BEARISH (trong downtrend):
  Breakout xuống dưới đường support → Tiếp tục giảm
```

### Ý Nghĩa
- Biên độ dao động tăng dần = thị trường đang tích lũy năng lượng
- Khác với Expanding Triangle Reversal: xuất hiện **giữa** xu hướng, không phải cuối
- Breakout theo hướng xu hướng chính = tiếp tục xu hướng với momentum mạnh

### Cách Giao Dịch
- **Bullish**: Mua khi breakout trên đường resistance cao nhất, stop dưới đáy gần nhất
- **Bearish**: Bán khi breakout dưới đường support thấp nhất, stop trên đỉnh gần nhất
- **Target**: Chiều cao phần rộng nhất của Triangle

### Volume
- Volume **tăng** theo biên độ dao động
- Volume **tăng mạnh** khi breakout

---

## 3.5 Bullish Falling Wedge / Bearish Rising Wedge (Continuation)

> Xem mục **3.3** — Wedge Continuation Context

---

## PHẦN 4: WYCKOFF PATTERN

---

## 4.1 Wyckoff Pattern

### Hình Dạng

```
WYCKOFF ACCUMULATION (Bullish):
  Phase A: Stopping the downtrend (SC, AR, ST)
  Phase B: Building a cause (trading range)
  Phase C: Test (Spring — giá phá xuống giả, bẫy bears)
  Phase D: Markup begins (SOS — Sign of Strength)
  Phase E: Trend up

WYCKOFF DISTRIBUTION (Bearish):
  Phase A: Stopping the uptrend (PSY, BC, AR, ST)
  Phase B: Building a cause (trading range)
  Phase C: Test (UTAD — Upthrust After Distribution)
  Phase D: Markdown begins (SOW — Sign of Weakness)
  Phase E: Trend down
```

### Ý Nghĩa
- Phương pháp phân tích thị trường của Richard Wyckoff
- Thị trường vận động theo chu kỳ: **Accumulation → Markup → Distribution → Markdown**
- **Spring** (Wyckoff Accumulation): Giá phá xuống dưới support giả → bẫy bears → đảo chiều tăng mạnh
- **UTAD** (Wyckoff Distribution): Giá phá lên trên resistance giả → bẫy bulls → đảo chiều giảm mạnh

### Các Khái Niệm Chính

| Thuật ngữ | Ý nghĩa |
|-----------|---------|
| SC (Selling Climax) | Đỉnh bán tháo — kết thúc downtrend |
| AR (Automatic Rally) | Phục hồi tự động sau SC |
| ST (Secondary Test) | Kiểm tra lại vùng SC |
| Spring | Phá xuống giả — bẫy bears |
| SOS (Sign of Strength) | Tín hiệu sức mạnh — bắt đầu markup |
| BC (Buying Climax) | Đỉnh mua — kết thúc uptrend |
| UTAD | Phá lên giả — bẫy bulls |
| SOW (Sign of Weakness) | Tín hiệu yếu — bắt đầu markdown |

### Cách Giao Dịch
- **Accumulation**: Mua tại Spring (phá xuống giả) hoặc khi SOS xác nhận
- **Distribution**: Bán tại UTAD (phá lên giả) hoặc khi SOW xác nhận
- Kết hợp với volume để xác nhận từng phase

---

## PHẦN 5: RECTANGLE PATTERN

---

## 5.1 Bullish Rectangle Chart Pattern

### Hình Dạng

```
BULLISH RECTANGLE:
  Xuất hiện trong UPTREND
  Giá dao động giữa 2 đường nằm ngang song song
  Resistance: Đường trên (nằm ngang)
  Support: Đường dưới (nằm ngang)
  Breakout: Lên trên resistance → Tiếp tục uptrend
```

### Ý Nghĩa
- Giai đoạn tích lũy (consolidation) trong uptrend
- Mô hình **tiếp diễn (continuation)**
- Giá "nghỉ ngơi" trước khi tiếp tục tăng

### Cách Giao Dịch
- **Entry**: Mua khi breakout lên trên resistance
- **Re-entry**: Mua khi pullback về resistance (nay là support)
- **Stop**: Dưới support của rectangle
- **Target**: Chiều cao rectangle chiếu từ điểm breakout

### Hình Dạng

```
WYCKOFF ACCUMULATION (Bullish):
  Phase A: Stopping the downtrend (SC, AR, ST)
  Phase B: Building a cause (trading range)
  Phase C: Test (Spring — giá phá xuống giả, bẫy bears)
  Phase D: Markup begins (SOS — Sign of Strength)
  Phase E: Trend up

WYCKOFF DISTRIBUTION (Bearish):
  Phase A: Stopping the uptrend (PSY, BC, AR, ST)
  Phase B: Building a cause (trading range)
  Phase C: Test (UTAD — Upthrust After Distribution)
  Phase D: Markdown begins (SOW — Sign of Weakness)
  Phase E: Trend down
```

### Ý Nghĩa
- Phương pháp phân tích thị trường của Richard Wyckoff
- Thị trường vận động theo chu kỳ: **Accumulation → Markup → Distribution → Markdown**
- **Spring** (Wyckoff Accumulation): Giá phá xuống dưới support giả → bẫy bears → đảo chiều tăng mạnh
- **UTAD** (Wyckoff Distribution): Giá phá lên trên resistance giả → bẫy bulls → đảo chiều giảm mạnh

### Các Khái Niệm Chính

| Thuật ngữ | Ý nghĩa |
|-----------|---------|
| SC (Selling Climax) | Đỉnh bán tháo — kết thúc downtrend |
| AR (Automatic Rally) | Phục hồi tự động sau SC |
| ST (Secondary Test) | Kiểm tra lại vùng SC |
| Spring | Phá xuống giả — bẫy bears |
| SOS (Sign of Strength) | Tín hiệu sức mạnh — bắt đầu markup |
| BC (Buying Climax) | Đỉnh mua — kết thúc uptrend |
| UTAD | Phá lên giả — bẫy bulls |
| SOW (Sign of Weakness) | Tín hiệu yếu — bắt đầu markdown |

### Cách Giao Dịch
- **Accumulation**: Mua tại Spring (phá xuống giả) hoặc khi SOS xác nhận
- **Distribution**: Bán tại UTAD (phá lên giả) hoặc khi SOW xác nhận
- Kết hợp với volume để xác nhận từng phase

---

## Tổng Kết: Bảng Phân Loại Tất Cả Patterns

### Candlestick Patterns

| Pattern | Số Bar | Loại | Tín Hiệu |
|---------|--------|------|----------|
| Engulfing (Bullish/Bearish) | 2 | Reversal mạnh | Đảo chiều |
| Island Reversal | 3+ | Reversal rất mạnh | Đảo chiều |
| Three Inside Up | 3 | Reversal | Tăng |
| Three White Soldiers | 3 | Reversal mạnh | Tăng |
| Three Black Crows | 3 | Reversal mạnh | Giảm |
| Breakaway (Bullish/Bearish) | 5 | Reversal | Đảo chiều |
| Harami (Bullish/Bearish) | 2 | Reversal yếu | Đảo chiều (cần xác nhận) |
| Abandoned Baby | 3 | Reversal rất mạnh | Đảo chiều |
| Piercing Line / Dark Cloud Cover | 2 | Reversal trung bình | Đảo chiều |
| Tweezer Top / Bottom | 2 | Reversal | Đảo chiều |
| Upside/Downside Gap Three Methods | 3 | Continuation | Tiếp diễn |
| Falling/Rising Three Methods | 5 | Continuation | Tiếp diễn |
| 3 Bar Play | 3 | Continuation | Tiếp diễn |
| Hanging Man | 1 | Reversal | Giảm |
| Hammer | 1 | Reversal | Tăng |

### Chart Patterns — Reversal

| Pattern | Loại | Tín Hiệu | Độ Tin Cậy |
|---------|------|----------|------------|
| Double Top | Reversal | Giảm | Cao |
| Double Bottom | Reversal | Tăng | Cao |
| Head & Shoulders | Reversal | Giảm | Rất cao |
| Inverted Head & Shoulders | Reversal | Tăng | Rất cao |
| Bearish Rising Wedge | Reversal | Giảm | Cao |
| Bullish Falling Wedge | Reversal | Tăng | Cao |
| Bearish Expanding Triangle | Reversal | Giảm | Trung bình |
| Bullish Expanding Triangle | Reversal | Tăng | Trung bình |
| Triple Top | Reversal | Giảm | Rất cao |
| Triple Bottom | Reversal | Tăng | Rất cao |
| Wyckoff Distribution | Reversal | Giảm | Cao (cần volume) |
| Wyckoff Accumulation | Reversal | Tăng | Cao (cần volume) |

### Chart Patterns — Continuation

| Pattern | Loại | Tín Hiệu | Ghi Chú |
|---------|------|----------|---------|
| Bullish Flag | Continuation | Tiếp tục tăng | Target = Flag Pole |
| Bearish Flag | Continuation | Tiếp tục giảm | Target = Flag Pole |
| Bullish Pennant | Continuation | Tiếp tục tăng | Biến thể của Flag |
| Bearish Pennant | Continuation | Tiếp tục giảm | Biến thể của Flag |
| Bullish Falling Wedge | Continuation | Tiếp tục tăng | Giữa uptrend |
| Bearish Rising Wedge | Continuation | Tiếp tục giảm | Giữa downtrend |
| Descending Triangle | Continuation | Tiếp tục giảm | Support nằm ngang |
| Symmetrical Expanding Triangle | Continuation | Theo xu hướng | Biên độ mở rộng |
| Bullish Rectangle | Continuation | Tiếp tục tăng | Consolidation |
| Bearish Rectangle | Continuation | Tiếp tục giảm | Consolidation |

---

## Nguyên Tắc Sử Dụng Advanced Patterns

> 1. **Xác nhận bằng volume** — Volume tăng khi breakout = tín hiệu đáng tin cậy hơn
> 2. **Kết hợp với S/R** — Pattern tại vùng S/R quan trọng có xác suất cao hơn
> 3. **Xem xét xu hướng lớn hơn** — Pattern thuận chiều trend chính > pattern ngược chiều
> 4. **Chờ xác nhận với pattern yếu** — Harami, Hanging Man cần bar xác nhận tiếp theo
> 5. **Gap = hiếm trong intraday** — Island Reversal, Abandoned Baby, Piercing Line ít gặp trong khung ngắn
> 6. **Wyckoff cần khung thời gian lớn** — Hiệu quả nhất trên daily/weekly chart

---

## Liên Kết Với Các Tài Liệu Khác

| Tài liệu | Nội dung liên quan |
|----------|-------------------|
| `price-action/candlestick-patterns.md` | Chi tiết 10 candlestick patterns cơ bản |
| `price-action/chart-patterns-reversal.md` | Double Bottom, Triple Top/Bottom, Rounding, Island |
| `price-action/chart-patterns-continuation.md` | Wedge, Triangle, Flag, Cup & Handle |
| `price-action/bar-patterns.md` | Pin Bar, Inside Bar, Two-Bar Reversal |

---

*Nguồn: Advanced Chart Patterns Cheat Sheet + Chart Patterns Cheat Sheet — HowToTrade.com*
*Tài liệu này dành cho mục đích giáo dục và tham khảo lý thuyết*
