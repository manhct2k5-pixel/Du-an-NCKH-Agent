# Baseline Comparison

- Source: `paysim`
- Random seed: `42`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`

| Model | Family | Threshold | Val AUC | Test AUC | Test PR AUC | Test F1 | Precision | Recall | Train s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | HistGradientBoostingClassifier | 0.5 | 1.0000 | 0.9999 | 0.9929 | 0.9231 | 1.0000 | 0.8571 | 0.20 |
| random_forest | RandomForestClassifier | 0.5 | 1.0000 | 0.9994 | 0.9769 | 0.9474 | 0.9310 | 0.9643 | 0.37 |
| xgboost | XGBClassifier | 0.5 | 1.0000 | 0.9984 | 0.9705 | 0.9643 | 0.9643 | 0.9643 | 0.86 |
| logistic_regression | LogisticRegression | 0.7 | 0.9864 | 0.9612 | 0.7645 | 0.3768 | 0.2364 | 0.9286 | 0.07 |
| dummy_prior | DummyClassifier | 0.5 | 0.5000 | 0.5000 | 0.0093 | 0.0000 | 0.0000 | 0.0000 | 0.00 |