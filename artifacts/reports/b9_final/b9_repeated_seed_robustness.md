# B9 Repeated-seed Robustness

Experiment meaning: **stochastic robustness of the fixed deployed XGBoost configuration**.

This is not a robustness test of the hyperparameter-search pipeline. No candidate search, HistGradientBoosting repeated seeds, baseline selection, bootstrap CI, McNemar test, or IEEE-CIS experiment is used.

## Protocol

- Dataset: `PaySim` (`/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv`)
- Dataset SHA-256: `437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498`
- Split: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Rows: total=460394, train=322275, validation=69059, test=69060
- Features: 25 fixed PaySim features
- Seeds: 42, 43, 44
- Fixed threshold: 0.5
- Training-derived `scale_pos_weight`: 750.2237762237762
- Historical fraud-rate state: trained on train labels, then frozen for validation/test labels

## Fixed XGBoost Configuration

| Parameter | Value |
| --- | ---: |
| n_estimators | 260 |
| max_depth | 6 |
| learning_rate | 0.06 |
| subsample | 0.9 |
| colsample_bytree | 0.85 |
| max_delta_step | 1 |
| tree_method | hist |

## Per-seed Test Results

| Seed | Threshold | Test AUC | Test PR-AUC | Test F1 | Precision | Recall | TN | FP | FN | TP |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 42 | 0.5 | 0.9983827150776428 | 0.9970017406400512 | 0.993103448275862 | 0.9893129770992366 | 0.9969230769230769 | 68403 | 7 | 2 | 648 |
| 43 | 0.5 | 0.9987623266953773 | 0.9970987605238817 | 0.9900687547746372 | 0.9833080424886191 | 0.9969230769230769 | 68399 | 11 | 2 | 648 |
| 44 | 0.5 | 0.9988008051004689 | 0.9975486999259158 | 0.9908256880733946 | 0.9848024316109423 | 0.9969230769230769 | 68400 | 10 | 2 | 648 |

## Across-seed Summary

Population standard deviation (`ddof=0`) is reported over the three requested seeds.

| Metric | Mean | Standard deviation | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| AUC | 0.9986486156244964 | 0.00018867515739557264 | 0.9983827150776428 | 0.9988008051004689 |
| PR-AUC | 0.9972164003632829 | 0.00023828619201725262 | 0.9970017406400512 | 0.9975486999259158 |
| F1 | 0.9913326303746312 | 0.0012897245272231583 | 0.9900687547746372 | 0.993103448275862 |
| Precision | 0.985807817066266 | 0.002552503327425876 | 0.9833080424886191 | 0.9893129770992366 |
| Recall | 0.9969230769230769 | 0.0 | 0.9969230769230769 | 0.9969230769230769 |

## Threshold Sensitivity

`b9_threshold_sensitivity.csv` is a byte-for-byte copy of the existing production validation threshold sweep. This is **validation-only threshold sensitivity**. Validation F1 is tied on a plateau from 0.35 through 0.70, so 0.50 is retained as the tie-preserving production default. The held-out test set was not used to select the B9 threshold.

## Provenance

- `generated_at`: `2026-10-10T15:54:18.058476+00:00`
- `git_commit`: `8ad06aff01a5932d94436df9e34f7fca820c9fea`
- `git_dirty`: `true`
- `dataset_sha256`: `437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498`
- `code_sha256`: `a93c1bbd68a76f227155bc34d32b7e3ec7958832dd186010591a7db6123dbea4`
- `validation_threshold_sweep_sha256`: `39c2146681dfc9601a10738ba66605d0b18b86f399b26e759297df5dedd7421e`
