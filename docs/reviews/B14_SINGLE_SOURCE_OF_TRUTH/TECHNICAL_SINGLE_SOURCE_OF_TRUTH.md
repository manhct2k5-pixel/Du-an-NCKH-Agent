# Technical Single Source of Truth

Generated at: `2026-10-11T13:39:08Z`

Repository commit: `8ad06aff01a5932d94436df9e34f7fca820c9fea` (`git_dirty = true`)

This document is the authoritative technical handoff for TV1/TV2/TV4/TV5. Final B8–B13 artifacts override README text, legacy reports, historical review packages, and the current manuscript. `FINAL` means supported by the cited final artifact or active configuration; `OBSOLETE` and `PROVISIONAL` values must not be reported as final results.

## 1. Dataset

| Metric | Final value | Source artifact | JSON field / derivation | Status |
|---|---:|---|---|---|
| Total rows after filter | 460,394 | `artifacts/reports/evaluation_report.json` | `split.total_rows` | FINAL |
| Fraud rows | 1,142 | same | `class_balance.positive_count + validation.confusion_matrix.(false_negative + true_positive) + test.confusion_matrix.(false_negative + true_positive)` = 429 + 63 + 650 | FINAL |
| Legitimate rows | 459,252 | same | 321,846 + 68,996 + 68,410 | FINAL |
| Train rows | 322,275 | same | `split.train_rows` | FINAL |
| Train fraud / legitimate | 429 / 321,846 | same | `class_balance.positive_count / negative_count` | FINAL |
| Validation rows | 69,059 | same | `split.validation_rows` | FINAL |
| Validation fraud / legitimate | 63 / 68,996 | same | validation confusion-matrix marginals | FINAL |
| Test rows | 69,060 | same | `split.test_rows` | FINAL |
| Test fraud / legitimate | 650 / 68,410 | same | test confusion-matrix marginals | FINAL |
| Feature count | 25 | same | `feature_columns` length | FINAL |
| Split strategy | chronological by `step` after TRANSFER/CASH_OUT filtering | same | `split_strategy` | FINAL |

The counts are internally consistent: 322,275 + 69,059 + 69,060 = 460,394 and 1,142 + 459,252 = 460,394.

## 2. Preprocessing and leakage control

| Setting | Final value | Source artifact | Field | Status |
|---|---|---|---|---|
| Transaction filter | Retain `TRANSFER` and `CASH_OUT` | `artifacts/reports/evaluation_report.json` | `split_strategy` | FINAL |
| Split order | Chronological by PaySim `step` | same | `split_strategy` | FINAL |
| Shuffle | `false` | `artifacts/reports/b9_final/b9_repeated_seed_robustness.json` | `protocol.shuffle` | FINAL |
| Leakage-control rule | Train labels may update historical fraud-rate state; validation/test labels never update that state before feature construction or policy decisions. Validation/test activity is updated sequentially only. | `artifacts/reports/b8_final/feature_ablation_b8.json` | `provenance.leakage_control_protocol` | FINAL |

## 3. Production XGBoost

| Parameter | Final value | Source artifact | Field | Status |
|---|---:|---|---|---|
| `n_estimators` | 260 | `artifacts/reports/evaluation_report.json` | `selected_params.n_estimators` | FINAL |
| `max_depth` | 6 | same | `selected_params.max_depth` | FINAL |
| `learning_rate` | 0.06 | same | `selected_params.learning_rate` | FINAL |
| `subsample` | 0.9 | same | `selected_params.subsample` | FINAL |
| `colsample_bytree` | 0.85 | same | `selected_params.colsample_bytree` | FINAL |
| `scale_pos_weight` | 750.2237762237762 | same | `class_balance.scale_pos_weight` | FINAL |
| `max_delta_step` | 1 | same | `training_controls.max_delta_step` | FINAL |
| `tree_method` | `hist` | `artifacts/reports/b9_final/b9_repeated_seed_robustness.json` | `protocol.fixed_hyperparameters.tree_method` | FINAL |
| `n_jobs` | 4 | same | `protocol.fixed_runtime_controls.n_jobs` | FINAL |
| `random_state` | 42 | `artifacts/reports/evaluation_report.json` | `random_state` | FINAL |
| Classification threshold | 0.5 | same | `selected_threshold` | FINAL |

## 4. Routing

| Setting | Final value | Source | Field | Status |
|---|---:|---|---|---|
| Low threshold | 0.30 | `artifacts/reports/evaluation_report.json` | `routing_thresholds.low` | FINAL |
| High threshold | 0.85 | same | `routing_thresholds.high` | FINAL |
| High-route raw-probability safety floor | 0.05 | `fraud_flow/config.py` | `RoutingThresholds.high_raw_probability_floor` | FINAL |

The safety floor is enforced by `FraudFlowRunner._handle_high`: a high operational score with raw probability below 0.05 is sent to review instead of being blocked.

## 5. Primary PaySim holdout metrics

| Metric | Final value | Source artifact | JSON field | Status |
|---|---:|---|---|---|
| AUC | 0.9983827150776428 | `artifacts/reports/evaluation_report.json` | `test.roc_auc` | FINAL |
| PR-AUC | 0.9970017406400512 | same | `test.pr_auc` | FINAL |
| F1 | 0.993103448275862 | same | `test.metrics.f1` | FINAL |
| Precision | 0.9893129770992366 | same | `test.metrics.precision` | FINAL |
| Recall | 0.9969230769230769 | same | `test.metrics.recall` | FINAL |
| TN / FP / FN / TP | 68,403 / 7 / 2 / 648 | same | `test.confusion_matrix` | FINAL |

These metrics use the held-out 69,060-row chronological test split and threshold 0.5.

## 6. Baseline comparison (B7)

All values below are holdout-test values from `artifacts/reports/baseline_comparison.json`, fields `models[].test.*`.

| Model | AUC | PR-AUC | F1 | Precision | Recall | Status |
|---|---:|---:|---:|---:|---:|---|
| HistGradientBoosting | 0.9999321511699818 | 0.997849385204436 | 0.9969135802469136 | 1.0 | 0.9938461538461538 | FINAL |
| Random Forest | 0.9998431740748653 | 0.9975016124891384 | 0.9953775038520801 | 0.9969135802469136 | 0.9938461538461538 | FINAL |
| XGBoost | 0.9983827150776428 | 0.9970017406400512 | 0.993103448275862 | 0.9893129770992366 | 0.9969230769230769 | FINAL |
| Logistic Regression | 0.9963643641842734 | 0.8844123778149597 | 0.4857477547832878 | 0.32548403976975404 | 0.9569230769230769 | FINAL |
| Dummy (`prior`) | 0.5 | 0.009412105415580654 | 0.0 | 0.0 | 0.0 | FINAL |

## 7. Feature ablation (B8 final)

Source for every row: `artifacts/reports/b8_final/feature_ablation_b8.json`, `ablations[]`. Thresholds were selected on validation; `test_set_used_for_selection = false`.

| Configuration | Features | Threshold | Test F1 | ΔF1 vs full | Status |
|---|---:|---:|---:|---:|---|
| `full_feature_set` | 25 | 0.50 | 0.993103448275862 | 0.000000 | FINAL |
| `no_online_behavior` | 17 | 0.65 | 0.9899923017705927 | -0.003111 | FINAL |
| `no_llm_analysis` | 20 | 0.50 | 0.9704321455648218 | -0.022671 | FINAL |
| `no_contextual_aggregates` | 19 | 0.70 | 0.8530805687203792 | -0.140023 | FINAL |
| `transaction_core_only` | 6 | 0.70 | 0.8117977528089888 | -0.181306 | FINAL |
| `no_online_behavior_and_dependent_analysis` | 12 | 0.50 | 0.9751318764129616 | -0.017972 | FINAL |
| `no_contextual_and_dependent_analysis` | 14 | 0.70 | 0.8564593301435407 | -0.136644 | FINAL |

The two dependency-aware configurations are part of the final seven and must not be omitted.

## 8. Medium branch (B8 final)

| Metric | Final value | Source artifact | JSON field | Status |
|---|---:|---|---|---|
| All-medium-review count | 14,181 | `artifacts/reports/b8_final/medium_branch_ablation_b8.json` | `policies[policy=all_medium_manual_review].review_count` | FINAL |
| Deterministic replay review count | 6,383 | same | `policies[policy=deterministic_offline_investigation_replay].review_count` | FINAL |
| Review reduction | 7,798 | same | `...manual_review_reduction_count` | FINAL |
| Review reduction rate | 54.99% | same | `...manual_review_reduction_rate = 0.549891` | FINAL |
| Block precision | 94.88% | same | `...block_precision = 0.9487554904831625` | FINAL |
| Block recall | 99.69% | same | `...block_recall = 0.9969230769230769` | FINAL |
| False-positive blocks | 35 | same | `...false_positive_blocks` | FINAL |

The replay is deterministic and offline; `full_react_runtime_executed = false` and classifier probabilities did not change. Old values `6,395`, `33 FP`, and `95.15%` are not final.

## 9. Robustness (B9 final)

Source: `artifacts/reports/b9_final/b9_repeated_seed_robustness.json`; the only varied parameter is `random_state`, using seeds 42, 43, and 44 with a fixed threshold of 0.5.

| Seed | AUC | PR-AUC | F1 | Precision | Recall | Status |
|---:|---:|---:|---:|---:|---:|---|
| 42 | 0.9983827150776428 | 0.9970017406400512 | 0.993103448275862 | 0.9893129770992366 | 0.9969230769230769 | FINAL |
| 43 | 0.9987623266953773 | 0.9970987605238817 | 0.9900687547746372 | 0.9833080424886191 | 0.9969230769230769 | FINAL |
| 44 | 0.9988008051004689 | 0.9975486999259158 | 0.9908256880733946 | 0.9848024316109423 | 0.9969230769230769 | FINAL |

| Metric | Mean ± population SD | JSON field | Status |
|---|---|---|---|
| AUC | 0.9986486156244964 ± 0.00018867515739557264 | `summary.test_auc` | FINAL |
| PR-AUC | 0.9972164003632829 ± 0.00023828619201725262 | `summary.test_pr_auc` | FINAL |
| F1 | 0.9913326303746312 ± 0.0012897245272231583 | `summary.test_f1` | FINAL |
| Precision | 0.985807817066266 ± 0.002552503327425876 | `summary.test_precision` | FINAL |
| Recall | 0.9969230769230769 ± 0.0 | `summary.test_recall` | FINAL |

These are across-seed stochastic variations of the fixed deployed XGBoost configuration, not robustness of a repeated hyperparameter-search pipeline.

## 10. Statistical validation (B10 final)

Source: `artifacts/reports/b10_final/b10_bootstrap_ci.json`. Protocol: 2,000-replicate stratified nonparametric percentile bootstrap with within-class resampling, seed 42, fixed fitted model, and fixed test class counts.

| Metric | Point estimate | 95% CI | JSON fields | Status |
|---|---:|---|---|---|
| AUC | 0.9983827150776428 | [0.9952713267291107, 0.9999996176897215] | `metrics.auc.point_estimate/ci95_low/ci95_high` | FINAL |
| PR-AUC | 0.9970017406400512 | [0.992546899838475, 0.9999598708634057] | `metrics.pr_auc.*` | FINAL |
| F1 | 0.993103448275862 | [0.9885228961647714, 0.9969325153374233] | `metrics.f1.*` | FINAL |
| Precision | 0.9893129770992366 | [0.9817351598173516, 0.9969135802469136] | `metrics.precision.*` | FINAL |
| Recall | 0.9969230769230769 | [0.9923076923076923, 1.0] | `metrics.recall.*` | FINAL |

The intervals are conditional test-sample uncertainty. They are not training-pipeline uncertainty and must not be pooled with B9 seed variation. `MCNEMAR_FINAL_USE = NO`.

## 11. Isolation Forest sidecar

Source: `artifacts/reports/evaluation_report.json`, object `anomaly_sidecar`.

| Split / metric | Final value | JSON field | Status |
|---|---:|---|---|
| Threshold | 0.41828539293549033 (report as 0.4183) | `flag_threshold` | FINAL |
| Validation flagged | 3,453 / 69,059 | `val_eval.flagged_total / total_rows` | FINAL |
| Validation fraud caught | 22 / 63 = 34.9206% | `val_eval.flagged_fraud / fraud_catch_rate` | FINAL |
| Validation false-flag | 3,431 legitimate; 4.97275% | `val_eval.flagged_legit / false_flag_rate` | FINAL |
| Test flagged | 4,866 / 69,060 | `test_eval.flagged_total / total_rows` | FINAL |
| Test fraud caught | 344 / 650 = 52.9231% | `test_eval.flagged_fraud / fraud_catch_rate` | FINAL |
| Test false-flag | 4,522 legitimate; 6.61014% | `test_eval.flagged_legit / false_flag_rate` | FINAL |

## 12. Efficiency (B11 final)

| Metric | Final value | Source artifact | JSON field | Status |
|---|---:|---|---|---|
| Fixed-fit mean | 1.669062444332667 s (1.669 s) | `artifacts/reports/b11_final/b11_training_time.json` | `timing.mean_seconds` | FINAL |
| Local end-to-end mean | 14.192055347616355 ms (14.19 ms) | `artifacts/reports/b11_final/b11_latency_components.json` | `overall.local_end_to_end_ms.mean_ms` | FINAL |
| Local end-to-end p95 | 28.13968635018682 ms (28.14 ms) | same | `overall.local_end_to_end_ms.p95_ms` | FINAL |
| Local end-to-end p99 | 46.46767077978442 ms (46.47 ms) | same | `overall.local_end_to_end_ms.p99_ms` | FINAL |
| Sequential local throughput | 70.46195744776011 tx/s (70.5 tx/s) | same | `overall.local_end_to_end_ms.throughput_tx_per_second` | FINAL |
| Raw XGBoost mean | 3.550239045042334 ms (3.55 ms) | same | `overall.xgboost_predict_proba_ms.mean_ms` | FINAL |
| TreeSHAP mean | 3.3466839083969475 ms (3.35 ms) | same | `overall.shap_explanation_ms.mean_ms` | FINAL |
| Isolation Forest mean | 6.859352249277064 ms (6.86 ms) | same | `overall.anomaly_sidecar_ms.mean_ms` | FINAL |
| Medium deterministic replay mean | 0.09786381843594455 ms (0.098 ms) | same | `overall.deterministic_medium_investigation_ms.mean_ms` | FINAL |
| Old overall mean | 35.72 ms | `artifacts/reports/latency_report.json` | `overall.mean_ms = 35.716` | OBSOLETE |
| Old overall p99 | 51.55 ms | same | `overall.p99_ms = 51.546` | OBSOLETE |

The final B11 boundary is local, sequential, and single-process. It uses in-memory `FeatureStore` and excludes Redis, network, external LLM/API, logging, concurrency, dataset/model loading, and training.

## 13. IEEE-CIS external validation (B12 final)

| Experiment | AUC | Source artifact | Field | Status |
|---|---:|---|---|---|
| Frozen PaySim → IEEE-CIS | 0.6260447267256386 | `artifacts/reports/b12_final/b12_frozen_ieee.json` | `metrics.auc` | FINAL |
| Transfer/adapted → IEEE-CIS | 0.6525325347771955 | `artifacts/reports/b12_final/b12_transfer_ieee.json` | `metrics.auc` | FINAL |
| Native IEEE-CIS (`no_target_encoding`) | 0.9063988875252156 | `artifacts/reports/b12_final/b12_native_ieee.json` | `metrics.auc` | FINAL |
| Leakage detected | NO | all three files | `protocol.test_label_leakage = false` and `test_used_for_model_selection = false` | FINAL |
| Old frozen AUC | 0.6285 | legacy external-validation/research artifacts | superseded by clean B12 | OBSOLETE / PROVISIONAL |
| Old transfer AUC | 0.6774 | legacy transfer report and active documentation | superseded by clean B12 | OBSOLETE / PROVISIONAL |
| Old native AUC | 0.8415 | legacy 42-feature native benchmark | not the final 328-feature native B12 benchmark | OBSOLETE / PROVISIONAL |

Interpretation: B12 assesses transferability under domain shift. The low frozen and adapted results do **not** support a claim that the PaySim model generalizes well to IEEE-CIS.

## 14. Implementation environment (B13 final)

| Setting | Final value | Source artifact | Field | Status |
|---|---|---|---|---|
| OS | Linux 6.17.0-20-generic x86_64 (glibc 2.39) | `B13_IMPLEMENTATION_REVIEW/b13_environment.json` | `final_environment.operating_system` | FINAL |
| Python | 3.12.3 | same | `final_environment.python_version` | FINAL |
| CPU | AMD Ryzen 7 7435HS; 8 physical / 16 logical cores | same | `final_environment.cpu_model/physical_cores/logical_cores` | FINAL |
| RAM | 16 GB installed; 15.304630279541016 GiB OS-reported | same | `final_environment.ram_total_gib` | FINAL |
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU available; not used by XGBoost | same | `final_environment.gpu` | FINAL |
| XGBoost | 3.2.0; CPU; `tree_method=hist`; `n_jobs=4` | same | `xgboost_execution` | FINAL |
| Redis required for full online pipeline | YES | same | `redis.production_full_online_pipeline_requires_redis` | FINAL |
| Redis required for B11 research benchmark | NO | same | `redis.b11_latency_includes_redis_or_network` | FINAL |
| External LLM required for reported experiments | NO | same | `external_llm.required_for_paysim_reported_classifier_results` and deterministic replay field | FINAL |

Python 3.13.2 and Windows 11/WSL remain old environment descriptions, not the final B11/B12 execution environment.

## 15. Artifact integrity references

| Artifact | SHA-256 |
|---|---|
| `artifacts/reports/evaluation_report.json` | `b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4` |
| `artifacts/reports/baseline_comparison.json` | `4e2b248b742e17a480f8e0b0f18d34173061f31a2a6ee16d018c54649f2d6f43` |
| `artifacts/reports/b8_final/feature_ablation_b8.json` | `e1ec71ebed71e71107234d44cc4e31f08127bf970190a31ae1d82b9f177c01d9` |
| `artifacts/reports/b8_final/medium_branch_ablation_b8.json` | `e985779737da22ed1a27631746492ab37e770d103e0a9f536e143ffe880bd803` |
| `artifacts/reports/b9_final/b9_repeated_seed_robustness.json` | `4af1ab990a75846bc47a3149337ba57ad7e33cfc7b4a9d5ce1dfef8b8e90e3bb` |
| `artifacts/reports/b10_final/b10_bootstrap_ci.json` | `717f2b83905bd7ee818319c7f17e4bd1c5eff01ae23b09ea8a553d826dde73a8` |
| `artifacts/reports/b11_final/b11_training_time.json` | `7ea49b0a88a5bc972f4581905b85b7364802a828c009746528850b5d75da9062` |
| `artifacts/reports/b11_final/b11_latency_components.json` | `30ac5a55fe158e1a817f64865952f9d8f23761eaca62245a289d8b49c469715f` |
| `artifacts/reports/b12_final/b12_comparison.csv` | `253d7415788fdbc1b1cc5afb0d8f84aa9d2f1ed8b6027d989227cc2d2869947f` |
| `B13_IMPLEMENTATION_REVIEW/b13_environment.json` | `a28f37e9f8fbf6f73cc1a20bc4d9c199d0cd055f6452f3090fdad7e5ff59c62c` |

The worktree was dirty before B14. No clean-checkout claim is made.
