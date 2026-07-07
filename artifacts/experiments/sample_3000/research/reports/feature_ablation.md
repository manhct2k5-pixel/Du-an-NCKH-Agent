# Feature Ablation

- Source: `paysim`
- Fixed XGBoost params: `{"n_estimators": 160, "max_depth": 4, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.9}`

| Ablation | Features | Test AUC | Test PR AUC | Test F1 | Delta AUC | Delta F1 | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_feature_set | 25 | 1.0000 | 1.0000 | 0.8333 | +0.0000 | +0.0000 | Full engineered feature set. |
| no_online_behavior | 17 | 1.0000 | 1.0000 | 0.7692 | +0.0000 | -0.0641 | Removes velocity and historical risk lookup features. |
| no_llm_analysis | 20 | 0.9996 | 0.9667 | 0.7692 | -0.0004 | -0.0641 | Removes the LLM-style risk, review, and semantic category features. |
| no_contextual_aggregates | 19 | 0.9497 | 0.6432 | 0.5714 | -0.0503 | -0.2619 | Removes aggregate context and entity-hash context features. |
| transaction_core_only | 6 | 0.9139 | 0.4793 | 0.5714 | -0.0861 | -0.2619 | Keeps only direct transaction-side features. |