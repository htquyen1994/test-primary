# Fibonacci Retracement — Skill

> Tổng hợp từ: project/docs/fibonacci-retracement.md
> Dùng để xác định mức support/resistance động và target trong intraday trading

---

## 1. NGUYÊN LÝ CỐT LÕI

```
Fibonacci Retracement = Công cụ xác định các mức S/R dựa trên tỷ lệ toán học tự nhiên
→ Giá có xu hướng dừng lại, đảo chiều, hoặc breakout tại các mức Fibonacci
```

**Các mức quan trọng nhất:**
- **61.8%** — Golden Ratio (quan trọng nhất cho retracement)
- **38.2%** — Retracement trung bình
- **1.382** — Extension level 1 (intraday target)
- **1.618** — Golden Level (intraday target quan trọng nhất)

---

## 2. CÁCH VẼ FIBONACCI INTRADAY

### Quy trình:
```
Bước 1: Chọn nến 15 phút ĐẦU TIÊN của ngày (Opening Range)
Bước 2: Vẽ Fib tool từ HIGH xuống LOW của nến đó
         → Tạo ra 4 đường nằm ngang:
         
  ─────────── 1.618 upside  ← Target nếu trending up
  ─────────── 1.382 upside  ← Target 1 nếu trending up
  ═══════════ HIGH nến 15 phút đầu tiên
  ▓▓▓▓▓▓▓▓▓▓▓ Opening Range (nến 15 phút đầu)
  ═══════════ LOW nến 15 phút đầu tiên
  ─────────── 1.382 downside ← Target 1 nếu trending down
  ─────────── 1.618 downside ← Target nếu trending down

Bước 3: Xóa Fib tool, giữ lại 4 đường nằm ngang
```

---

## 3. ĐỌC TÍN HIỆU THEO ĐIỀU KIỆN THỊ TRƯỜNG

### Trending Day (Ngày có xu hướng):
```
Dấu hiệu: Giá phá vỡ 1.618 và DUY TRÌ trên/dưới đó

TRENDING UP:
  Giá phá 1.618 upside + sustenance → Xu hướng tăng mạnh
  Target: 2.618 → Midpoint → 3.618

TRENDING DOWN:
  Giá phá 1.618 downside + sustenance → Xu hướng giảm mạnh
  Target: 2.618 → Midpoint → 3.618
```

### Range-Bound Day (Ngày sideway):
```
Dấu hiệu: Giá không vượt qua 1.618 cả 2 chiều

  ─── 1.618 upside ← Kháng cự — Giá bật lại
  [   Giá dao động trong vùng này   ]
  ─── 1.618 downside ← Hỗ trợ — Giá bật lại

Fake breakout: Phá 1.618 nhưng quay lại ngay → RANGE-BOUND
Hành động: Giao dịch đảo chiều tại 1.618, KHÔNG giao dịch breakout
```

### Gap Up Day:
```
Giá mở cửa cao hơn hôm qua
→ Chú ý mức 1.618 downside

Nếu giá chạm 1.618 downside và bật lại ngay:
  → BẪY sellers — Không bán
  → Giá có thể ở trong range cả ngày, không lấp gap
```

### Gap Down Day:
```
Giá mở cửa thấp hơn hôm qua
→ Chú ý mức 1.618 upside

Nếu giá chạm 1.618 upside và bật lại ngay:
  → BẪY buyers — Không mua
  → Giá có thể đảo chiều từ đây
```

---

## 4. QUY TẮC ENTRY

### Entry Trending Day:
```
BUY:
  ✅ Giá breakout trên 1.382 upside
  ✅ Sustenance: 2-4 nến M5 đóng cửa trên 1.382
  → Vào BUY, target 1.618

  ✅ Giá breakout trên 1.618 upside
  ✅ Sustenance xác nhận
  → Vào BUY, target 2.618

SELL:
  ✅ Giá breakdown dưới 1.382 downside
  ✅ Sustenance: 2-4 nến M5 đóng cửa dưới 1.382
  → Vào SELL, target 1.618

  ✅ Giá breakdown dưới 1.618 downside
  ✅ Sustenance xác nhận
  → Vào SELL, target 2.618
```

### Entry Range-Bound Day:
```
BUY tại 1.618 downside:
  ✅ Giá chạm 1.618 downside
  ✅ Nến đảo chiều bullish xuất hiện
  → Vào BUY, target 1.618 upside

SELL tại 1.618 upside:
  ✅ Giá chạm 1.618 upside
  ✅ Nến đảo chiều bearish xuất hiện
  → Vào SELL, target 1.618 downside
```

---

## 5. CHUỖI TARGET TRENDING DAY

```
Trending Up:
  Entry → 1.382 (chốt nửa) → 1.618 (chốt nửa còn lại)
  Nếu xu hướng mạnh: 1.618 → 2.618 → Midpoint → 3.618

Trending Down:
  Entry → 1.382 (chốt nửa) → 1.618 (chốt nửa còn lại)
  Nếu xu hướng mạnh: 1.618 → 2.618 → Midpoint → 3.618

Tính Midpoint:
  Midpoint = (2.618 + 3.618) / 2
  Hoặc: Khoảng cách 2.618-3.618 chia đôi
```

---

## 6. SUSTENANCE — XÁC NHẬN BREAKOUT

```
Sustenance = Giá duy trì ngoài mức Fibonacci sau breakout

Cách kiểm tra:
  Chuyển sang M5
  Đếm 2-4 nến đóng cửa ngoài mức Fibonacci
  
✅ 2-4 nến đóng cửa ngoài mức → Breakout thật
❌ Nến tiếp theo quay lại trong range → Fake breakout

Strong Breakout:
  Phá vỡ cả 1.382 VÀ 1.618 trong một nến
  → Vẫn cần sustenance xác nhận
```

---

## 7. BẢNG TỔNG KẾT THEO ĐIỀU KIỆN

| Điều kiện | Dấu hiệu Fib | Hành động | Lưu ý |
|-----------|-------------|-----------|-------|
| **Gap Up** | Giá chạm 1.618 downside + bật | KHÔNG bán | Bẫy sellers |
| **Gap Down** | Giá chạm 1.618 upside + bật | KHÔNG mua | Bẫy buyers |
| **Range-Bound** | Giá không vượt 1.618 cả 2 chiều | Đảo chiều tại 1.618 | Fake breakout quay lại ngay |
| **Trending Up** | Phá + duy trì trên 1.618 upside | BUY, target 2.618 | Kiểm tra sustenance M5 |
| **Trending Down** | Phá + duy trì dưới 1.618 downside | SELL, target 2.618 | Kiểm tra sustenance M5 |

---

## 8. QUY TRÌNH GIAO DỊCH HOÀN CHỈNH

```
Bước 1: Xác định xu hướng tổng thể (H1 hoặc Daily)

Bước 2: Vẽ Fib trên nến 15 phút đầu tiên
         → 4 đường: 1.382 và 1.618 (upside và downside)

Bước 3: Quan sát 30-60 phút đầu
         → Giá ở trong range? → Range-bound day
         → Giá phá 1.618? → Trending day

Bước 4: Xác nhận sustenance (M5, 2-4 nến)

Bước 5: Entry theo điều kiện thị trường

Bước 6: Stop Loss
         Trending: Dưới/Trên mức 1.618 (hoặc 1.382)
         Range-bound: Ngoài mức 1.618

Bước 7: Profit Target
         Target 1: 1.382 (chốt nửa nếu xu hướng mạnh)
         Target 2: 1.618 (chốt nửa còn lại hoặc toàn bộ)
         Target 3: 2.618 (nếu trending day mạnh)
         Target 4: Midpoint 2.618-3.618
```

---

## 9. CHECKLIST TRƯỚC KHI VÀO LỆNH

```
✅ Đã vẽ Fib trên nến 15 phút đầu tiên?
✅ Đã xác định loại ngày (trending hay range-bound)?
✅ Có sustenance xác nhận breakout không?
✅ Không phải fake breakout (quay lại ngay)?
✅ Stop loss đã xác định?
✅ Target đã xác định (1.382 → 1.618 → 2.618)?
```

---

## 10. KẾT HỢP VỚI CÁC CÔNG CỤ KHÁC

| Công cụ | Cách kết hợp |
|---------|-------------|
| **S/R Zones** | Fib level trùng S/R = confluence mạnh |
| **FVG** | FVG tại mức Fib 61.8% = entry chính xác |
| **Divergence** | Divergence tại Fib level = xác nhận đảo chiều |
| **ChoCh** | ChoCh tại Fib level = tín hiệu mạnh |
| **Order Blocks** | OB tại Fib level = vùng entry chất lượng cao |

---

## 11. NGUYÊN TẮC VÀNG

1. **Vẽ Fib trên nến 15 phút đầu tiên** — Opening Range là nền tảng
2. **1.618 là mức quyết định** — Phá vỡ = trending, bật lại = range-bound
3. **Sustenance là bắt buộc** — Không có sustenance = không vào lệnh
4. **Fake breakout quay lại ngay** — Dấu hiệu range-bound
5. **Kết hợp với S/R và indicators** — Fibonacci không dùng đơn độc
6. **Chốt nửa tại 1.382, trail nửa còn lại** — Quản lý lệnh linh hoạt

---

*Nguồn: project/docs/fibonacci-retracement.md*
