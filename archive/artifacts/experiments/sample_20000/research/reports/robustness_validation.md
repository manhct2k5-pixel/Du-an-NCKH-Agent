# Robustness Validation

- Source: `paysim`
- Seeds: `[42, 43]`
- Bootstrap iterations: `25`
- Best single-seed baseline: `hist_gradient_boosting`

| Model | Seeds | AUC mean+/-std | F1 mean+/-std | Precision mean+/-std | Recall mean+/-std | PR AUC mean+/-std |
| --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | 42,43 | 0.9999 +/- 0.0000 | 0.8782 +/- 0.0449 | 1.0000 +/- 0.0000 | 0.7857 +/- 0.0714 | 0.9942 +/- 0.0013 |
| xgboost | 42,43 | 0.9988 +/- 0.0004 | 0.9643 +/- 0.0000 | 0.9643 +/- 0.0000 | 0.9643 +/- 0.0000 | 0.9730 +/- 0.0025 |

## XGBoost 95% Bootstrap CI

- AUC: `0.996186` to `1.000000`
- F1: `0.932093` to `1.000000`
- Precision: `0.909091` to `1.000000`
- Recall: `0.912467` to `1.000000`

## McNemar Test vs hist_gradient_boosting

- better_for_xgboost: `3`
- better_for_baseline: `1`
- discordant: `4`
- chi_square: `0.25`
- p_value: `0.617075`

## hist_gradient_boosting 95% Bootstrap CI

- AUC: `0.999659` to `1.000000`
- F1: `0.843697` to `0.965710`