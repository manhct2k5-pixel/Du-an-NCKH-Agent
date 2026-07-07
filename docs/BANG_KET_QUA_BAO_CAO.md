# Bảng kết quả đưa vào báo cáo

**Ngày cập nhật tài liệu:** 2026-04-20  
**Nguồn số liệu:** train/simulation/transfer adaptive run ngày 2026-04-20 và research suite clean run ngày 2026-04-17

File này gom các bảng ngắn, dễ chèn vào báo cáo hoặc slide.

---

## 1. Cấu hình mô hình production

| Hạng mục | Giá trị |
|---|---|
| Dataset chính | PaySim |
| External validation | IEEE-CIS |
| Model deploy | XGBoost |
| Active version | `v20260420T053341630222Z` |
| Tổng số dòng | 460,394 |
| Train / Val / Test | 322,275 / 69,059 / 69,060 |
| Số feature | 25 |
| Classification threshold | 0.50 |
| Routing low threshold | 0.30 |
| Routing high threshold | 0.85 |
| Anomaly flag threshold | 0.418285, P95 validation |

---

## 2. Metric XGBoost trên PaySim

| Tập đánh giá | AUC | PR-AUC | F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Validation | 0.999413 | 0.961260 | 0.960000 | 0.967742 | 0.952381 |
| Test | 0.998383 | 0.997002 | 0.993103 | 0.989313 | 0.996923 |

Confusion matrix test:

| | Dự đoán hợp lệ | Dự đoán gian lận |
|---|---:|---:|
| Thực tế hợp lệ | 68,403 | 7 |
| Thực tế gian lận | 2 | 648 |

---

## 3. Baseline comparison

| Model | Test AUC | Test PR-AUC | Test F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| HistGradientBoosting | 0.999932 | 0.997849 | 0.996914 | 1.000000 | 0.993846 |
| RandomForest | 0.999843 | 0.997502 | 0.995378 | 0.996914 | 0.993846 |
| XGBoost deploy | 0.998383 | 0.997002 | 0.993103 | 0.989313 | 0.996923 |
| Logistic Regression | 0.996364 | 0.884412 | 0.485748 | 0.325521 | 0.956923 |
| Dummy prior | 0.500000 | 0.009412 | 0.000000 | 0.000000 | 0.000000 |

---

## 4. Feature ablation

| Cấu hình | Số feature | Test AUC | Test PR-AUC | Test F1 | Delta F1 |
|---|---:|---:|---:|---:|---:|
| Full feature set | 25 | 0.998383 | 0.997002 | 0.993103 | 0.000000 |
| No online behavior | 17 | 0.998409 | 0.996741 | 0.989992 | -0.003111 |
| No LLM-style analysis | 20 | 0.998647 | 0.995205 | 0.970432 | -0.022671 |
| No contextual aggregates | 19 | 0.996902 | 0.920048 | 0.853081 | -0.140023 |
| Transaction core only | 6 | 0.997233 | 0.929678 | 0.811798 | -0.181306 |

---

## 5. Robustness validation

| Model | Seeds | Test AUC mean ± std | Test F1 mean ± std | Precision mean ± std | Recall mean ± std |
|---|---|---:|---:|---:|---:|
| HistGradientBoosting | 42,43,44 | 0.999928 ± 0.000031 | 0.996912 ± 0.001264 | 1.000000 ± 0.000000 | 0.993846 ± 0.002512 |
| XGBoost | 42,43,44 | 0.998649 ± 0.000189 | 0.992077 ± 0.000958 | 0.988792 ± 0.000725 | 0.995385 ± 0.001256 |

| Kiểm định | Giá trị |
|---|---:|
| XGBoost AUC 95% CI | 0.995236 đến 1.000000 |
| XGBoost F1 95% CI | 0.989130 đến 0.996811 |
| McNemar p-value vs HistGradientBoosting | 0.182422 |

---

## 6. External validation IEEE-CIS

| Model | Mode | Test AUC | PR-AUC | F1 | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|
| XGBoost train lại trên IEEE-CIS | Native, 42 IEEE features | 0.841506 | 0.326239 | 0.332844 | 0.255282 | 0.478106 |
| Frozen PaySim XGBoost | Frozen, 25 PaySim features aligned | 0.628517 | 0.053153 | 0.020140 | 0.063907 | 0.011954 |

Ghi chú để viết báo cáo: frozen PaySim AUC `0.6285` trên IEEE-CIS là bằng chứng domain shift/schema shift, không phải bằng chứng tổng quát hóa trực tiếp.

---

## 7. Transfer learning IEEE-CIS

| Model | Protocol | Feature schema | Test rows | AUC | PR-AUC | F1 | Precision | Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Frozen PaySim XGBoost | Không adapt | 25 PaySim-aligned | 590,540 | 0.628517 | 0.053153 | 0.020140 | 0.063907 | 0.011954 |
| Transfer-adapted XGBoost | Adapt 10% IEEE, test 90% | 25 PaySim-aligned | 531,486 | 0.677369 | 0.082577 | 0.189437 | 0.124906 | 0.391919 |
| IEEE-native XGBoost | Train lại trên IEEE | 42 IEEE-native | 88,581 | 0.841506 | 0.326239 | 0.332844 | 0.255282 | 0.478106 |

Ghi chú: transfer learning cải thiện AUC so với frozen PaySim (`0.6285` → `0.6774`) nhưng vẫn thấp hơn train native (`0.8415`).

---

## 8. Anomaly sidecar

| Split | Fraud mean | Legit mean | Fraud P90 | Legit P90 | Flagged fraud | Flagged legit |
|---|---:|---:|---:|---:|---:|---:|
| Train | 0.4033 | 0.1854 | 0.6232 | 0.3795 | - | - |
| Validation | 0.3437 | 0.1640 | 0.5716 | 0.3266 | 22 | 3,431 |
| Test | 0.4135 | 0.1798 | 0.6254 | 0.3649 | 344 | 4,522 |

---

## 9. Medium branch ablation

| Policy | Review rate | Block precision | Block recall | Block F1 |
|---|---:|---:|---:|---:|
| `score_threshold_block` | 0.0000 | 0.9893 | 0.9969 | 0.9931 |
| `route_without_agent` | 0.2053 | 0.9893 | 0.9969 | 0.9931 |
| `route_with_medium_agent` | 0.0926 | 0.9515 | 0.9969 | 0.9737 |

---

## 10. Simulation 5,000 giao dịch

| Route/Action | Count | Tỷ lệ |
|---|---:|---:|
| Route low | 3,950 | 79.00% |
| Route medium | 1,048 | 20.96% |
| Route high | 2 | 0.04% |
| Approve | 4,579 | 91.58% |
| Review | 394 | 7.88% |
| Step-up | 25 | 0.50% |
| Block | 2 | 0.04% |

| Latency | Giá trị |
|---|---:|
| End-to-end avg | 65.465 ms |
| End-to-end p95 | 76.030 ms |
| Model avg | 61.555 ms |
| Model p95 | 67.138 ms |

---

## 10. Đoạn diễn giải ngắn

Trên tập holdout test PaySim gồm 69,060 giao dịch, XGBoost đạt AUC `0.998383`, PR-AUC `0.997002`, F1 `0.993103`, Precision `0.989313` và Recall `0.996923`. Research suite cho thấy HistGradientBoosting là baseline offline mạnh nhất, nhưng XGBoost được giữ làm model triển khai vì phù hợp với SHAP explanation và pipeline vận hành hiện tại. External validation trên IEEE-CIS cho thấy frozen PaySim model đạt AUC `0.628517`, thấp hơn IEEE-native retrained benchmark `0.841506`. Transfer learning với 10% IEEE-CIS cải thiện AUC lên `0.677369`, nên kết quả IEEE-CIS cần được trình bày như bằng chứng domain shift và hướng giảm domain shift một phần, không phải tổng quát hóa trực tiếp.
