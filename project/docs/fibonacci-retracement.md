# Fibonacci Retracement in Day Trading

> Nguồn: "Fibonacci Retracement in Day Trading" — Sushantkumar Pawar, Nikhil Bhoite (IJIRMPS, Volume 9, Issue 4, 2021)
> Tài liệu tham khảo lý thuyết cho hệ thống giao dịch

---

## Tổng Quan

<cite index="4-2,4-3">Traders thường sử dụng Fibonacci numbers cho phân tích kỹ thuật. Lịch sử cho thấy giá cổ phiếu có xu hướng tuân theo Fibonacci Retracements như các mức support và resistance.</cite>

<cite index="4-4,4-5">Nghiên cứu này nhằm kiểm tra tính hợp lệ của việc sử dụng Fibonacci như một công cụ phân tích kỹ thuật trong intraday trading và tối ưu hóa chiến lược bằng cách kết hợp với các chỉ báo khác. Kết quả cho thấy giao dịch sử dụng Fibonacci Retracements dẫn đến kết quả có lợi nhuận, và trong trường hợp không có lợi nhuận thì stop-loss thường nhỏ.</cite>

<cite index="4-20,4-21">Fibonacci retracements phổ biến trong giới technical traders. Đây là công cụ thị trường chứng khoán giúp xác định xu hướng và retracements trong giá cổ phiếu, hỗ trợ nhà đầu tư quyết định chiến lược entry và exit cho cả Positional Trading lẫn Intraday.</cite>

---

## 1. Nền Tảng Lý Thuyết

### 1.1 Dãy Fibonacci

<cite index="4-24,4-25,4-26">Fibonacci numbers được đặt theo tên nhà toán học người Ý Leonardo of Pisa (Fibonacci). Trong dãy Fibonacci, số tiếp theo là tổng của hai số liên tiếp trước đó. Ví dụ: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89… và tiếp tục.</cite>

```
DÃY FIBONACCI:
  1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144...
  Quy tắc: F(n) = F(n-1) + F(n-2)
```

### 1.2 Golden Ratio (Tỷ Lệ Vàng)

<cite index="4-34,4-35,4-36,4-37">Golden Ratio là một số đặc biệt có giá trị khoảng 1.618. Nó được biểu diễn bằng chữ cái Hy Lạp "Phi" (φ). Đây là số vô tỷ — các chữ số thập phân không có quy luật, phân bố ngẫu nhiên. Golden ratio được áp dụng trong nhiều lĩnh vực từ kiến trúc đến nhiếp ảnh.</cite>

```
GOLDEN RATIO:
  φ = 1.618...
  
  Nguồn gốc từ Fibonacci:
  Lấy bất kỳ số Fibonacci nào chia cho số trước nó:
  89 / 55 = 1.618...
  55 / 34 = 1.617...
  34 / 21 = 1.619...
  → Tỷ lệ hội tụ về 1.618
```

### 1.3 Các Mức Fibonacci Retracement Phổ Biến

```
CÁC MỨC FIBONACCI RETRACEMENT:
  0%      — Điểm bắt đầu (High hoặc Low)
  23.6%   — Retracement nhỏ
  38.2%   — Retracement trung bình (quan trọng)
  50%     — Midpoint (không phải Fibonacci nhưng được dùng rộng rãi)
  61.8%   — Golden Ratio retracement (quan trọng nhất)
  78.6%   — Retracement sâu
  100%    — Điểm kết thúc (Low hoặc High)
  
CÁC MỨC FIBONACCI EXTENSION (cho target):
  1.382   — Extension level 1 (quan trọng trong intraday)
  1.618   — Golden Level (quan trọng nhất trong intraday)
  2.618   — Extension level 2
  3.618   — Extension level 3
```

---

## 2. Các Khái Niệm Cơ Bản

### 2.1 Xu Hướng (Trend)

<cite index="4-46,4-47,4-48">Xu hướng là hướng tổng thể của thị trường hoặc giá tài sản. Chúng không nhất thiết di chuyển theo đường thẳng. Tuy nhiên, nếu bạn zoom out và nhìn vào các mẫu giá dài hạn hơn, bạn sẽ có bức tranh tốt hơn về xu hướng thị trường.</cite>

#### Uptrend (Xu Hướng Tăng)

<cite index="4-51,4-52,4-53">Cổ phiếu được gọi là trong 'Uptrend' khi hướng di chuyển giá là đi lên. Một trong những cách dễ nhất để xác định 'Uptrend' là xem liệu cổ phiếu có vượt qua đỉnh trước đó và không rơi xuống dưới đáy trước đó không. Điều này thường được gọi là 'Higher Highs and Higher Lows' — rất giống một cầu thang đi lên.</cite>

```
UPTREND:
  HH₂ > HH₁ (Higher Highs)
  HL₂ > HL₁ (Higher Lows)
  
  Hình dạng: Cầu thang đi LÊN
  HL₁ → HH₁ → HL₂ → HH₂ → HL₃ → HH₃...
```

#### Downtrend (Xu Hướng Giảm)

<cite index="4-56,4-59,4-60">Cổ phiếu được gọi là trong 'Downtrend' khi hướng di chuyển giá là đi xuống. Một trong những cách dễ nhất để xác định 'Downtrend' là xem liệu cổ phiếu có đi xuống, tăng lên rồi lại xuống dưới đáy trước đó không. Điều này được gọi là 'Lower Highs and Lower Lows' — rất giống một cầu thang đi xuống.</cite>

```
DOWNTREND:
  LH₂ < LH₁ (Lower Highs)
  LL₂ < LL₁ (Lower Lows)
  
  Hình dạng: Cầu thang đi XUỐNG
  LH₁ → LL₁ → LH₂ → LL₂ → LH₃ → LL₃...
```

#### Range-Bound (Thị Trường Đi Ngang)

<cite index="4-73,4-74,4-75,4-76">Trading range xảy ra khi cổ phiếu/index giao dịch giữa các mức giá cao và thấp nhất quán trong một khoảng thời gian. Đỉnh của trading range thường cung cấp price resistance, trong khi đáy thường cung cấp price support. Trong range-bound trend, biến động giá bị kẹt trong một dải nhỏ và giá di chuyển rất chậm. Trong thị trường range-bound, trader có rất ít cơ hội giao dịch.</cite>

```
RANGE-BOUND:
  Resistance ————————————————
  |  Giá dao động trong vùng này  |
  Support   ————————————————
  
  Đặc điểm: Volume thấp, biến động nhỏ
```

### 2.2 Intraday Timeframes

<cite index="4-72,4-73">Có nhiều khung thời gian để sử dụng trong day trading. Các khung phổ biến nhất là: 5 phút, 15 phút, 1 giờ.</cite>

| Timeframe | Dùng cho |
|-----------|---------|
| 5 phút | Xác nhận entry, kiểm tra sustenance |
| 15 phút | Vẽ Fibonacci (nến đầu tiên của ngày) |
| 1 giờ | Xác định xu hướng tổng thể trong ngày |

---

## 3. Cách Vẽ Fibonacci Retracement Trong Intraday

<cite index="4-77,4-78,4-79">Trong intraday, Fibonacci Retracement đóng vai trò rất quan trọng. Level 1.382 và Golden Level 1.618 giúp ra quyết định. Chúng cũng giúp xác định xu hướng/hướng của thị trường trong ngày đó.</cite>

### Quy Trình Vẽ

<cite index="4-82,4-83,4-85,4-87,4-89,4-91">Các bước vẽ Fibonacci Retracement Tool:
1. Chọn Fibonacci retracement tool từ nền tảng giao dịch
2. Vẽ fib tool trên nến 15 phút đầu tiên của ngày
3. Để vẽ, đặt grid từ high xuống low của nến cho downside fib levels và từ low lên high cho upside fib levels
4. Đánh dấu level / vẽ đường nằm ngang tại mức 1.382 và 1.618 cả phía trên lẫn phía dưới
5. Sau đó có thể xóa fib tool khỏi chart</cite>

<cite index="4-93">Kết quả cuối cùng sẽ có 4 đường nằm ngang trên chart — hai ở phía trên nến 15 phút đầu tiên và hai ở phía dưới.</cite>

```
KẾT QUẢ SAU KHI VẼ:
  
  ─────────── 1.618 (Upside Golden Level)
  ─────────── 1.382 (Upside Level)
  ═══════════ HIGH của nến 15 phút đầu tiên
  ▓▓▓▓▓▓▓▓▓▓▓ Nến 15 phút đầu tiên (Opening Range)
  ═══════════ LOW của nến 15 phút đầu tiên
  ─────────── 1.382 (Downside Level)
  ─────────── 1.618 (Downside Golden Level)
```

---

## 4. Quy Tắc Sử Dụng Fibonacci Tool

<cite index="4-96,4-97,4-98">Bạn phải biết hướng của thị trường và phải biết dynamic và static Support/Resistance. Bạn có thể dùng công cụ này cho mục đích exit hoặc entry. Nó sẽ giúp xác định reversal hoặc breakout.</cite>

<cite index="4-99">Nếu cổ phiếu/index phá vỡ mức 1.618 và duy trì trên đó (uptrend) hoặc dưới đó (downtrend) thì xu hướng đó sẽ mạnh trong intraday.</cite>

<cite index="4-100,4-101">Nếu cổ phiếu/index phá vỡ cả hai mức (1.382 và 1.618) trong một nến thì coi đó là strong breakout, nhưng sustenance là bắt buộc. Sustenance có thể kiểm tra trên khung 5 phút, 2-4 nến.</cite>

<cite index="4-102,4-103,4-104">Để exit hoặc chốt lời an toàn, bạn cũng có thể dùng công cụ này để re-entry trong trường hợp phá vỡ và test lại mức 1.618. Ví dụ, nếu bạn dùng opening range breakout để entry, bạn có thể chốt lời tại mức 1.382/1.618 nếu thấy dấu hiệu đảo chiều. Trong trường hợp xu hướng mạnh, bạn có thể chốt nửa và trail nửa còn lại.</cite>

<cite index="4-105">Sau khi phá vỡ 1.618, bạn có thể nhắm mục tiêu 2.618 hoặc 50% giữa 1.618 và 2.618.</cite>

### Tóm Tắt Quy Tắc

```
QUY TẮC FIBONACCI INTRADAY:

  1. ENTRY:
     - Mua khi giá breakout trên 1.382 (upside) với sustenance
     - Mua khi giá breakout trên 1.618 (upside) → xu hướng mạnh
     - Bán khi giá breakdown dưới 1.382 (downside) với sustenance
     - Bán khi giá breakdown dưới 1.618 (downside) → xu hướng mạnh

  2. EXIT / PROFIT TARGET:
     - Target 1: Mức 1.382
     - Target 2: Mức 1.618
     - Target 3 (trending day): Mức 2.618
     - Target 4 (trending day): Midpoint giữa 2.618 và 3.618

  3. SUSTENANCE (Xác nhận):
     - Kiểm tra trên khung 5 phút
     - Cần 2-4 nến đóng cửa trên/dưới mức Fibonacci

  4. STRONG BREAKOUT:
     - Phá vỡ cả 1.382 VÀ 1.618 trong một nến
     - Nhưng vẫn cần sustenance xác nhận
```

---

## 5. Fibonacci Trong Các Điều Kiện Thị Trường Khác Nhau

### 5.1 Gap Up (Mở Cửa Cao Hơn Hôm Qua)

<cite index="4-110">Khi giá của một công cụ tài chính mở cửa cao hơn giá đóng cửa ngày hôm trước, đó được gọi là gap-up opening.</cite>

**3 khả năng sau Gap Up:**

<cite index="4-114,4-115,4-116">
1. Xu hướng tiếp tục uptrend từ gap opening và di chuyển tiếp mà không lấp gap
2. Di chuyển trong dải cố định mà không lấp gap
3. Có vẻ như sẽ lấp gap, nhưng giữa chừng quay đầu lại</cite>

<cite index="4-117">Với Fibonacci Tool, trader có thể tự bảo vệ khỏi khả năng thứ ba (bẫy sellers).</cite>

```
GAP UP — CÁCH SỬ DỤNG FIB:

  Ngày hôm trước đóng cửa: 300
  Hôm nay mở cửa: 305 (Gap Up)
  
  Vẽ Fib trên nến 15 phút đầu tiên:
  ─── 1.618 upside ← Target nếu tiếp tục tăng
  ─── 1.382 upside
  ═══ HIGH nến 15 phút
  ▓▓▓ Nến 15 phút đầu tiên
  ═══ LOW nến 15 phút
  ─── 1.382 downside ← Nếu giá chạm và bật lại = KHÔNG lấp gap
  ─── 1.618 downside ← Nếu giá chạm và bật lại = BẪY sellers
  
  Khoảng gap (300-305)
```

**Tín hiệu quan trọng:** <cite index="4-122,4-123">Khi giá chạm mức 1.618 và ngay nến tiếp theo quay trở lại trong Fib range → đây là bẫy cho sellers. Sau đó giá có thể ở trong range cả ngày và không bao giờ lấp gap.</cite>

### 5.2 Gap Down (Mở Cửa Thấp Hơn Hôm Qua)

<cite index="4-126">Trong trường hợp này, cổ phiếu/index mở cửa gap down và lấp gap giữa giá đóng cửa ngày hôm trước và giá mở cửa hôm nay.</cite>

<cite index="4-128,4-129">Có thể xảy ra trường hợp cổ phiếu/index lấp gap và đảo chiều từ mức 1.618 fib nếu nó va chạm với gap down range. Sau khi lấp gap, giá đảo chiều từ mức 1.618 và ở trong range cả ngày.</cite>

```
GAP DOWN — CÁCH SỬ DỤNG FIB:

  Ngày hôm trước đóng cửa: 300
  Hôm nay mở cửa: 295 (Gap Down)
  
  Kịch bản lấp gap:
  Giá tăng lên lấp gap → Chạm 1.618 upside → Đảo chiều xuống
  → Ở trong range cả ngày
  
  Tín hiệu: 1.618 upside = kháng cự mạnh khi gap down
```

### 5.3 Range-Bound Market

<cite index="4-130,4-131">Range bound market, hay còn gọi là choppy market, là khi cổ phiếu/index di chuyển giữa các dải nhất định, với biên độ rất nhỏ.</cite>

<cite index="4-132,4-133,4-134,4-135">Fib đóng vai trò cực kỳ quan trọng trong range-bound trend. Trong thị trường range-bound, xu hướng sẽ không vượt qua Fibonacci golden level 1.618 cả phía trên lẫn phía dưới. Cả ngày, giá có thể ở trong dải giữa 1.618 upside và 1.618 downside. Nếu có fake breakout/breakdown tại mức 1.618, xu hướng sẽ quay lại trong range ngay nến tiếp theo hoặc vài nến tiếp theo.</cite>

```
RANGE-BOUND — DẤU HIỆU NHẬN BIẾT:

  ─── 1.618 upside ← Giá không vượt qua được
  ─── 1.382 upside
  ═══ HIGH nến 15 phút
  ▓▓▓ Opening Range
  ═══ LOW nến 15 phút
  ─── 1.382 downside ← Giá có thể đảo chiều tại đây
  ─── 1.618 downside ← Giá không vượt qua được
  
  Fake breakout: Phá 1.618 nhưng quay lại ngay → RANGE-BOUND
  Tín hiệu: KHÔNG giao dịch breakout, chờ đảo chiều tại 1.618
```

### 5.4 Trending Day (Ngày Có Xu Hướng Rõ)

<cite index="4-144,4-145,4-146">Trending day là ngày điển hình mà giá di chuyển theo cùng một hướng với xu hướng mạnh từ khi mở cửa và đóng cửa mạnh theo hướng xu hướng. Trong trending day, giá sẽ không bị kẹt trong dải cố định. Nó sẽ di chuyển tiếp lên hoặc xuống theo xu hướng thị trường.</cite>

<cite index="4-148,4-149">Trong trending day, sau khi phá vỡ 1.618, đó là xu hướng intraday mạnh. Trong trending day, sau khi phá vỡ 1.618, bạn có thể tiếp tục nhắm mục tiêu 2.618 và 3.618.</cite>

**Cách tính Midpoint Target:**

<cite index="4-150,4-151">Sau khi phá vỡ 2.618, nếu bạn thấy xu hướng mạnh thì có thể tính khoảng cách giữa 2.618 và 3.618 rồi chia đôi, kết quả đó là target tiếp theo. Chúng ta có thể gọi đó là midpoint.</cite>

```
TRENDING DAY — CHUỖI TARGET:

  Breakout 1.618 → Xu hướng mạnh xác nhận
       ↓
  Target 1: 2.618
       ↓
  Phá vỡ 2.618 → Tính Midpoint
  Midpoint = 2.618 - (2.618 - 3.618) / 2
       ↓
  Target 2: Midpoint
       ↓
  Target 3: 3.618

VÍ DỤ TÍNH TOÁN:
  Giá tại 2.618 = 12,261
  Giá tại 3.618 = 12,197
  Khoảng cách = 12,261 - 12,197 = 64
  Midpoint = 64 / 2 = 32
  Target = 12,261 - 32 = 12,229
```

---

## 6. Bảng Tổng Kết: Fibonacci Trong Các Điều Kiện Thị Trường

| Điều kiện | Dấu hiệu Fib | Hành động | Lưu ý |
|-----------|-------------|-----------|-------|
| **Gap Up** | Giá chạm 1.618 downside và bật lại | KHÔNG bán (bẫy sellers) | Chờ xem có lấp gap không |
| **Gap Down** | Giá chạm 1.618 upside và bật lại | KHÔNG mua (bẫy buyers) | Chờ xem có lấp gap không |
| **Range-Bound** | Giá không vượt 1.618 cả 2 chiều | Giao dịch đảo chiều tại 1.618 | Fake breakout quay lại ngay |
| **Trending Up** | Giá phá và duy trì trên 1.618 upside | Mua, target 2.618 → 3.618 | Kiểm tra sustenance 5 phút |
| **Trending Down** | Giá phá và duy trì dưới 1.618 downside | Bán, target 2.618 → 3.618 | Kiểm tra sustenance 5 phút |

---

## 7. Quy Trình Giao Dịch Hoàn Chỉnh

```
QUY TRÌNH FIBONACCI INTRADAY:

  Bước 1: Xác định xu hướng tổng thể (H1 hoặc Daily)
  
  Bước 2: Vẽ Fib trên nến 15 phút đầu tiên
          → 4 đường: 1.382 và 1.618 (cả upside và downside)
  
  Bước 3: Quan sát hành vi giá trong 30-60 phút đầu
          → Giá ở trong range? → Range-bound day
          → Giá phá 1.618? → Trending day
  
  Bước 4: Xác nhận sustenance (5 phút, 2-4 nến)
  
  Bước 5: Entry
          → Trending: Mua/Bán sau khi phá 1.618 với sustenance
          → Range-bound: Mua/Bán đảo chiều tại 1.618
  
  Bước 6: Đặt Stop Loss
          → Trending: Dưới/Trên mức 1.618 (hoặc 1.382)
          → Range-bound: Ngoài mức 1.618
  
  Bước 7: Profit Target
          → Target 1: 1.382 (chốt nửa nếu xu hướng mạnh)
          → Target 2: 1.618 (chốt nửa còn lại hoặc toàn bộ)
          → Target 3: 2.618 (nếu trending day mạnh)
          → Target 4: Midpoint 2.618-3.618
```

---

## 8. Kết Luận

<cite index="4-161,4-162,4-163,4-164,4-165,4-166,4-167">Quan sát cho thấy trong tất cả các điều kiện thị trường, Fibonacci Retracement cho kết quả tốt. Trước đây, Fibonacci Retracement chỉ được dùng cho positional trading hoặc short-term trading để xác định các mức dừng tiếp theo hoặc xác định mức giảm sau khi uptrend kết thúc. Nhưng trong day trading, Fib tool cũng có thể hoạt động như ma thuật. Nó có thể mang lại kết quả có lợi nhuận cho day traders. Bằng cách sử dụng Fib Retracement trong day trading, traders có thể tự bảo vệ khỏi các fake moves. Trong range bound market, họ có thể tránh các entry sai và thua lỗ. Trong trending day, nó cũng có thể tối đa hóa lợi nhuận.</cite>

<cite index="4-168">Kết hợp Fib Retracement với các công cụ thị trường chứng khoán khác hoặc các chỉ báo kỹ thuật khác để tăng hiệu quả.</cite>

---

## Nguyên Tắc Chung

> 1. **Vẽ Fib trên nến 15 phút đầu tiên** — Đây là opening range của ngày
> 2. **1.618 là mức quan trọng nhất** — Golden Level quyết định xu hướng ngày
> 3. **Sustenance là bắt buộc** — Phá vỡ không có sustenance = fake breakout
> 4. **Kiểm tra sustenance trên M5** — 2-4 nến đóng cửa ngoài mức Fibonacci
> 5. **Range-bound: Fake breakout quay lại ngay** — Không giao dịch breakout
> 6. **Trending day: Chuỗi target 1.618 → 2.618 → Midpoint → 3.618**
> 7. **Kết hợp với S/R và các chỉ báo khác** — Fibonacci không dùng đơn độc

---

## Liên Kết Với Các Tài Liệu Khác

| Tài liệu | Nội dung liên quan |
|----------|-------------------|
| `project/docs/advanced-chart-patterns.md` | Chart patterns kết hợp với Fibonacci |
| `project/docs/divergence-patterns.md` | Divergence kết hợp với Fibonacci |
| `price-action/support-and-resistance.md` | S/R levels kết hợp với Fibonacci |
| `price-action/reading-price-action.md` | Đọc price action tại các mức Fibonacci |

---

*Nguồn: "Fibonacci Retracement in Day Trading" — Sushantkumar Pawar, Nikhil Bhoite*
*IJIRMPS, Volume 9, Issue 4, 2021 | ISSN: 2349-7300*
*Tài liệu này dành cho mục đích giáo dục và tham khảo lý thuyết*
