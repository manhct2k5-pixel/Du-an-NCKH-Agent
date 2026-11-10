# Research Experiment Suite

- Source: `paysim`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Total rows: `3000`

## Dataset Strategy

- PaySim is the primary dataset for architecture performance: training, routing, agent replay, and monitoring/deploy flow.
- IEEE-CIS is the external validation dataset for out-of-distribution evidence against overfitting on PaySim.

## Best Baseline

- Model: `hist_gradient_boosting`
- Test AUC: `1.000000`
- Test F1: `1.000000`
- Test PR AUC: `1.000000`

## Best Feature Configuration

- Ablation: `full_feature_set`
- Test AUC: `1.000000`
- Test F1: `0.833333`
- LLM feature delta vs no-LLM: AUC `+0.000449`, F1 `+0.064103`

## Best Medium-Branch Policy

- Policy: `score_threshold_block`
- Block F1: `0.833333`
- Block Recall: `1.000000`
- Review Rate: `0.000000`

## Robustness

- Multi-seed best mean AUC model: `hist_gradient_boosting`
- Mean test AUC: `1.000000` +/- `0.000000`
- Mean test F1: `1.000000` +/- `0.000000`
- XGBoost 95% AUC CI: `1.000000` to `1.000000`
- McNemar p-value vs best baseline: `0.4795`

## External Validation

- External source: `ieee`
- External validation mode: `frozen_model_external_validation`
- Best external model: `xgboost_frozen_paysim` with external AUC `0.499190`

## Artifacts

- Baseline comparison: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_3000/research/reports/baseline_comparison.json`
- Feature ablation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_3000/research/reports/feature_ablation.json`
- Medium branch ablation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_3000/research/reports/medium_branch_ablation.json`
- Robustness validation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_3000/research/reports/robustness_validation.json`
- External validation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_3000/research/reports/external_validation.json`