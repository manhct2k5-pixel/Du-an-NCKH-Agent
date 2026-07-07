# Fraud Model Evaluation Report

- Source: `paysim`
- Data path: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv`
- Identity path: `N/A`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Random seed: `42`
- Selected threshold: `0.5`

## Split Summary

- Total rows: 460394
- Train rows: 322275
- Validation rows: 69059
- Test rows: 69060

## Validation Metrics

- AUC: 0.999413
- PR AUC: 0.961260
- F1: 0.960000
- Precision: 0.967742
- Recall: 0.952381
- Confusion matrix: TN=68994, FP=2, FN=3, TP=60

## Test Metrics

- AUC: 0.998383
- PR AUC: 0.997002
- F1: 0.993103
- Precision: 0.989313
- Recall: 0.996923
- Confusion matrix: TN=68403, FP=7, FN=2, TP=648

## Curve Artifacts

- Validation ROC: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/validation_roc_curve.csv`
- Validation PR: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/validation_pr_curve.csv`
- Test ROC: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/test_roc_curve.csv`
- Test PR: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/test_pr_curve.csv`
- Threshold sweep: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/validation_threshold_sweep.csv`

## Anomaly Sidecar

- Model: `IsolationForest`
- Adaptive flag threshold: `0.41828539293549033`
- Threshold method: `percentile_95_val`
- Validation flags: total=3453, fraud=22, legit=3431
- Test flags: total=4866, fraud=344, legit=4522