# Hồ sơ review

Các bản sao trùng từng byte với mã nguồn hoặc artifact chính đã được bỏ. Tài liệu và snapshot có nội dung riêng được giữ nguyên byte tại đây. Tên đường dẫn bên trong các hồ sơ là đường dẫn lịch sử tại thời điểm review; dùng [bảng tra cứu](../cleanup_manifest.csv) để tìm vị trí hiện tại.

## Hồ sơ cuối

- [B13 — môi trường và khả năng tái lập](B13_IMPLEMENTATION_REVIEW/B13_FINAL_AUDIT.md)
- [B14 — nguồn số liệu kỹ thuật](B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md)
- [B14 — số liệu CSV](B14_SINGLE_SOURCE_OF_TRUTH/technical_single_source_of_truth.csv)
- [B14 — danh mục giá trị cũ](B14_SINGLE_SOURCE_OF_TRUTH/obsolete_values_inventory.md)
- [B15 — thư phản hồi kỹ thuật](B15_TECHNICAL_RESPONSE/B15_TECHNICAL_RESPONSE_LETTER.md)

## Hồ sơ các bước trước

- [B2 — checklist tiền xử lý](B2_PREPROCESSING_REVIEW/B2_CHECKLIST.md)
- [B7 — danh mục baseline](B7_BASELINE_REVIEW/B7_FILE_INDEX.md)
- [B8 — ablation review](B8_ABLATION_REVIEW/B8_AUDIT_SUMMARY.md)
- [B9 — robustness review](B9_ROBUSTNESS_REVIEW/B9_AUDIT_SUMMARY.md)
- [B10 — thống kê review](B10_STATISTICAL_REVIEW/B10_AUDIT_SUMMARY.md)
- [B12 — IEEE-CIS review](B12_IEEE_CIS_REVIEW/B12_AUDIT_SUMMARY.md)

`B12_FINAL_REVIEW/` và 13 ZIP review cũ chỉ chứa bản sao đã có ở nơi khác nên đã được bỏ. Kết quả thực nghiệm final B8–B12 nằm trong `artifacts/reports/b8_final/` đến `b12_final/` ở gốc dự án.

Các file Python trong thư mục này là snapshot phục vụ đối chiếu lịch sử. Chạy chương trình từ `fraud_flow/`, `scripts/` và các entry point ở gốc dự án.
