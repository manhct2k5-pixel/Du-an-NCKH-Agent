# FraudFlow — Phát hiện gian lận giao dịch

Cập nhật cấu trúc: 2026-11-09. Xem [mục lục tài liệu](docs/README.md), [kết quả B14 đã đối chiếu](docs/reviews/B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md) và [nhật ký dọn dự án](docs/CLEANUP.md).

LLM runtime mặc định là **heuristic local**. Để dùng **DeepSeek hoặc OpenAI qua API**, điền key vào `.env` rồi chạy `.venv/bin/python run_fraud_flow.py llm-check` và `.venv/bin/python run_fraud_flow.py serve --llm-api`. SDK tùy chọn nằm trong `requirements-openai.txt`. Trang Giao dịch và `/llm/status` tách cấu hình API với phản hồi thành công. Xem [giải thích và cấu hình LLM](docs/LLM_RUNTIME.md).

Mô hình hiện tại đã được chỉnh lại theo hướng phù hợp hơn với đề tài Nghiên cứu Khoa học: `PaySim-first`, dùng `XGBoost` làm mô hình triển khai chính, có lớp phân tích kiểu LLM để tạo đặc trưng, và có nhánh `ReAct Agent` chỉ chạy cho giao dịch mức rủi ro trung bình. PaySim được dùng để chứng minh hiệu năng của kiến trúc, còn IEEE-CIS được dùng làm external validation: XGBoost PaySim được đóng băng, IEEE-CIS được align sang 25 PaySim features rồi chỉ dùng để dự đoán và tính metric cuối. Kết quả frozen-model hiện tại cho thấy domain shift mạnh, nên không diễn giải quá mức là model PaySim tổng quát hóa trực tiếp sang IEEE-CIS.

DeepSeek Web qua DS2API đã được thử với giao dịch medium thực tế. Xem [cách chạy và bằng chứng](docs/DS2API_SETUP.md).

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

- Luồng chính dùng `PaySim`. Dữ liệu IEEE-CIS đã cất trong `archive/data/ieee-fraud-detection/`; chỉ chạy external validation khi truyền đường dẫn này rõ ràng.
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
- Số liệu trên là **clean run** không có label leakage. Xem [báo cáo leakage lịch sử](archive/artifacts/reports/CLEAN_RUN_RESULTS.md) để đối chiếu.
- Kết quả so sánh các baseline, gồm HistGradientBoosting, được cất tại `archive/artifacts/reports/baseline_comparison.json`. Đây là kết quả nghiên cứu; model triển khai là XGBoost.
- `XGBoost` vẫn được giữ làm mô hình deploy chính để bám đúng kiến trúc đề tài và thuận tiện cho lớp giải thích theo SHAP.
- Active version hiện tại: `v20260424T074126106494Z`; simulation 5,000 giao dịch sau adaptive threshold tạo `25` step-up (`0.50%`).
- B12 final trên IEEE-CIS: frozen PaySim AUC `0.626045`; transfer/adapted AUC `0.652533`; native IEEE-CIS (`no_target_encoding`) AUC `0.906399`. Nguồn: `artifacts/reports/b12_final/`. Các kết quả này cho thấy domain shift mạnh, chưa đủ để kết luận frozen PaySim model tổng quát hóa trực tiếp.
- B8 final: deterministic medium replay giảm số ca review từ `14,181` xuống `6,383` (giảm `54.99%`). Nguồn: `artifacts/reports/b8_final/medium_branch_ablation_b8.json`.
- B11 final: local end-to-end mean `14.19 ms`, p95 `28.14 ms`, p99 `46.47 ms`. Phép đo tuần tự, dùng FeatureStore in-memory, không tính Redis, network, external LLM/API, logging, tải dữ liệu/model hoặc training. Nguồn: `artifacts/reports/b11_final/b11_latency_components.json`.

Các báo cáo theo giai đoạn, kết quả baseline cũ, notebook và biểu đồ được cất trong [khu lưu trữ](archive/README.md) và `docs/archive/`. Khi viết báo cáo cuối, ưu tiên [B14](docs/reviews/B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md) và các artifact `b8_final/`–`b12_final/` thay cho số liệu lịch sử.

## Cài đặt và chạy

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip redis-server
# Chạy tại thư mục gốc dự án
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 run_fraud_flow.py train
# Kết quả xuất ra artifacts/reports/
```

> **Yêu cầu:** Python >= 3.11, dataset `data/paysim.csv`. IEEE-CIS được giữ riêng trong `archive/data/ieee-fraud-detection/`.

`bash run.sh` chạy training và benchmark latency. Research so sánh mô hình và xuất biểu đồ là tùy chọn: `RUN_RESEARCH=1 GENERATE_PLOTS=1 bash run.sh`. Biểu đồ sinh thêm được lưu vào `archive/artifacts/reports/plots/`.

---

## Chạy đầy đủ (WSL/Ubuntu — có online simulation)

```bash
# Chạy tại thư mục gốc dự án
source .venv/bin/activate
python3 run_fraud_flow.py train
python3 run_fraud_flow.py deploy --reason "Research-ready model"
python3 run_fraud_flow.py simulate --limit 100   # requires Redis (redislite)
python3 run_fraud_flow.py serve                  # requires Redis (redislite)
```

Thực nghiệm bổ sung khi cần đối chiếu baseline hoặc IEEE-CIS:

```bash
python3 run_fraud_flow.py research --source paysim
python3 run_fraud_flow.py research --source paysim --external-data-path archive/data/ieee-fraud-detection/train_transaction.csv
python3 run_fraud_flow.py adapt --ieee-data-path archive/data/ieee-fraud-detection/train_transaction.csv --adapt-fraction 0.10
```

---

## Reproducibility

| Thông số | Giá trị |
|---|---|
| Python của môi trường B13 final | 3.12.3 |
| random_state | 42 |
| Split strategy | Chronological (không shuffle) |
| Train / Val / Test | 70% / 15% / 15% |
| Platform của môi trường B13 final | Linux x86_64; XGBoost CPU, tree_method=hist, n_jobs=4 |

Kết quả mong đợi khi `python3 run_fraud_flow.py train` với toàn bộ dataset:
- `selected_threshold`: 0.50
- `val_auc`: ~0.9994, `val_f1`: ~0.9600
- `test_auc`: ~0.9984, `test_f1`: ~0.9931

**Lưu ý về Redis:**
- `train` và `research` dùng `FeatureStore` in-memory — không cần Redis.
- `simulate`, `stream`, `serve` cần Redis. Trên Ubuntu: cài `redis-server` bằng `sudo apt install -y redis-server`. Nếu dùng Redis ngoài, set `REDIS_URL=redis://localhost:6379`.

Chi tiết: xem [THRESHOLDS.md](THRESHOLDS.md) và [báo cáo leakage lịch sử](archive/artifacts/reports/CLEAN_RUN_RESULTS.md).

## Tài liệu đi kèm

- Báo cáo mô hình trước đây: [REPORT_MO_HINH_PAYSIM.md](docs/archive/stages/REPORT_MO_HINH_PAYSIM.md)
- Case study 3 giao dịch: [docs/CASE_STUDY_3_GIAO_DICH.md](docs/CASE_STUDY_3_GIAO_DICH.md)
- Bảng kết quả trước đây: [BANG_KET_QUA_BAO_CAO.md](docs/archive/stages/BANG_KET_QUA_BAO_CAO.md)
- Hướng dẫn chạy chi tiết: [HUONG_DAN_CHAY_MO_HINH.md](HUONG_DAN_CHAY_MO_HINH.md)
- Hướng dẫn API: [HUONG_DAN_THU_NGHIEM_API.md](HUONG_DAN_THU_NGHIEM_API.md)
- Dữ liệu bổ sung MFAN, giữ nguyên trích dẫn từng đợt chạy: [DU_LIEU_BO_SUNG_MFAN.md](DU_LIEU_BO_SUNG_MFAN.md)
- Hồ sơ review và phản hồi kỹ thuật: [docs/reviews/README.md](docs/reviews/README.md)
- Bản thảo và dữ liệu bàn giao lịch sử: [docs/archive/README.md](docs/archive/README.md)
- Dữ liệu IEEE, baseline cũ, notebook và biểu đồ: [archive/README.md](archive/README.md)

## File artifact quan trọng

- Kết quả train/eval: `artifacts/reports/evaluation_report.json`
- So sánh baseline B7: `archive/artifacts/reports/baseline_comparison.json`
- Ablation final: `artifacts/reports/b8_final/`
- Robustness và thống kê final: `artifacts/reports/b9_final/`, `artifacts/reports/b10_final/`
- Hiệu năng và IEEE-CIS final: `artifacts/reports/b11_final/`, `artifacts/reports/b12_final/`

## Cấu trúc thư mục chính

```text
fraud_flow/                mã nguồn pipeline
scripts/                   script benchmark và thực nghiệm B8–B12
tests/                     kiểm thử pipeline và deployment
data/                      dữ liệu PaySim đang dùng
artifacts/models/          model, metadata, deploy state
artifacts/reports/         báo cáo thực nghiệm
artifacts/logs/            prediction log, review queue, feedback
archive/                   dữ liệu IEEE, kết quả cũ, notebook và biểu đồ
docs/                      tài liệu báo cáo và mục lục
docs/reviews/              hồ sơ review riêng, B13/B14/B15
docs/archive/              bản thảo và dữ liệu bàn giao lịch sử
```
