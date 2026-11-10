# Feature Ablation

- Source: `paysim`
- Fixed XGBoost params: `{"n_estimators": 260, "max_depth": 6, "learning_rate": 0.06, "subsample": 0.9, "colsample_bytree": 0.85}`

| Ablation | Features | Test AUC | Test PR AUC | Test F1 | Delta AUC | Delta F1 | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_feature_set | 25 | 0.9984 | 0.9970 | 0.9931 | +0.0000 | +0.0000 | Full engineered feature set. |
| no_online_behavior | 17 | 0.9984 | 0.9967 | 0.9900 | +0.0000 | -0.0031 | Removes velocity and historical risk lookup features. |
| no_llm_analysis | 20 | 0.9986 | 0.9952 | 0.9704 | +0.0003 | -0.0227 | Removes the LLM-style risk, review, and semantic category features. |
| no_contextual_aggregates | 19 | 0.9969 | 0.9200 | 0.8531 | -0.0015 | -0.1400 | Removes aggregate context and entity-hash context features. |
| transaction_core_only | 6 | 0.9972 | 0.9297 | 0.8118 | -0.0011 | -0.1813 | Keeps only direct transaction-side features. |