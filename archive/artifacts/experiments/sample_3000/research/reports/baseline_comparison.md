# Baseline Comparison

- Source: `paysim`
- Random seed: `42`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`

| Model | Family | Threshold | Val AUC | Test AUC | Test PR AUC | Test F1 | Precision | Recall | Train s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | HistGradientBoostingClassifier | 0.5 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.13 |
| random_forest | RandomForestClassifier | 0.5 | 0.0000 | 1.0000 | 1.0000 | 0.8889 | 1.0000 | 0.8000 | 0.18 |
| xgboost | XGBClassifier | 0.5 | 0.0000 | 1.0000 | 1.0000 | 0.8333 | 0.7143 | 1.0000 | 0.52 |
| logistic_regression | LogisticRegression | 0.5 | 0.0000 | 0.9991 | 0.9429 | 0.3571 | 0.2174 | 1.0000 | 0.01 |
| dummy_prior | DummyClassifier | 0.5 | 0.0000 | 0.5000 | 0.0111 | 0.0000 | 0.0000 | 0.0000 | 0.00 |