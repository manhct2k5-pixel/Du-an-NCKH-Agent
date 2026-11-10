# B12 FINAL — IEEE-CIS External Validation

This isolated run did not execute B1–B11, did not retrain PaySim, did not overwrite the production model, and did not edit the manuscript.

```objectivec
Frozen clean = YES
Transfer leakage fixed = YES
Native test selection clean = YES
B12_STATUS = PASS
```

## Final metrics

| Branch | AUC | PR-AUC | F1 | Precision | Recall | Threshold | Train | Validation | Test | Features |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen | 0.626045 | 0.051909 | 0.020116 | 0.063431 | 0.011954 | 0.500000 | 322,275 | 69,059 | 590,540 | 25 |
| Transfer | 0.652533 | 0.062449 | 0.133220 | 0.076984 | 0.494325 | 0.815057 | 47,243 | 11,811 | 531,486 | 25 |
| Native | 0.906399 | 0.523571 | 0.504229 | 0.582166 | 0.444697 | 0.743732 | 413,378 | 88,581 | 88,581 | 328 |

## Integrity assertions

```ini
frozen_model_retrained = NO
test_used_for_model_selection = NO
test_label_leakage = NO
transfer_final_test_updates_feature_history = NO
production_model_unchanged = YES
native_feature_profile = no_target_encoding
final_test_evaluations_per_branch = 1
```

Frozen alignment uses the complete IEEE covariate distribution without labels to fit its empirical CDF map; this is label-free transductive normalization and is disclosed in the frozen JSON. Transfer alignment is fitted only on adapt-train covariates. Native categorical mappings and V-feature selection are train-only.

## Provenance

```json
{
  "generated_at": "2026-10-11T12:43:03.211527+00:00",
  "git_commit": "8ad06aff01a5932d94436df9e34f7fca820c9fea",
  "git_dirty": true,
  "dataset_paths": {
    "ieee_transaction": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/train_transaction.csv",
    "ieee_identity": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/train_identity.csv",
    "paysim_reference": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv"
  },
  "dataset_sha256": {
    "ieee_transaction": "3a5c83ab6b3cc13dcabe5ffa9f522307fd5f7f7b6e6f6a60c32284ca6283d642",
    "ieee_identity": "b63c725d8377be90a995268d97f347c17d456b95db45807adcf9f59cd603c37c",
    "paysim_reference": "437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498"
  },
  "production_model_path": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/xgboost_fraud.json",
  "production_model_sha256": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
  "code_sha256": {
    "composite": "085e7c78d3114350bea597d0fbe50c0165228845c371cd14339920f91e0a76b3",
    "files": {
      "scripts/run_b12_final.py": "7d802b5d511c382165162b08d780fdd9ac016ea3ee1d74d7171b80a79050da50",
      "scripts/ieee_cis_optimized_benchmark.py": "48e439e1b46ef58927dea93ad3f2840560acb157984b4095910aef7c8d57dbf7",
      "fraud_flow/config.py": "7ff1a1597e21c700e96a56166115685c4f9db2c357fd664b7c6c4cd9b946a4e1",
      "fraud_flow/features.py": "83ddb3f634daed961a216ea1cac053aac38d2e6272e2db3fb5eba4fa385ad1a9",
      "fraud_flow/feature_store.py": "f524dd2e43a5aec7a161af2e642de4478c556d07f2abbcaf7b19c31a6cb8bd5e",
      "fraud_flow/llm_features.py": "307cc0984287998a81620544f8a04fc7274a6fbc1b35e9f22bf3a63a95baad92",
      "fraud_flow/schema.py": "987448560d8851f0518374afa282ad787d7eed6c13daed9be3c19372c7d73cbc"
    }
  },
  "exact_command": "'/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python' scripts/run_b12_final.py",
  "artifact_scope": "b12_final_only",
  "random_state": 42
}
```

The three JSON files contain branch-specific model hashes, candidate/threshold selection records, confusion matrices, and the same run provenance.
