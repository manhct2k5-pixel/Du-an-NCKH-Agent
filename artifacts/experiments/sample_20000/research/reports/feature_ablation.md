# Feature Ablation

- Source: `paysim`
- Fixed XGBoost params: `{"n_estimators": 220, "max_depth": 5, "learning_rate": 0.08, "subsample": 0.95, "colsample_bytree": 0.9}`

| Ablation | Features | Test AUC | Test PR AUC | Test F1 | Delta AUC | Delta F1 | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_feature_set | 25 | 0.9984 | 0.9705 | 0.9643 | +0.0000 | +0.0000 | Full engineered feature set. |
| no_online_behavior | 17 | 0.9998 | 0.9865 | 0.9643 | +0.0014 | +0.0000 | Removes velocity and historical risk lookup features. |
| no_llm_analysis | 20 | 0.9999 | 0.9876 | 0.9474 | +0.0015 | -0.0169 | Removes the LLM-style risk, review, and semantic category features. |
| no_contextual_aggregates | 19 | 0.9887 | 0.7407 | 0.7234 | -0.0097 | -0.2409 | Removes aggregate context and entity-hash context features. |
| transaction_core_only | 6 | 0.9911 | 0.7554 | 0.7556 | -0.0073 | -0.2087 | Keeps only direct transaction-side features. |