# B2 Preprocessing & Data-Leakage Review — File Index

Thư mục này là bản sao phục vụ audit. Các đường dẫn trong cột **File gốc** tính từ root repository; cấu trúc thư mục con được giữ nguyên. Không có CSV dữ liệu, model, cache, `.git`, `.venv`, `node_modules` hay log dung lượng lớn nào được sao chép.

> Lưu ý phạm vi: `notebooks/B2.ipynb` là notebook thử nghiệm/legacy có random `train_test_split`; pipeline production đi qua `run_fraud_flow.py` và `fraud_flow/training.py`. `scripts/ieee_cis_optimized_benchmark.py` là benchmark IEEE-CIS riêng (schema nhiều hơn 25 feature), được giữ lại để reviewer không nhầm nó với model PaySim 25 feature.

| File gốc | Vai trò | Vì sao cần kiểm tra |
|---|---|---|
| `run_fraud_flow.py` | CLI entrypoint cho train, research, adapt, simulate và retrain | Xác định pipeline thực tế được gọi, tham số data/source/sample và luồng tạo report. |
| `run_phase5_ablation.py` | Thử nghiệm ablation/anomaly dùng lại dataset và split chính | Kiểm tra nhánh đánh giá bổ sung có giữ split thời gian, feature schema và ngưỡng validation hay không. |
| `run.sh` | Script tái lập train/research/benchmark | Cho biết lệnh production, seed môi trường và artifact nào được sinh ra. |
| `fraud_flow/config.py` | Cấu hình trung tâm | Chứa danh sách 25 `PAYSIM_FEATURE_COLUMNS`, encoding loại giao dịch, tỷ lệ 70/15/15, `random_state=42` và path `evaluation_report.json`. |
| `fraud_flow/features.py` | Load, filter, sort, sampling, enrich và tạo feature | File lõi để audit `TRANSFER`/`CASH_OUT`, sort `step`, không shuffle, NaN/Inf, log1p, encoding/hash, balance feature, IEEE alignment và `freeze_risk_labels`. |
| `fraud_flow/feature_store.py` | Historical/rolling state in-memory và Redis | Chứa cửa sổ 24h/7d, entity fraud-rate, `lookup`, `observe_activity`, `observe_feedback`, `warm_start`; quyết định feature t chỉ thấy state trước t hay không. |
| `fraud_flow/llm_features.py` | Tạo 5 feature phân tích deterministic kiểu LLM | Hoàn tất schema 25 feature và dùng historical/context lookup, nên cần kiểm tra phụ thuộc nhãn gián tiếp. |
| `fraud_flow/schema.py` | Kiểu dữ liệu transaction, lookup và prediction | Xác nhận field label tùy chọn, `step`, entity IDs và ranh giới giữa event/feature/output. |
| `fraud_flow/training.py` | Pipeline train/evaluation production | File lõi cho split-before-feature, train/validation/test slicing, class balance, threshold tuning, anomaly sidecar và ghi `evaluation_report.json`. |
| `fraud_flow/anomaly.py` | Preprocessing và đánh giá IsolationForest sidecar | Kiểm tra feature con, `fillna(0)`, chỉ train trên legitimate train rows và ngưỡng P95 lấy từ validation. |
| `fraud_flow/calibration.py` | Calibration operational score từ validation | Kiểm tra validation data được dùng ở đâu và có lan sang huấn luyện/test không. |
| `fraud_flow/pipeline.py` | Runtime/simulation pipeline | Chứa thứ tự lookup → feature → predict → activity update → feedback, warm-start history và phạm vi holdout. |
| `fraud_flow/service.py` | API gateway và manual-feedback endpoint | Cần audit nhánh medium, batch, thời điểm `observe_activity` và chỉ update label sau review/feedback. |
| `fraud_flow/agent.py` | Các tool đọc card/device/merchant/IP history | Cho thấy context aggregation nào được đưa vào quyết định online, dù không trực tiếp tạo 25 feature model. |
| `fraud_flow/research.py` | Baseline, ablation, robustness và external-validation pipeline | Kiểm tra việc tái sử dụng split production, history trong medium-agent replay, frozen IEEE features và cam kết label chỉ dùng sau prediction. |
| `scripts/compute_leakage_comparison.py` | Tái hiện pipeline leaky và pipeline fixed | Bằng chứng trực tiếp về bug cũ, split-before-feature và `freeze_risk_labels=True`. |
| `scripts/benchmark_latency.py` | Replay online feature lookup/prediction | Kiểm tra thứ tự `lookup`/`observe_activity` trong benchmark runtime có nhất quán với production. |
| `scripts/ieee_cis_optimized_benchmark.py` | Pipeline benchmark IEEE-CIS tối ưu, độc lập | Chứa preprocessing, missingness, encoding train-only và split thời gian riêng; cần tách bạch khỏi schema PaySim 25 feature khi audit. |
| `notebooks/B2.ipynb` | Notebook B2 thử nghiệm/legacy | Có filter hai loại và feature balance nhưng dùng random stratified `train_test_split`; cần reviewer ghi nhận nó không phải production pipeline. |
| `tests/test_research_statistics.py` | Test cho external path, quantile projection và alignment 25 feature | Xác nhận schema đầu ra, thang tham chiếu và không còn NaN trong aligned external features. |
| `README.md` | Tài liệu pipeline chính | Ghi tuyên bố filter, chronological/no-shuffle, split counts, 25 features và clean-run sau fix để đối chiếu code. |
| `CHECKLIST_CHUNG_MINH_4_LOP_NCKH.md` | Checklist bằng chứng dự án | Chỉ ra file split, report, seed và các artifact mà tài liệu dự án coi là bằng chứng. |
| `BAO_CAO_NCKH_PHAN_CAI_TIEN.md` | Báo cáo kiến trúc/cải tiến | Mô tả schema 25 feature, split thời gian và chính sách frozen external labels; dùng đối chiếu implementation. |
| `HUONG_DAN_CHAY_MO_HINH.md` | Hướng dẫn chạy train/research/external validation | Xác định protocol mong đợi và tuyên bố IEEE labels không update history trước prediction. |
| `docs/experiments_setup.md` | Thiết kế thực nghiệm và chi tiết leakage fix | Mô tả bug cũ, fix hiện tại, deterministic sampling, no-shuffle và holdout protocol. |
| `docs/methodology_draft.md` | Mô tả phương pháp/feature theo công thức | Dùng kiểm tra ý định past-only rolling/risk rate và so sánh với code. |
| `docs/REPORT_MO_HINH_PAYSIM.md` | Báo cáo model PaySim/IEEE | Tóm tắt filter, split, 25 feature, external-label policy và các số liệu artifact. |
| `docs/report_content.md` | Nội dung chuyên về leakage fix | Ghi rõ before/after, distribution shift, file script/report và các hạn chế FeatureStore. |
| `data/README.md` | Mô tả vị trí dataset | Giúp reviewer biết input mong đợi mà không cần copy CSV lớn. |
| `requirements.txt` | Phụ thuộc trực tiếp | Cần để hiểu/khôi phục đúng behavior pandas, sklearn, XGBoost và Redis. |
| `requirements_locked.txt` | Môi trường khóa phiên bản | Hỗ trợ tái lập chính xác các phép preprocess/train/evaluate. |
| `artifacts/models/model_metadata.json` | Metadata model production | Chứa feature list thực tế, split counts/end indices, class balance, threshold và train profile để đối chiếu code. |
| `artifacts/reports/evaluation_report.json` | Kết quả machine-readable của train/evaluation | Bằng chứng thực tế về source, 25 feature, chronological split, seed, validation/test metrics và anomaly calibration. |
| `artifacts/reports/evaluation_report.md` | Bản đọc của evaluation report | Cho phép reviewer đối chiếu nhanh split, metrics và artifact paths với JSON. |
| `artifacts/reports/leakage_comparison.json` | Kết quả before/after leakage fix | Cho thấy metric của leaky pipeline và fixed pipeline trên cùng dữ liệu. |
| `artifacts/reports/external_validation.json` | Kết quả frozen PaySim vs IEEE-native | Chứa protocol external all-rows, alignment 25 feature và khai báo cách dùng IEEE labels. |
| `artifacts/reports/external_validation.md` | Bản đọc external validation | Hỗ trợ audit cách diễn giải frozen evaluation và split native benchmark. |
| `artifacts/reports/feature_ablation.json` | Kết quả ablation theo nhóm feature | Giúp xác định nhóm online behavior/contextual aggregates/LLM nào thực sự được đánh giá. |
| `artifacts/reports/feature_ablation.md` | Bản đọc feature ablation | Cho phép kiểm tra nhanh vai trò các nhóm feature mà không cần chạy lại. |
| `artifacts/reports/CLEAN_RUN_RESULTS.md` | Snapshot clean-run sau fix | Tổng hợp kết quả production/research để phát hiện chênh lệch giữa tài liệu và artifact gốc. |

## File quan trọng nhất cho leakage review

1. `fraud_flow/features.py`
2. `fraud_flow/feature_store.py`
3. `fraud_flow/training.py`
4. `fraud_flow/pipeline.py`
5. `fraud_flow/service.py`
6. `fraud_flow/research.py`
7. `scripts/compute_leakage_comparison.py`
8. `notebooks/B2.ipynb` (legacy/random-split contrast)

## Mapping nhanh

- Chia train/validation/test: `fraud_flow/training.py`; research dùng lại qua `fraud_flow/research.py`; benchmark IEEE riêng nằm trong `scripts/ieee_cis_optimized_benchmark.py`.
- Historical features: `fraud_flow/feature_store.py`, được orchestration bởi `fraud_flow/features.py`.
- Runtime state update sau prediction/feedback: `fraud_flow/pipeline.py` và `fraud_flow/service.py`.
- Tạo `evaluation_report.json`: `fraud_flow/training.py` (entrypoint: `run_fraud_flow.py train`).
