# Change of Character (ChoCh) — Skill

> Tổng hợp từ: project/docs/change-of-character.md
> Dùng để xác nhận đảo chiều xu hướng — "Khi nào trend dừng là bạn?"

---

## 1. NGUYÊN LÝ CỐT LÕI

```
ChoCh = Sự dịch chuyển lớn đầu tiên trong order flow
→ Vùng cung/cầu nhỏ không giữ được → Xu hướng có thể đảo chiều
```

- **Fractal** — Xuất hiện trên mọi timeframe, mọi công cụ
- Dùng để **xác nhận đảo chiều**, không phải dự đoán
- Luôn kết hợp với công cụ khác — có **false ChoCh**

---

## 2. NHẬN DIỆN CHOCH BẰNG PRICE ACTION

### Định nghĩa xu hướng trước:
```
Uptrend:   Higher Highs (HH) + Higher Lows (HL)
Downtrend: Lower Highs (LH) + Lower Lows (LL)
```

### Bullish ChoCh (trong Downtrend):
```
Điều kiện:
  1. Thị trường tạo thêm Lower Low (LH + LL mới)
  2. Sau khi tạo LL → Giá đảo chiều VƯỢT QUA Lower High gần nhất
  
Tín hiệu: Đảo chiều TĂNG tiềm năng
  
  LH₁ ─────────────────────────────
       \                    ↗ (ChoCh: vượt LH₁)
        \    LH₂ ──────────
         \  /    \        /
          LL₁     LL₂ ──
```

### Bearish ChoCh (trong Uptrend):
```
Điều kiện:
  1. Thị trường tạo thêm Higher High (HH + HL mới)
  2. Sau khi tạo HH → Giá đảo chiều PHÁ VỠ Higher Low gần nhất
  
Tín hiệu: Đảo chiều GIẢM tiềm năng
  
          HH₂ ──────────
         /    \    HL₂ ──────────
        /      \  /              \
  HH₁ ─        HL₁               ↘ (ChoCh: phá HL₂)
```

---

## 3. HAI CÁCH SỬ DỤNG CHOCH

### Higher Timeframe ChoCh:
```
Mục đích: Xác định bias tổng thể
Timeframe: H4, Daily, Weekly
Ứng dụng: Căn chỉnh vị thế với tâm lý thị trường lớn
```

### Lower Timeframe ChoCh:
```
Mục đích: Tìm điểm vào lệnh chính xác
Timeframe: M1, M5, M15
Ứng dụng: Xác nhận entry sau khi bias đã xác định trên HTF
```

---

## 4. NHẬN DIỆN BẰNG INDICATOR

**Smart Money Concepts (Luxalgo) trên TradingView:**
- Tự động xác định market structure (HH/HL, LH/LL)
- Tự động phát hiện Break of Structure (BOS)
- Cảnh báo khi ChoCh hình thành

**Hạn chế:** Không bắt được tất cả ChoCh → Có thể bỏ lỡ cơ hội

---

## 5. CHIẾN LƯỢC A: PRICE ACTION TRADERS

### Bước 1: Xác định Market Structure trên HTF (H4)
```
- Xác định uptrend/downtrend rõ ràng
- Đánh dấu vùng Supply/Demand quan trọng
- Xác định giá đang tiếp cận vùng nào
```

### Bước 2: Xuống LTF (M15) tìm ChoCh
```
- Chờ giá chạm vào vùng Demand/Supply trên HTF
- Quan sát price action trên M15
- Tìm ChoCh: Giá tạo LL mới → Bật mạnh vượt LH gần nhất (Bullish)
```

### Bước 3: Entry
```
Cách 1 — Aggressive Entry:
  Vào lệnh ngay khi ChoCh hình thành (phá swing high/low)
  
Cách 2 — Conservative Entry (Ưu tiên):
  Đánh dấu Fair Value Gap (FVG) tạo ra trong cú đảo chiều
  Đặt Limit Order tại:
    - Cạnh TRÊN FVG (cho lệnh BUY)
    - Cạnh DƯỚI FVG (cho lệnh SELL)
```

### Bước 4: Stop Loss & Take Profit
```
Stop Loss:
  BUY: Dưới swing low cuối cùng
  SELL: Trên swing high cuối cùng

Take Profit (chọn 1 và tuân thủ):
  Option 1: Tỷ lệ R:R cố định (1:2, 1:3)
  Option 2: Swing high/low tiếp theo
  Option 3: Order Block đối lập tiếp theo
```

---

## 6. CHIẾN LƯỢC B: INDICATOR TRADERS (ChoCh + RSI)

### Bước 1: Tìm tài sản Overbought/Oversold
```
Dùng RSI trên H1:
  RSI > 70 → Overbought → Tìm Bearish ChoCh
  RSI < 30 → Oversold  → Tìm Bullish ChoCh
```

### Bước 2: Chờ ChoCh xác nhận
```
Overbought + Bearish ChoCh hình thành → SELL
Oversold  + Bullish ChoCh hình thành → BUY
```

### Bước 3: Stop Loss & Exit
```
Stop Loss:
  SELL: Trên swing high
  BUY:  Dưới swing low

Exit:
  SELL: Thoát khi RSI đạt oversold (< 30)
  BUY:  Thoát khi RSI đạt overbought (> 70)
```

---

## 7. CHECKLIST TRƯỚC KHI VÀO LỆNH

```
✅ Đã xác định xu hướng hiện tại (HH/HL hay LH/LL)?
✅ Giá đang tiếp cận vùng Supply/Demand quan trọng?
✅ ChoCh đã hình thành rõ ràng trên LTF?
✅ Có FVG để đặt limit order không?
✅ Stop loss đã xác định (dưới LL / trên HH)?
✅ Take profit đã chọn phương pháp và tuân thủ?
✅ Đây có phải false ChoCh không? (Kiểm tra confluence)
```

---

## 8. CẢNH BÁO FALSE CHOCH

```
False ChoCh xảy ra khi:
  - Giá vượt swing high/low nhưng ngay sau đó quay lại xu hướng cũ
  - Không có volume xác nhận
  - Không có FVG đi kèm
  
Cách tránh:
  ✅ Chờ FVG xác nhận sức mạnh đảo chiều
  ✅ Kết hợp với RSI overbought/oversold
  ✅ Kết hợp với Order Block / Supply-Demand Zone
  ✅ Kiểm tra volume (nếu có)
```

---

## 9. TIMEFRAME PAIRING

| HTF (Bias) | LTF (Entry) |
|-----------|-------------|
| Daily | H4 |
| H4 | H1 hoặc M15 |
| H1 | M15 hoặc M5 |
| M15 | M5 hoặc M1 |

---

## 10. NGUYÊN TẮC VÀNG

1. **ChoCh = Xác nhận, không phải dự đoán** — Chờ nó hình thành
2. **Luôn dùng confluence** — RSI, OB, FVG, Supply/Demand
3. **False ChoCh tồn tại** — Không bao giờ vào lệnh chỉ dựa vào ChoCh đơn thuần
4. **Fractal** — Áp dụng được trên mọi timeframe
5. **Demo trước live** — Backtest kỹ trước khi dùng thực

---

*Nguồn: project/docs/change-of-character.md*
