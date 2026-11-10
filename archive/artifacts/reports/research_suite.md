# Research Experiment Suite

- Source: `paysim`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Total rows: `460394`

## Dataset Strategy

- PaySim is the primary dataset for architecture performance: training, routing, agent replay, and monitoring/deploy flow.
- IEEE-CIS is the external validation dataset for out-of-distribution evidence against overfitting on PaySim.

## Best Baseline

- Model: `hist_gradient_boosting`
- Test AUC: `0.999932`
- Test F1: `0.996914`
- Test PR AUC: `0.997849`

## Best Feature Configuration

- Ablation: `no_llm_analysis`
- Test AUC: `0.998647`
- Test F1: `0.970432`
- LLM feature delta vs no-LLM: AUC `-0.000264`, F1 `+0.022671`

## Best Medium-Branch Policy

- Policy: `score_threshold_block`
- Block F1: `0.993103`
- Block Recall: `0.996923`
- Review Rate: `0.000000`

## Robustness

- Multi-seed best mean AUC model: `hist_gradient_boosting`
- Mean test AUC: `0.999928` +/- `0.000031`
- Mean test F1: `0.996912` +/- `0.001264`
- XGBoost 95% AUC CI: `0.995236` to `1.000000`
- McNemar p-value vs best baseline: `0.182422`

## External Validation

- External source: `ieee`
- Validation mode: `frozen_vs_native_benchmark`
- IEEE-native XGBoost AUC: `0.841506` (trained on IEEE-CIS train split, 42 native features)
- Frozen PaySim AUC on IEEE-CIS: `0.628517` (cross-dataset, expected lower due to distribution shift)

## Artifacts

- Baseline comparison: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/baseline_comparison.json`
- Feature ablation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/feature_ablation.json`
- Medium branch ablation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/medium_branch_ablation.json`
- Robustness validation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/robustness_validation.json`
- External validation: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/external_validation.json`