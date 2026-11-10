# B8 Final Audit

- Generated at: `2026-10-10T14:42:29.119846+00:00`
- Git commit: `8ad06aff01a5932d94436df9e34f7fca820c9fea`
- Git dirty: `true`
- Code SHA-256: `{"fraud_flow/research.py": "b4084e86b8657df99a87be403e3dba3324d6b688c1c53c6c30a608bd1c686a6a", "scripts/run_b8_ablation.py": "2c303d7f638a0f25c3572202e94437c277d32823ec613bfcd377a4b965a64c2b"}`
- Dataset SHA-256: `437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498`
- Random state: `42`
- Dataset source: `paysim`
- Dataset rows: `460394`
- Train rows: `322275`
- Validation rows: `69059`
- Test rows: `69060`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Leakage-control protocol: Chronological PaySim split after TRANSFER+CASH_OUT filtering. Training rows update activity and label-based historical risk state. Validation and test rows update activity sequentially only; their labels never update historical fraud-rate state before feature construction or policy decisions.
- Experiment version: `b8-v2-dependency-aware-leakage-aligned`

## Answers

1. **Same dataset/split?** Yes. Every feature ablation uses the same `ExperimentSplits`: 460394 / 322275 / 69059 / 69060, chronological and unshuffled.
2. **Fixed hyperparameters?** Yes. Every configuration uses the same `B8_FIXED_XGBOOST_PARAMS`; no per-ablation tuning is run.
3. **Threshold selected only on validation?** Yes. `find_best_threshold` receives validation labels/probabilities only.
4. **Test used for model selection?** No. Test is final evaluation only; any highest observed test result is descriptive and not a selection decision.
5. **Test-label leakage?** No in the audited protocol. Classifier eval freezes validation/test risk labels. Medium replay uses train labels, validation activity only, and test activity only after each decision.
6. **Dependencies of `llm_*`?** All five are deterministic derivatives of the same heuristic analysis and depend directly/transitively on transaction/context plus all eight online/history lookup inputs; see the feature JSON/Markdown dependency table.
7. **Direct vs dependency-aware?** Direct ablation removes named input columns only. Dependency-aware ablation also removes all `llm_*` proxy columns that consume the removed source information.
8. **Does medium policy change classifier probability?** No. The identical full-model probability vector is reused; its SHA-256 is recorded.
9. **Does medium experiment run full ReAct runtime?** No. It calls deterministic offline replay (`build_decision_payload` plus deterministic finalization rules) only for medium cases.
10. **Can this be called ReAct performance?** No. It is workflow/operational policy evidence, not ReAct or classifier-performance evidence.
11. **Artifact git commit/hash?** Yes. Git commit, dirty flag, code SHA-256 and dataset SHA-256 are recorded.
12. **Need another rerun?** No, provided these generated artifacts and recorded dirty-source hashes are the evidence submitted. A clean committed rerun is optional for stronger archival provenance, not required by the checks here.

## Machine-checked conditions

- [x] `expected_dataset_and_split`
- [x] `direct_feature_counts`
- [x] `dependency_aware_configs_present`
- [x] `fixed_hyperparameters`
- [x] `validation_only_thresholds`
- [x] `test_not_used_for_selection`
- [x] `llm_dependencies_audited`
- [x] `same_held_out_test_set`
- [x] `low_high_fixed`
- [x] `classifier_predictions_unchanged`
- [x] `not_react_runtime`
- [x] `required_medium_policies`
- [x] `policy_counts_cover_test`

B8_STATUS = PASS