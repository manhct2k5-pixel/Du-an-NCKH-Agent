# External Validation

- Validation mode: `frozen_model_external_validation`
- External source: `ieee`
- Data path: `data/train_transaction.csv`
- Identity path: `data/train_identity.csv`
- Split strategy: `external_all_rows_no_ieee_fit`
- Random seed: `42`
- Purpose: `out-of-distribution check against overfitting on the primary dataset`
- Freeze protocol: `PaySim model weights and threshold are reused; IEEE-CIS labels are used only for final metrics.`
- Feature alignment: `rank_quantile_projection_to_paysim_train_distribution`

| Model | Family | Test AUC | Test PR AUC | Test F1 | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| xgboost_frozen_paysim | XGBClassifier | 0.4992 | 0.0361 | 0.0000 | 0.0000 | 0.0000 |