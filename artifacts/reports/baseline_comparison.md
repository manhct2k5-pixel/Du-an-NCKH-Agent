# Baseline Comparison

- Source: `paysim`
- Random seed: `42`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`

| Model | Family | Threshold | Val AUC | Test AUC | Test PR AUC | Test F1 | Precision | Recall | Train s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | HistGradientBoostingClassifier | 0.5 | 0.9928 | 0.9999 | 0.9978 | 0.9969 | 1.0000 | 0.9938 | 0.79 |
| random_forest | RandomForestClassifier | 0.5 | 0.9995 | 0.9998 | 0.9975 | 0.9954 | 0.9969 | 0.9938 | 15.73 |
| xgboost | XGBClassifier | 0.5 | 0.9994 | 0.9984 | 0.9970 | 0.9931 | 0.9893 | 0.9969 | 8.19 |
| logistic_regression | LogisticRegression | 0.7 | 0.9895 | 0.9964 | 0.8844 | 0.4857 | 0.3255 | 0.9569 | 3.01 |
| dummy_prior | DummyClassifier | 0.5 | 0.5000 | 0.5000 | 0.0094 | 0.0000 | 0.0000 | 0.0000 | 0.02 |