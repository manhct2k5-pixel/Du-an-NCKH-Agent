# Robustness Validation

- Source: `paysim`
- Seeds: `[42]`
- Bootstrap iterations: `10`
- Best single-seed baseline: `hist_gradient_boosting`

| Model | Seeds | AUC mean+/-std | F1 mean+/-std | Precision mean+/-std | Recall mean+/-std | PR AUC mean+/-std |
| --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | 42 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 |
| xgboost | 42 | 1.0000 +/- 0.0000 | 0.8333 +/- 0.0000 | 0.7143 +/- 0.0000 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 |

## XGBoost 95% Bootstrap CI

- AUC: `1.000000` to `1.000000`
- F1: `0.516071` to `0.897403`
- Precision: `0.348333` to `0.814583`
- Recall: `1.000000` to `1.000000`

## McNemar Test vs hist_gradient_boosting

- better_for_xgboost: `0`
- better_for_baseline: `2`
- discordant: `2`
- chi_square: `0.5`
- p_value: `0.4795`

## hist_gradient_boosting 95% Bootstrap CI

- AUC: `1.000000` to `1.000000`
- F1: `1.000000` to `1.000000`