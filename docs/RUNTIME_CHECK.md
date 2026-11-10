# Chạy thử và sửa lỗi — 2026-11-09

Đã khởi động Uvicorn và Redis thật trên localhost, gửi request HTTP, chạy kiểm thử tự động và thử các lệnh train/simulate. API chạy trên bản sao dự án trong thư mục tạm; model đang triển khai được sao chép để kiểm tra, dataset PaySim chỉ được đọc. Kết quả test không thay thế số liệu NCKH.

## Lỗi đã sửa

| Vấn đề | Hành vi sau sửa |
|---|---|
| `Infinity` lọt vào amount/balance làm XGBoost trả HTTP 500 | Từ chối giá trị không hữu hạn với HTTP 422; lỗi validation cũng xuất JSON hợp lệ khi request chứa NaN/Infinity dạng literal |
| Timestamp sai vẫn được nhận khi truyền thêm `step` | Kiểm tra timestamp bất kể có `step`, trả HTTP 400 nếu sai định dạng |
| Nhãn giao dịch nhận giá trị ngoài 0/1 | `is_fraud` và `is_flagged_fraud` chỉ nhận 0, 1 hoặc null |
| API đơn nhánh medium chỉ trả `pending_review`, thiếu score/giải thích cuối và làm mất nhãn trong prediction/feedback log | Dùng cùng luồng xử lý với batch, chờ agent hoàn tất và trả đủ quyết định, explanation, latency, nhãn; ghi log và monitoring qua cùng một lần xử lý |
| `FRAUD_FLOW_BOOTSTRAP_ROWS=0` bị hiểu thành nạp toàn bộ lịch sử | Trả về 0 ngay, không đọc dataset hoặc warm-start Redis |
| Test integration ghi kết quả mẫu vào thư mục dự án | Ghi vào `tmp_path` và kiểm tra đường dẫn output nằm trong thư mục tạm |

Nhánh medium hiện xử lý đồng bộ: response đầy đủ đến sau khi agent kết thúc. Chế độ kiểm tra dùng heuristic agent có sẵn, không gọi external LLM.

Mã sửa ở [service.py](../fraud_flow/service.py), [pipeline.py](../fraud_flow/pipeline.py); kiểm thử hồi quy ở [test_service.py](../tests/test_service.py). Các snapshot nguồn cũ được hồ sơ review tham chiếu vẫn giữ nguyên trong `archive/source_before_cleanup/` và được cập nhật đích tra cứu trong CSV.

## Kết quả kiểm tra

- `pip check`: không có dependency bị thiếu hoặc xung đột theo metadata cài đặt.
- Toàn bộ pytest: **31 passed**, gồm integration research với mẫu 20.000 giao dịch.
- **33 lượt kiểm tra HTTP** đạt mã trạng thái mong đợi: trang chủ, form, docs/Swagger, research, dashboard, static assets, gateway đơn/batch, review queue, review thủ công, xuất XLSX và request sai.
- Batch 18 giao dịch mẫu chạy qua đủ ba nhánh: low 3, medium 14, high 1. Đây là dữ liệu kiểm tra chức năng, không phải thống kê đánh giá mô hình.
- `train --sample-size 3000`: hoàn tất, model mẫu được lưu vào vùng thí nghiệm của bản sao tạm.
- `simulate --limit 50` với model mẫu: hoàn tất 50 giao dịch; low 39, medium 11. Deployment state trong bản sao được khôi phục sau phép thử.
- Hash của 63 file production thuộc model, reports, deployment và logs giữ nguyên so với trước khi chạy thử.
- Trước tối ưu, đọc dashboard từ log production mất khoảng **6.52 giây** trong một lần đo local. Điểm chậm này đã được xử lý ở đợt tiếp theo: xem [kết quả tối ưu dashboard](DASHBOARD_PERFORMANCE.md).

Chưa kiểm tra tải đồng thời, external LLM hoặc chạy lại toàn bộ benchmark IEEE-CIS. Các giới hạn này không được suy ra từ kết quả kiểm thử chức năng ở trên.

Chạy lại kiểm thử từ gốc dự án:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```
