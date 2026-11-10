# External Validation — IEEE-CIS Dual Benchmark

- Source: `ieee`
- Data path: `data/train_transaction.csv`
- Alignment method: `semantic_proxy_with_mfield_balance_diff`
- Frozen eval rows: `590540`
- Native train / val / test: `413378` / `88581` / `88581`

## Benchmark legend

| Model | Description |
| --- | --- |
| `xgboost_ieee_retrained` | XGBoost trained from scratch on 70% IEEE-CIS (42 native features, chronological split) |
| `xgboost_frozen_paysim` | PaySim-trained weights frozen, applied to IEEE-CIS via semantic feature alignment |

| Model | Family | Test AUC | PR AUC | F1 | Precision | Recall | Mode |
| --- | --- | --- | --- | --- | --- | --- | --- |
| xgboost_ieee_retrained | XGBClassifier | 0.8415 | 0.3262 | 0.3328 | 0.2553 | 0.4781 | native (42 IEEE features) |
| xgboost_frozen_paysim | XGBClassifier | 0.6285 | 0.0532 | 0.0201 | 0.0639 | 0.0120 | frozen (25 PaySim features, aligned) |

## Interpretation

- High `xgboost_ieee_retrained` AUC confirms IEEE-CIS features discriminate fraud when trained in-distribution.
- Lower `xgboost_frozen_paysim` AUC reflects cross-dataset distribution shift — expected: PaySim fraud
  relies on balance-drain patterns; IEEE-CIS fraud relies on card/device fingerprints.
- Improved alignment (M-field balance_diff proxy, velocity-based account proxy) raises frozen AUC
  versus the prior rank-quantile-only projection.