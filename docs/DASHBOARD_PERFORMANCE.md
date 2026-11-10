# Tối ưu dashboard — 2026-11-09

Dashboard trước đây đọc lại toàn bộ JSONL và giải mã hơn 500.000 bản ghi cho mỗi request. Các log hiện có chiếm khoảng 372 MB. Phần lớn feedback chỉ cần số lượng; prediction chỉ cần cửa sổ gần nhất và giao dịch đang xem.

## Thay đổi

- Thêm chỉ mục JSONL trong bộ nhớ, theo vị trí byte. Sau lần đầu, chỉ quét phần file được nối thêm.
- Feedback được đếm theo bản ghi hoàn chỉnh; drift/high-risk chỉ giải mã những dòng cuối cần hiển thị.
- Prediction giữ vị trí giao dịch và giao dịch gần nhất có agent, nên vẫn mở được case cũ ngoài cửa sổ 500 dòng mà không quét lại toàn bộ JSON.
- Review queue giữ metadata phục vụ lọc và ưu tiên; chỉ đọc đầy đủ agent trace cho những case thực sự hiển thị.
- Bộ nhớ đệm bản ghi có giới hạn 8.192 dòng mỗi chỉ mục; giữ tối đa 32 chỉ mục file. Không tạo bản sao log hay database trên đĩa, không thêm dependency.
- Chỉ mục nhận biết log được nối thêm, ghi lại, truncate, thay file hoặc xóa. Dòng cuối chưa có newline được chờ tới khi writer ghi xong. Dashboard thử đọc lại nếu log bị thay trong lúc lấy snapshot.
- Bổ sung xử lý `agent=null` khi dashboard chọn một giao dịch tự động duyệt/chặn làm focus.

Mã chính: [log_reader.py](../fraud_flow/log_reader.py) và [ops.py](../fraud_flow/ops.py). Việc ghi log, tính score, nhãn và model không thay đổi.

## Kết quả trên log hiện có

| Phép đo | Thời gian |
|---|---:|
| Dựng dữ liệu dashboard trước tối ưu | 6,61 giây |
| Lần đầu tạo chỉ mục trong tiến trình mới | 3,21 giây |
| Các lần dựng dữ liệu tiếp theo | 0,108–0,112 giây |
| Request `/dashboard` đầu tiên qua TestClient với Redis thật | 3,28 giây |
| Request `/dashboard` tiếp theo, gồm mã hóa JSON | 0,31 giây |
| Request `/dashboard/html` khi chỉ mục đã có | 0,11 giây |
| Trang chủ và research khi chỉ mục đã có | 0,10–0,11 giây |

Đây là đo local với dữ liệu hiện có, không phải benchmark tải đồng thời. Chỉ mục nằm trong từng tiến trình; khởi động lại hoặc thay thế toàn bộ log cần tạo lại chỉ mục. Phép đo API dùng model thật và Redis riêng, mọi output được chuyển vào thư mục tạm.

## Kiểm tra độ đúng

- Payload trên log production khớp toàn bộ với bản đọc cũ, trừ trường thời gian `generated_at`.
- Tổng số vẫn là 64.125 prediction, 364.395 feedback, 30.611 pending review và 2.060 high-risk log.
- So sánh với bộ đọc toàn bộ file sau khi có prediction mới, thêm queue, ghi quyết định review và xoay log; kiểm tra cả case cũ, ID lặp và giới hạn số thẻ hiển thị.
- Kiểm tra Unicode, dòng trắng, dòng đang ghi dở, truncate/replace/delete và snapshot cũ bị vô hiệu hóa.
- Toàn bộ kiểm thử: **40 passed**, trong đó chín trường hợp kiểm tra phần dashboard/log mới tại [test_dashboard_logs.py](../tests/test_dashboard_logs.py).
- 63 file production thuộc model, report, deployment và log giữ nguyên SHA-256 sau kiểm tra.
