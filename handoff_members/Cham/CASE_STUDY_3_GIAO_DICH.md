# Case Study 3 Giao Dịch

File này chọn 3 giao dịch đại diện cho 3 nhánh trong luồng mới:
- `low` -> tự động approve
- `medium` -> đưa qua agent để review
- `high` -> tự động block

## 1. Tóm tắt nhanh

| Case | Tx ID | Loại giao dịch | Số tiền | Score | Route | Kết quả cuối | Nhãn thật |
|---|---|---|---:|---:|---|---|---:|
| Case 1 | `tx_0102000` | CASH_OUT | 194,026.15 | 0.000003 | Low | Approve | 0 |
| Case 2 | `tx_0025517` | TRANSFER | 564,314.98 | 0.428375 | Medium | Review | 0 |
| Case 3 | `tx_0106432` | TRANSFER | 2,093,951.47 | 0.999983 | High | Block | 1 |

## 2. Case 1: Low-risk -> Auto Approve

### Thông tin giao dịch

| Trường | Giá trị |
|---|---|
| Tx ID | `tx_0102000` |
| Thời điểm | `2025-01-01T14:00:00` |
| Loại | `CASH_OUT` |
| Số tiền | `194,026.15` |
| Device | `device_12869` |
| Location | `zone_014` |
| Nhãn thật | `0` |

### Lookup online

| Đặc trưng lookup | Giá trị |
|---|---:|
| `tx_count_24h` | 0 |
| `device_tx_count_24h` | 3 |
| `location_tx_count_24h` | 467 |
| `merchant_tx_count_24h` | 8 |
| `location_fraud_rate` | 0.004283 |
| `ip_fraud_rate` | 0.000000 |
| `merchant_fraud_rate` | 0.000000 |

### Giải thích mô hình

Top 3 đặc trưng có tác động mạnh nhất:

| Thứ hạng | Đặc trưng | Tác động SHAP |
|---|---|---:|
| 1 | `balance_diff` | -5.0252 |
| 2 | `oldbalanceDest` | -1.4955 |
| 3 | `location_tx_count_24h` | -1.4597 |

### Quyết định cuối

- Score rất thấp: `0.000003`
- Route: `low`
- Action: `approve`
- Ghi chú hệ thống: giao dịch được thông qua tự động, không tốn chi phí agent/LLM

### Diễn giải

Đây là một giao dịch nằm trong vùng rủi ro rất thấp:
- không có dấu hiệu bất thường mạnh ở lookup online
- top SHAP đều kéo score xuống
- hệ thống xử lý đúng theo triết lý tối ưu chi phí: `low` thì không gọi agent

## 3. Case 2: Medium-risk -> ReAct Agent giữ lại để review

### Thông tin giao dịch

| Trường | Giá trị |
|---|---|
| Tx ID | `tx_0025517` |
| Thời điểm | `2025-01-01T09:00:00` |
| Loại | `TRANSFER` |
| Số tiền | `564,314.98` |
| Device | `device_17601` |
| Location | `zone_118` |
| Nhãn gốc trong log | `0` |

### Tín hiệu từ mô hình

| Chỉ số | Giá trị |
|---|---:|
| Score | 0.428375 |
| Route | `medium` |
| Latency | 21.84 ms |

Top 3 đặc trưng có ảnh hưởng mạnh:

| Thứ hạng | Đặc trưng | Tác động SHAP |
|---|---|---:|
| 1 | `amount_ratio` | -3.5148 |
| 2 | `newbalanceOrig` | -1.9711 |
| 3 | `balance_diff` | -1.8693 |

### Tool mà agent đã gọi

| Tool | Kết quả chính |
|---|---|
| `get_card_history` | Không có lịch sử 24h, chưa có lịch sử gian lận |
| `verify_device_id` | Thiết bị mới, cần step-up verification |
| `query_merchant_risk` | Merchant chưa có lịch sử rủi ro đáng kể |

### Kết quả agent

| Thuộc tính | Giá trị |
|---|---|
| Recommended action | `review` |
| Confidence | `0.5784` |
| Reason codes | `device_step_up`, `new_device` |

Evidence chính:
- thiết bị chưa có giao dịch trước đó trong cửa sổ 24h
- tool xác nhận `needs_step_up = true`
- mô hình chưa đủ mạnh để auto-block, nhưng cũng chưa đủ an toàn để auto-approve

### Quyết định cuối

- Route: `medium`
- Action: `review`
- Reviewer note: giữ giao dịch để xác minh thêm

### Diễn giải

Case này thể hiện đúng vai trò của nhánh `medium`:
- mô hình lõi chưa đẩy lên `high`
- nhưng thông tin về thiết bị mới khiến hệ thống không cho approve ngay
- agent bổ sung tầng giải thích và đưa giao dịch sang review có kiểm soát

## 4. Case 3: High-risk -> Auto Block

### Thông tin giao dịch

| Trường | Giá trị |
|---|---|
| Tx ID | `tx_0106432` |
| Thời điểm | `2025-01-01T14:00:00` |
| Loại | `TRANSFER` |
| Số tiền | `2,093,951.47` |
| Device | `device_12732` |
| Location | `zone_113` |
| Nhãn thật | `1` |

### Lookup online

| Đặc trưng lookup | Giá trị |
|---|---:|
| `tx_count_24h` | 0 |
| `device_tx_count_24h` | 8 |
| `location_tx_count_24h` | 555 |
| `merchant_tx_count_24h` | 0 |
| `location_fraud_rate` | 0.000000 |
| `ip_fraud_rate` | 0.000000 |
| `merchant_fraud_rate` | 0.000000 |

### Giải thích mô hình

| Thứ hạng | Đặc trưng | Tác động SHAP |
|---|---|---:|
| 1 | `balance_diff` | 5.6282 |
| 2 | `amount_log1p` | 1.3199 |
| 3 | `org_balance_delta_ratio` | 0.8511 |

Monitoring flag:
- `device_shift`

### Quyết định cuối

- Raw probability: `0.999983`
- Route: `high`
- Action: `block`
- Ghi chú hệ thống: chặn ngay và lưu explanation log bất đồng bộ
- Kết quả thực tế: nhãn thật là `fraud`

### Diễn giải

Đây là case tiêu biểu cho khả năng phát hiện gian lận của mô hình:
- số tiền rất lớn
- biến động balance rất mạnh
- score gần như tuyệt đối
- hệ thống chặn ngay mà không cần qua agent
- quyết định cuối khớp với nhãn thật

## 5. Kết luận từ 3 case study

Ba case trên minh họa đúng triết lý thiết kế của mô hình mới:
- `low`: tối ưu tốc độ và chi phí
- `medium`: thêm lớp điều tra và giải thích
- `high`: ưu tiên an toàn, chặn tức thì

Khi trình bày trong báo cáo hoặc slide, bạn có thể dùng đúng 3 case này để minh họa toàn bộ luồng hệ thống mà không cần giải thích lại code.
