# Hướng Dẫn Chạy Mô Hình Fraud Flow

Entry point chính:

```bash
python3 run_fraud_flow.py <command>
```

Mặc định hệ thống dùng `data/paysim.csv`. Các lệnh online (`simulate`, `stream`, `serve`) luôn bám theo `model active`, đọc `source`, `data_path`, `sample_size_used` từ metadata của model đang deploy.

Định hướng nghiên cứu hiện tại là **không chọn một trong hai** giữa dữ liệu mô phỏng và dữ liệu thực tế:

- **PaySim** là nguồn chính để làm rõ hiệu năng của kiến trúc 4 lớp: training, routing, agent, monitoring/deploy.
- **IEEE-CIS** là nguồn external validation để kiểm tra rủi ro học vẹt/domain shift của mô hình PaySim đã đóng băng.
- Khi chạy `research` với PaySim làm nguồn chính, hệ thống sẽ tự dùng IEEE-CIS làm external validation nếu tìm thấy `train_transaction.csv` và `train_identity.csv` trong `data/` hoặc `data/ieee-fraud-detection/`.
- Kết quả frozen-model hiện tại trên IEEE-CIS có AUC khoảng `0.6285`, thấp hơn rất xa PaySim; đây là bằng chứng domain shift mạnh, không được diễn giải là model PaySim tổng quát hóa trực tiếp sang IEEE-CIS.

---

## 1. Chuẩn bị môi trường

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip redis-server
cd "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection"
python3 -m venv --clear .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

---

## 2. Chạy từng bước khuyến nghị

Luôn bắt đầu bằng 2 lệnh này để terminal đứng đúng thư mục project và dùng đúng môi trường Python:

```bash
cd "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection"
source .venv/bin/activate
```

### Bước 1. Sinh báo cáo nghiên cứu PaySim + IEEE-CIS

Lệnh đầy đủ để dùng trong báo cáo NCKH:

```bash
python3 run_fraud_flow.py research --source paysim --external-data-path data/train_transaction.csv --seeds 42,43,44 --bootstrap-iterations 300
```

Nếu chỉ muốn kiểm tra nhanh trước khi chạy đầy đủ:

```bash
python3 run_fraud_flow.py research --source paysim --external-data-path data/train_transaction.csv --sample-size 20000 --seeds 42,43 --bootstrap-iterations 25
```

Kết quả cần xem:

- `docs/REPORT_MO_HINH_PAYSIM.md`
- `docs/BANG_KET_QUA_BAO_CAO.md`
- `artifacts/reports/research_suite.md`
- `artifacts/reports/baseline_comparison.md`
- `artifacts/reports/robustness_validation.md`
- `artifacts/reports/external_validation.md`

Ghi chú quan trọng về IEEE-CIS:

- `external_validation` hiện dùng chế độ `frozen_vs_native_benchmark`: vừa đánh giá frozen PaySim model trên IEEE-CIS, vừa báo cáo benchmark train lại trên IEEE-CIS để so sánh in-domain.
- XGBoost được huấn luyện trên PaySim trước, sau đó đóng băng weights và threshold.
- IEEE-CIS chỉ đi qua bước align sang 25 PaySim features rồi dùng để dự đoán/tính metric cuối.
- Nhãn IEEE-CIS không được dùng để train model, chọn threshold, hay cập nhật fraud-rate history trước khi dự đoán.
- Nếu kết quả frozen external AUC thấp hơn nhiều so với PaySim, đó là bằng chứng domain shift/schema shift, không phải lỗi chạy lệnh.

### Bước 2. Train model production trên PaySim

```bash
python3 run_fraud_flow.py train --source paysim
```

Lệnh này ghi model và metadata vào `artifacts/models/`, đồng thời tạo candidate để deploy.

### Bước 3. Transfer learning thử nghiệm trên IEEE-CIS

```bash
python3 run_fraud_flow.py adapt --ieee-data-path data/train_transaction.csv --adapt-fraction 0.10
```

Lệnh này dùng PaySim booster làm base model, align IEEE-CIS sang 25 PaySim features, train tiếp trên 10%
IEEE-CIS đầu tiên và đánh giá trên 90% còn lại. Kết quả hiện tại: AUC `0.6774`, PR-AUC `0.0826`,
F1 `0.1894`. Đây là cải thiện so với frozen PaySim AUC `0.6285`, nhưng vẫn thấp hơn IEEE-native benchmark
`0.8415`.

Artifact cần xem:

- `artifacts/reports/transfer_learning_report.json`
- `artifacts/models/xgboost_adapted_ieee.json`

### Bước 4. Deploy model vừa train

```bash
python3 run_fraud_flow.py deploy --reason "Full PaySim production model; IEEE-CIS frozen validation documents domain shift"
```

### Bước 5. Kiểm tra model active

```bash
python3 run_fraud_flow.py status
```

Nếu có `active_version` nghĩa là model đã được deploy thành công.

### Bước 6. Chạy mô phỏng giao dịch

```bash
python3 run_fraud_flow.py simulate --limit 5000
```

Lệnh này replay holdout transactions và tạo dữ liệu cho dashboard.

### Bước 7. Mở web demo

```bash
python3 run_fraud_flow.py serve
```

Khi chạy `serve`, terminal sẽ đứng yên để giữ server hoạt động. Muốn dừng web thì bấm `Ctrl + C`.

Mở trình duyệt:

| URL | Mục đích |
|-----|----------|
| `http://127.0.0.1:8000/` | Trang chủ |
| `http://127.0.0.1:8000/research` | Kết quả nghiên cứu |
| `http://127.0.0.1:8000/dashboard/html` | Dashboard |
| `http://127.0.0.1:8000/transaction/form` | Form nhập giao dịch thử |

### Block lệnh đầy đủ để copy chạy một lần

```bash
cd "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection"
source .venv/bin/activate
python3 run_fraud_flow.py research --source paysim --external-data-path data/train_transaction.csv --seeds 42,43,44 --bootstrap-iterations 300
python3 run_fraud_flow.py train --source paysim
python3 run_fraud_flow.py adapt --ieee-data-path data/train_transaction.csv --adapt-fraction 0.10
python3 run_fraud_flow.py deploy --reason "Full PaySim production model; IEEE-CIS frozen validation documents domain shift"
python3 run_fraud_flow.py status
python3 run_fraud_flow.py simulate --limit 5000
python3 run_fraud_flow.py serve
```

---

## 3. Chạy trên file dữ liệu khác

Hệ thống hỗ trợ hai nguồn: `paysim` và `ieee`. Dùng `--data-path` và `--source` để chỉ định file khác cho `train`, `retrain`, `research`.

**Quy tắc `--source`:** bắt buộc khi tên file không phải `paysim.csv` hoặc `train_transaction.csv`.

### PaySim format

File cần các cột: `step`, `type`, `amount`, `nameOrig`, `oldbalanceOrg`, `newbalanceOrig`, `nameDest`, `oldbalanceDest`, `newbalanceDest`, `isFraud`, `isFlaggedFraud`.

```bash
python3 run_fraud_flow.py train --data-path data/my_paysim_2024.csv --source paysim
```

### IEEE-CIS format

File transaction kèm file identity (tự tìm cùng thư mục theo tên `train_identity.csv`):

```bash
python3 run_fraud_flow.py train --data-path data/train_transaction.csv --source ieee
```

Nếu dữ liệu nằm trong thư mục Kaggle gốc:

```bash
python3 run_fraud_flow.py train --data-path data/ieee-fraud-detection/train_transaction.csv --source ieee
```

### Giới hạn số dòng để test nhanh

```bash
python3 run_fraud_flow.py train --data-path data/my_paysim_2024.csv --source paysim --sample-size 50000
```

Tương tự cho `retrain` và `research`:

```bash
python3 run_fraud_flow.py research --data-path data/my_paysim_2024.csv --source paysim
python3 run_fraud_flow.py retrain  --data-path data/my_paysim_2024.csv --source paysim
```

---

## 4. Các lệnh chi tiết

### train

```bash
python3 run_fraud_flow.py train                        # production, PaySim mặc định
python3 run_fraud_flow.py train --sample-size 6000     # thực nghiệm nhanh
python3 run_fraud_flow.py train --data-path data/train_transaction.csv --source ieee
```

- Production ghi vào `artifacts/models/` và `artifacts/reports/`.
- `--sample-size` ghi vào `artifacts/experiments/sample_<N>/`, **không** đăng ký candidate, không được promote tự động.

### research

```bash
python3 run_fraud_flow.py research
python3 run_fraud_flow.py research --sample-size 6000
python3 run_fraud_flow.py research --source paysim --external-data-path data/train_transaction.csv
python3 run_fraud_flow.py research --source paysim --external-data-path data/ieee-fraud-detection/train_transaction.csv

# Chạy kiểm tra độ ổn định (quan trọng cho NCKH)
# Báo cáo mean/std, confidence interval, và McNemar test
python3 run_fraud_flow.py research --seeds 42,43,44 --bootstrap-iterations 300
```

- Nếu nguồn chính là `paysim` và repo có đủ IEEE files, research tự chạy external validation trên IEEE theo kiểu frozen model.
- Kết quả PaySim nằm ở `baseline_comparison`, `feature_ablation`, `medium_branch_ablation`, `robustness_validation`.
- Kết quả IEEE-CIS nằm ở `external_validation.*`; đây là phần dùng để kiểm tra mô hình PaySim đã đóng băng trên dữ liệu ngoài phân bố mô phỏng.
- Kết quả hiện tại: frozen PaySim model trên IEEE-CIS đạt AUC khoảng `0.6285`, còn IEEE-native retrained benchmark đạt khoảng `0.8415`. Cần trình bày trung thực đây là domain shift/schema shift; benchmark IEEE-native chỉ chứng minh pipeline/kiến trúc học được trên dataset khác, không chứng minh cùng một frozen model tổng quát hóa.

### deploy / status / rollback

```bash
python3 run_fraud_flow.py deploy --reason "Full PaySim production model; IEEE-CIS frozen validation documents domain shift"
python3 run_fraud_flow.py status
python3 run_fraud_flow.py rollback --reason "Khôi phục model cũ"
```

### retrain

```bash
python3 run_fraud_flow.py retrain
python3 run_fraud_flow.py retrain --sample-size 6000
```

- Train lại và so sánh với `model active`. Auto-promote khi `new_test_auc >= previous_test_auc`.

### simulate

```bash
python3 run_fraud_flow.py simulate --limit 1000
python3 run_fraud_flow.py simulate --limit 5000
```

- Dùng `model active`, warm online feature store bằng lịch sử trước `val_end`, sau đó replay holdout.

### stream

```bash
python3 run_fraud_flow.py stream --batch-size 1000
python3 run_fraud_flow.py stream --batch-size 1000 --pause 1   # nghỉ 1 giây giữa batch
# Dừng: Ctrl + C
```

### serve

```bash
python3 run_fraud_flow.py serve
python3 run_fraud_flow.py serve --host 0.0.0.0 --port 8000
export FRAUD_FLOW_BOOTSTRAP_ROWS=10000 && python3 run_fraud_flow.py serve
```

URL quan trọng:

| URL | Mô tả |
|-----|-------|
| `http://127.0.0.1:8000/` | Trang chủ |
| `http://127.0.0.1:8000/dashboard/html` | Dashboard HTML |
| `http://127.0.0.1:8000/transaction/form` | Form nhập giao dịch thử |
| `http://127.0.0.1:8000/docs` | Docs portal |
| `http://127.0.0.1:8000/swagger-ui` | Swagger UI tương tác |
| `http://127.0.0.1:8000/health` | Health check |

Endpoint API chính: `POST /gateway/transaction`, `POST /gateway/transactions`, `POST /reviews/{tx_id}`.

### all

```bash
python3 run_fraud_flow.py all --limit 300
```

Train production → promote candidate → simulate trong một lệnh. `--sample-size` bị khóa.

---

## 5. Chạy web và quét dữ liệu cùng lúc

**Terminal 1:**
```bash
python3 run_fraud_flow.py serve
```

**Terminal 2:**
```bash
python3 run_fraud_flow.py simulate --limit 5000
# hoặc liên tục:
python3 run_fraud_flow.py stream --batch-size 1000
```

Sau đó refresh `http://127.0.0.1:8000/dashboard/html`.

---

## 6. Kiểm tra model active đang dùng

```bash
python3 run_fraud_flow.py status
```

Hoặc xem chi tiết metadata:

```bash
python3 - <<'PY'
import json
from pathlib import Path
state = json.loads(Path("artifacts/deployment/deployment_state.json").read_text(encoding="utf-8"))
meta  = json.loads(Path(state["active_metadata_path"]).read_text(encoding="utf-8"))
print("source            =", meta["source"])
print("data_path         =", meta["data_path"])
print("sample_size_used  =", meta["sample_size_used"])
print("selected_threshold=", meta["selected_threshold"])
print("routing_thresholds=", meta["routing_thresholds"])
PY
```

Routing online dùng `operational score` với ngưỡng mặc định: `low < 0.30`, `medium 0.30–0.85`, `high > 0.85`. Nếu vào vùng `high` nhưng `raw_probability < 0.05`, hệ thống chuyển sang `review`.

---

## 7. Lỗi hay gặp

| Lỗi | Nguyên nhân / Cách xử lý |
|-----|--------------------------|
| `python3: command not found` | Cài Python 3: `sudo apt install -y python3 python3-pip` |
| `ensurepip is not available` | Thiếu venv trên Ubuntu: chạy `sudo apt install -y python3-venv`, rồi tạo lại `.venv` |
| `ModuleNotFoundError` | Chưa activate venv hoặc chưa `pip install -r requirements.txt` |
| `No redis-server binary found` | Cài Redis: `sudo apt install -y redis-server`, hoặc set `REDIS_URL=redis://localhost:6379` |
| `Model metadata missing` / `Trained model missing` | Chưa train: chạy `python3 run_fraud_flow.py train` |
| `No candidate version available for promotion` | Chưa chạy `train` production (chỉ có sample) |
| `No rollback target is available` | Chưa có version trước |
| Dashboard không cập nhật | Chạy `simulate` hoặc `stream` rồi refresh trình duyệt |
| `POST /gateway/transaction` báo lỗi khi mở bằng browser | Endpoint chỉ nhận POST — test qua `/swagger-ui` hoặc `curl` |
