# B9 – Robustness Audit Summary

## Phạm vi và kết luận ngắn

Audit này chỉ đọc code/artifact và tính lại summary statistics từ các per-seed values đã lưu. Không model hay experiment nào được chạy.

Artifact nhất quán nội bộ và repeated-seed logic thực sự refit model với ba seed trên cùng chronological split. Tuy nhiên, bằng chứng hiện tại chưa đủ để gọi là fixed-configuration stochastic robustness: mỗi seed chạy lại candidate search, selected params không được lưu, không có held-out test threshold sensitivity, baseline cho McNemar được chọn post-hoc trên test, và artifact thiếu provenance.

## A. Repeated-seed robustness

- [x] Seeds đúng là `42, 43, 44` trong config, JSON và từng model summary.
- [x] Cả ba seed nhận cùng một `ExperimentSplits`; code không tạo lại row split trong seed loop.
- [x] Không shuffle dataset. PaySim được filter `TRANSFER` + `CASH_OUT`, sort theo `step`, sau đó split bằng `iloc`.
- [x] Tổng rows = `460394`.
- [x] Train = `322275`.
- [x] Validation = `69059`.
- [x] Test = `69060`.
- [x] Leakage-control giống experiment chính vì robustness tái sử dụng `prepare_experiment_splits()` / `build_dataset()`.
- [x] Validation/test labels không cập nhật historical fraud-rate features. Train dùng `observe`; eval dùng `freeze_risk_labels=True` và chỉ gọi `observe_activity`.

### XGBoost per-seed results nguyên gốc

| Seed | Selected threshold | Test AUC | Test PR-AUC | Test F1 | Test precision | Test recall |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 42 | 0.5 | 0.9983827150776428 | 0.9970017406400512 | 0.993103448275862 | 0.9893129770992366 | 0.9969230769230769 |
| 43 | 0.7 | 0.9987623266953773 | 0.9970987605238817 | 0.99079754601227 | 0.9877675840978594 | 0.9938461538461538 |
| 44 | 0.7 | 0.9988008051004689 | 0.9975486999259158 | 0.9923312883435583 | 0.9892966360856269 | 0.9953846153846154 |

Mỗi run có đủ AUC, PR-AUC, F1, precision, recall và selected threshold trong JSON. CSV chỉ chứa summary, không chứa per-seed rows.

### Tính lại summary từ ba XGBoost runs

Standard deviation dưới đây là population standard deviation (`ddof=0`), đúng với code. Artifact JSON lưu bản làm tròn 6 chữ số; bảng này giữ kết quả tính lại từ các số per-seed nguyên gốc.

| Metric | Mean | Standard deviation | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| AUC | 0.9986486156244964 | 0.00018867515739557264 | 0.9983827150776428 | 0.9988008051004689 |
| PR-AUC | 0.9972164003632829 | 0.00023828619201725262 | 0.9970017406400512 | 0.9975486999259158 |
| F1 | 0.9920774275438968 | 0.0009583424201934456 | 0.99079754601227 | 0.993103448275862 |
| Precision | 0.988792399094241 | 0.0007246843403799568 | 0.9877675840978594 | 0.9893129770992366 |
| Recall | 0.9953846153846154 | 0.00125614858604266 | 0.9938461538461538 | 0.9969230769230769 |

### Hyperparameter protocol và cách diễn giải

`run_robustness_validation()` gọi:

```python
fit_best_xgboost(splits, splits.bundle.feature_columns, random_state=seed)
```

Tham số `fixed_params` bị bỏ trống, nên mỗi seed chạy lại toàn bộ bốn XGBoost candidates và chọn theo `validation AUC + validation F1`. Artifact không lưu selected params của từng seed, do đó không thể xác định sau chạy rằng ba seed có chọn cùng hyperparameters hay không.

Kết quả hiện tại đo:

> **robustness of the full model-selection pipeline**

Nó không chỉ đo:

> **stochastic stability of one fixed XGBoost configuration**

Ba seed là ba refit riêng biệt về random state, nhưng bằng chứng không tách được model stochasticity khỏi hyperparameter-selection variability.

## B. Baseline selection

```ini
TEST_SET_BASELINE_SELECTION = YES
```

Code chọn baseline như sau:

```python
best_baseline_artifact = max(
    baseline_candidates,
    key=lambda item: (
        item.report["test"]["metrics"]["auc"],
        item.report["test"]["metrics"]["f1"],
    ),
)
```

Vì baseline `hist_gradient_boosting` được chọn sau khi nhìn test AUC/F1, McNemar trên chính test set không hỗ trợ claim inferential kiểu “XGBoost statistically superior to the best baseline”. Phần này chỉ nên được xem là exploratory/post-hoc cho tới khi baseline được pre-specified hoặc chọn hoàn toàn trên validation.

## C. Threshold sensitivity

Grid trong config và CSV khớp hoàn toàn:

| Threshold | Validation precision | Validation recall | Validation F1 |
| ---: | ---: | ---: | ---: |
| 0.20 | 0.8955223880597015 | 0.9523809523809523 | 0.9230769230769231 |
| 0.25 | 0.9090909090909091 | 0.9523809523809523 | 0.9302325581395349 |
| 0.30 | 0.9230769230769231 | 0.9523809523809523 | 0.9375 |
| 0.35 | 0.967741935483871 | 0.9523809523809523 | 0.96 |
| 0.40 | 0.967741935483871 | 0.9523809523809523 | 0.96 |
| 0.45 | 0.967741935483871 | 0.9523809523809523 | 0.96 |
| 0.50 | 0.967741935483871 | 0.9523809523809523 | 0.96 |
| 0.55 | 0.967741935483871 | 0.9523809523809523 | 0.96 |
| 0.60 | 0.967741935483871 | 0.9523809523809523 | 0.96 |
| 0.65 | 0.967741935483871 | 0.9523809523809523 | 0.96 |
| 0.70 | 0.967741935483871 | 0.9523809523809523 | 0.96 |

- Selected threshold trong `evaluation_report.json` là `0.50`.
- Validation có 63 fraud rows, nên `find_best_threshold()` hiện tại đi qua configured grid. Hàm khởi tạo ở 0.50 và chỉ thay khi F1 **lớn hơn**; vì 0.35–0.70 cùng F1 = 0.96, 0.50 là tie-preserving default, không phải optimum duy nhất.
- `validation_threshold_sweep.csv` là validation-only artifact và có đủ precision/recall/F1.
- Không tìm thấy artifact sweep các threshold trên held-out PaySim test set.

```ini
TEST_THRESHOLD_SENSITIVITY_AVAILABLE = NO
```

## D. Phân tách B9 và B10

B9 chỉ nên dùng hai nhóm bằng chứng chính:

1. repeated-seed stability;
2. threshold sensitivity.

Bootstrap confidence intervals (`300` iterations) và McNemar test có trong robustness JSON/Markdown và đã được copy để audit, nhưng thuộc **B10 – Statistical validation**. Chúng không được dùng làm kết luận chính của B9. Audit này không chạy lại bootstrap hay McNemar.

## E. Artifact provenance

| Trường | Trong `robustness_validation.json` | Có thể đối chiếu từ `research_suite.json` | Kết luận |
| --- | --- | --- | --- |
| Random seeds | Có: `[42, 43, 44]` | Có trong object nhúng | PASS |
| Dataset source | Có: `paysim` | Có | PASS |
| Split strategy | Không | Có: `chronological_by_step_after_TRANSFER_CASH_OUT_filter` | Thiếu trong standalone artifact |
| Dataset size | Không | Có: `460394` | Thiếu trong standalone artifact |
| Train/validation/test counts | Không | Có: `322275 / 69059 / 69060` | Thiếu trong standalone artifact |
| Bootstrap iterations | Có: `300` | Có trong object nhúng | PASS, nhưng thuộc B10 |
| `generated_at` | Không | Không | FAIL |
| Git commit/hash | Không | Không | FAIL |
| Dataset/code hash | Không | Không | FAIL |
| Selected XGBoost params từng seed | Không | Không | FAIL cho việc phân biệt fixed-config và pipeline-selection robustness |

## F. Freshness và consistency

- `research_suite.json.robustness` bằng hoàn toàn `robustness_validation.json` khi so sánh cấu trúc JSON.
- Summary trong JSON/CSV khớp với phép tính lại từ per-seed values; Markdown chỉ format ngắn hơn.
- Seed-42 XGBoost test metrics và threshold khớp `evaluation_report.json`; validation sweep cùng artifact cho threshold `0.50`.
- Artifact được ghi lần cuối trong Git revision `71d83588f0667f122dee55a043e2a9c6d36e37d2`. Code hiện tại ở HEAD `8ad06aff01a5932d94436df9e34f7fca820c9fea`, và worktree còn dirty.
- Thay đổi committed sau artifact nằm trong `find_best_threshold()`. Với PaySim validation có 63 positives, code mới vẫn dùng grid cũ, nên không phát hiện mâu thuẫn số học do thay đổi này. Tuy nhiên, do không có commit/code hash trong artifact, không thể chứng minh đây là output của exact code hiện tại.
- Mtime cho robustness component là 2026-04-24 14:36:41 +07, suite là 14:40:45 +07; threshold sweep/evaluation được ghi sau đó khoảng một phút. Các số tương thích, nhưng thiếu run ID/timestamp trong payload để chứng minh chúng thuộc cùng clean run.

## Main issues

1. Mỗi XGBoost seed chạy lại candidate search, nhưng artifact không lưu selected params từng seed; không thể tuyên bố fixed-configuration stochastic stability.
2. Baseline cho McNemar được chọn post-hoc bằng test AUC/F1 (`TEST_SET_BASELINE_SELECTION = YES`).
3. Chỉ có validation threshold sweep; không có held-out test threshold sensitivity (`TEST_THRESHOLD_SENSITIVITY_AVAILABLE = NO`).
4. Robustness artifact thiếu split/counts tại chỗ, `generated_at`, git commit, code/data hash và run ID.
5. Artifact không mang provenance của exact code hiện tại; bootstrap/McNemar cần được tách khỏi claim chính của B9.

```ini
B9_RERUN_REQUIRED = YES
```
