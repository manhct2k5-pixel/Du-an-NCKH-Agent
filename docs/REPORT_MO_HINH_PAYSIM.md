# Báo cáo mô hình Fraud Flow - PaySim + IEEE-CIS

**Ngày cập nhật tài liệu:** 2026-04-20  
**Số liệu artifact sử dụng:** train/simulation/transfer adaptive run ngày 2026-04-20; research suite clean run ngày 2026-04-17  
**Model active:** `v20260420T053341630222Z`  
**Nguồn chính:** PaySim  
**External validation:** IEEE-CIS theo chế độ frozen-vs-native benchmark

Tài liệu này tóm tắt mô hình đang triển khai trong dự án Fraud Flow. Nội dung có thể đưa trực tiếp vào phần mô hình, thực nghiệm và thảo luận kết quả trong báo cáo NCKH.

---

## 1. Tóm tắt mô hình hiện tại

| Hạng mục | Giá trị |
|---|---|
| Backbone triển khai | XGBoost |
| Dataset huấn luyện chính | PaySim, sau khi lọc `TRANSFER` và `CASH_OUT` |
| Số dòng dùng cho production | 460,394 giao dịch |
| Chia dữ liệu | Chronological split theo `step`, không shuffle |
| Train / Validation / Test | 322,275 / 69,059 / 69,060 |
| Số feature đầu vào | 25 |
| Classification threshold | 0.50 |
| Routing low / high | 0.30 / 0.85 trên operational score |
| Anomaly sidecar | IsolationForest, ngưỡng adaptive P95 validation = 0.418285 |
| Active version | `v20260420T053341630222Z` |
| Rollback version | `v20260417T101732307255Z` |

Mục tiêu của hệ thống không chỉ là đạt metric offline cao, mà còn chứng minh kiến trúc 4 lớp: huấn luyện offline, xử lý giao dịch online, agent hỗ trợ quyết định vùng medium, và lớp monitoring/deploy.

---

## 2. Chiến lược dữ liệu

Nghiên cứu sử dụng chiến lược **PaySim-first**:

| Dataset | Vai trò | Cách diễn giải |
|---|---|---|
| PaySim | Dataset chính để train, test, chạy routing, agent, simulation và monitoring | Chứng minh hiệu năng kiến trúc trong miền mô phỏng có timeline rõ ràng |
| IEEE-CIS | External validation ngoài phân bố | Kiểm tra rủi ro học vẹt/domain shift của frozen PaySim model |

Điểm quan trọng: IEEE-CIS không được dùng để train lại frozen PaySim model, chọn threshold hoặc cập nhật fraud-rate history trước khi dự đoán. Dữ liệu IEEE-CIS được align sang 25 feature PaySim rồi chỉ dùng để tính metric cuối.

---

## 3. Kiến trúc 4 lớp

### 3.1 Lớp huấn luyện offline

- Đọc dữ liệu PaySim từ `data/paysim.csv`.
- Chỉ giữ hai loại giao dịch phù hợp với bài toán gian lận: `TRANSFER` và `CASH_OUT`.
- Sinh 25 feature gồm feature giao dịch, feature hành vi online, feature rủi ro theo thực thể và feature phân tích kiểu LLM.
- Train XGBoost với split theo thời gian.
- Lưu model, metadata và báo cáo vào `artifacts/models/` và `artifacts/reports/`.

### 3.2 Lớp xử lý giao dịch online

- Nhận giao dịch mới qua simulation/API.
- Lookup feature online qua feature store.
- Tính raw probability và operational score.
- Sinh SHAP explanation.
- Route giao dịch theo 3 vùng:

| Vùng | Điều kiện | Xử lý |
|---|---|---|
| Low | `score < 0.30` | Auto approve |
| Medium | `0.30 <= score <= 0.85` | Gọi ReAct Agent |
| High | `score > 0.85` | Auto block, trừ trường hợp raw probability quá thấp thì chuyển review |

### 3.3 Lớp agent và explainability

Nhánh medium dùng ReAct Agent để tra cứu tín hiệu bổ sung, tạo `reason_codes`, evidence và narrative. Agent hiện chạy đồng bộ trong pipeline, vì vậy báo cáo cần trình bày agent như lớp hỗ trợ vận hành/audit cho vùng rủi ro trung gian, không phải là bằng chứng tăng accuracy so với XGBoost.

Hệ thống xuất giải thích ở 3 cấp:

| Cấp giải thích | Mục tiêu |
|---|---|
| `human_readable_explanation` | Diễn giải dễ hiểu cho người dùng cuối |
| `analyst_report` | Chi tiết kỹ thuật cho analyst/audit |
| `dashboard_summary` | Tóm tắt ngắn cho dashboard |

### 3.4 Lớp monitoring, feedback và deploy

- Ghi prediction log, feedback log, drift alert và manual review queue.
- Có deployment state, deployment history, candidate version, active version và rollback version.
- Dashboard snapshot hiện có 5,000 giao dịch simulation để kiểm tra route/action, latency và drift flag.

---

## 4. Cấu hình huấn luyện XGBoost

| Tham số | Giá trị |
|---|---:|
| `n_estimators` | 260 |
| `max_depth` | 6 |
| `learning_rate` | 0.06 |
| `subsample` | 0.90 |
| `colsample_bytree` | 0.85 |
| `max_delta_step` | 1 |
| `scale_pos_weight` | 750.2238 |
| `random_state` | 42 |
| `anomaly_flag_threshold` | 0.418285, học từ P95 anomaly score trên validation |

Class imbalance trên train split:

| Nhóm | Số lượng |
|---|---:|
| Fraud | 429 |
| Legitimate | 321,846 |

---

## 5. Kết quả XGBoost trên PaySim

Nguồn: `artifacts/reports/evaluation_report.json`.

| Tập đánh giá | AUC | PR-AUC | F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Validation | 0.999413 | 0.961260 | 0.960000 | 0.967742 | 0.952381 |
| Test | 0.998383 | 0.997002 | 0.993103 | 0.989313 | 0.996923 |

Confusion matrix trên test set:

| | Dự đoán hợp lệ | Dự đoán gian lận |
|---|---:|---:|
| Thực tế hợp lệ | 68,403 | 7 |
| Thực tế gian lận | 2 | 648 |

Diễn giải: mô hình đạt recall rất cao trên PaySim holdout test, chỉ bỏ sót 2/650 fraud trong test set. Tuy nhiên PaySim là dữ liệu mô phỏng, nên kết quả cao cần đi kèm external validation để tránh kết luận quá mức.

---

## 6. So sánh baseline

Nguồn: `artifacts/reports/baseline_comparison.json`.

| Model | Test AUC | Test PR-AUC | Test F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| HistGradientBoosting | 0.999932 | 0.997849 | 0.996914 | 1.000000 | 0.993846 |
| RandomForest | 0.999843 | 0.997502 | 0.995378 | 0.996914 | 0.993846 |
| XGBoost deploy | 0.998383 | 0.997002 | 0.993103 | 0.989313 | 0.996923 |
| Logistic Regression | 0.996364 | 0.884412 | 0.485748 | 0.325521 | 0.956923 |
| Dummy prior | 0.500000 | 0.009412 | 0.000000 | 0.000000 | 0.000000 |

HistGradientBoosting là baseline offline mạnh nhất, nhưng XGBoost vẫn được chọn làm backbone triển khai vì pipeline hiện tại đã tích hợp tốt với SHAP explanation, versioning và routing.

---

## 7. Feature ablation

Nguồn: `artifacts/reports/feature_ablation.json`.

| Cấu hình | Số feature | Test AUC | Test PR-AUC | Test F1 | Delta F1 |
|---|---:|---:|---:|---:|---:|
| Full feature set | 25 | 0.998383 | 0.997002 | 0.993103 | 0.000000 |
| No online behavior | 17 | 0.998409 | 0.996741 | 0.989992 | -0.003111 |
| No LLM-style analysis | 20 | 0.998647 | 0.995205 | 0.970432 | -0.022671 |
| No contextual aggregates | 19 | 0.996902 | 0.920048 | 0.853081 | -0.140023 |
| Transaction core only | 6 | 0.997233 | 0.929678 | 0.811798 | -0.181306 |

Kết quả cho thấy các nhóm feature ngữ cảnh, aggregate và LLM-style có đóng góp rõ rệt cho F1, đặc biệt khi so với cấu hình chỉ giữ transaction core.

---

## 8. Robustness validation

Nguồn: `artifacts/reports/robustness_validation.json`.

| Model | Seeds | Test AUC mean ± std | Test F1 mean ± std | Precision mean ± std | Recall mean ± std |
|---|---|---:|---:|---:|---:|
| HistGradientBoosting | 42,43,44 | 0.999928 ± 0.000031 | 0.996912 ± 0.001264 | 1.000000 ± 0.000000 | 0.993846 ± 0.002512 |
| XGBoost | 42,43,44 | 0.998649 ± 0.000189 | 0.992077 ± 0.000958 | 0.988792 ± 0.000725 | 0.995385 ± 0.001256 |

Bootstrap 95% CI cho XGBoost:

| Metric | 95% CI |
|---|---|
| AUC | 0.995236 đến 1.000000 |
| F1 | 0.989130 đến 0.996811 |
| Precision | 0.982163 đến 0.995663 |
| Recall | 0.992870 đến 1.000000 |

McNemar p-value giữa XGBoost và HistGradientBoosting là `0.182422`, chưa đủ bằng chứng thống kê để kết luận hai model khác biệt có ý nghĩa ở mức 0.05 trên lỗi phân loại test.

---

## 9. External validation trên IEEE-CIS

Nguồn: `artifacts/reports/external_validation.json`.

| Model | Mode | Test AUC | PR-AUC | F1 | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|
| XGBoost train lại trên IEEE-CIS | Native, 42 IEEE features | 0.841506 | 0.326239 | 0.332844 | 0.255282 | 0.478106 |
| Frozen PaySim XGBoost | Frozen, 25 PaySim features aligned | 0.628517 | 0.053153 | 0.020140 | 0.063907 | 0.011954 |

Diễn giải đúng:

- IEEE-native benchmark đạt AUC 0.8415, cho thấy pipeline học được tín hiệu fraud khi được train trong đúng miền IEEE-CIS.
- Frozen PaySim model chỉ đạt AUC 0.6285 trên IEEE-CIS. Kết quả này tốt hơn đoán mò về ranking nhưng thấp hơn rất xa PaySim.
- Chênh lệch này là bằng chứng domain shift/schema shift mạnh giữa PaySim và IEEE-CIS, không phải lỗi chạy lệnh.
- Không nên viết rằng frozen PaySim model đã tổng quát hóa tốt sang IEEE-CIS.

---

## 10. Transfer learning trên IEEE-CIS

Nguồn: `artifacts/reports/transfer_learning_report.json`.

| Model | Protocol | Feature schema | Test rows | AUC | PR-AUC | F1 | Precision | Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Frozen PaySim XGBoost | Không adapt, đánh giá trực tiếp IEEE-CIS | 25 PaySim-aligned features | 590,540 | 0.628517 | 0.053153 | 0.020140 | 0.063907 | 0.011954 |
| Transfer-adapted XGBoost | Adapt 10% IEEE-CIS, test 90% còn lại | 25 PaySim-aligned features | 531,486 | 0.677369 | 0.082577 | 0.189437 | 0.124906 | 0.391919 |
| IEEE-native XGBoost | Train lại trong miền IEEE-CIS | 42 IEEE-native features | 88,581 | 0.841506 | 0.326239 | 0.332844 | 0.255282 | 0.478106 |

Transfer learning dùng `xgb.train(..., xgb_model=paysim_booster)` để thêm cây mới trên nền booster PaySim.
Trước khi adapt, IEEE-CIS được align sang đúng 25 PaySim features bằng method
`semantic_proxy_with_mfield_balance_diff`; điều này tránh lỗi schema mismatch giữa PaySim model 25 feature
và IEEE-native 42 feature. Kết quả cho thấy transfer learning cải thiện rõ so với frozen model
(AUC tăng từ 0.6285 lên 0.6774), nhưng vẫn thấp hơn IEEE-native benchmark. Vì vậy đây là bằng chứng
giảm domain shift một phần, chưa phải giải pháp hoàn toàn.

---

## 11. Anomaly sidecar

Nguồn: `artifacts/reports/evaluation_report.json`.

| Split | Fraud mean | Legit mean | Fraud P90 | Legit P90 | Flagged fraud | Flagged legit |
|---|---:|---:|---:|---:|---:|---:|
| Train | 0.4033 | 0.1854 | 0.6232 | 0.3795 | - | - |
| Validation | 0.3437 | 0.1640 | 0.5716 | 0.3266 | 22 | 3,431 |
| Test | 0.4135 | 0.1798 | 0.6254 | 0.3649 | 344 | 4,522 |

Ngưỡng `anomaly_flag` hiện được tự học bằng P95 anomaly score trên validation: `0.418285`.
So với ngưỡng cứng cũ `0.70`, ngưỡng adaptive bắt được nhiều fraud hơn trên test (`344/650`, 52.92%)
nhưng cũng flag nhiều legitimate hơn (`4,522/68,410`, false flag rate 6.61%). Vì vậy sidecar phù hợp
làm tín hiệu phụ cho `review` hoặc `step_up`, không phù hợp để thay thế XGBoost hoặc block cứng độc lập.

---

## 12. Medium branch và agent

Nguồn: `artifacts/reports/medium_branch_ablation.json`.

| Policy | Review rate | Block precision | Block recall | Block F1 | Ghi chú |
|---|---:|---:|---:|---:|---|
| `score_threshold_block` | 0.0000 | 0.9893 | 0.9969 | 0.9931 | Baseline nhị phân |
| `route_without_agent` | 0.2053 | 0.9893 | 0.9969 | 0.9931 | Mọi medium case đi review |
| `route_with_medium_agent` | 0.0926 | 0.9515 | 0.9969 | 0.9737 | Agent giảm review nhưng giảm precision |

Kết luận: agent có giá trị vận hành vì giảm số ca review thủ công và tạo giải thích có cấu trúc, nhưng không nên trình bày như thành phần làm tăng accuracy so với score-only baseline.

---

## 13. Simulation và latency

Nguồn: `artifacts/reports/simulation_report.json`.

Simulation hiện tại chạy trên 5,000 giao dịch:

| Route/Action | Count | Tỷ lệ |
|---|---:|---:|
| Route low | 3,950 | 79.00% |
| Route medium | 1,048 | 20.96% |
| Route high | 2 | 0.04% |
| Approve | 4,579 | 91.58% |
| Review | 394 | 7.88% |
| Step-up | 25 | 0.50% |
| Block | 2 | 0.04% |

Latency end-to-end:

| Metric | Giá trị |
|---|---:|
| Avg | 65.465 ms |
| P95 | 76.030 ms |
| Model avg | 61.555 ms |
| Model P95 | 67.138 ms |

---

## 14. Kết luận báo cáo

Mô hình XGBoost trên PaySim đạt hiệu năng offline rất cao và pipeline 4 lớp đã có đủ bằng chứng vận hành: train/evaluation artifact, baseline comparison, feature ablation, robustness validation, external validation, simulation, dashboard snapshot và deployment state.

Kết quả IEEE-CIS là điểm cần trình bày trung thực nhất: frozen PaySim model chưa tổng quát hóa tốt sang dữ liệu thực tế hơn. Vì vậy đóng góp chính của đề tài nên được viết là một kiến trúc phát hiện gian lận có khả năng huấn luyện, giải thích, điều phối review và giám sát triển khai, đồng thời có cơ chế external validation để phát hiện giới hạn chuyển miền.

---

## 15. Artifact tham chiếu

| File | Nội dung |
|---|---|
| `artifacts/reports/evaluation_report.json` | Metric XGBoost, confusion matrix, anomaly sidecar |
| `artifacts/reports/research_suite.json` | Tổng hợp baseline, ablation, robustness, external validation |
| `artifacts/reports/baseline_comparison.json` | So sánh model baseline |
| `artifacts/reports/feature_ablation.json` | Ablation theo nhóm feature |
| `artifacts/reports/medium_branch_ablation.json` | Ablation chính sách vùng medium |
| `artifacts/reports/robustness_validation.json` | Multi-seed, bootstrap CI, McNemar test |
| `artifacts/reports/external_validation.json` | IEEE-CIS frozen-vs-native benchmark |
| `artifacts/reports/transfer_learning_report.json` | Transfer learning PaySim → IEEE-CIS với 25 PaySim-aligned features |
| `artifacts/reports/simulation_report.json` | Route/action/latency trong simulation |
| `artifacts/deployment/deployment_state.json` | Active, candidate và rollback version |
| `artifacts/monitoring/dashboard_snapshot.json` | Snapshot dashboard sau simulation |
