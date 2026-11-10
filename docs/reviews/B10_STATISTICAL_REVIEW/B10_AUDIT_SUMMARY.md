# B10 Statistical Validation Audit

## Scope and decision

This is a read-only audit of existing code and artifacts. No XGBoost or baseline model was trained, no bootstrap was executed, no new p-value was calculated, and B1-B9, IEEE-CIS, latency tests, and the manuscript were not run or modified.

The B9 fixed-configuration mean +/- population SD is valid for reuse in B10. The existing 300-replicate bootstrap is mathematically valid as an ordinary, row-level, nonparametric percentile bootstrap conditional on one already-fitted XGBoost model. It is not sufficient as the final B10 artifact because 300 replicates give weak resolution at the 2.5% and 97.5% tails, the sampling is not class-stratified, and the artifact omits important provenance. A dedicated bootstrap-only rerun is therefore required; model retraining is not required.

```ini
B9 mean±SD valid for B10 = YES
current bootstrap CI valid = YES
bootstrap iterations sufficient = NO
stratified bootstrap recommended = YES
McNemar suitable for final paper = NO
model retraining required = NO
bootstrap-only rerun required = YES
B10_RERUN_REQUIRED = YES
```

`current bootstrap CI valid = YES` means that the current intervals pass the implementation and numerical checks for the limited interpretation stated above. It does not mean that the 300-replicate artifact has enough Monte Carlo resolution or provenance for final-paper use.

## Evidence inventory

| Evidence | Audit role |
| --- | --- |
| `artifacts/reports/b9_final/b9_repeated_seed_robustness.json` | Fixed-configuration seed runs, protocol, parameters, threshold, provenance, and mean/SD summary |
| `artifacts/reports/b9_final/b9_repeated_seed_robustness.csv` | Independent row-level source for recomputing the five B9 summary metrics |
| `artifacts/reports/b9_final/B9_FINAL_AUDIT.md` | B9 protocol confirmations |
| `artifacts/reports/robustness_validation.json` | Existing 300-replicate bootstrap intervals and McNemar result |
| `artifacts/reports/robustness_validation.csv` and `.md` | Existing summarized statistical-validation presentation |
| `artifacts/reports/research_suite.json` | Split context and object-equivalent robustness payload |
| `artifacts/reports/evaluation_report.json` | Production point estimates, threshold, feature list, model parameters, split, and class counts |
| `fraud_flow/research.py` | Bootstrap, McNemar, baseline-selection, and robustness orchestration logic |
| `fraud_flow/training.py` and `fraud_flow/config.py` | Metric definitions, split protocol, defaults, and bootstrap-iteration configuration |
| `run_fraud_flow.py` | CLI entry point that invokes the research suite |
| `scripts/run_b9_robustness.py` | Generator of the fixed-configuration B9 artifact |
| `tests/test_research_statistics.py` | Existing unit checks for ordered bootstrap bounds and McNemar behavior |

## B9 mean +/- population SD

Protocol checks from the B9 final run:

```ini
seeds = 42, 43, 44
same dataset = YES
same chronological split = YES
same 25 features = YES
same fixed production hyperparameters = YES
seed 42 threshold = 0.50
seed 43 threshold = 0.50
seed 44 threshold = 0.50
only random_state changed = YES
```

The raw three-seed values were read again and recomputed with population standard deviation (`ddof=0`), rather than accepting the stored summary. Every recomputed value exactly matches the B9 JSON summary.

| Metric | Recomputed mean | Recomputed population SD | Min | Max | Stored summary match |
| --- | ---: | ---: | ---: | ---: | --- |
| AUC | 0.9986486156244964 | 0.00018867515739557264 | 0.9983827150776428 | 0.9988008051004689 | YES |
| PR-AUC | 0.9972164003632829 | 0.00023828619201725262 | 0.9970017406400512 | 0.9975486999259158 | YES |
| F1 | 0.9913326303746312 | 0.0012897245272231583 | 0.9900687547746372 | 0.993103448275862 | YES |
| Precision | 0.985807817066266 | 0.002552503327425876 | 0.9833080424886191 | 0.9893129770992366 | YES |
| Recall | 0.9969230769230769 | 0.0 | 0.9969230769230769 | 0.9969230769230769 | YES |

These statistics measure stochastic variation across three fits of one fixed XGBoost configuration. They do not measure test-set sampling uncertainty.

## Existing bootstrap implementation

| Item | Audited value |
| --- | --- |
| Bootstrap unit | One held-out test row represented by the paired values `(y_i, probability_i)` |
| Sampling | Ordinary row bootstrap: sample 69,060 row indices independently with replacement |
| Bootstrap iterations | 300 |
| Bootstrap random seed | 42, inferred from `resolved_seeds[0]`; not explicitly recorded in the artifact |
| CI method | Nonparametric percentile bootstrap using empirical 2.5th and 97.5th percentiles |
| Metrics | AUC, PR-AUC, F1, precision, recall |
| Classification threshold | 0.50 for the audited XGBoost probabilities |
| Prediction source | `xgb_artifact.test_proba`, generated once before entering the bootstrap function |
| Label source | Held-out test labels, `splits.y_test` |
| Test-set size | 69,060 rows: 650 fraud and 68,410 legitimate |
| Retraining inside an iteration | NO |

For each iteration, `bootstrap_confidence_intervals()` samples indices, applies those indices to the fixed test labels and fixed probability vector, and recomputes metrics. It contains no model construction, fit, tuning, or inference call. The correct interpretation is therefore:

> nonparametric bootstrap confidence intervals conditional on the fitted production model

The phrase above must not be interpreted as uncertainty of the full training or model-selection process.

### Prediction-source qualification

The probability vector is fixed throughout bootstrap. It comes from the XGBoost artifact created earlier in the same research-suite run, after validation-based candidate selection. The five point metrics and threshold exactly match both the production evaluation report and B9 seed 42. This strongly supports numerical consistency with the production configuration.

However, the old robustness artifact does not record model parameters, a model hash, or a hash/path for the per-row prediction vector. The code path also creates the artifact through `fit_best_xgboost()` rather than loading a named frozen deployed model. Exact production-model identity is therefore consistent but not independently provable from the old bootstrap artifact alone.

## Existing confidence intervals

The point estimate is the fixed seed-42 production-model test result at threshold 0.50. The bootstrap block itself does not repeat the point estimate, so it was cross-checked against `evaluation_report.json`, the seed-42 robustness run, and B9 final.

| Metric | Point estimate | Bootstrap mean | Bootstrap SD | 2.5th percentile | 97.5th percentile | Point inside CI | Bounds in [0,1] |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| AUC | 0.9983827150776428 | 0.998521 | 0.001411 | 0.995236 | 1.0 | YES | YES |
| PR-AUC | 0.9970017406400512 | 0.997184 | 0.001865 | 0.993166 | 0.99995 | YES | YES |
| F1 | 0.993103448275862 | 0.993245 | 0.002095 | 0.98913 | 0.996811 | YES | YES |
| Precision | 0.9893129770992366 | 0.989416 | 0.003791 | 0.982163 | 0.995663 | YES | YES |
| Recall | 0.9969230769230769 | 0.997113 | 0.001971 | 0.99287 | 1.0 | YES | YES |

All interval-order and domain checks pass. The JSON stores values rounded to six decimals.

## Are 300 iterations sufficient?

No, not for the final-paper artifact. It is adequate for an exploratory implementation check, but weak for final percentile endpoints:

- At 300 replicates, each 2.5% tail is represented by only 7.5 expected order positions. The binomial Monte Carlo standard error of an empirical 2.5% tail probability is approximately `sqrt(0.025 * 0.975 / 300) = 0.009014`.
- At 1,000 replicates, the tail has 25 expected order positions and the corresponding value falls to approximately `0.004937`.
- At 2,000 replicates, the tail has 50 expected order positions and the corresponding value falls to approximately `0.003491`.

Because bootstrapping stored/fixed predictions is inexpensive compared with training, the recommended final setting is **2,000 stratified replicates**, with **1,000 as the minimum acceptable setting**. Increasing iterations improves Monte Carlo stability; it does not correct dataset shift, model-selection uncertainty, or dependence between transactions.

```ini
current iterations = 300
minimum acceptable final iterations = 1000
recommended final iterations = 2000
bootstrap iterations sufficient = NO
```

## Severe class imbalance and bootstrap design

The held-out test set has 650 fraud and 68,410 legitimate rows, for a fraud prevalence of `0.009412105415580654`. The current implementation samples all rows together, so it is an **ordinary row bootstrap**, not a stratified bootstrap.

Under ordinary row resampling, the fraud count per replicate is approximately binomial with mean 650 and standard deviation `25.374832639445575`. A no-fraud replicate is effectively impossible here (approximately `2.35e-284`), so ordinary resampling is not numerically invalid. Its replicate-to-replicate class prevalence nevertheless varies, which adds prevalence variation to PR-AUC, precision, recall, and F1.

A stratified bootstrap is recommended for the final B10 presentation because the desired comparison is conditional on this fixed benchmark test composition. Each replicate should independently resample 650 fraud rows and 68,410 legitimate rows with replacement, concatenate them, and evaluate the same fixed probability vector at threshold 0.50. This keeps the severe imbalance structure constant and makes interval comparisons more stable. The resulting intervals must be described as conditional on the observed class composition; stratification should not be claimed to estimate population-prevalence uncertainty.

```ini
current bootstrap type = ordinary row bootstrap
stratified bootstrap recommended = YES
```

## McNemar audit

`run_robustness_validation()` chooses the comparator with:

```python
best_baseline_artifact = max(
    baseline_candidates,
    key=lambda item: (
        item.report["test"]["metrics"]["auc"],
        item.report["test"]["metrics"]["f1"],
    ),
)
```

The same held-out test set is first used to select `hist_gradient_boosting` and is then used for McNemar inference. This is post-hoc comparator selection and invalidates a confirmatory claim such as "statistically significantly better than the best baseline." The existing p-value (`0.182422`) is copied only as provenance and must not be used for a final inferential claim. No new p-value was calculated in this audit.

```ini
MCNEMAR_FINAL_USE = NO
```

B10 does not need a p-value if the reviewer requirement is satisfied by fixed-seed mean +/- SD plus clearly scoped 95% bootstrap confidence intervals.

## Separation of B9 and B10

| Section | Statistical object | Interpretation |
| --- | --- | --- |
| B9 | Fixed-configuration repeated-seed robustness; validation-only threshold sensitivity | Stochastic variation caused by changing `random_state` while data, features, hyperparameters, and threshold stay fixed |
| B10 | B9 mean +/- SD; 95% bootstrap CI of fixed production-model held-out test metrics | Test-sample uncertainty conditional on one fitted model, reported separately from across-seed variation |

The two uncertainty sources must not be pooled into one SD or one confidence interval.

## Provenance audit

| Required field | Existing bootstrap artifact | Audit result |
| --- | --- | --- |
| `generated_at` | Missing | Must be added in dedicated B10 output |
| `git_commit` | Missing | Must be added |
| `git_dirty` | Missing | Must be added |
| Dataset SHA-256 | Missing | Must be added |
| Code SHA-256 | Missing | Must be added |
| Test row count | Missing in standalone robustness JSON; available indirectly as 69,060 in `research_suite.json` and `evaluation_report.json` | Must be explicit in B10 output |
| Model parameters | Missing in robustness JSON; available indirectly in evaluation/B9 artifacts | Must be explicit in B10 output |
| Classification threshold | 0.50 is recoverable from the XGBoost seed-42 run, but not attached explicitly to the CI block | Must be explicit in B10 output |
| Bootstrap iterations | Present: 300 | Pass, but insufficient for final use |
| Bootstrap random seed | Missing; 42 is inferred from code | Must be explicit in B10 output |

The robustness object in `research_suite.json` is identical to `robustness_validation.json`. The bootstrap point estimates match the production evaluation and B9 seed 42, but cross-file consistency does not replace direct provenance.

## Exact rerun required

Only the following dedicated B10 work is required:

1. Obtain one probability vector for the existing fixed production XGBoost model on the unchanged 69,060-row held-out test set. Load the persisted model or reuse a securely saved prediction vector; do not fit or tune a model.
2. Verify and record the model parameters/hash, ordered test-row identity or test-data hash, probability-vector hash, threshold 0.50, test class counts, code hash, git state, and bootstrap seed.
3. Run 2,000 class-stratified nonparametric bootstrap replicates on paired held-out labels and fixed probabilities.
4. Export the point estimate, bootstrap mean, population bootstrap SD, and percentile 2.5%/97.5% endpoints for AUC, PR-AUC, F1, precision, and recall.
5. Keep B9 across-seed mean +/- SD separate and omit McNemar from final inference.

No XGBoost retraining, candidate search, baseline training/selection, IEEE-CIS run, B1-B9 rerun, latency benchmark, or new p-value is required.
