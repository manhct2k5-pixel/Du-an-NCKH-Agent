# B9 – Robustness: File Index

Gói này chỉ chứa artifact và source code phục vụ audit tĩnh. Không có dataset, model, virtual environment, cache, `.git` hay log. Các file copy được giữ theo cấu trúc gốc và đã được kiểm tra byte-identical với nguồn tại thời điểm đóng gói.

| File gốc | Vai trò | Dùng để kiểm tra gì |
| --- | --- | --- |
| `artifacts/reports/robustness_validation.json` | Artifact robustness chính, giữ precision đầy đủ | Per-seed runs, summary mean/std/min/max, bootstrap CI, McNemar, baseline được chọn |
| `artifacts/reports/robustness_validation.csv` | Bảng summary theo model | Đối chiếu repeated-seed mean/std với JSON; không chứa per-seed rows |
| `artifacts/reports/robustness_validation.md` | Bản trình bày robustness | Kiểm tra cách diễn giải seed stability, bootstrap CI và McNemar |
| `artifacts/reports/research_suite.json` | Artifact suite tổng hợp | Xác minh `robustness` được nhúng nguyên vẹn; bổ sung source, split strategy và row counts thiếu trong robustness JSON |
| `artifacts/reports/research_suite.md` | Summary của suite | Kiểm tra claim robustness đang được trình bày như thế nào |
| `artifacts/reports/validation_threshold_sweep.csv` | Validation threshold sweep | Grid 0.20–0.70; precision, recall, F1 và confusion counts trên validation set |
| `artifacts/reports/evaluation_report.json` | Artifact evaluation model chính | Selected threshold 0.50, selected params, split counts và xác nhận threshold sweep là validation artifact |
| `fraud_flow/research.py` | Logic robustness chính | `summarize_seed_runs`, `bootstrap_confidence_intervals`, `mcnemar_error_test`, `run_robustness_validation`, test-set baseline selection |
| `fraud_flow/training.py` | Split, metric và threshold logic | `split_indices`, `classification_metrics`, `threshold_sweep_frame`, `find_best_threshold`, `build_dataset` và leakage control |
| `fraud_flow/config.py` | Cấu hình experiment | Seeds `(42, 43, 44)`, bootstrap iterations `300`, split 70/15/15, threshold grid và XGBoost candidate grid |
| `fraud_flow/features.py` | Load/sort và feature construction | Filter PaySim `TRANSFER` + `CASH_OUT`, sort theo `step`, không shuffle; `freeze_risk_labels` cho eval rows |
| `fraud_flow/feature_store.py` | Historical activity/risk state | Phân biệt `observe_activity` với `observe_feedback`; audit validation/test label leakage |
| `fraud_flow/calibration.py` | Routing calibration dependency | Không phải repeated-seed metric chính, nhưng là file code được yêu cầu thu thập |
| `run_fraud_flow.py` | CLI duy nhất gọi robustness gián tiếp | Lệnh `research` gọi toàn `run_research_suite`; repo không có entry point production chỉ chạy robustness |
| `tests/test_research_statistics.py` | Unit tests hiện có cho statistical helpers | Kiểm tra bootstrap bounds, single-class behavior và McNemar neutral case; không test repeated-seed protocol end-to-end |

## Bản đồ logic bắt buộc

- Repeated-seed logic: `fraud_flow/research.py::run_robustness_validation`; seed defaults từ `fraud_flow/config.py::ResearchConfig.repeated_seed_values`.
- Threshold selection: `fraud_flow/training.py::find_best_threshold`.
- Threshold sweep: `fraud_flow/training.py::threshold_sweep_frame`; được ghi bởi `train_model` vào `validation_threshold_sweep.csv`.
- Bootstrap CI: `fraud_flow/research.py::bootstrap_confidence_intervals`.
- McNemar: `fraud_flow/research.py::mcnemar_error_test`.
- Baseline selection: `fraud_flow/research.py::run_robustness_validation`, biến `best_baseline_artifact`.
- Dataset/split protocol: `fraud_flow/features.py::load_filtered_frame`, `fraud_flow/training.py::build_dataset`, `split_indices`, và `fraud_flow/research.py::prepare_experiment_splits`.

## Script chạy robustness

Không tìm thấy script standalone chỉ chạy robustness. `run_fraud_flow.py research` chạy cả baseline, feature ablation, medium branch, robustness và external validation; do đó **không được chạy trong audit này**.
