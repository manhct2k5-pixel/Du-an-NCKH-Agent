# B11 Computational Efficiency and Deployment Feasibility

## Environment

- CPU: `AMD Ryzen 7 7435HS`
- Cores: physical=8, logical=16
- RAM: 15.304630279541016 GiB
- OS: `Linux-6.17.0-20-generic-x86_64-with-glibc2.39`
- Python: `3.12.3`
- XGBoost: `3.2.0`; scikit-learn: `1.8.0`; pandas: `2.2.3`; NumPy: `2.2.5`; SHAP: `0.51.0`
- GPU available: `true` (NVIDIA GeForce RTX 4050 Laptop GPU)
- Redis mode: `not used; in-memory FeatureStore; Redis/network overhead excluded`

## Fixed-configuration model fitting time

This is fixed-configuration model fitting time, not full hyperparameter-search time. Models were temporary in-memory objects and were not saved.

- Training rows: 322275; features: 25; repetitions: 3
- Individual seconds: `[1.823165555999367, 1.586516784998821, 1.5975049919998128]`
- Mean/median/min/max seconds: 1.669062444332667 / 1.5975049919998128 / 1.586516784998821 / 1.823165555999367

## Local component latency

Measured 1332 sequential held-out test transactions after 100 stateful warm-up transactions. Route counts: `{'low': 1072, 'medium': 259, 'high': 1}`.

| Component | n | Mean ms | p50 ms | p95 ms | p99 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| feature_store_lookup_ms | 1332 | 0.02259052630083292 | 0.022170999727677554 | 0.028833499254687926 | 0.03406769021239601 | 0.04259900015313178 |
| feature_assembly_ms | 1332 | 0.020794278509139997 | 0.020337999558250885 | 0.024724999639147427 | 0.028847109297203133 | 0.035876999390893616 |
| xgboost_predict_proba_ms | 1332 | 3.550239045042334 | 1.5914599998723133 | 16.636054500486352 | 18.446936149248362 | 20.35675499973877 |
| shap_explanation_ms | 1332 | 3.3466839083969475 | 2.7176789999430184 | 5.15295645082006 | 20.47196220933986 | 40.94133100079489 |
| calibration_and_routing_ms | 1332 | 0.004271492511802248 | 0.004237999746692367 | 0.005249999958323315 | 0.005738599447795425 | 0.009617999239708297 |
| anomaly_sidecar_ms | 1332 | 6.859352249277064 | 6.818486000156554 | 7.132253950294398 | 7.441498969619715 | 9.714522999274777 |
| model_service_total_ms | 1332 | 14.108352302564008 | 11.535494501003996 | 28.061725400038995 | 46.38491170078854 | 67.6028319994657 |
| deterministic_medium_investigation_ms | 259 | 0.09786381843594455 | 0.09679100003268104 | 0.11407909987610765 | 0.11974102020758437 | 0.13084300007903948 |
| activity_state_update_ms | 1332 | 0.015819686239836726 | 0.015443500160472468 | 0.022089999674790306 | 0.024217100544774443 | 0.030627001251559705 |
| local_end_to_end_ms | 1332 | 14.192055347616355 | 11.61940650035831 | 28.13968635018682 | 46.46767077978442 | 67.69028499911656 |

Sequential single-process local throughput: **70.46195744776011 tx/s**. This is not production capacity.

## Local end-to-end latency by route

| Route | n | Mean ms | p50 ms | p95 ms | p99 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 1072 | 14.165578430053566 | 11.602710500483226 | 28.09144905022549 | 43.27854960998579 | 67.69028499911656 |
| medium | 259 | 14.312091235546296 | 11.679162000291399 | 28.43165310077893 | 50.82025867955962 | 65.11029600005713 |
| high | 1 | 11.48601600107213 | 11.48601600107213 | 11.48601600107213 | 11.48601600107213 | 11.48601600107213 |

## Medium branch and deployment boundary

Deterministic offline investigation replay takes mean=0.09786381843594455 ms locally (n=259, p95=0.11407909987610765 ms). This is not a measurement of external LLM-backed ReAct latency.

```ini
external_llm_react_latency = NOT MEASURED
Redis/network overhead = excluded
```

## Timing boundary

For each measured transaction, local_end_to_end_ms starts immediately before the in-memory FeatureStore lookup and stops immediately after activity-only state update. It includes feature lookup, feature assembly, one-row DataFrame construction, raw XGBoost predict_proba, TreeSHAP explanation, calibration/routing, anomaly-sidecar scoring, deterministic offline investigation replay for medium routes, and observe_activity. Event parsing, dataset loading, model/explainer loading, training, external LLM/API calls, Redis, network, logging, and concurrency are outside this boundary.

## Old benchmark audit

The old report is reproduced as mean=35.716 ms, p50=35.795 ms, p95=44.463 ms, p99=51.546 ms, sample=1000, routes={'low': 887, 'medium': 113, 'high': 0}.

Its timer starts after FeatureStore lookup and feature assembly; warm-up events do not advance FeatureStore state. It therefore cannot support a local end-to-end claim.

```ini
OLD_BENCHMARK_REUSABLE = NO
```
