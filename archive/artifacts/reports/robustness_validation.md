# Robustness Validation

- Source: `paysim`
- Seeds: `[42, 43, 44]`
- Bootstrap iterations: `300`
- Best single-seed baseline: `hist_gradient_boosting`

| Model | Seeds | AUC mean+/-std | F1 mean+/-std | Precision mean+/-std | Recall mean+/-std | PR AUC mean+/-std |
| --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosting | 42,43,44 | 0.9999 +/- 0.0000 | 0.9969 +/- 0.0013 | 1.0000 +/- 0.0000 | 0.9938 +/- 0.0025 | 0.9974 +/- 0.0009 |
| xgboost | 42,43,44 | 0.9986 +/- 0.0002 | 0.9921 +/- 0.0010 | 0.9888 +/- 0.0007 | 0.9954 +/- 0.0013 | 0.9972 +/- 0.0002 |

## XGBoost 95% Bootstrap CI

- AUC: `0.995236` to `1.000000`
- F1: `0.989130` to `0.996811`
- Precision: `0.982163` to `0.995663`
- Recall: `0.992870` to `1.000000`

## McNemar Test vs hist_gradient_boosting

- better_for_xgboost: `2`
- better_for_baseline: `7`
- discordant: `9`
- chi_square: `1.777778`
- p_value: `0.182422`

## hist_gradient_boosting 95% Bootstrap CI

- AUC: `0.999827` to `1.000000`
- F1: `0.993251` to `0.999257`