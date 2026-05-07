# Mean Reversion Trading

## Tổng Quan

Mean Reversion (Hồi Quy Về Trung Bình) là chiến lược giao dịch dựa trên giả định rằng giá tài sản và lợi nhuận lịch sử cuối cùng sẽ quay trở lại mức trung bình dài hạn. Khái niệm này bắt nguồn từ hiện tượng thống kê gọi là **regression toward the mean**, được Sir Francis Galton phổ biến vào thế kỷ 19.

---

## Nguyên Lý Cơ Bản

- Giá tài sản dao động xung quanh một mức trung bình lịch sử.
- Khi giá lệch quá xa khỏi mức trung bình (quá cao hoặc quá thấp), có xu hướng quay trở lại mức đó.
- Nguyên nhân bình thường hóa: thay đổi tâm lý thị trường, yếu tố kinh tế, hoặc biến động ngẫu nhiên.

**Ví dụ thực tế:**
- Cổ phiếu dao động quanh $50, đột ngột tăng lên $80 mà không có thay đổi cơ bản → cơ hội **bán** (kỳ vọng giá giảm về $50).
- Cổ phiếu giảm xuống $20 → cơ hội **mua** (kỳ vọng giá tăng về $50).

---

## Cách Xác Định Mức Trung Bình (Mean)

Tính trung bình bằng cách lấy giá lịch sử của tài sản trong một khoảng thời gian cụ thể. Có thể thực hiện qua:

1. Tính thủ công bằng bảng tính (spreadsheet).
2. Dùng indicator tự động hóa quá trình.
3. Quan sát trực quan trên biểu đồ để xác định mức giá trung bình.

---

## 6 Indicator Tốt Nhất Cho Mean Reversion

### 1. Bollinger Bands
- Tạo bởi John Bollinger vào thập niên 1980.
- Cấu trúc: **dải giữa** (SMA 20 ngày) + **2 dải ngoài** (±2 độ lệch chuẩn).
- Khi giá chạm hoặc vượt dải ngoài → tín hiệu lệch quá mức → khả năng đảo chiều cao.
- Dải trên = vùng **overbought**, dải dưới = vùng **oversold**.

### 2. Relative Strength Index (RSI)
- Oscillator đo tốc độ và sự thay đổi của biến động giá.
- **RSI > 70** → overbought → tín hiệu bán.
- **RSI < 30** → oversold → tín hiệu mua.
- Dùng làm công cụ xác nhận (confluence) kết hợp với các indicator khác.

### 3. Moving Averages (MA)
- Biểu diễn mức giá trung bình của tài sản theo thời gian.
- Giá vượt lên cao hơn MA đáng kể → kỳ vọng giảm về MA.
- Giá giảm xuống dưới MA đáng kể → kỳ vọng tăng về MA.

### 4. Standard Deviation (Độ Lệch Chuẩn)
- Đo lường mức độ biến động lịch sử.
- Độ lệch chuẩn cao → giá biến động mạnh → khả năng hồi quy về trung bình lớn hơn.

### 5. MACD (Moving Average Convergence Divergence)
- Indicator xu hướng đo động lượng và hướng của tài sản.
- Sử dụng 2 đường EMA liên tục cắt nhau để tạo tín hiệu tăng/giảm.
- Khoảng cách giữa 2 đường EMA ngày càng lớn → tài sản đang lệch khỏi trung bình.

### 6. Mean Reversion Indicator (MRI)
- Indicator chuyên dụng cho mean reversion trading.
- Giúp xác định điểm giá lệch đáng kể khỏi mức trung bình lịch sử.
- Hiệu quả trong thị trường ổn định với biến động nhất quán.
- Lưu ý: không tích hợp sẵn trên MT4/MT5, cần tải và cài đặt thủ công.

---

## Ví Dụ Thực Hành: Intraday Mean Reversion

**Công cụ sử dụng:** 50 EMA + RSI trên khung H1

**Quy trình:**

1. Dùng **50 EMA** xác định mức trung bình của tài sản.
2. Khi giá ở trên EMA + RSI báo **overbought** → vào lệnh **SELL**, đặt profit target tại đường EMA.
3. Khi giá ở dưới EMA + RSI báo **oversold** → vào lệnh **BUY**, đặt profit target tại đường EMA.

**Quản lý rủi ro:**
- Profit target: tại đường moving average.
- Stop loss: đặt ngay trên đỉnh cao nhất (khi bán) hoặc dưới đáy thấp nhất (khi mua).

---

## Mean Reversion vs Trend Following

| Khía Cạnh | Mean Reversion | Trend Following |
|---|---|---|
| Lý thuyết cốt lõi | Giá hồi quy về trung bình sau cực trị | Giá tiếp tục theo xu hướng hiện tại |
| Chiến lược | Khai thác cực trị giá tạm thời | Theo đuổi xu hướng dài hạn |
| Phản ứng thị trường | Phản ứng thái quá với tin tức/sự kiện | Sự bền vững của biến động giá |
| Định giá | Tìm lệch khỏi trung bình lịch sử | Tập trung vào tiếp diễn xu hướng |
| Thực thi lệnh | Stop loss chặt, chốt lời nhanh | Stop loss rộng, giữ lệnh lâu hơn |
| Quản lý rủi ro | Nắm bắt biến động ngắn hạn | Hưởng lợi từ dịch chuyển giá lớn |
| Hiệu suất | Tốt trong thị trường sideway | Tốt trong thị trường có xu hướng rõ |
| Phù hợp với | Trader ngắn hạn, tìm lợi nhuận nhanh | Trader kiên nhẫn, đầu tư dài hạn |
| Triển vọng thị trường | Thị trường dao động trong biên độ | Thị trường tăng/giảm bền vững |

> Lựa chọn giữa hai chiến lược phụ thuộc vào khẩu vị rủi ro, horizon đầu tư và quan điểm thị trường của trader — không có chiến lược nào vượt trội tuyệt đối.

---

## Ưu và Nhược Điểm

### Ưu Điểm ✅
- **Tỷ lệ thắng cao** — khai thác dòng chảy tự nhiên của giá quanh mức trung bình lịch sử.
- **Tiêu chí rõ ràng** — điểm vào/ra lệnh rõ ràng, đơn giản hóa quyết định giao dịch.
- **Hiệu quả trong thị trường sideway** — đặc biệt phù hợp khi thị trường không có xu hướng mạnh.
- **Lợi nhuận nhanh** — giao dịch ngắn hạn, có thể kép lãi theo thời gian.
- **Dễ tự động hóa** — tính chất rule-based phù hợp cho backtesting và thực thi hệ thống.

### Nhược Điểm ❌
- **Phản trực giác** — mua khi thị trường giảm, bán khi thị trường tăng — thách thức tâm lý.
- **Kém hiệu quả trong trending market** — giá có thể tiếp tục lệch xa trung bình trong thời gian dài.
- **Rủi ro sự kiện bất ngờ** — biến động lớn đột ngột có thể không hồi quy nhanh, gây drawdown lớn.
- **Cần theo dõi liên tục** — đòi hỏi giám sát và điều chỉnh vị thế thường xuyên.

---

## Khả Năng Sinh Lời

Dựa trên kết quả backtesting, nếu thực hiện đúng cách, tỷ lệ thắng có thể đạt **66% - 80%**. Tuy nhiên, chiến lược này có risk-reward ratio thấp hơn so với trend trading — phù hợp đặc biệt với day trader vì không chịu ảnh hưởng của biến động thị trường qua đêm.

> **Kết luận:** Mean reversion là chiến lược sinh lời, nhưng cần có kế hoạch giao dịch được cân nhắc kỹ lưỡng để tận dụng tối đa lợi thế của nó.

---

## Tóm Tắt Điều Kiện Áp Dụng

- ✅ Thị trường sideway / dao động trong biên độ
- ✅ Giá lệch đáng kể khỏi mức trung bình lịch sử
- ✅ Không có tin tức cơ bản lớn thay đổi xu hướng
- ❌ Tránh dùng trong thị trường có xu hướng mạnh (trending)
- ❌ Tránh dùng khi có sự kiện thị trường bất ngờ lớn
