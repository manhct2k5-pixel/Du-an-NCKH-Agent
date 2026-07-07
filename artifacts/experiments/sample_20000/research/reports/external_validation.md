# External Validation — IEEE-CIS Dual Benchmark

- Source: `ieee`
- Data path: `/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/train_transaction.csv`
- Alignment method: `semantic_proxy_with_mfield_balance_diff`
- Frozen eval rows: `20000`
- Native train / val / test: `14000` / `3000` / `3000`

## Benchmark legend

| Model | Description |
| --- | --- |
| `xgboost_ieee_retrained` | XGBoost trained from scratch on 70% IEEE-CIS (42 native features, chronological split) |
| `xgboost_frozen_paysim` | PaySim-trained weights frozen, applied to IEEE-CIS via semantic feature alignment |

| Model | Family | Test AUC | PR AUC | F1 | Precision | Recall | Mode |
| --- | --- | --- | --- | --- | --- | --- | --- |
| xgboost_ieee_retrained | XGBClassifier | 0.7934 | 0.3462 | 0.3889 | 0.4118 | 0.3684 | native (42 IEEE features) |
| xgboost_frozen_paysim | XGBClassifier | 0.5306 | 0.0372 | 0.0117 | 0.0208 | 0.0081 | frozen (25 PaySim features, aligned) |

## Interpretation

- High `xgboost_ieee_retrained` AUC confirms IEEE-CIS features discriminate fraud when trained in-distribution.
- Lower `xgboost_frozen_paysim` AUC reflects cross-dataset distribution shift — expected: PaySim fraud
  relies on balance-drain patterns; IEEE-CIS fraud relies on card/device fingerprints.
- Improved alignment (M-field balance_diff proxy, velocity-based account proxy) raises frozen AUC
  versus the prior rank-quantile-only projection.