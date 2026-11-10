# B10 Final Statistical Validation

CI interpretation: **nonparametric stratified percentile bootstrap confidence intervals conditional on the fixed fitted production model and the observed held-out test-set class composition**.

The intervals do not quantify uncertainty of the training or hyperparameter-selection pipeline.

## Fixed Production Test Result and Bootstrap CI

| Metric | Point estimate | Bootstrap mean | Population SD | 2.5th percentile | 97.5th percentile |
| --- | ---: | ---: | ---: | ---: | ---: |
| AUC | 0.9983827150776428 | 0.9983673266616442 | 0.0015420914359937498 | 0.9952713267291107 | 0.9999996176897215 |
| PR-AUC | 0.9970017406400512 | 0.9969620698564483 | 0.0020904236082865345 | 0.992546899838475 | 0.9999598708634057 |
| F1 | 0.993103448275862 | 0.993161284818031 | 0.0022958233801349814 | 0.9885228961647714 | 0.9969325153374233 |
| Precision | 0.9893129770992366 | 0.9894810269971376 | 0.003852824345287306 | 0.9817351598173516 | 0.9969135802469136 |
| Recall | 0.9969230769230769 | 0.9968784615384616 | 0.002206048168266072 | 0.9923076923076923 | 1.0 |

## B9 Across-seed Results (kept separate)

B9 mean+/-SD is across-seed stochastic variation. B10 bootstrap CI is held-out test-sample uncertainty conditional on one fitted model. These uncertainty sources are not pooled.

| Metric | B9 mean | B9 population SD |
| --- | ---: | ---: |
| AUC | 0.9986486156244964 | 0.00018867515739557264 |
| PR-AUC | 0.9972164003632829 | 0.00023828619201725262 |
| F1 | 0.9913326303746312 | 0.0012897245272231583 |
| Precision | 0.985807817066266 | 0.002552503327425876 |
| Recall | 0.9969230769230769 | 0.0 |

## Protocol

- Bootstrap: stratified nonparametric bootstrap
- Iterations: 2000
- Random seed: 42
- Per replicate: fraud=650, legitimate=68410, total=69060
- CI: empirical percentile, 2.5th and 97.5th percentiles; no normal approximation
- Threshold: 0.50 for F1, precision, and recall
- Model inference calls: 1
- Model refits: 0
- McNemar final use: NO
