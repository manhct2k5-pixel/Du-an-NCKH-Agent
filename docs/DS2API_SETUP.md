# DeepSeek Web qua DS2API trong FraudFlow

Thư mục được cung cấp: `ds2api-main-20261110T061707Z-1-001/ds2api-main/`.

## Kết quả thực tế ngày 10/11/2026

- Binary Linux đi kèm chạy được, không cần cài Go hoặc Docker.
- `/healthz`, `/readyz`, `/v1/models` trả HTTP 200.
- Đăng nhập email/password ban đầu bị từ chối với `RISK_DEVICE_DETECTED`. Dùng token của phiên Firefox đã đăng nhập thì chat API trả HTTP 200 và `API_OK`.
- Lệnh `run_fraud_flow.py llm-check` nhận phản hồi thật với `backend=ds2api`, `external_response_observed=true`, không dùng heuristic.
- Mẫu medium trên trình duyệt chạy **4 công cụ, 6 phản hồi model qua API, 0 lỗi parser**, quyết định `review`. Thời gian giao dịch này khoảng **16,94 giây**; đây là một mẫu thử, không phải benchmark thống kê.
- **68 kiểm thử Python đạt**. Kết quả thật ở 1440, 390 và 320 px không tràn ngang, không có lỗi JavaScript hoặc vi phạm trong bộ quy tắc axe đã chọn.

[Báo cáo gọi API và trình duyệt](ui-audit/nckh/ds2api-live-result.json).

Theo [README DS2API](../ds2api-main-20261110T061707Z-1-001/ds2api-main/README.en.md), dịch vụ này nối DeepSeek Web sang API tương thích OpenAI bằng phiên đăng nhập web. Đường chính thức `api.deepseek.com` là cấu hình riêng; lần thử trước trả HTTP 402. Không dùng kết quả DS2API để khẳng định đường API chính thức đã hoạt động.

## Chạy lại

Khi clone từ Git, binary, `config.json`, `.env` và token không được đưa lên repository. Mã nguồn DS2API và giấy phép gốc được giữ trong thư mục đi kèm. Với Go 1.26 trở lên, tạo binary bằng `go build -o ds2api ./cmd/ds2api` trong thư mục DS2API; copy `config.example.json` thành `config.json`, điền thông tin tài khoản/phiên web của bạn, rồi tạo `.env` từ `.env.example` ở gốc FraudFlow. `DS2API_API_KEY` phải khớp khóa client trong `config.json`.

`.env` local và khóa client đã được ghép với cấu hình DS2API. Mở hai terminal ở thư mục gốc dự án:

```bash
# Terminal 1: nếu cầu nối chưa chạy
.venv/bin/python scripts/run_ds2api.py
```

```bash
# Terminal 2: kiểm tra và chạy ứng dụng
.venv/bin/python run_fraud_flow.py llm-check
.venv/bin/python run_fraud_flow.py serve --llm-api
```

Mở `http://127.0.0.1:8000/transaction/form`, chọn mẫu **Trung bình**. Khối thực thi phải ghi `ds2api · LLM qua API: đã nhận phản hồi`. `/llm/status` báo bộ đếm của tiến trình server đó.

Phiên kiểm thử riêng hiện dùng `http://127.0.0.1:18766/transaction/form`, Redis và log dưới `/tmp`; giao dịch kiểm tra không ghi vào log production. Không chạy hai server trên cùng port.

Binary DS2API đi kèm lắng nghe trên `0.0.0.0`; FraudFlow gọi qua loopback. Launcher dùng khóa admin riêng và tắt tự build WebUI để chạy binary có sẵn.

## Cấu hình và phiên đăng nhập

| Trường | Vai trò |
| --- | --- |
| `.env`: `FRAUD_LLM_PROVIDER=ds2api` | Chọn cầu nối local |
| `.env`: `DS2API_API_BASE=http://127.0.0.1:5001/v1` | Địa chỉ API DS2API |
| `.env`: `DS2API_API_KEY` | Khóa client, khớp một key trong DS2API `config.json` |
| `.env`: `FRAUD_LLM_MODEL=deepseek-v4-flash` | Model đã thử trên binary cung cấp |
| DS2API `config.json`: `accounts[0].token` | Mã phiên DeepSeek Web đã đăng nhập |

Token phiên web, khóa client local và key API chính thức có vai trò khác nhau. Dữ liệu nhạy cảm chỉ lưu local, file quyền `0600`, được Git bỏ qua. Báo cáo không chứa token, password hoặc API key.

Nếu phiên hết hạn, đăng nhập DeepSeek Web bình thường rồi cập nhật token bằng công cụ nhập ẩn:

```bash
.venv/bin/python scripts/set_ds2api_token.py
```

Khởi động lại DS2API sau khi cập nhật token. Script chỉ lưu token local, không tự thực hiện xác minh thiết bị.

## Diễn giải NCKH

- `backend=ds2api` chỉ phản hồi nhận qua cầu nối web, phân biệt với API chính thức. Chỉ đọc bộ đếm của giao dịch đang xem.
- Lượt sửa định dạng ReAct được ghi ở `react_parser_errors`; `_Exception` không tính thành công cụ.
- Các đặc trưng `llm_*`, B8/B11 offline và artifact thực nghiệm cũ vẫn giữ nguyên; không biến thành kết quả đánh giá LLM qua API.
- Latency ở báo cáo live tính cả network, khác phép đo B11.
- DS2API phụ thuộc phiên đăng nhập và giao thức web; báo cáo xác nhận hoạt động tại thời điểm kiểm tra.
