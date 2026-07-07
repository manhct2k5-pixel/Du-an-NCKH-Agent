# Research Experiment Suite

- Source: `paysim`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Total rows: `20000`

## Dataset Strategy

- PaySim is the primary dataset for architecture performance: training, routing, agent replay, and monitoring/deploy flow.
- IEEE-CIS is the external validation dataset for out-of-distribution evidence against overfitting on PaySim.

## Best Baseline

- Model: `hist_gradient_boosting`
- Test AUC: `0.999916`
- Test F1: `0.923077`
- Test PR AUC: `0.992857`

## Best Feature Configuration

- Ablation: `no_llm_analysis`
- Test AUC: `0.999892`
- Test F1: `0.947368`
- LLM feature delta vs no-LLM: AUC `-0.001478`, F1 `+0.016917`

## Best Medium-Branch Policy

- Policy: `score_threshold_block`
- Block F1: `0.964286`
- Block Recall: `0.964286`
- Review Rate: `0.000000`

## Robustness

- Multi-seed best mean AUC model: `hist_gradient_boosting`
- Mean test AUC: `0.999934` +/- `0.000018`
- Mean test F1: `0.878205` +/- `0.044872`
- XGBoost 95% AUC CI: `0.996186` to `1.000000`
- McNemar p-value vs best baseline: `0.617075`

## External Validation

- External source: `ieee`
- Validation mode: `frozen_vs_native_benchmark`
- IEEE-native XGBoost AUC: `0.793419` (trained on IEEE-CIS train split, 42 native features)
- Frozen PaySim AUC on IEEE-CIS: `0.530616` (cross-dataset, expected lower due to distribution shift)

## Artifacts

- Baseline comparison: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_20000/research/reports/baseline_comparison.json`
- Feature ablation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_20000/research/reports/feature_ablation.json`
- Medium branch ablation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_20000/research/reports/medium_branch_ablation.json`
- Robustness validation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_20000/research/reports/robustness_validation.json`
- External validation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/experiments/sample_20000/research/reports/external_validation.json`