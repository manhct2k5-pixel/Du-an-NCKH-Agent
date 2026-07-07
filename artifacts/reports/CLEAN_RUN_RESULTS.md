# Current Results Snapshot

**Ngày cập nhật:** 2026-04-20  
**Nguồn chính:** PaySim  
**External validation:** IEEE-CIS theo chế độ frozen-model external validation  

> File này là snapshot tóm tắt để đọc nhanh. Số liệu chi tiết và đáng tin cậy nhất nằm trong
> `evaluation_report.*`, `research_suite.*`, `external_validation.*`, `feature_ablation.*`,
> `medium_branch_ablation.*` và `robustness_validation.*`.

---

## 1. Kết quả training PaySim hiện tại

| | Validation | Test |
|---|---:|---:|
| **AUC** | 0.999413 | 0.998383 |
| **PR-AUC** | 0.961260 | 0.997002 |
| **F1** | 0.960000 | 0.993103 |
| **Precision** | 0.967742 | 0.989313 |
| **Recall** | 0.952381 | 0.996923 |

**Confusion matrix test:** TN=68,403, FP=7, FN=2, TP=648  
**Selected threshold:** 0.50  

**Params chọn:**

```text
n_estimators=260, max_depth=6, learning_rate=0.06,
subsample=0.90, colsample_bytree=0.85
```

---

## 2. Baseline comparison

| Model | Test AUC | Test PR-AUC | Test F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| HistGradientBoosting | 0.999932 | 0.997849 | 0.996914 | 1.000000 | 0.993846 |
| RandomForest | 0.999843 | 0.997502 | 0.995378 | 0.996914 | 0.993846 |
| XGBoost | 0.998383 | 0.997002 | 0.993103 | 0.989313 | 0.996923 |

Ghi chú: XGBoost vẫn là model triển khai chính trong pipeline hiện tại. HistGradientBoosting là baseline mạnh nhất trong research suite.

---

## 3. Feature ablation

| Ablation | Test AUC | Test PR-AUC | Test F1 | Delta F1 |
|---|---:|---:|---:|---:|
| full_feature_set | 0.998383 | 0.997002 | 0.993103 | +0.000000 |
| no_online_behavior | 0.998409 | 0.996741 | 0.989992 | -0.003111 |
| no_llm_analysis | 0.998647 | 0.995205 | 0.970432 | -0.022671 |
| no_contextual_aggregates | 0.996902 | 0.920048 | 0.853081 | -0.140023 |
| transaction_core_only | 0.997233 | 0.929678 | 0.811798 | -0.181306 |

---

## 4. Medium branch ablation

| Policy | Review Rate | Block Precision | Block Recall | Block F1 |
|---|---:|---:|---:|---:|
| score_threshold_block | 0.0000 | 0.9893 | 0.9969 | 0.9931 |
| route_without_agent | 0.2053 | 0.9893 | 0.9969 | 0.9931 |
| route_with_medium_agent | 0.0926 | 0.9515 | 0.9969 | 0.9737 |

Medium Agent giảm review từ 14,181 xuống 6,395 case, nhưng precision/F1 của block giảm. Vì vậy agent nên được trình bày là lớp hỗ trợ vận hành và giải thích cho vùng medium, không phải bằng chứng tăng accuracy so với backbone.

---

## 5. Robustness — Multi-seed

Best multi-seed model: **HistGradientBoosting** với seeds 42, 43, 44.

| Metric | Mean | Std | Min | Max |
|---|---:|---:|---:|---:|
| Test AUC | 0.999928 | 0.000031 | 0.999888 | 0.999963 |
| Test F1 | 0.996912 | 0.001264 | 0.995363 | 0.998459 |
| Precision | 1.000000 | 0.000000 | 1.000000 | 1.000000 |
| Recall | 0.993846 | 0.002512 | 0.990769 | 0.996923 |
| PR-AUC | 0.997444 | 0.000898 | 0.996200 | 0.998283 |

---

## 6. External Validation — IEEE-CIS

| | |
|---|---|
| Mode | frozen_vs_native_benchmark |
| Frozen model | xgboost_frozen_paysim |
| Frozen split | external_all_rows_no_ieee_fit |
| Frozen PaySim AUC | 0.6285 |
| Frozen PaySim PR-AUC | 0.0532 |
| Frozen PaySim F1 | 0.0201 |
| IEEE-native retrained AUC | 0.8415 |

Diễn giải đúng: frozen model có tín hiệu tốt hơn đoán mò về ranking, nhưng thấp hơn rất xa PaySim và thấp hơn benchmark train lại trên IEEE-CIS. Đây là bằng chứng domain shift/schema shift rất mạnh, không phải bằng chứng tổng quát hóa trực tiếp.

---

## 7. Transfer Learning — IEEE-CIS

| Model | Protocol | Feature schema | Test rows | AUC | PR-AUC | F1 | Precision | Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Frozen PaySim XGBoost | Không adapt | 25 PaySim-aligned | 590,540 | 0.628517 | 0.053153 | 0.020140 | 0.063907 | 0.011954 |
| Transfer-adapted XGBoost | Adapt 10% IEEE, test 90% | 25 PaySim-aligned | 531,486 | 0.677369 | 0.082577 | 0.189437 | 0.124906 | 0.391919 |
| IEEE-native XGBoost | Train lại trên IEEE | 42 IEEE-native | 88,581 | 0.841506 | 0.326239 | 0.332844 | 0.255282 | 0.478106 |

Transfer learning cải thiện AUC so với frozen model, nhưng vẫn thấp hơn benchmark train native trong đúng miền IEEE-CIS.

---

## 8. Anomaly Sidecar

| Split | Fraud mean | Legit mean | Fraud P90 | Legit P90 | Flagged fraud | Flagged legit |
|---|---:|---:|---:|---:|---:|---:|
| Train | 0.4033 | 0.1854 | 0.6232 | 0.3795 | — | — |
| Validation | 0.3437 | 0.1640 | 0.5716 | 0.3266 | 22 | 3,431 |
| Test | 0.4135 | 0.1798 | 0.6254 | 0.3649 | 344 | 4,522 |

Ngưỡng `anomaly_flag = 0.418285` được học tự động bằng P95 anomaly score trên validation. So với ngưỡng cứng cũ `0.70`, ngưỡng này bắt nhiều fraud hơn nhưng tăng false flag legitimate. Sidecar là side signal để ưu tiên kiểm tra, không phải primary classifier hay block rule.

---

## 9. Simulation

Simulation hiện tại với `5,000` giao dịch:

| Route/Action | Count |
|---|---:|
| Route low | 3,950 |
| Route medium | 1,048 |
| Route high | 2 |
| Approve | 4,579 |
| Review | 394 |
| Step-up | 25 |
| Block | 2 |

Latency end-to-end: avg `65.465 ms`, p95 `76.030 ms`.

---

## 10. Ghi chú cho báo cáo

- PaySim dùng để chứng minh hiệu năng kiến trúc trong miền mô phỏng.
- IEEE-CIS dùng để kiểm tra ngoài phân bố. Kết quả frozen-model thấp phải được trình bày như giới hạn/domain shift, không phải lỗi chạy lệnh.
- Transfer learning PaySim → IEEE-CIS đã được chạy như hướng giảm domain shift một phần, không phải bằng chứng thay thế train native.
- Medium ReAct Agent hiện chạy đồng bộ; high-risk explanation log mới là phần bất đồng bộ. Khi scale TPS lớn, cần async queue hoặc timeout/fallback.
