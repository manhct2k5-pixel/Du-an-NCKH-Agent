# B12 — IEEE-CIS External Validation Audit Summary

Audit date: 2026-10-11 (Asia/Vientiane)

## Executive verdict

All three result families are present, and their reported precision/recall/F1 values are internally consistent with their confusion matrices. They are **not all manuscript-ready**:

- The frozen artifact is a real no-IEEE-fit evaluation, but it evaluates an in-memory PaySim model refit by the research suite, not a model loaded from the production artifact.
- The transfer artifact has test-label leakage in feature construction because `build_dataset(source="ieee")` is executed before the special 10/90 transfer split.
- The native optimized artifact is structurally a full-data, non-quick run, but it lacks an embedded run manifest/provenance and its final feature-profile selection is not cleanly separated from test-visible ablation reporting.

The defensible interpretation is: **external validation assesses transferability under domain shift**. The current frozen result is evidence of substantial PaySim→IEEE schema/domain shift; it is not evidence that the PaySim model generalizes well.

```ini
B12_RERUN_REQUIRED = YES
B12_RERUN_SCOPE = all IEEE-CIS experiments
```

## 1. Frozen PaySim → IEEE-CIS

### What the artifact reports

| Field | Audited value |
|---|---:|
| IEEE evaluation rows | 590,540 |
| Feature count | 25 PaySim-schema features |
| Threshold | 0.50 |
| AUC | 0.6285168245 |
| PR-AUC | 0.0531529294 |
| F1 | 0.0201402479 |
| Precision | 0.0639068564 |
| Recall | 0.0119537337 |
| Confusion matrix | TN 566,259; FP 3,618; FN 20,416; TP 247 |

### Model identity and freezing

`run_research_suite()` first fits a PaySim XGBoost through `run_baseline_comparison()` and passes the resulting in-memory `xgb_artifact` to `run_external_validation()`. The latter does not fit that model on IEEE labels, so it is frozen **with respect to IEEE-CIS**, but it does not load `artifacts/models/xgboost_fraud.json`.

Therefore:

```ini
PRODUCTION_PAYSIM_MODEL_LOADED = NO
PAYSIM_MODEL_REFIT_IN_RESEARCH_RUN = YES
IEEE_MODEL_RETRAINED_FOR_FROZEN_ARM = NO
```

File times reinforce this reading: `external_validation.json` is dated 2026-04-24 14:40:44 +07, while the current production model file is dated 14:41:23. The external artifact cannot establish that it evaluated that later file.

The PaySim in-memory model used 322,275 PaySim training rows. Its candidate and threshold selection came from the 69,059-row PaySim validation split; IEEE labels were consumed after prediction for metric calculation only. The IEEE feature values are nevertheless processed as a complete batch for rank/quantile projection, making the alignment transductive at the covariate level, though not label-driven.

### Feature alignment

The mapping is `semantic_proxy_with_mfield_balance_diff`. It is approximate domain mapping, not a common semantic feature schema:

- `TransactionAmt` is rank/quantile projected onto the PaySim amount distribution.
- `ProductCD` is mapped to PaySim transfer/cash-out type codes.
- balances are proxies made from IEEE velocity/card/count fields.
- `M1`–`M9` mismatches create a synthetic PaySim-style balance discrepancy.
- unavailable PaySim behavioral/LLM fields may be proxy-derived or default to zero.

This limitation must accompany any frozen result.

```ini
POST_HOC_TEST_SELECTION = NO
TEST_LABEL_LEAKAGE = NO EVIDENCE
IDENTITY/PROVENANCE FAILURE = YES
```

## 2. Transfer/adapted PaySim → IEEE-CIS

### Reported protocol and result

| Field | Audited value |
|---|---:|
| Total IEEE rows implied | 590,540 |
| Adapt fraction | 0.10 |
| Adapt block | first 59,054 chronological rows |
| Adapt train | first 47,243 rows of adapt block (80%) |
| Adapt validation | remaining 11,811 rows of adapt block (20%) |
| Held-out block declared as test | final 531,486 rows (90%) |
| Features | 25 approximate PaySim-aligned features |
| `num_boost_round` candidates | 25, 50, 75, 100 |
| Round selection | highest adapt-validation AUC |
| Selected rounds | 100 |
| Threshold selection | adapt-validation F1; historical discrete grid |
| Selected threshold | 0.65 |
| Test AUC | 0.6773685463 |
| Test PR-AUC | 0.0825769062 |
| Test F1 | 0.1894373262 |
| Test Precision | 0.1249058057 |
| Test Recall | 0.3919188735 |
| Confusion matrix | TN 460,196; FP 52,258; FN 11,573; TP 7,459 |

The function loads the PaySim booster from `artifacts/models/xgboost_fraud.json` and uses `xgb.train(..., xgb_model=paysim_booster)` to add IEEE-adaptation trees. The model-round and threshold choices do not directly use the declared 90% test metrics.

### Leakage finding

The held-out IEEE test is **not untouched**. Before `adapt_model_to_ieee()` creates the 10/90 split, it calls `build_dataset(source="ieee")`. That function uses the first 70% of IEEE rows (413,378 rows) as a label-observing feature-history segment. Only afterward does transfer split off the first 10% for adaptation.

Consequently, rows in the declared test interval from index 59,054 through 413,377 have historical fraud-rate/derived LLM features influenced by labels from earlier rows that are also part of the declared test block. This is test-label leakage in feature generation. Full-dataset rank/quantile projection also makes the alignment covariate-transductive.

```ini
POST_HOC_TEST_SELECTION = NO
TEST_LABEL_LEAKAGE = YES
HELD_OUT_IEEE_TEST_UNTOUCHED = NO
MANUSCRIPT_READY = NO
```

## 3. Native IEEE-CIS benchmarks

### Legacy 42-feature benchmark

| Field | Audited value |
|---|---:|
| Total rows | 590,540 |
| Chronological split | 413,378 / 88,581 / 88,581 (70/15/15) |
| Feature count | 42 IEEE-native features |
| Candidate grid | four XGBoost parameter sets from `TrainingConfig` |
| Model selection | validation AUC + validation F1 |
| Threshold selection | validation F1 on historical grid |
| Threshold | 0.70 |
| Test AUC | 0.8415061172 |
| Test PR-AUC | 0.3262386440 |
| Test F1 | 0.3328440781 |
| Test Precision | 0.2552823000 |
| Test Recall | 0.4781057412 |
| Confusion matrix | TN 81,198; FP 4,300; FN 1,609; TP 1,474 |

Feature construction observes labels only in the training block and freezes label-derived history for validation/test. Candidate and threshold selection are validation-only; test is used for final evaluation.

```ini
POST_HOC_TEST_SELECTION = NO EVIDENCE WITHIN RUN
TEST_LABEL_LEAKAGE = NO EVIDENCE
```

### Optimized 328-feature benchmark

| Field | Audited value |
|---|---:|
| `sample_size` | null (all 590,540 rows) |
| Chronological split | 413,378 / 88,581 / 88,581 |
| Feature profile | `no_target_encoding` |
| Feature count | 328, including 220 selected V-features |
| Candidate models | four XGBoost candidates plus mean-probability ensemble |
| Candidate selection | validation PR-AUC + validation F1 |
| Selected candidate | candidate 4 |
| Threshold selection | maximum validation PR-curve F1 |
| Threshold | 0.7437319756 |
| Test AUC | 0.9063988875 |
| Test PR-AUC | 0.5235711747 |
| Test F1 | 0.5042294961 |
| Test Precision | 0.5821656051 |
| Test Recall | 0.4446967240 |
| Confusion matrix | TN 84,514; FP 984; FN 1,712; TP 1,371 |

The artifact contains five candidate records, non-null ablation/robustness/sidecar summaries, plots, and `sample_size=null`. It therefore cannot be a `--quick` execution as currently implemented (`--quick` trains only candidate 1). It is structurally consistent with a full-data run.

It is not certifiable as a **clean final run** because the report omits the executed command/CLI flags, `generated_at`, Git commit/dirty state, dataset hashes, and code hash. It also does not record whether `no_target_encoding` was predeclared. The accompanying ablation exposes test metrics and computes `delta_f1_vs_full` from test F1, while project prose says the final profile was adopted after ablation. Conservatively:

```ini
QUICK_RUN = NO (inferred from artifact structure)
FULL_DATA_RUN = YES (sample_size=null; 590,540 rows)
CLEAN_FINAL_RUN = NOT PROVEN
POST_HOC_TEST_SELECTION = YES (feature-profile/reporting level)
POST_HOC_TEST_SELECTION = NO (candidate and threshold level)
```

The optimized test metrics should be treated as descriptive until a predeclared, provenance-complete rerun is produced.

## 4. Objective domain-shift comparison

| Case | IEEE fit | Test/evaluation rows | Features | AUC | PR-AUC | F1 | Audit status |
|---|---|---:|---:|---:|---:|---:|---|
| Frozen PaySim research model | none | 590,540 | 25 proxy-aligned | 0.628517 | 0.053153 | 0.020140 | Found; not verified as deployed production model |
| Transfer-adapted model | first 10% | 531,486 | 25 proxy-aligned | 0.677369 | 0.082577 | 0.189437 | Found; invalid as clean holdout due feature leakage |
| Native IEEE legacy | train 70% | 88,581 | 42 native | 0.841506 | 0.326239 | 0.332844 | Found; older benchmark |
| Native IEEE optimized | train 70% | 88,581 | 328 native/engineered | 0.906399 | 0.523571 | 0.504229 | Found; newer descriptive benchmark, provenance incomplete |

The frozen AUC is far below the PaySim holdout AUC recorded in `training_report.json` (0.998383), and its F1/recall collapse at the PaySim threshold. Subject to the model-identity caveat, this is strong evidence of domain/schema shift. Transfer appears numerically better, but leakage prevents using the delta as clean evidence of adaptation benefit.

## 5. README provisional-number status

| README number | Status | Reason |
|---|---|---|
| frozen AUC ≈ 0.6285 | **CONFIRMED** | Exact value exists in JSON/CSV/research-suite artifacts. Confirmation is numerical only; it is not verified against the deployed model file. |
| transfer AUC ≈ 0.6774 | **PROVISIONAL** | Exact artifact exists, but its declared held-out test has label-dependent feature leakage. Do not use in the manuscript. |
| native IEEE AUC ≈ 0.8415 | **OUTDATED** | Exact legacy 42-feature result is supported, but a newer 328-feature optimized artifact reports 0.906399. Neither should be presented as the final confirmatory native number until provenance/selection is repaired. |

## 6. Test-set integrity matrix

| Experiment | Train data | Validation data | Test data | Model selection | Threshold selection | Test labels used before final evaluation? |
|---|---|---|---|---|---|---|
| Frozen | PaySim 70% (research refit) | PaySim 15% | all IEEE rows | PaySim validation | PaySim validation | No label use found; full IEEE covariate ranks are used transductively |
| Transfer | first 8% IEEE after preprocessing | next 2% IEEE | final 90% declared | adapt validation AUC | adapt validation F1 | **Yes**, through pre-split label-derived historical features for part of declared test |
| Native 42 | IEEE first 70% | IEEE next 15% | IEEE final 15% | validation AUC + F1 | validation F1 | No evidence |
| Native optimized | IEEE first 70% | IEEE next 15% | IEEE final 15% | validation PR-AUC + F1 | validation PR-curve F1 | Candidate/threshold: no; final feature-profile reporting: post-hoc concern |

## 7. Metric consistency

Precision, recall, and F1 were recomputed algebraically from every principal confusion matrix and match the stored values exactly at machine precision. Confusion-matrix totals also match the reported evaluation sizes:

- frozen: 590,540
- transfer: 531,486
- native legacy: 88,581
- native optimized: 88,581

AUC and PR-AUC cannot be reconstructed from a single confusion matrix. Cross-file checks found:

- frozen and native-legacy AUC/PR-AUC agree across `external_validation.json`, `.csv`, and the embedded research-suite payload;
- optimized values agree across `ieee_optimized_report.json` and `.csv`;
- transfer has no copied prediction-level output or independent CSV, so its AUC/PR-AUC are artifact assertions only.

## 8. Provenance

### Present

- Dataset files currently exist at `data/train_transaction.csv` (590,541 lines including header; 683,351,067 bytes) and `data/train_identity.csv` (144,234 lines including header; 26,529,680 bytes).
- External artifact: `artifact_scope="production"`, source paths, row counts, random state, split text, parameters, feature count, and alignment method.
- Optimized artifact: source paths, `sample_size=null`, row counts, split strategy, feature profile/count, candidates, and auxiliary artifact paths.
- Git history tracks external/transfer artifacts at commit `71d83588f0667f122dee55a043e2a9c6d36e37d2` and optimized artifacts/script at `8ad06aff01a5932d94436df9e34f7fca820c9fea`.

### Missing or insufficient

- No B12 result JSON embeds `generated_at`, `git_commit`, `git_dirty`, dataset hash, command line, environment lock hash, or code hash.
- Transfer does not declare `artifact_scope` or an explicit split manifest.
- Optimized JSON does not store `quick=false` or the skip flags; non-quick/full status is inferred from structure.
- Current checkout is at `8ad06aff...` and is dirty. The copied current `fraud_flow/research.py` contains unrelated later B8–B11 edits; its external-validation section is unchanged, but whole-file identity differs from the historical clean source.
- Artifact mtime is not a reliable substitute for `generated_at`.

Selected SHA-256 values:

| Item | SHA-256 |
|---|---|
| `external_validation.json` | `879763034fb5bd34407846057b1ee73fb193201d6fcb068e1ec6df1cd30d1ffa` |
| `transfer_learning_report.json` | `92b38ce1960230510ee0365c13f1f5c31cf8480b2ef6c7fde8c0c3cf08e9ef5f` |
| `ieee_optimized_report.json` | `9efff3b264ceda40622bd090db63ad155f963b2355158c54604cc981b8de1b2c` |
| optimized benchmark script | `48e439e1b46ef58927dea93ad3f2840560acb157984b4095910aef7c8d57dbf7` |
| historical transfer/external `training.py` | `235d722f54edea416d36be6e2a81b6e0cef3bae7c5ede78e6a2ffb8f58b7a4f0` |

## 9. Exact rerun required

Rerun all IEEE-CIS experiments, without rerunning PaySim B1–B11 and without replacing the production PaySim model:

1. **Frozen only:** load the existing production PaySim model file and metadata; record model SHA-256; do not refit any PaySim model; fit all alignment transforms from allowed reference/training data only; evaluate IEEE once.
2. **Transfer only:** define chronological adapt-train/adapt-validation/test partitions before constructing any label-derived features; allow labels only in adapt-train and adapt-validation for their specified roles; keep the final IEEE test labels and feature-history updates isolated until one final evaluation.
3. **Native only:** predeclare the 328-feature `no_target_encoding` profile (or select a profile using validation only), run full data with `quick=false`, and never use test metrics for feature/model/threshold selection.
4. For every run, emit a manifest with UTC `generated_at`, exact command and flags, Git commit/dirty state, dataset paths/sizes/SHA-256, model/code hashes, environment hash, split indices/counts, candidate scores, threshold source, and explicit `sample_size`, `quick`, and artifact-scope fields.
5. Save prediction-level IDs/labels/probabilities or a hash-addressed prediction file so AUC and PR-AUC can be independently recomputed.

Until those reruns exist, do not promote `0.6285 / 0.6774 / 0.8415` as a single final comparison table. The only safe high-level statement is that the existing external-validation artifacts reveal substantial transfer degradation under domain shift and motivate domain-specific adaptation/native training.
