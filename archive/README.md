# Khu lưu trữ thực nghiệm

Cất ngày 2026-11-09 để thư mục chạy chính tập trung vào PaySim và model XGBoost đang triển khai. Các file được chuyển giữ nguyên nội dung; [manifest.csv](manifest.csv) ghi đường dẫn cũ, đường dẫn hiện tại, kích thước và SHA-256.

| Thư mục | Nội dung |
|---|---|
| `artifacts/reports/` | Kết quả research/baseline gồm HistGradientBoosting, ablation và thống kê cũ, IEEE optimized, latency và leakage các đợt trước |
| `artifacts/reports/plots/` | 13 biểu đồ sinh từ script; không thấy tham chiếu ảnh trong tài liệu hiện có |
| `artifacts/reports/b8_before_rerun/` | Snapshot trước khi chạy lại B8 |
| `artifacts/experiments/` | Các đợt research mẫu 3.000 và 20.000 giao dịch |
| `artifacts/models/` | Model XGBoost đã adapt cho IEEE-CIS; không dùng trong deployment PaySim |
| `notebooks/` | Notebook khám phá/baseline cũ và ba ảnh phân tích dữ liệu |
| `data/ieee-fraud-detection/` | Đủ năm CSV IEEE-CIS: train, test và sample submission; bỏ qua trong Git |
| `source_before_cleanup/` | Các snapshot code/hướng dẫn được hồ sơ review cũ tham chiếu trước khi cập nhật đường dẫn, tùy chọn chạy và sửa lỗi runtime |

Các báo cáo nội bộ theo giai đoạn nằm ở [docs/archive/stages/](../docs/archive/README.md). Hồ sơ audit B13/B14/B15 ở [docs/reviews/](../docs/reviews/README.md). Artifact final B8–B12, model PaySim, các phiên bản và model rollback vẫn ở `artifacts/`.

HistGradientBoosting và các baseline khác không có model huấn luyện được lưu riêng trong dự án; mã so sánh vẫn ở `fraud_flow/research.py` để tái lập khi cần. Kết quả baseline B7 vẫn là bằng chứng tham chiếu cho B14 dù được cất tại đây.

## Đọc lại hoặc tái lập

Trang research đọc snapshot ở đây khi chưa có kết quả mới và đánh dấu dữ liệu lịch sử. `research` hoặc training được gọi chủ động vẫn ghi kết quả mới vào `artifacts/` như trước.

```bash
# Tùy chọn: chạy lại baseline/ablation với PaySim
python3 run_fraud_flow.py research --source paysim

# Tùy chọn: kiểm định ngoài với IEEE-CIS đã lưu trữ
python3 run_fraud_flow.py research --source paysim --external-data-path archive/data/ieee-fraud-detection/train_transaction.csv

# Tùy chọn: sinh lại biểu đồ, lưu vào archive/artifacts/reports/plots/
python3 scripts/generate_plots.py
```

`bash run.sh` mặc định chạy training và latency benchmark; bật thêm research/biểu đồ bằng `RUN_RESEARCH=1 GENERATE_PLOTS=1 bash run.sh`. Đợt cất này không chạy lại các thực nghiệm hoặc ghi đè kết quả lịch sử.

110 đường dẫn được xử lý: 108 file được chuyển, hai CSV trùng hoàn toàn được gộp về bản IEEE-CIS đầy đủ. Phần gộp dữ liệu giải phóng **709,880,747 byte (~677 MiB)**; các file chuyển vị trí không làm giảm dung lượng.
