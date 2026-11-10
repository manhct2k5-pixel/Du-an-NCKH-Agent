# B8 Final Feature Ablation

- Generated at: `2026-10-10T14:42:29.119846+00:00`
- Git commit: `8ad06aff01a5932d94436df9e34f7fca820c9fea`
- Git dirty: `true`
- Experiment version: `b8-v2-dependency-aware-leakage-aligned`
- Dataset: `paysim` / `460394` rows
- Split: `322275 / 69059 / 69060`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Random state: `42`
- Leakage control: Chronological PaySim split after TRANSFER+CASH_OUT filtering. Training rows update activity and label-based historical risk state. Validation and test rows update activity sequentially only; their labels never update historical fraud-rate state before feature construction or policy decisions.
- Fixed XGBoost params: `{"n_estimators": 260, "max_depth": 6, "learning_rate": 0.06, "subsample": 0.9, "colsample_bytree": 0.85}`
- Threshold selection: validation only.
- Test-set use: final evaluation only; never model/feature/threshold selection.

## Audited dependencies of `llm_*`

All five llm_* columns depend directly or transitively on both transaction/context inputs and online behavioral/historical-risk inputs.

| Feature | Derivation | Transaction/context inputs | Online/history inputs |
| --- | --- | --- | --- |
| llm_risk_score | risk_score from deterministic rule increments | event.tx_type, event.amount, event.oldbalanceOrg, event.newbalanceOrig, event.oldbalanceDest, event.extras.source | lookup.tx_count_24h, lookup.avg_amount_7d, lookup.device_tx_count_24h, lookup.location_tx_count_24h, lookup.merchant_tx_count_24h, lookup.location_fraud_rate, lookup.ip_fraud_rate, lookup.merchant_fraud_rate |
| llm_reason_count | length of reason_codes emitted by the same deterministic rules | event.tx_type, event.amount, event.oldbalanceOrg, event.newbalanceOrig, event.oldbalanceDest, event.extras.source | lookup.tx_count_24h, lookup.avg_amount_7d, lookup.device_tx_count_24h, lookup.location_tx_count_24h, lookup.merchant_tx_count_24h, lookup.location_fraud_rate, lookup.ip_fraud_rate, lookup.merchant_fraud_rate |
| llm_high_risk_flag | int(llm_risk_score >= 0.70); transitive dependencies equal llm_risk_score | event.tx_type, event.amount, event.oldbalanceOrg, event.newbalanceOrig, event.oldbalanceDest, event.extras.source | lookup.tx_count_24h, lookup.avg_amount_7d, lookup.device_tx_count_24h, lookup.location_tx_count_24h, lookup.merchant_tx_count_24h, lookup.location_fraud_rate, lookup.ip_fraud_rate, lookup.merchant_fraud_rate |
| llm_review_flag | int(0.30 <= llm_risk_score < 0.70); transitive dependencies equal llm_risk_score | event.tx_type, event.amount, event.oldbalanceOrg, event.newbalanceOrig, event.oldbalanceDest, event.extras.source | lookup.tx_count_24h, lookup.avg_amount_7d, lookup.device_tx_count_24h, lookup.location_tx_count_24h, lookup.merchant_tx_count_24h, lookup.location_fraud_rate, lookup.ip_fraud_rate, lookup.merchant_fraud_rate |
| llm_category_hash | stable hash of a category selected from risk_score and reason_codes | event.tx_type, event.amount, event.oldbalanceOrg, event.newbalanceOrig, event.oldbalanceDest, event.extras.source | lookup.tx_count_24h, lookup.avg_amount_7d, lookup.device_tx_count_24h, lookup.location_tx_count_24h, lookup.merchant_tx_count_24h, lookup.location_fraud_rate, lookup.ip_fraud_rate, lookup.merchant_fraud_rate |

## Results

| Configuration | Experiment | Features | Threshold | Val AUC | Val F1 | Test AUC | Test PR-AUC | Test F1 | Test precision | Test recall | Delta AUC | Delta PR-AUC | Delta F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_feature_set | direct_feature_group_ablation | 25 | 0.5 | 0.9994133545353906 | 0.96 | 0.9983827150776428 | 0.9970017406400512 | 0.993103448275862 | 0.9893129770992366 | 0.9969230769230769 | 0.0 | 0.0 | 0.0 |
| no_online_behavior | direct_feature_group_ablation | 17 | 0.65 | 0.9994730543385538 | 0.9375 | 0.9984086559544827 | 0.9967407558963038 | 0.9899923017705927 | 0.9907550077041603 | 0.9892307692307692 | 2.6e-05 | -0.000261 | -0.003111 |
| no_llm_analysis | direct_feature_group_ablation | 20 | 0.5 | 0.99726669224901 | 0.8391608391608392 | 0.9986469589466227 | 0.9952047809970387 | 0.9704321455648218 | 0.9566517189835575 | 0.9846153846153847 | 0.000264 | -0.001797 | -0.022671 |
| no_contextual_aggregates | direct_feature_group_ablation | 19 | 0.7 | 0.9913201777512752 | 0.4392523364485981 | 0.996902297234997 | 0.9200482675822834 | 0.8530805687203792 | 0.8766233766233766 | 0.8307692307692308 | -0.00148 | -0.076953 | -0.140023 |
| transaction_core_only | direct_feature_group_ablation | 6 | 0.7 | 0.9968712241887498 | 0.33540372670807456 | 0.9972326920265819 | 0.9296777640918964 | 0.8117977528089888 | 0.7467700258397932 | 0.8892307692307693 | -0.00115 | -0.067324 | -0.181306 |
| no_online_behavior_and_dependent_analysis | dependency_aware_ablation | 12 | 0.5 | 0.999276125508081 | 0.851063829787234 | 0.9979583844017407 | 0.9948811361863485 | 0.9751318764129616 | 0.9556868537666174 | 0.9953846153846154 | -0.000424 | -0.002121 | -0.017972 |
| no_contextual_and_dependent_analysis | dependency_aware_ablation | 14 | 0.7 | 0.9911901955208814 | 0.4519230769230769 | 0.996916307782263 | 0.9237596824495883 | 0.8564593301435407 | 0.8890728476821192 | 0.8261538461538461 | -0.001466 | -0.073242 | -0.136644 |