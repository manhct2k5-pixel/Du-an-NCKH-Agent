# B9 Final Audit

Experiment meaning: **stochastic robustness of the fixed deployed XGBoost configuration**.

## Required Confirmations

```ini
seed 42 threshold = 0.50
seed 43 threshold = 0.50
seed 44 threshold = 0.50

same dataset = YES
same split = YES
same 25 features = YES
same hyperparameters = YES
same threshold = YES
only random seed changed = YES
candidate search rerun = NO
test used for selection = NO
leakage detected = NO
```

Evidence: all three models use the same in-memory train/test matrices from one PaySim dataset build, the same ordered 25-feature list, the same training-derived class weight, the same fixed configuration, and threshold 0.50. Only `random_state` changes among 42, 43, and 44. Test labels are accessed only after fitting, solely to compute final test metrics and confusion matrices.

Leakage control is inherited from the production dataset builder: rows are sorted chronologically by `step`; features are built after splitting; historical fraud-rate state learns labels only on training rows and is frozen for validation/test rows (`freeze_risk_labels=True`).

## Dataset and Split

- Dataset: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv`
- Dataset SHA-256: `437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498`
- Total/train/validation/test: 460394 / 322275 / 69059 / 69060
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Feature count: 25
- Training labels: positive=429, negative=321846
- Computed `scale_pos_weight`: 750.2237762237762

## Threshold and B9/B10 Boundary

The repeated-seed experiment fixes threshold 0.50 and performs no threshold selection. The copied table is validation-only threshold sensitivity. Validation F1 is tied from 0.35 through 0.70, so 0.50 is retained as the tie-preserving production default. HistGradientBoosting repeated seeds, best-baseline-by-test-AUC selection, bootstrap confidence intervals, McNemar tests, and IEEE-CIS are not run or reported for B9 final.

## Provenance

- `generated_at`: `2026-10-10T15:54:18.058476+00:00`
- `git_commit`: `8ad06aff01a5932d94436df9e34f7fca820c9fea`
- `git_dirty`: `true`
- `dataset_sha256`: `437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498`
- `code_sha256`: `a93c1bbd68a76f227155bc34d32b7e3ec7958832dd186010591a7db6123dbea4`

Per-file code hashes are recorded in `b9_repeated_seed_robustness.json`.

```ini
B9_STATUS = PASS
```
