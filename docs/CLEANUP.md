# Dọn cấu trúc dự án — 2026-11-09

## Đợt 1 — loại bản trùng và gom tài liệu

- Xóa 13 ZIP review sau khi đối chiếu tất cả thành viên với file đã giải nén: nội dung trùng từng byte.
- Xóa 165 bản sao trùng SHA-256 với mã nguồn, báo cáo hoặc bản lưu được giữ lại.
- Xóa hai log bàn giao `handoff_members/CamTu/predictions.jsonl` và `manual_review_queue.jsonl`: đã kiểm tra toàn bộ byte, cả hai là phần đầu của file cùng tên trong `artifacts/logs/` (279,846,020 byte tổng cộng).
- Giữ 35 file có nội dung riêng trong `docs/reviews/` và `docs/archive/`, bao gồm các bản thảo và nội dung bàn giao đã chỉnh sửa trước đợt dọn.
- Lưu thêm README trước khi cập nhật tại `docs/archive/manuscripts/README_before_cleanup.md` để giữ nguyên nguồn của hai bản review trùng.
- Bỏ hai README giữ chỗ ở `models/` và `results/`; model dùng thực tế nằm trong `artifacts/models/`. Kết quả baseline cũ chuyển vào `docs/archive/results/`.
- Xóa cache Python/pytest; thêm ignore cho ZIP review sinh tự động.
- Cập nhật README, mục lục tài liệu và ghi chú đường dẫn cho tài liệu MFAN. README dùng số liệu B8/B11/B12 final và môi trường B13.

Tổng kích thước file dư đã bỏ: **282,732,769 byte (~269.6 MiB)**, chưa tính cache. Đây là kích thước nội dung file, không phải dung lượng block đo trên ổ đĩa.

## Nội dung được giữ

Mã nguồn chạy chính, script thực nghiệm, notebook, dataset, model và lịch sử deployment/rollback, log vận hành chính và tất cả artifact thực nghiệm được giữ nguyên. Các snapshot review và bản thảo lưu trữ được giữ nguyên byte; đường dẫn và SHA-256 lịch sử bên trong vẫn phản ánh thời điểm tạo chúng.

Không chạy lại training, research hoặc simulation để cập nhật số liệu. Các kết quả khác đợt chạy được giữ riêng; xem [B14](reviews/B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md) để chọn số liệu cuối.

## Tra cứu

[cleanup_manifest.csv](cleanup_manifest.csv) ghi `old_path`, `new_path`, `action`, `bytes`, `sha256` cho 217 file đã xử lý. Mọi đường dẫn trong CSV tính từ gốc dự án.

| Action | Ý nghĩa |
|---|---|
| `archive_unique_file` | Chuyển file có nội dung riêng, giữ nguyên byte |
| `remove_identical_copy` | Bỏ bản trùng; `new_path` là bản được giữ |
| `remove_duplicate_log_prefix` | Bỏ log bàn giao là phần đầu của log chính |
| `remove_redundant_zip` | Bỏ ZIP đã có đầy đủ file giải nén; tra đường dẫn từng thành viên theo CSV |
| `remove_obsolete_placeholder` | Bỏ README giữ chỗ; mục lục tài liệu thay thế hướng dẫn cũ |

## Kiểm tra sau khi dọn

- Đối chiếu đầy đủ 217 dòng CSV: file cũ đã được xử lý, đích tra cứu tồn tại; SHA-256 của bản lưu và bản chính khớp nội dung trước khi dọn. Hai log chính vẫn chứa đầy đủ phần log bàn giao đã bỏ.
- Mã nguồn, script, test, model, lịch sử deployment, artifact và log chính khớp SHA-256 trước đợt dọn. Nội dung chỉnh sửa có sẵn được giữ ở vị trí ban đầu hoặc vị trí lưu trữ đã ghi trong CSV.
- Kiểm tra 56 liên kết nội bộ trong README, mục lục và ghi chú MFAN; đối chiếu AUC B12 trong README với JSON final.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -m 'not integration' -p no:cacheprovider`: **10 passed, 1 deselected**. Test integration chạy lại research và ghi báo cáo mẫu nên không chạy trong đợt dọn này.
- `run_fraud_flow.py --help`, `scripts/run_b8_ablation.py --help`, `bash -n run.sh` và `git diff --check` đều thành công.

## Đợt 2 — cất kết quả theo giai đoạn theo yêu cầu bổ sung

- Chuyển 108 file vào `archive/` hoặc `docs/archive/stages/`: kết quả research/baseline (gồm HistGradientBoosting), kết quả IEEE cũ, snapshot B8 trước rerun, hai bộ thực nghiệm mẫu, model IEEE đã adapt, notebook, biểu đồ và báo cáo nội bộ.
- Cất đủ năm CSV IEEE-CIS vào `archive/data/ieee-fraud-detection/`. Hai CSV train trùng ở `data/` được gộp sau khi đối chiếu toàn bộ byte, giảm thêm **709,880,747 byte (~677 MiB)**. PaySim vẫn ở `data/paysim.csv`.
- Giữ artifact final B8–B12, model PaySim, phiên bản deployment/rollback và log chính tại chỗ. Nội dung dataset/model/report được giữ nguyên SHA-256.
- Thêm đường dẫn đọc snapshot cho trang research và các script dùng báo cáo lịch sử; trang research ghi rõ khi đang xem kết quả trước đây. Kết quả mới được ưu tiên nếu người dùng chạy lại research.
- `run.sh` chuyển research và vẽ biểu đồ thành tùy chọn `RUN_RESEARCH=1`, `GENERATE_PLOTS=1`; mặc định chạy training và latency benchmark. Script vẽ ảnh ghi vào khu lưu trữ.
- IEEE-CIS lưu trữ được dùng qua `--external-data-path`/`--transaction-path`; research PaySim mặc định không tự lấy dữ liệu này.
- Giữ thêm bốn snapshot mã nguồn/hướng dẫn trước cập nhật tại `archive/source_before_cleanup/` để SHA-256 của các hồ sơ review cũ vẫn tra được.

[Manifest đợt 2](../archive/manifest.csv) ghi 110 đường dẫn đã xử lý. CSV đợt 1 đã được cập nhật đích tra cứu hiện tại; các khối trích dẫn trong MFAN, bản thảo và review tiếp tục giữ nguyên nội dung lịch sử.

Kiểm thử nhanh sau đợt 2: **14 passed, 1 deselected**. Đã dựng HTML research từ snapshot, kiểm tra đường dẫn IEEE chỉ được dùng khi truyền rõ, đối chiếu hash dữ liệu/model/kết quả và kiểm tra hai nhánh mặc định/tùy chọn của `run.sh` bằng lệnh giả lập. Không chạy lại training, research, simulation hoặc tạo lại biểu đồ.
