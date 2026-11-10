# Tài liệu FraudFlow

Cấu trúc được dọn ngày 2026-11-09. Bắt đầu từ [README dự án](../README.md).

## Chạy dự án

- [Hướng dẫn chạy mô hình](../HUONG_DAN_CHAY_MO_HINH.md)
- [Hướng dẫn thử nghiệm API](../HUONG_DAN_THU_NGHIEM_API.md)
- [Ngưỡng và phân luồng](../THRESHOLDS.md)
- [Chuẩn bị dữ liệu](../data/README.md)

## Kết quả và bằng chứng

- [B14 — nguồn số liệu kỹ thuật đã đối chiếu](reviews/B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md): ưu tiên khi viết báo cáo cuối; dẫn nguồn tới artifact final B8–B13.
- [Dữ liệu bổ sung MFAN](../DU_LIEU_BO_SUNG_MFAN.md): tổng hợp nguyên văn nhiều đợt chạy, kèm SHA-256; đọc ghi chú về đường dẫn lịch sử ở đầu file.
- [Hồ sơ review](reviews/README.md): môi trường B13, đối chiếu B14 và phản hồi B15.
- [Case study ba giao dịch](CASE_STUDY_3_GIAO_DICH.md)

## Tài liệu mô tả và bản thảo

- [Báo cáo mô hình PaySim trước đây](archive/stages/REPORT_MO_HINH_PAYSIM.md)
- [Bảng kết quả báo cáo trước đây](archive/stages/BANG_KET_QUA_BAO_CAO.md)
- [Thiết lập thực nghiệm trước đây](archive/stages/experiments_setup.md)
- [Bản thảo phương pháp](archive/stages/methodology_draft.md)
- [Báo cáo tuần về leakage](archive/stages/report_content.md)
- [Checklist chứng minh bốn lớp](archive/stages/CHECKLIST_CHUNG_MINH_4_LOP_NCKH.md)
- [Bản thảo và bàn giao lịch sử](archive/README.md)
- [Kết quả cũ, dữ liệu IEEE, notebook và biểu đồ](../archive/README.md)

Các hướng dẫn và bản thảo trên có số liệu của những đợt chạy trước. Khi số liệu khác nhau, dùng B14 và các thư mục `artifacts/reports/b8_final/` đến `b12_final/`; giữ báo cáo gốc để tra cứu nguồn.

## Tra cứu sau khi dọn

- [Nội dung và phạm vi dọn](CLEANUP.md)
- [Chạy thử dự án và các lỗi đã sửa](RUNTIME_CHECK.md)
- [Tối ưu tốc độ dashboard và phép đo trước/sau](DASHBOARD_PERFORMANCE.md)
- [Kiểm tra UI/UX trên desktop và mobile](UI_UX_REVIEW.md)
- [Giao diện và kịch bản trình diễn NCKH phiên bản 1.3](DEMO_NCKH.md)
- [LLM có thực sự chạy? Nguồn giải thích và cách đối chiếu](LLM_RUNTIME.md)
- [Chạy DeepSeek Web qua DS2API và kiểm chứng thật](DS2API_SETUP.md)
- [Bảng đường dẫn cũ → mới](cleanup_manifest.csv): mỗi file đã xóa hoặc chuyển có hành động, kích thước và SHA-256 trước khi dọn.
