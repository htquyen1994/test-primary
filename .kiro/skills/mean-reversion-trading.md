# Mean Reversion Trading — Skill

> Tổng hợp từ: project/docs/mean-reversion-trading.md
> Dùng để nhận diện cơ hội giao dịch khi giá lệch xa khỏi trung bình lịch sử

---

## 1. NGUYÊN LÝ CỐT LÕI

```
Giá lệch xa khỏi trung bình → Có xu hướng quay về trung bình
```

- Mua khi giá **quá thấp** so với trung bình (oversold)
- Bán khi giá **quá cao** so với trung bình (overbought)
- Hiệu quả nhất trong **thị trường sideway / range-bound**
- Kém hiệu quả trong **trending market mạnh**

---

## 2. ĐIỀU KIỆN ÁP DỤNG

| Điều kiện | Áp dụng? |
|-----------|---------|
| Thị trường sideway / dao động trong biên độ | ✅ |
| Giá lệch đáng kể khỏi trung bình lịch sử | ✅ |
| Không có tin tức cơ bản lớn | ✅ |
| Thị trường có xu hướng mạnh (trending) | ❌ |
| Sự kiện thị trường bất ngờ lớn | ❌ |

---

## 3. CÔNG CỤ XÁC ĐỊNH TRUNG BÌNH (MEAN)

### Ưu tiên sử dụng:
1. **50 EMA** — Trung bình động cho intraday
2. **Bollinger Bands (SMA 20)** — Dải giữa = mean, dải ngoài = cực trị
3. **Moving Average** — Bất kỳ MA nào phù hợp với timeframe

### Cách đọc:
- Giá **trên MA đáng kể** → kỳ vọng giảm về MA
- Giá **dưới MA đáng kể** → kỳ vọng tăng về MA

---

## 4. 6 INDICATOR CHO MEAN REVERSION

| Indicator | Tín hiệu Overbought | Tín hiệu Oversold | Ghi chú |
|-----------|--------------------|--------------------|---------|
| **Bollinger Bands** | Giá chạm dải trên | Giá chạm dải dưới | Phổ biến nhất |
| **RSI** | RSI > 70 | RSI < 30 | Dùng làm confluence |
| **Moving Average** | Giá >> MA | Giá << MA | Nền tảng cơ bản |
| **Standard Deviation** | Độ lệch chuẩn cao | Độ lệch chuẩn cao | Đo biến động |
| **MACD** | EMA lines xa midpoint | EMA lines xa midpoint | Đo momentum |
| **MRI** | Lệch xa mean | Lệch xa mean | Cần cài thủ công MT4/5 |

---

## 5. CHIẾN LƯỢC INTRADAY (50 EMA + RSI, H1)

### Setup SELL:
```
✅ Giá ở TRÊN 50 EMA
✅ RSI > 70 (overbought)
→ Vào lệnh SELL
→ Profit target: Đường 50 EMA
→ Stop loss: Trên đỉnh cao nhất gần nhất
```

### Setup BUY:
```
✅ Giá ở DƯỚI 50 EMA
✅ RSI < 30 (oversold)
→ Vào lệnh BUY
→ Profit target: Đường 50 EMA
→ Stop loss: Dưới đáy thấp nhất gần nhất
```

---

## 6. CHECKLIST TRƯỚC KHI VÀO LỆNH

```
✅ Thị trường đang sideway / range-bound?
✅ Giá lệch đáng kể khỏi MA/mean?
✅ RSI xác nhận overbought/oversold?
✅ Không có tin tức lớn sắp ra?
✅ Stop loss đã xác định rõ?
✅ Profit target tại đường MA?
✅ R:R ≥ 1:1?
```

---

## 7. QUẢN LÝ RỦI RO

- **Win rate kỳ vọng**: 66% - 80% (backtesting)
- **Risk-reward**: Thấp hơn trend trading — phù hợp day trader
- **Stop loss**: Trên đỉnh (SELL) / Dưới đáy (BUY)
- **Profit target**: Tại đường moving average
- **Không giữ lệnh qua đêm** — tránh overnight risk

---

## 8. SO SÁNH VỚI TREND FOLLOWING

| Yếu tố | Mean Reversion | Trend Following |
|--------|---------------|-----------------|
| Thị trường phù hợp | Sideway | Trending |
| Stop loss | Chặt | Rộng |
| Giữ lệnh | Ngắn | Dài |
| Win rate | Cao (66-80%) | Thấp hơn |
| R:R ratio | Thấp hơn | Cao hơn |
| Tâm lý | Khó (mua khi giảm) | Dễ hơn |

---

## 9. NGUYÊN TẮC VÀNG

1. **Không dùng trong trending market** — Giá có thể tiếp tục lệch xa mãi
2. **Luôn dùng confluence** — RSI + MA + Bollinger Bands cùng lúc
3. **Profit target = MA** — Không tham, chốt lời tại trung bình
4. **Stop loss chặt** — Bảo vệ vốn khi thị trường đột ngột trending
5. **Backtesting trước** — Kiểm tra trên demo trước khi live

---

*Nguồn: project/docs/mean-reversion-trading.md*
