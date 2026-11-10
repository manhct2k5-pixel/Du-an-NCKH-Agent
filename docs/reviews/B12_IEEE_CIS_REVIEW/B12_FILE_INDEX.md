# B12 — IEEE-CIS External Validation: File Index

Audit date: 2026-10-11 (Asia/Vientiane)

This package is read-only evidence for B12. No experiment was rerun, no manuscript was edited, and no model or dataset was copied.

## Result artifacts

| File in this package | Audit role |
|---|---|
| `artifacts/reports/external_validation.json` | Primary structured evidence for frozen PaySim → IEEE-CIS and the legacy 42-feature IEEE-native benchmark. |
| `artifacts/reports/external_validation.csv` | Tabular cross-check of thresholds and test metrics in `external_validation.json`. |
| `artifacts/reports/external_validation.md` | Human-readable rendering of the frozen-vs-native artifact. |
| `artifacts/reports/research_suite.json` | Parent research-suite artifact; establishes the PaySim split/model-selection context and embeds the same external-validation payload. |
| `artifacts/reports/transfer_learning_report.json` | Primary structured evidence for adapted PaySim → IEEE-CIS. |
| `artifacts/reports/ieee_optimized_report.json` | Primary structured evidence for the newer 328-feature IEEE-native optimized benchmark. |
| `artifacts/reports/ieee_optimized_report.csv` | Candidate-by-candidate metric cross-check for the optimized benchmark. |
| `artifacts/reports/ieee_optimized_ablation.{json,csv}` | Feature-profile experiments; relevant to whether the final `no_target_encoding` profile was selected post hoc. |
| `artifacts/reports/ieee_optimized_robustness.{json,csv}` | Three-seed robustness outputs for the optimized native benchmark. |
| `artifacts/reports/ieee_optimized_sidecar.{json,csv}` | Sidecar-policy results; ancillary, not one of the three principal B12 claims. |
| `artifacts/reports/ieee_optimized_threshold_sweep.csv` | Validation threshold sweep for the optimized native model. |
| `artifacts/reports/training_report.json` | PaySim production-training context: split, selected parameters, threshold, and PaySim test metrics. |
| `artifacts/models/model_metadata.json` | Small metadata-only evidence for the PaySim model schema and threshold. The model binary itself is intentionally excluded. |
| `README.md` | Source of the provisional rounded values `0.6285`, `0.6774`, and `0.8415`. |

## Code

| File in this package | Audit role |
|---|---|
| `fraud_flow/research.py` | Frozen external-validation orchestration; PaySim/IEEE model fitting, validation-only candidate and threshold selection, feature alignment, metric calculation, report writing. |
| `fraud_flow/training.py` | Dataset construction, chronological splitting, metric functions, production training, and `adapt_model_to_ieee()`. |
| `fraud_flow/features.py` | IEEE loading/sorting, feature construction, label-history freezing, and schema definitions used by the legacy/native/transfer paths. |
| `fraud_flow/config.py` | 70/15/15 fractions, candidate grids, threshold grid, paths, and output configuration. |
| `fraud_flow/feature_store.py` | Historical activity/fraud-rate state used while features are built; needed to understand transfer leakage. |
| `fraud_flow/llm_features.py` | Deterministic `llm_*` feature derivation, including dependence on historical fraud-rate lookups. |
| `fraud_flow/schema.py` | Event and feature lookup schemas used by feature construction. |
| `run_fraud_flow.py` | CLI entry point that invokes research external validation and transfer learning. |
| `scripts/ieee_cis_optimized_benchmark.py` | Actual generator for all `ieee_optimized_*` benchmark artifacts. |

## Historical source snapshot

`provenance/source_at_external_transfer_commit/` contains the relevant files exactly as stored at commit `71d83588f0667f122dee55a043e2a9c6d36e37d2`, the last Git commit touching the external and transfer artifacts. This matters because current `fraud_flow/training.py` changed threshold selection after those artifacts were committed: the historical version uses the configured discrete threshold grid, consistent with transfer threshold `0.65` and legacy-native threshold `0.70`.

## Functional mapping

| Required audit item | Files/functions |
|---|---|
| frozen PaySim → IEEE-CIS | `external_validation.json`, `research_suite.json`; `fraud_flow/research.py::run_external_validation()` |
| transfer/adapted PaySim → IEEE-CIS | `transfer_learning_report.json`; `fraud_flow/training.py::adapt_model_to_ieee()` |
| native IEEE-CIS model (legacy) | `external_validation.json`; `fraud_flow/research.py::prepare_experiment_splits()` and `fit_best_xgboost()` |
| native IEEE-CIS model (optimized) | `ieee_optimized_report.{json,csv}`; `scripts/ieee_cis_optimized_benchmark.py::run()` |
| feature alignment | `fraud_flow/research.py::align_ieee_dataset_to_paysim_features()`; the mapping is approximate semantic/proxy alignment, not equal-semantic features |
| split protocol | `fraud_flow/features.py::load_filtered_frame()`, `fraud_flow/training.py::build_dataset()`, `fraud_flow/research.py::prepare_experiment_splits()`, optimized script `prepare_splits()` |
| threshold selection | historical/current `fraud_flow/training.py::find_best_threshold()`; optimized script `best_threshold_from_pr_curve()` |
| metric calculation | `classification_metrics()`, `pr_auc_score()`, `confusion_payload()`; optimized script `metrics_at_threshold()` |
| model/candidate selection | `fraud_flow/research.py::fit_best_xgboost()`; optimized script `fit_xgboost_candidates()` |
| provenance and run scope | the JSON fields, Git history, file metadata, and hashes documented in `B12_AUDIT_SUMMARY.md` |

## Deliberately excluded

- IEEE-CIS CSV datasets (approximately 678 MB total)
- `xgboost_fraud.json` and `xgboost_adapted_ieee.json`
- caches, virtual environments, plots not matched by the requested top-level `artifacts/reports/*ieee*` patterns
- manuscript files
