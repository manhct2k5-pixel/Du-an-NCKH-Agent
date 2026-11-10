# B8 Final Medium-Branch Policy Ablation

- Generated at: `2026-10-10T14:42:29.119846+00:00`
- Git commit: `8ad06aff01a5932d94436df9e34f7fca820c9fea`
- Git dirty: `true`
- Experiment version: `b8-v2-dependency-aware-leakage-aligned`
- Dataset: `paysim` / `460394` rows
- Split: `322275 / 69059 / 69060`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Random state: `42`
- Leakage control: Chronological PaySim split after TRANSFER+CASH_OUT filtering. Training rows update activity and label-based historical risk state. Validation and test rows update activity sequentially only; their labels never update historical fraud-rate state before feature construction or policy decisions.
- Experiment meaning: deterministic offline medium-branch investigation replay.
- Full ReAct runtime executed: `false`.
- Classifier predictions changed: `false`.
- Low/high route actions fixed across policies: `true`.

| Policy | Medium cases | Approve | Approve rate | Review | Review rate | Block | Block rate | Block precision | Block recall | Block F1 | Fraud reviewed | Fraud review rate | FP blocks | FP block rate | Review reduction | Review reduction rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_medium_manual_review | 14181 | 54224 | 0.785172 | 14181 | 0.205343 | 655 | 0.009485 | 0.9893129770992366 | 0.9969230769230769 | 0.993103448275862 | 1 | 0.001538 | 7 | 0.000102 | 0 | 0.0 |
| deterministic_offline_investigation_replay | 14181 | 61994 | 0.897683 | 6383 | 0.092427 | 683 | 0.00989 | 0.9487554904831625 | 0.9969230769230769 | 0.9722430607651913 | 1 | 0.001538 | 35 | 0.000512 | 7798 | 0.549891 |