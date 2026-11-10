# B10 Final Audit

```ini
production model loaded = YES
model retrained = NO
test probability vector fixed = YES
production metrics reproduced = YES
test rows = 69060
fraud rows = 650
legitimate rows = 68410
threshold = 0.50
bootstrap type = stratified nonparametric bootstrap
bootstrap iterations = 2000
bootstrap random seed = 42
model refit inside bootstrap = NO
percentile CI = YES
B9 SD kept separate from bootstrap uncertainty = YES
McNemar final use = NO
```

The production model was loaded from the persisted XGBoost JSON. Test probabilities were generated once, hashed, and then held fixed. Each bootstrap replicate resampled 650 fraud and 68,410 legitimate test indices with replacement and applied identical multiplicities to labels and probabilities.

CI interpretation: **nonparametric stratified percentile bootstrap confidence intervals conditional on the fixed fitted production model and the observed held-out test-set class composition**.

B9 mean+/-SD remains across-seed stochastic variation. B10 bootstrap intervals remain held-out test-sample uncertainty conditional on one fitted model. They are not combined.

No baseline model, IEEE-CIS model, training pipeline, candidate search, latency benchmark, McNemar test, or p-value was run.

```ini
B10_STATUS = PASS
```
