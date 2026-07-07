# 4. Experiments

## 4.1 Experimental Setup

### 4.1.1 Hardware

| Component | Specification |
|---|---|
| **CPU** | AMD Ryzen 7 7435HS (8 cores / 16 threads) |
| **RAM** | 16 GB DDR5 |
| **Storage** | NVMe SSD |
| **OS** | Ubuntu 24.04 LTS (kernel 6.17) |
| **Python** | 3.12.3 |
| **XGBoost** | 3.2.0 (tree_method="hist", n_jobs=4) |
| **scikit-learn** | 1.8.0 |
| **pandas** | 2.2.3 |
| **numpy** | 2.2.5 |

All experiments run on CPU only. No GPU acceleration. Training time ≈ 2–8 seconds per XGBoost run on the full PaySim dataset (460,394 rows).

---

### 4.1.2 Dataset

**Primary dataset — PaySim (synthetic financial transactions):**

| Property | Value |
|---|---|
| Source | Mobile money payment simulator |
| Total rows (after type filter) | 460,394 |
| Transaction types used | TRANSFER, CASH_OUT |
| Fraud rate | 0.1331% |
| Split strategy | Chronological by simulation step |
| Train rows | 322,275 (70%) |
| Validation rows | 69,059 (15%) |
| Test rows | 69,060 (15%) |
| Train fraud count | 429 |
| Test fraud count | 650 |

**External validation dataset — IEEE-CIS (real-world card transactions):**

| Property | Value |
|---|---|
| Source | IEEE-CIS Fraud Detection competition (Kaggle) |
| Total transaction rows | ~590,540 |
| Fraud rate | ~3.5% |
| Use in this work | Domain shift analysis, transfer learning |

---

### 4.1.3 Model Hyperparameters

**XGBoost (selected via grid search on validation AUC + F1):**

| Hyperparameter | Value | Search Range |
|---|---|---|
| `n_estimators` | 260 | {160, 220, 260, 180} |
| `max_depth` | 6 | {4, 5, 6, 5} |
| `learning_rate` | 0.06 | {0.08, 0.08, 0.06, 0.10} |
| `subsample` | 0.90 | {0.90, 0.95, 0.90, 1.00} |
| `colsample_bytree` | 0.85 | {0.90, 0.90, 0.85, 1.00} |
| `objective` | binary:logistic | — |
| `tree_method` | hist | — |
| `scale_pos_weight` | 750.2 | Computed from class ratio |
| `max_delta_step` | 1 | Fixed |
| `random_state` | 42 | Fixed |

4 candidate configurations were evaluated; the winning configuration was selected by:

$$\text{ranking\_score} = \text{val\_AUC} + \text{val\_F1}$$

**IsolationForest (anomaly sidecar):**

| Hyperparameter | Value |
|---|---|
| `n_estimators` | 100 |
| `contamination` | 0.01 |
| `random_state` | 42 |
| Anomaly flag threshold | 0.4183 (P95 of validation scores) |
| Training set | Legitimate transactions only (321,846 rows) |

**Routing thresholds:**

| Threshold | Value | Route |
|---|---|---|
| `θ_low` | 0.30 | Below → auto-approve (low) |
| `θ_high` | 0.85 | Above → auto-block (high) |
| `τ*` (decision) | 0.50 | XGBoost classification cutoff |

---

### 4.1.4 Data Leakage Fix Details

**Bug identified:** `build_feature_frame()` was called on the full dataset BEFORE the train/val/test split. This caused the historical fraud-rate features (`location_fraud_rate`, `ip_fraud_rate`, `merchant_fraud_rate`) of validation/test rows to incorporate fraud labels from within the evaluation period — information unavailable at real deployment time.

**Fix applied (2026-04-15):**
- Enriched data is split chronologically into `enriched_train` (70%) and `enriched_eval` (30%) before any feature computation.
- Training features are built with full FeatureStore updates (`freeze_risk_labels=False`).
- Val/test features are built with `freeze_risk_labels=True` using the store frozen at the end of training — fraud rates are NOT updated with val/test labels.

**Verification:** The script `scripts/compute_leakage_comparison.py` re-runs both the leaky and the fixed pipelines on any data sample and reports per-metric deltas, allowing future reviewers to quantitatively confirm the fix is effective.

---

### 4.1.5 Reproducibility Protocol

All experiments are deterministic and reproducible from a single command:

```bash
bash run.sh
```

Reproducibility is guaranteed by:
1. **Fixed random seed:** `random_state=42` hardcoded in `config.py`
2. **Fixed shell hash seed:** `PYTHONHASHSEED=42` exported in `run.sh`
3. **Deterministic data sampling:** `deterministic_time_sample()` uses `np.linspace` (no shuffle)
4. **Chronological split:** no random shuffling at any stage
5. **XGBoost `tree_method="hist"`:** deterministic on CPU

Expected test metrics after re-running from clean state:

| Metric | Expected Value |
|---|---|
| Test AUC | 0.9984 |
| Test PR-AUC | 0.9970 |
| Test F1 | 0.9931 |
| Test Precision | 0.9893 |
| Test Recall | 0.9969 |

---

### 4.1.6 Evaluation Protocol

All metrics are computed on the **held-out test set** (chronologically last 15% of data, never used for any training or threshold selection):

- **AUC-ROC:** Area under the Receiver Operating Characteristic curve
- **PR-AUC:** Area under the Precision-Recall curve (more informative under class imbalance)
- **F1:** Harmonic mean of precision and recall at threshold $\tau^*$
- **Precision / Recall:** At threshold $\tau^*$ selected on validation set only

**Latency evaluation** uses the `scripts/benchmark_latency.py` script:
- 1,000 benchmark transactions after 100-transaction JIT warmup
- Measures end-to-end pipeline latency: feature lookup + model inference + routing + agent (for medium branch)
- Reports p50, p95, p99 latency and throughput (TPS) per route
