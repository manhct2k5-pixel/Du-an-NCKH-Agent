# B8 – Ablation Study Audit Summary

## Kết luận

```ini
RERUN_REQUIRED = YES
```

Các artifact hiện tại **nhất quán nội bộ** và logic metric/split chính là hợp lệ. Tuy nhiên, chưa nên trình bày chúng như một clean run của code hiện tại hoặc như bằng chứng tách biệt hoàn toàn các nguồn feature, vì:

1. Artifact được commit ở revision `71d83588f0667f122dee55a043e2a9c6d36e37d2`, trong khi `fraud_flow/training.py` hiện tại đã thay đổi ở revision `8ad06aff01a5932d94436df9e34f7fca820c9fea` (logic `find_best_threshold`). Với validation PaySim hiện có 63 fraud case, nhánh code mới vẫn dùng threshold grid cũ, nên chưa phát hiện sai số do thay đổi này; dù vậy artifact không phải output được sinh từ chính xác source revision hiện tại.
2. Artifact không ghi git commit, hash dataset hay hash code, nên không thể xác minh bằng provenance rằng một clean checkout của code hiện tại sẽ sinh đúng byte output này.
3. `no_online_behavior` bỏ đúng 8 cột trực tiếp nhưng vẫn giữ 5 `llm_*` features; các feature này là heuristic xác định có dùng velocity và historical fraud-rate lookup. Vì vậy nó không loại hoàn toàn online-behavior signal. Tương tự, `llm_*` cũng dùng transaction/context signal. Muốn tuyên bố “predictive contribution của nguồn tín hiệu” theo nghĩa độc lập cần ablation dependency-aware và rerun.

Không experiment nào được chạy trong audit này. Kết luận trên chỉ dựa vào code, artifact, metadata file và lịch sử Git hiện có.

## Feature Ablation

- [x] Full model có đúng 25 features.
- [x] `no_online_behavior` bỏ đúng 8 cột: `tx_count_24h`, `avg_amount_7d`, `device_tx_count_24h`, `location_tx_count_24h`, `merchant_tx_count_24h`, `location_fraud_rate`, `ip_fraud_rate`, `merchant_fraud_rate`.
- [x] `no_llm_analysis` bỏ đúng 5 cột: `llm_risk_score`, `llm_reason_count`, `llm_high_risk_flag`, `llm_review_flag`, `llm_category_hash`.
- [x] `no_contextual_aggregates` bỏ đúng 6 cột: `balance_diff`, `amount_ratio`, `org_balance_delta_ratio`, `hour_of_day`, `is_night_tx`, `recipient_new_flag`.
- [x] `transaction_core_only` chỉ giữ đúng 6 cột: `amount_log1p`, `oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest`, `type_encoded`.
- [x] Feature counts lần lượt là 25 / 17 / 20 / 19 / 6.
- [x] Mọi ablation nhận cùng một `ExperimentSplits`, với strategy `chronological_by_step_after_TRANSFER_CASH_OUT_filter`.
- [x] Code không dùng test metric để chọn hyperparameter. Full XGBoost params được chọn theo `validation AUC + validation F1`; sau đó cố định cho tất cả feature ablation.
- [x] Threshold của từng configuration được chọn từ validation labels/probabilities.
- [x] Leakage control vẫn được áp dụng: split enriched frame trước khi build feature; train store quan sát label, eval store được freeze label.
- [x] Validation/test labels không được đưa vào `location_fraud_rate`, `ip_fraud_rate`, `merchant_fraud_rate`; `freeze_risk_labels=True` chỉ gọi `observe_activity` cho eval rows.

Lưu ý diễn giải: AUC và PR-AUC phản ánh ranking contribution của tập cột. F1 còn bao gồm ảnh hưởng của việc chọn lại threshold trên validation cho từng configuration. Tên `llm_analysis` không có nghĩa là online LLM inference: code sinh nó bằng heuristic xác định trong `llm_features.py`.

### Số liệu nguyên gốc từ `feature_ablation.json`

| Configuration | Feature count | Test AUC | Test PR-AUC | Test F1 | Delta AUC vs full | Delta F1 vs full |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_feature_set` | 25 | 0.9983827150776428 | 0.9970017406400512 | 0.993103448275862 | 0.0 | 0.0 |
| `no_online_behavior` | 17 | 0.9984086559544827 | 0.9967407558963038 | 0.9899923017705927 | 0.000026 | -0.003111 |
| `no_llm_analysis` | 20 | 0.9986469589466227 | 0.9952047809970387 | 0.9704321455648218 | 0.000264 | -0.022671 |
| `no_contextual_aggregates` | 19 | 0.996902297234997 | 0.9200482675822834 | 0.8530805687203792 | -0.00148 | -0.140023 |
| `transaction_core_only` | 6 | 0.9972326920265819 | 0.9296777640918964 | 0.8117977528089888 | -0.00115 | -0.181306 |

## Medium-Branch Ablation

- [x] Tất cả policy được áp dụng trên cùng 69,060 held-out test rows và cùng `test_proba`.
- [x] Trong ba routed policies, low luôn approve và high luôn block; chỉ medium action thay đổi. `score_threshold_block` là comparator nhị phân không routing.
- [x] Manual-review-only baseline được định nghĩa đúng theo phạm vi medium branch: `route_without_agent` đưa mọi medium case sang review, trong khi low/high giữ nguyên.
- [x] Investigation/replay policy chỉ được gọi khi `route == "medium"`.
- [x] Policy không thay classifier probability/output. Nó tái sử dụng cùng `raw_probability`, operational score và SHAP explanation, sau đó chỉ thay final action.
- [x] Approve/review/block counts của mỗi policy cộng đúng 69,060; các rate là count chia tổng và tổng rate bằng 1.0 sau format 6 chữ số.
- [x] Block precision được tính bằng `precision_score(y_true, pred_block)` với chỉ action `block` là positive prediction.
- [x] Block recall được tính bằng `recall_score(y_true, pred_block)`.
- [x] Block F1 được tính bằng `f1_score(y_true, pred_block)`.
- [x] False-positive block rate được tính là normal-in-block / tổng normal. Artifact phù hợp: baseline routed có 7/68,410 = 0.000102 sau format; agent replay có 33/68,410 = 0.000482 sau format.
- [x] Fraud review rate được tính là fraud-in-review / tổng fraud. Artifact phù hợp với 650 fraud test rows: 0 hoặc 1/650 = 0.001538 sau format.

### Số liệu nguyên gốc từ `medium_branch_ablation.json`

| Policy | Medium case count | Approve count/rate | Review count/rate | Block count/rate | Block precision | Block recall | Block F1 | Fraud review rate | False-positive block rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `score_threshold_block` | 14181 | 68405 / 0.990515 | 0 / 0.0 | 655 / 0.009485 | 0.9893129770992366 | 0.9969230769230769 | 0.993103448275862 | 0.0 | 0.000102 |
| `route_without_agent` | 14181 | 54224 / 0.785172 | 14181 / 0.205343 | 655 / 0.009485 | 0.9893129770992366 | 0.9969230769230769 | 0.993103448275862 | 0.001538 | 0.000102 |
| `route_medium_auto_approve` | 14181 | 68405 / 0.990515 | 0 / 0.0 | 655 / 0.009485 | 0.9893129770992366 | 0.9969230769230769 | 0.993103448275862 | 0.0 | 0.000102 |
| `route_with_medium_agent` | 14181 | 61984 / 0.897538 | 6395 / 0.092601 | 681 / 0.009861 | 0.9515418502202643 | 0.9969230769230769 | 0.9737039819684448 | 0.001538 | 0.000482 |

Tất cả cột được yêu cầu đều có trong JSON; không có giá trị nào phải điền bằng suy đoán trong bảng trên.

## Freshness và consistency

| Kiểm tra | Kết quả | Bằng chứng |
| --- | --- | --- |
| `feature_ablation.json` so với `research_suite.json.feature_ablation` | PASS | So sánh JSON theo cấu trúc: bằng nhau hoàn toàn |
| `medium_branch_ablation.json` so với `research_suite.json.medium_branch` | PASS | So sánh JSON theo cấu trúc: bằng nhau hoàn toàn |
| JSON so với CSV | PASS | Các field số và row trùng nhau; CSV có thể biểu diễn số nhỏ bằng scientific notation |
| JSON so với Markdown gốc | PASS có format | Nội dung trùng; Markdown hiển thị metric đã format 4 chữ số, nên JSON phải là nguồn trích số cho bài báo |
| Dataset size | PASS | `total_rows = 460394` |
| Split size | PASS | `train_rows = 322275`, `validation_rows = 69059`, `test_rows = 69060`; tổng bằng 460394 |
| Random seed | PASS | Suite, baseline và feature ablation ghi `42`; medium JSON không có field seed riêng nhưng được nhúng nguyên trong suite cùng run |
| Cùng một artifact run | PASS (nội bộ) | Mtime: feature 2026-04-24 14:35:31 +07, medium 14:35:57 +07, suite 14:40:45 +07; hai object con được nhúng nguyên trong suite |
| Khớp exact source revision hiện tại | FAIL | `training.py` đã thay đổi sau revision chứa artifact; artifact không có code/data hash |

## Cách diễn giải được phép

- Feature ablation đo **predictive contribution của các cột trong nhóm feature được bỏ** dưới cùng split và fixed XGBoost params. Không nên nâng thành causal contribution của toàn bộ nguồn tín hiệu khi derived features còn mang proxy signal.
- Medium-branch ablation đo **workflow / operational decision-support effect**: action mix, review load và block classification metrics trên held-out test set.
- Không được kết luận ReAct làm tăng AUC, PR-AUC hoặc classifier F1. Medium replay không retrain model, không thay `raw_probability`, và artifact không báo cáo classifier AUC/PR-AUC cho policy.
- `route_with_medium_agent` chỉ thay final operational action ở medium branch. Hơn nữa, code audit gọi trực tiếp `build_decision_payload` và rule-based `review_and_finalize`; nó **không chạy** `ReActInvestigator`. Vì vậy tên chính xác cho bằng chứng này là “offline deterministic investigator replay”, không phải “ReAct ablation”.

## Các vấn đề cần lưu ý

1. Medium replay không thực thi ReAct runtime; không thể dùng artifact này để chứng minh hiệu quả của ReAct/LLM.
2. Các group đúng theo danh sách cột nhưng không độc lập về nguồn tín hiệu: `llm_*` là derived proxy của online/context features.
3. Source revision hiện tại không trùng exact revision chứa artifact; thiếu git commit, code hash và dataset hash trong artifact provenance.
4. Medium replay warm-start `FeatureStore` bằng train + validation rows và label của chúng, trong khi classifier feature frame đóng băng fraud-rate state sau train. Test labels không bị dùng, nhưng khác biệt state protocol này phải được công bố khi mô tả medium-policy experiment.
5. `research_suite.md` gọi `no_llm_analysis` là “Best Feature Configuration” dựa trên test AUC. Code không dùng test để tune model, nhưng cách gắn nhãn “best” này là post-hoc test-set selection và không nên được trình bày như model-selection protocol.
