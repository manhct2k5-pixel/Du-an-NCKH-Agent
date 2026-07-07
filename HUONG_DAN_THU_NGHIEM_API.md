# Hướng Dẫn Thử Nghiệm `/docs` Và `/swagger-ui`

File này chỉ dùng để demo nhanh trước thầy, không giải thích dài.

## 1. Mở hệ thống

Trong terminal:

```bash
cd "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection"
source .venv/bin/activate
python3 run_fraud_flow.py serve
```

Nếu chạy thành công, mở trình duyệt:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/swagger-ui`

## 2. Cách nói ngắn gọn trước thầy

### Khi mở `/docs`

Nói:

```text
Đây là cổng tài liệu API của hệ thống. Ở đây em giới thiệu nhanh model đang chạy, nguồn dữ liệu đang dùng, payload mẫu để test, và cách gọi API nhận giao dịch.
```

### Khi mở `/swagger-ui`

Nói:

```text
Đây là trang để em thử trực tiếp API. Em sẽ gửi một giao dịch mẫu để hệ thống chấm điểm.
```

## 3. Các bước thử nghiệm trên `/swagger-ui`

### Bước 1

Tìm endpoint:

```text
POST /gateway/transaction
```

### Bước 2

Bấm:

```text
Try it out
```

### Bước 3

Dán JSON mẫu này vào ô request body:

```json
{
  "source": "paysim",
  "tx_type": "TRANSFER",
  "amount": 275000.0,
  "timestamp": "2025-01-01T14:00:00+00:00",
  "extras": {
    "card_id": "C123456789",
    "merchant_id": "merchant_12000",
    "device_id": "device_0801",
    "ip_address": "10.88.42.17",
    "location_id": "zone_041"
  },
  "oldbalanceOrg": 300000.0,
  "newbalanceOrig": 25000.0,
  "oldbalanceDest": 40000.0,
  "newbalanceDest": 315000.0,
  "is_fraud": 0
}
```

### Bước 4

Bấm:

```text
Execute
```

### Bước 5

Chỉ vào phần response và nói:

```text
Hệ thống đã nhận giao dịch, tính score rủi ro, gán route low/medium/high, rồi đưa ra quyết định cuối cùng là approve, review hoặc block.
```

## 4. Cách demo riêng cho `/docs`

Khi đang đứng ở:

```text
http://127.0.0.1:8000/docs
```

Bạn chỉ cần chỉ vào 3 vùng chính và nói ngắn gọn:

### Vùng 1: Giới thiệu

Nói:

```text
Đây là cổng tài liệu của hệ thống fraud detection. Trang này dùng để hướng dẫn cách test API, không phải dashboard kết quả.
```

### Vùng 2: Model hiện dùng gì

Nói:

```text
Ở đây hệ thống cho biết model đang chạy trên dữ liệu nào, đường dẫn dữ liệu và phiên bản model active hiện tại.
```

### Vùng 3: Payload mẫu PaySim

Nói:

```text
Đây là giao dịch mẫu để em copy sang Swagger và test ngay.
```

### Vùng 4: Swagger bên dưới

Nói:

```text
Ngay trong trang docs này cũng có vùng Swagger để em test API trực tiếp mà không cần rời sang trang khác.
```

## 5. Cách đọc kết quả trả về

Chỉ cần nhớ 3 ý:

- `score`: điểm rủi ro
- `route`: mức rủi ro (`low`, `medium`, `high`)
- `final_action`: quyết định cuối cùng (`approve`, `review`, `block`)

## 6. Câu chốt ngắn gọn

Nếu thầy hỏi 2 trang này khác nhau chỗ nào, nói:

```text
/docs là trang giới thiệu API.
/swagger-ui là trang để chạy thử API thật.
```

## 7. Nếu muốn demo thêm 1 câu

Bạn có thể nói thêm:

```text
Như vậy hệ thống không chỉ có mô hình huấn luyện offline, mà còn có API để nhận giao dịch mới và trả kết quả dự đoán theo thời gian thực.
```
