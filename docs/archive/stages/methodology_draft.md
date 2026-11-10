# 3. Methodology

## 3.1 Proposed Methodology

### 3.1.1 System Architecture Overview

We propose **FraudFlow**, a four-stage online fraud detection system that combines a batch-trained gradient-boosted classifier with a real-time feature store, a rule-based routing layer, and an explanation-oriented agent. The architecture is designed to handle the practical constraints of production payment systems: sub-100 ms latency, severe class imbalance (~0.13% fraud rate), and the need for human-readable decisions on ambiguous transactions.

```
┌──────────────────────────────────────────────────────────────────┐
│  Stage 1 · Offline Training                                      │
│  PaySim / IEEE-CIS  →  Feature Pipeline  →  XGBoost + Anomaly   │
└───────────────────────────┬──────────────────────────────────────┘
                            │  model artifacts + metadata
┌───────────────────────────▼──────────────────────────────────────┐
│  Stage 2 · Real-Time Feature Store                               │
│  Incoming tx  →  FeatureStore.lookup()  →  feature vector        │
│                  (rolling windows + historical risk rates)       │
└───────────────────────────┬──────────────────────────────────────┘
                            │  enriched feature vector
┌───────────────────────────▼──────────────────────────────────────┐
│  Stage 3 · Risk Scoring + Routing                                │
│  XGBoost.predict_proba()  →  calibrated score                    │
│  score < θ_low  →  LOW:    auto-approve                          │
│  θ_low ≤ score ≤ θ_high →  MEDIUM: ReAct Agent investigation    │
│  score > θ_high →  HIGH:   auto-block + async explanation        │
└───────────────────────────┬──────────────────────────────────────┘
                            │  decision + explanation
┌───────────────────────────▼──────────────────────────────────────┐
│  Stage 4 · Anomaly Sidecar (IsolationForest)                     │
│  Provides secondary anomaly signal in medium-risk branch         │
│  anomaly_score > P95_val  →  force step_up regardless of agent  │
└──────────────────────────────────────────────────────────────────┘
```

---

### 3.1.2 Feature Engineering Pipeline

For each incoming transaction $t$, we compute a feature vector $\mathbf{x}_t \in \mathbb{R}^{25}$ composed of four groups:

#### (a) Transaction-side features

| Feature | Definition |
|---|---|
| `amount_log1p` | $\log(1 + \text{amount}_t)$ |
| `oldbalanceOrg`, `newbalanceOrig` | Sender balance before/after |
| `oldbalanceDest`, `newbalanceDest` | Recipient balance before/after |
| `balance_diff` | $\text{oldbalanceOrg} - \text{newbalanceOrig} - \text{amount}_t$ |
| `amount_ratio` | $\text{amount}_t \;/\; (\text{oldbalanceOrg} + 1)$ |
| `org_balance_delta_ratio` | $\text{balance\_diff} \;/\; (\text{oldbalanceOrg} + 1)$ |
| `type_encoded` | Integer encoding: TRANSFER=1, CASH_OUT=2 |
| `hour_of_day` | $\text{step}_t \bmod 24$ |
| `is_night_tx` | $\mathbf{1}[\text{hour\_of\_day} < 6]$ |
| `recipient_new_flag` | $\mathbf{1}[\text{oldbalanceDest} = 0]$ |

#### (b) Behavioral velocity features (rolling window, from FeatureStore)

| Feature | Definition |
|---|---|
| `tx_count_24h` | Count of card transactions in the past 24 hours |
| `avg_amount_7d` | Mean transaction amount over the past 7 days |
| `device_tx_count_24h` | Count of device transactions in the past 24 hours |
| `location_tx_count_24h` | Count of location transactions in the past 24 hours |
| `merchant_tx_count_24h` | Count of merchant transactions in the past 24 hours |

Formally, for a rolling window of width $W$ hours ending at step $s_t$:

$$\text{count}_{W}(e, s_t) = \sum_{\tau \in \mathcal{H}(e)} \mathbf{1}[s_t - W \leq \tau < s_t]$$

where $\mathcal{H}(e)$ is the historical step sequence for entity $e$ (card, device, etc.).

#### (c) Historical risk rate features

$$\hat{r}(e) = \frac{\sum_{\tau \in \mathcal{H}(e)} y_\tau}{\left| \{  \tau \in \mathcal{H}(e) : y_\tau \text{ is labeled} \} \right|}$$

where $y_\tau \in \{0, 1\}$ is the fraud label for historical transaction $\tau$, and $e$ is the entity (location, IP, merchant).

**Critical design note — no data leakage:** $\hat{r}(e)$ at prediction time is computed using only transactions prior to and *outside* the current evaluation window. During training, the FeatureStore is frozen for validation/test rows (`freeze_risk_labels=True`): fraud rates do not update with val/test labels, preventing the risk-rate features from encoding future information.

#### (d) LLM-style risk analysis features (deterministic)

Five features derived from rule-based transaction analysis:

| Feature | Definition |
|---|---|
| `llm_risk_score` | Weighted composite of heuristic risk signals $\in [0, 1]$ |
| `llm_reason_count` | Number of triggered risk rules |
| `llm_high_risk_flag` | $\mathbf{1}[\text{llm\_risk\_score} > 0.6]$ |
| `llm_review_flag` | $\mathbf{1}[\text{llm\_risk\_score} > 0.4]$ |
| `llm_category_hash` | Hash of transaction risk category $\bmod 2048$ |

---

### 3.1.3 XGBoost Classifier

The primary model is an XGBoost gradient boosted tree classifier trained to minimize the binary cross-entropy loss:

$$\mathcal{L} = -\sum_{i=1}^{N} \left[ y_i \log p_i + (1 - y_i) \log(1 - p_i) \right]$$

To compensate for class imbalance (fraud rate $\approx 0.13\%$), we set:

$$\text{scale\_pos\_weight} = \frac{N_{\text{legit}}}{N_{\text{fraud}}} \approx 750$$

and use `max_delta_step=1` to stabilize tree updates under high imbalance.

The prediction score is:

$$\hat{p}_t = \sigma\left( \sum_{k=1}^{K} f_k(\mathbf{x}_t) \right)$$

where $\sigma$ is the sigmoid function, $K = 260$ trees, and $f_k$ is the $k$-th tree.

**Threshold selection:** The decision threshold $\tau^*$ is chosen by grid search to maximize validation-set F1:

$$\tau^* = \arg\max_{\tau \in \mathcal{G}} F_1(y_{\text{val}},\; \mathbf{1}[\hat{p} \geq \tau])$$

with $\mathcal{G} = \{0.20, 0.25, \ldots, 0.70\}$.

---

### 3.1.4 Three-Branch Routing Layer

The calibrated output score $s_t \in (0, 1)$ determines the routing branch:

$$\text{route}(t) = \begin{cases} \text{low} & \text{if } s_t < \theta_{\text{low}} \\ \text{medium} & \text{if } \theta_{\text{low}} \leq s_t \leq \theta_{\text{high}} \\ \text{high} & \text{if } s_t > \theta_{\text{high}} \end{cases}$$

with $\theta_{\text{low}} = 0.30$ and $\theta_{\text{high}} = 0.85$.

- **Low branch:** Auto-approve. No agent invocation. Covers ~85% of transactions.
- **Medium branch:** Invokes the ReAct Agent for deeper investigation (§3.1.5).
- **High branch:** Auto-block. Asynchronous explanation logged for audit trail.

---

### 3.1.5 ReAct Agent (Medium Branch)

The medium branch triggers a tool-augmented reasoning agent that queries the FeatureStore for contextual signals:

```
Thought: Check card history and device behavior
Action: get_card_summary(card_id)
Observation: {tx_count_24h: 15, avg_amount_7d: 250.0, fraud_rate: 0.0}
Thought: High velocity, check merchant risk
Action: get_merchant_summary(merchant_id)
Observation: {merchant_fraud_rate: 0.03, tx_count_24h: 42}
→ Decision: step_up (request additional authentication)
```

The agent produces one of three actions: `approve`, `step_up`, or `block`. If the anomaly sidecar raises a flag ($\text{anomaly\_score}_t > \hat{\alpha}$), the agent's decision is overridden to `step_up` regardless of its reasoning output.

---

### 3.1.6 Anomaly Sidecar (IsolationForest)

An IsolationForest is trained on the *legitimate* training transactions:

$$\text{AnomalyScore}(t) = 1 - 2^{-E[h(\mathbf{x}_t)]/c(n)}$$

where $h(\mathbf{x}_t)$ is the expected tree path length for transaction $t$ and $c(n)$ is the normalization factor. The anomaly flag threshold is auto-calibrated:

$$\hat{\alpha} = \text{P}_{95}\left\{ \text{AnomalyScore}(\mathbf{x}) : \mathbf{x} \in \mathcal{D}_{\text{val}} \right\} \approx 0.4183$$

This data-driven threshold replaces the previous hardcoded value of 0.70, reducing false negatives significantly.

---

### 3.1.7 Data Leakage Fix

**Bug (pre-fix):** `build_feature_frame()` was called on the full dataset before train/val/test split. As a result, `location_fraud_rate`, `ip_fraud_rate`, and `merchant_fraud_rate` for val/test rows were computed using fraud labels observed from other val/test rows — information unavailable at real deployment time.

**Fix:** The enriched dataset is split into `enriched_train` and `enriched_eval` *before* building any features. Training features use full label observation (`freeze_risk_labels=False`). Validation/test features use the FeatureStore frozen at the end of training (`freeze_risk_labels=True`):

```python
# Correct, post-fix implementation
train_feature_frame, _, trained_store = build_feature_frame(enriched_train, source=source)
eval_feature_frame, _, _ = build_feature_frame(
    enriched_eval, source=source, freeze_risk_labels=True, store=trained_store
)
```

This ensures the feature distribution seen during evaluation matches production conditions exactly.
