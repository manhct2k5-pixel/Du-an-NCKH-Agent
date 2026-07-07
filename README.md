# Du-an-NCKH-Agent

## Fraud Detection Flow for NCKH

Mô hình hiện tại đã được chỉnh lại theo hướng phù hợp hơn với đề tài Nghiên cứu Khoa học: `PaySim-first`, dùng `XGBoost` làm mô hình triển khai chính, có lớp phân tích kiểu LLM để tạo đặc trưng, và có nhánh `ReAct Agent` chỉ chạy cho giao dịch mức rủi ro trung bình. PaySim được dùng để chứng minh hiệu năng của kiến trúc, còn IEEE-CIS được dùng làm external validation: XGBoost PaySim được đóng băng, IEEE-CIS được align sang 25 PaySim features rồi chỉ dùng để dự đoán và tính metric cuối. Kết quả frozen-model hiện tại cho thấy domain shift mạnh, nên không diễn giải quá mức là model PaySim tổng quát hóa trực tiếp sang IEEE-CIS.

## Mô hình đang triển khai

### Giai đoạn 1. Xây dựng và huấn luyện offline
- Dữ liệu mặc định: `data/paysim.csv`
- Chỉ giữ hai loại giao dịch có ý nghĩa phát hiện gian lận: `TRANSFER`, `CASH_OUT`
- Tách tập theo thời gian, không shuffle:
  - train: `322,275`
  - validation: `69,059`
  - test: `69,060`
- Mô hình deploy chính: `XGBoost`
- Ngưỡng phân lớp chính hiện tại: `0.50` (chọn tự động theo F1 trên val, seed=42)

### Giai đoạn 2. Xử lý giao dịch thời gian thực
- Nhận giao dịch mới từ gateway/API
- Lookup đặc trưng online qua Redis:
  - `tx_count_24h`
  - `avg_amount_7d`
  - `device_tx_count_24h`
  - `location_fraud_rate`
  - `merchant_fraud_rate`
- Sinh `fraud score`
- Giải thích top đặc trưng bằng SHAP
- Route theo 3 nhánh:
  - `score < 0.30` → `low` (auto approve)
  - `0.30 <= score <= 0.85` → `medium` (ReAct agent)
  - `score > 0.85` → `high` (auto block)

### Giai đoạn 3. Giải thích và ra quyết định
- `low`: tự động thông qua, không gọi agent
- `medium`: đi qua `ReAct Agent` + tool calling + JSON validation. Nhánh này hiện chạy đồng bộ theo từng giao dịch.
- `high`: chặn ngay, lưu explanation log bất đồng bộ

### Giai đoạn 4. Phản hồi và cải tiến
- Lưu log dự đoán
- Lưu feedback nhãn thật
- Theo dõi drift
- Retrain định kỳ
- Hỗ trợ deploy, canary, rollback

## Điểm mới so với bản cũ

- Mặc định ưu tiên `PaySim`, đồng thời tự dùng `IEEE-CIS` làm frozen-model external validation khi có đủ file trong `data/`.
- Anomaly sidecar không còn dùng ngưỡng cứng `0.70` trong runtime; model active hiện học ngưỡng P95 validation `0.418285` và lưu vào `model_metadata.json`.
- Bổ sung lớp đặc trưng `LLM-style` có tính tái lập:
  - `llm_risk_score`
  - `llm_reason_count`
  - `llm_high_risk_flag`
  - `llm_review_flag`
  - `llm_category_hash`
- Chế độ `sample-size` lấy mẫu theo timeline một cách deterministic, không còn lấy đơn giản `N` giao dịch đầu tiên.
- Tách artifact giữa `production` và `sample experiment`, tránh ghi đè kết quả chính thức.

## Kết quả chính của bản production hiện tại

Trên tập PaySim đã lọc (460,394 rows — **sau khi fix label leakage**, 2026-04-15):

| Tập đánh giá | AUC | PR-AUC | F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Validation | 0.9994 | 0.9613 | 0.9600 | 0.9677 | 0.9524 |
| Test | 0.9984 | 0.9970 | 0.9931 | 0.9893 | 0.9969 |

Ghi chú:
- Số liệu trên là **clean run** không có label leakage. Xem `artifacts/reports/CLEAN_RUN_RESULTS.md` để so sánh với kết quả trước khi fix.
- `HistGradientBoosting` là baseline có điểm test tốt nhất trong research suite (test AUC=0.9999).
- `XGBoost` vẫn được giữ làm mô hình deploy chính để bám đúng kiến trúc đề tài và thuận tiện cho lớp giải thích theo SHAP.
- Active version hiện tại: `v20260420T053341630222Z`; simulation 5,000 giao dịch sau adaptive threshold tạo `25` step-up (`0.50%`).
- Frozen PaySim model trên IEEE-CIS hiện đạt AUC `0.6285`, PR-AUC `0.0532`, F1 `0.0201`. Đây là bằng chứng domain shift mạnh giữa PaySim và IEEE-CIS: model vẫn có tín hiệu tốt hơn đoán mò, nhưng chưa đủ để nói tổng quát hóa trực tiếp.
- Transfer learning dùng 10% IEEE-CIS đã align sang 25 PaySim features đạt AUC `0.6774`, PR-AUC `0.0826`, F1 `0.1894` trên 90% IEEE-CIS còn lại; đây là cải thiện so với frozen model nhưng vẫn thấp hơn train native.
- Nếu train lại cùng kiến trúc trên IEEE-CIS, benchmark hiện tại đạt khoảng AUC `0.8415`; con số này chỉ chứng minh pipeline học được trên dataset khác, không chứng minh frozen PaySim model tổng quát hóa.

## Quickstart (3 lệnh)

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip redis-server
cd "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection"
python3 -m venv --clear .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 run_fraud_flow.py train
python3 run_fraud_flow.py research
# Kết quả xuất ra artifacts/reports/
```

> **Yêu cầu:** Python >= 3.11, dataset `data/paysim.csv`. Để có external validation, thêm IEEE-CIS `train_transaction.csv` và `train_identity.csv` vào `data/` hoặc `data/ieee-fraud-detection/`.

---

## Chạy đầy đủ (WSL/Ubuntu — có online simulation)

```bash
cd "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection"
source .venv/bin/activate
python3 run_fraud_flow.py train
python3 run_fraud_flow.py research
python3 run_fraud_flow.py adapt --ieee-data-path data/train_transaction.csv --adapt-fraction 0.10
python3 run_fraud_flow.py deploy --reason "Research-ready model"
python3 run_fraud_flow.py simulate --limit 100   # requires Redis (redislite)
python3 run_fraud_flow.py serve                  # requires Redis (redislite)
```

PaySim + IEEE-CIS external validation:

```bash
python3 run_fraud_flow.py research --source paysim --external-data-path data/train_transaction.csv
# hoặc:
python3 run_fraud_flow.py research --source paysim --external-data-path data/ieee-fraud-detection/train_transaction.csv
```

---

## Reproducibility

| Thông số | Giá trị |
|---|---|
| Python | 3.13.2 |
| random_state | 42 |
| Split strategy | Chronological (không shuffle) |
| Train / Val / Test | 70% / 15% / 15% |
| Platform tested | Windows 11 (train/research), WSL Ubuntu (full pipeline) |

Kết quả mong đợi khi `python3 run_fraud_flow.py train` với toàn bộ dataset:
- `selected_threshold`: 0.50
- `val_auc`: ~0.9994, `val_f1`: ~0.9600
- `test_auc`: ~0.9984, `test_f1`: ~0.9931

**Lưu ý về Redis:**
- `train` và `research` dùng `FeatureStore` in-memory — không cần Redis.
- `simulate`, `stream`, `serve` cần Redis. Trên Ubuntu: cài `redis-server` bằng `sudo apt install -y redis-server`. Nếu dùng Redis ngoài, set `REDIS_URL=redis://localhost:6379`.

Chi tiết: xem [THRESHOLDS.md](THRESHOLDS.md) và [artifacts/reports/CLEAN_RUN_RESULTS.md](artifacts/reports/CLEAN_RUN_RESULTS.md).

## Tài liệu đi kèm

- Báo cáo mô hình: [docs/REPORT_MO_HINH_PAYSIM.md](docs/REPORT_MO_HINH_PAYSIM.md)
- Case study 3 giao dịch: [docs/CASE_STUDY_3_GIAO_DICH.md](docs/CASE_STUDY_3_GIAO_DICH.md)
- Bảng kết quả để đưa vào báo cáo: [docs/BANG_KET_QUA_BAO_CAO.md](docs/BANG_KET_QUA_BAO_CAO.md)
- Hướng dẫn chạy chi tiết: [HUONG_DAN_CHAY_MO_HINH.md](HUONG_DAN_CHAY_MO_HINH.md)

## File artifact quan trọng

- Kết quả train/eval: `artifacts/reports/evaluation_report.json`
- So sánh baseline: `artifacts/reports/baseline_comparison.json`
- Ablation feature: `artifacts/reports/feature_ablation.json`
- Ablation medium branch: `artifacts/reports/medium_branch_ablation.json`
- Tổng hợp research: `artifacts/reports/research_suite.json`
- Transfer learning IEEE-CIS: `artifacts/reports/transfer_learning_report.json`

## Cấu trúc thư mục chính

```text
fraud_flow/                mã nguồn pipeline
data/                      dữ liệu PaySim và IEEE-CIS
artifacts/models/          model, metadata, deploy state
artifacts/reports/         báo cáo thực nghiệm
artifacts/logs/            prediction log, review queue, feedback
docs/                      tài liệu viết lại cho báo cáo NCKH
```
