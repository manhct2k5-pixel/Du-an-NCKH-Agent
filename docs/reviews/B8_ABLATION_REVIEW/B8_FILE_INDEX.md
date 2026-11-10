# B8 – Ablation Study: File Index

Phạm vi gói này chỉ gồm artifact và source code phục vụ audit. Cấu trúc thư mục gốc được giữ lại để có thể truy vết. Các file đã copy được kiểm tra SHA-256 và byte-identical với file gốc tại thời điểm đóng gói.

| File gốc | Vai trò | Dùng để kiểm tra gì |
| -------- | ------- | ------------------- |
| `artifacts/reports/feature_ablation.json` | Artifact gốc của feature ablation, giữ precision đầy đủ | Feature list/count, threshold, validation/test metrics, delta so với full |
| `artifacts/reports/feature_ablation.csv` | Bảng phẳng của feature ablation | Đối chiếu các trường số với JSON |
| `artifacts/reports/feature_ablation.md` | Bản trình bày của feature ablation | Kiểm tra cách trình bày; lưu ý file này hiển thị số đã format 4 chữ số thập phân |
| `artifacts/reports/medium_branch_ablation.json` | Artifact gốc của medium-branch ablation, giữ precision đầy đủ | Policy, action counts/rates, block metrics, review metrics, routing calibration |
| `artifacts/reports/medium_branch_ablation.csv` | Bảng phẳng của medium-branch ablation | Đối chiếu các trường số với JSON |
| `artifacts/reports/medium_branch_ablation.md` | Bản trình bày của medium-branch ablation | Kiểm tra cách diễn giải và bảng policy; số hiển thị đã format 4 chữ số thập phân |
| `artifacts/reports/research_suite.json` | Artifact tổng hợp | Nơi tạo/nhúng nguyên `feature_ablation` và `medium_branch`; xác nhận dataset size, split, seed và artifact paths |
| `artifacts/reports/research_suite.md` | Báo cáo tóm tắt suite | Kiểm tra cách chọn/diễn giải “best” configuration và policy |
| `run_fraud_flow.py` | CLI thực sự gọi research suite | Xác nhận lệnh `research` gọi `run_research_suite(...)` |
| `run_phase5_ablation.py` | Script Phase 5/anomaly ablation được yêu cầu copy nếu tồn tại | Chứng minh script này **không** tạo hai artifact B8; nó tạo `phase5_ablation.*` cho anomaly sidecar |
| `fraud_flow/research.py` | Logic B8 chính | Định nghĩa feature group/ablation set; chạy XGBoost cho từng ablation; medium policies; metric policy; ghi các artifact và `research_suite.json` |
| `fraud_flow/training.py` | Dataset protocol và metric classifier | Chronological split, leakage control, `classification_metrics`, PR-AUC, chọn threshold trên validation |
| `fraud_flow/config.py` | Cấu hình thực nghiệm và schema feature | 25 PaySim features, seed 42, tỷ lệ split 70/15/15, XGBoost candidates, threshold grid, output paths |
| `fraud_flow/features.py` | Xây dựng feature thực tế | Cách tạo transaction/context/online/`llm_*` features và cơ chế `freeze_risk_labels` |
| `fraud_flow/feature_store.py` | State và historical risk lookup | Cách tính velocity, fraud-rate, `observe_activity` so với `observe_feedback`; audit label leakage |
| `fraud_flow/calibration.py` | Calibration/routing cho medium branch | Biến classifier probability thành operational score và route low/medium/high cố định |
| `fraud_flow/llm_features.py` | Logic sinh 5 feature mang tên `llm_*` | Xác nhận đây là heuristic xác định và truy vết các phụ thuộc vào online/context signal |
| `fraud_flow/langchain_models.py` | Logic `build_decision_payload` mà offline replay gọi trực tiếp | Xác nhận medium replay là heuristic decision payload, không phải một lần chạy ReAct agent |
| `fraud_flow/agent.py` | Implementation ReAct runtime thực | So sánh ReAct runtime với replay trong `research.py`; xác định không được gán kết quả replay cho ReAct |
| `fraud_flow/schema.py` | Schema event, lookup, prediction và agent decision | Kiểm tra payload/action mà medium replay thao tác |
| `fraud_flow/narratives.py` | Dependency của decision payload | Xác nhận phần narrative không thay classifier probability |

## Bản đồ logic bắt buộc

- Feature ablation: artifact trong `feature_ablation.*`; group và vòng train nằm trong `fraud_flow/research.py` (`paysim_feature_groups`, `feature_ablation_sets`, `run_feature_ablation`, `fit_best_xgboost`).
- Medium-branch ablation: artifact trong `medium_branch_ablation.*`; policy/replay/metric nằm trong `fraud_flow/research.py` (`replay_medium_agent`, `action_policy_report`, `run_medium_branch_ablation`).
- XGBoost cho từng feature ablation: `fraud_flow/research.py::fit_best_xgboost`, được gọi bởi `run_feature_ablation` với cùng fixed params.
- Classifier metrics và threshold: `fraud_flow/training.py::classification_metrics`, `find_best_threshold`; PR-AUC được tính trong `fraud_flow/research.py::summarize_model_run`.
- Operational metrics: `fraud_flow/research.py::action_policy_report`.
- `research_suite.json`: được lắp và ghi bởi `fraud_flow/research.py::run_research_suite`; CLI entry point là `run_fraud_flow.py`.

## Không đóng gói

Không có dataset, model, virtual environment, cache, `.git`, log, manuscript hay file ngoài phạm vi audit B8 trong gói này.
