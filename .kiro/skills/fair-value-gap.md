# Fair Value Gap (FVG) — Skill

> Tổng hợp từ: project/docs/fair-value-gap.md
> Dùng để xác định vùng imbalance mà thị trường có xu hướng quay lại lấp

---

## 1. NGUYÊN LÝ CỐT LÕI

```
FVG = Vùng giá bị "bỏ qua" do cú di chuyển quá mạnh và nhanh
→ Thị trường tự nhiên quay lại lấp vùng này trước khi tiếp tục
```

**Tên gọi khác:** Imbalance | Inefficiency | Liquidity Void

- **Bullish FVG** → Giá sẽ pullback xuống lấp → Cơ hội BUY
- **Bearish FVG** → Giá sẽ pullback lên lấp → Cơ hội SELL
- Chỉ giao dịch FVG **thuận chiều xu hướng**

---

## 2. CẤU TRÚC FVG — 3 NẾN

```
BEARISH FVG (Sell opportunity):
  Bar 1: [Nến nhỏ]     ← Low(Bar 1) = Đỉnh FVG
  Bar 2: [NẾN ĐỎ LỚN]  ← Impulse move mạnh (~70% body)
  Bar 3: [Nến nhỏ]     ← High(Bar 3) = Đáy FVG
  
  FVG Zone = Khoảng giữa Low(Bar 1) và High(Bar 3)
  → Giá tăng lên lấp FVG → SELL tại đây

BULLISH FVG (Buy opportunity):
  Bar 1: [Nến nhỏ]      ← High(Bar 1) = Đáy FVG
  Bar 2: [NẾN XANH LỚN] ← Impulse move mạnh (~70% body)
  Bar 3: [Nến nhỏ]      ← Low(Bar 3) = Đỉnh FVG
  
  FVG Zone = Khoảng giữa High(Bar 1) và Low(Bar 3)
  → Giá giảm xuống lấp FVG → BUY tại đây
```

---

## 3. CÁCH NHẬN DIỆN FVG TRÊN CHART

### Bước 1: Tìm nến lớn (Big Candle)
```
Tiêu chí:
  ✅ Body chiếm ~70% tổng chiều dài nến
  ✅ Di chuyển mạnh và nhanh (impulse)
  ❌ Nến có bóng quá dài so với body
```

### Bước 2: Kiểm tra nến lân cận
```
Bar 1 (trước nến lớn): Không chồng hoàn toàn lên Bar 2
Bar 3 (sau nến lớn):   Không chồng hoàn toàn lên Bar 2

✅ Có gap giữa Low(Bar 1) và High(Bar 3) → FVG hợp lệ
❌ Bar 3 chồng hoàn toàn lên Bar 1 → Không có FVG
```

### Bước 3: Xác định vùng FVG
```
Bearish FVG:
  Đỉnh FVG = Low của Bar 1
  Đáy FVG  = High của Bar 3

Bullish FVG:
  Đáy FVG  = High của Bar 1
  Đỉnh FVG = Low của Bar 3
```

---

## 4. QUY TRÌNH GIAO DỊCH FVG

```
Bước 1: XÁC ĐỊNH XU HƯỚNG (H1/Daily/Weekly)
         Uptrend (HH+HL)   → Tìm Bullish FVG để BUY
         Downtrend (LH+LL) → Tìm Bearish FVG để SELL
         ↓
Bước 2: TÌM FVG
         Tìm nến lớn (~70% body)
         Kiểm tra gap giữa Bar 1 và Bar 3
         Xác định vùng FVG
         ↓
Bước 3: XÁC ĐỊNH SUPPLY/DEMAND ZONE
         Dùng nến đầu tiên (Bar 1) của FVG để vẽ zone
         Bullish: Demand Zone
         Bearish: Supply Zone
         ↓
Bước 4: CHỜ GIÁ QUAY LẠI LẤP FVG
         Giá retracement về vùng FVG
         FVG + Supply/Demand Zone trùng nhau = Tín hiệu mạnh
         ↓
Bước 5: ENTRY
         Khi giá chạm vào FVG zone
         Xác nhận bằng price action (nến đảo chiều, ChoCh)
         ↓
Bước 6: ĐẶT SL/TP
         SL: Trên/dưới nến đầu tiên của FVG (Bar 1)
         TP: Tại S/R zone tiếp theo
```

---

## 5. BẢNG TỔNG KẾT ENTRY

| Yếu tố | Bearish FVG (SELL) | Bullish FVG (BUY) |
|--------|-------------------|------------------|
| Xu hướng | Downtrend (LH+LL) | Uptrend (HH+HL) |
| Nến lớn | Nến đỏ (~70% body) | Nến xanh (~70% body) |
| Vùng FVG | Low(Bar1) → High(Bar3) | High(Bar1) → Low(Bar3) |
| Zone kết hợp | Supply Zone | Demand Zone |
| Entry | Giá lấp FVG từ dưới lên | Giá lấp FVG từ trên xuống |
| Stop Loss | Trên nến đầu tiên FVG | Dưới nến đầu tiên FVG |
| Take Profit | Demand zone tiếp theo | Supply zone tiếp theo |

---

## 6. FVG KẾT HỢP VỚI CHOCH

```
Kết hợp mạnh nhất:
  1. ChoCh hình thành (xác nhận đảo chiều)
  2. FVG xuất hiện trong cú đảo chiều đó
  3. Đặt Limit Order tại FVG
  
  → Entry chính xác, R:R tốt hơn aggressive entry
```

---

## 7. CHECKLIST TRƯỚC KHI VÀO LỆNH

```
✅ Đã xác định xu hướng trên HTF?
✅ FVG thuận chiều xu hướng?
✅ Nến lớn có body ~70% không?
✅ Có gap thực sự giữa Bar 1 và Bar 3 không?
✅ Đã xác định Supply/Demand Zone kết hợp chưa?
✅ Giá đang quay lại lấp FVG không?
✅ Có xác nhận price action tại FVG không?
✅ Stop loss đã xác định (trên/dưới Bar 1)?
✅ Take profit tại S/R zone tiếp theo?
```

---

## 8. KẾT HỢP VỚI CÁC CÔNG CỤ KHÁC

| Công cụ | Cách kết hợp |
|---------|-------------|
| **ChoCh** | FVG trong cú ChoCh = entry chính xác |
| **Order Blocks** | FVG trong vùng OB = confluence mạnh |
| **Fibonacci** | FVG tại mức Fib 61.8% = tín hiệu rất mạnh |
| **Divergence** | Divergence khi giá chạm FVG = xác nhận thêm |
| **S/R Zones** | FVG tại S/R = xác suất cao nhất |

---

## 9. NGUYÊN TẮC VÀNG

1. **Chỉ giao dịch FVG thuận chiều xu hướng** — Không counter-trend
2. **Nến lớn ~70% body** — Tiêu chí quan trọng nhất
3. **FVG + Supply/Demand Zone** — Tín hiệu mạnh hơn khi trùng nhau
4. **SL trên/dưới Bar 1** — Bảo vệ vốn hiệu quả
5. **TP tại S/R zone tiếp theo** — Risk-reward thuận lợi
6. **Dùng HTF để xác định trend** — H1, Daily, Weekly

---

*Nguồn: project/docs/fair-value-gap.md*
