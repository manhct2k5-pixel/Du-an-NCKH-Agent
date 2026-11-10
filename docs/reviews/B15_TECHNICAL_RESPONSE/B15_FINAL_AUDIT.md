# B15 FINAL – Technical Response Letter Audit

Generated at: `2026-10-11T14:08:36Z`

Repository commit: `8ad06aff01a5932d94436df9e34f7fca820c9fea`  
Worktree dirty before B15: `true`

## Scope controls

- No model was retrained.
- No B1–B14 experiment, evaluation, benchmark, or bootstrap was rerun.
- No manuscript, README, production artifact, or B14 SOT file was modified.
- B15 created only the technical response letter, cross-check CSV, final audit, and requested ZIP package.

## Authoritative inputs

| Input | SHA-256 | Use |
|---|---|---|
| `B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md` | `30aff06d03245447c329d70618102b9663799ebcbe0c4c8d53fc53b88beba64e` | Sole authoritative numerical result source |
| `B14_SINGLE_SOURCE_OF_TRUTH/technical_single_source_of_truth.csv` | `d3afb8dda4ab11bac589ba52ff869bb90394dab8fdfab1df001d7ab02a0ed59a` | Machine-readable numerical cross-check |
| `/home/phan-van-manh/Bản tải về/XPayFraDet_B14_Final.docx` | `16313b80fb97192efc8b1b03498d14617fba1b06a0c57001bb2dc69bb4deccbe` | Current manuscript wording and location verification |

The manuscript contains the requested Sections 3.5–3.7.9 and 4.1/4.4–4.6/4.8–4.9, Figure 1, Figure 8, Algorithm 1, Tables 2/3/4/7/9/10/12/13/15/16, the ReAct configuration table, and the Conclusion. Its 49 existing Word comments were read but not changed.

## Reviewer-wording control

- Eight comments are reproduced verbatim from the available B6–B13 verification/response notes: architecture, baseline, ablation, robustness, statistical validation, computational efficiency, external validation, and implementation settings.
- Five items have no original reviewer/editor sentence in the available material and are explicitly labelled as summaries from the revision task sheet: dataset distribution, preprocessing/leakage control, feature engineering, XGBoost configuration, and ReAct implementation.
- No Reviewer A/B/C identity was inferred.

## Response coverage

| Response | Topic | Complete | SOT match | Status |
|---|---|---|---|---|
| TR-01 | Dataset distribution | YES | YES | ADDRESSED |
| TR-02 | Preprocessing and leakage control | YES | YES | ADDRESSED |
| TR-03 | Feature engineering | YES | YES | ADDRESSED |
| TR-04 | Architecture and algorithm | YES | YES | ADDRESSED |
| TR-05 | XGBoost hyperparameters and thresholds | YES | YES | ADDRESSED |
| TR-06 | ReAct implementation and evaluation boundary | YES | YES | ADDRESSED |
| TR-07 | Baseline comparison and deployment rationale | YES | YES | ADDRESSED |
| TR-08 | Feature and medium-branch ablations | YES | YES | ADDRESSED |
| TR-09 | Robustness and threshold sensitivity | YES | YES | ADDRESSED |
| TR-10 | Statistical validation | YES | YES | ADDRESSED |
| TR-11 | Computational efficiency | YES | YES | ADDRESSED |
| TR-12 | IEEE-CIS external validation | YES | YES | ADDRESSED |
| TR-13 | Implementation and reproducibility | YES | YES | ADDRESSED |

## Numerical and claim checks

- All dataset, metric, threshold, ablation, robustness, confidence-interval, efficiency, IEEE-CIS, and environment values match the B14 SOT exactly or use the manuscript's documented rounding of those SOT values.
- Required architecture/controller cardinalities and settings are reproduced from the current B14 manuscript and do not introduce an alternative result source.
- The obsolete medium-branch values are absent.
- The obsolete IEEE-CIS values are absent.
- The obsolete latency values are absent.
- The letter does not claim that XGBoost is the best standalone classifier.
- The letter does not claim external-LLM accuracy or latency from deterministic replay.
- The letter does not describe local sequential throughput as production capacity.
- The letter does not claim strong direct PaySim-to-IEEE generalization.
- Page and line fields use only `[to be inserted after final layout]`; no page or line number was guessed.

## Required final assertions

```text
dataset response complete = YES
preprocessing response complete = YES
architecture response complete = YES
hyperparameter response complete = YES
baseline response complete = YES
ablation response complete = YES
robustness response complete = YES
statistical response complete = YES
efficiency response complete = YES
external validation response complete = YES
implementation response complete = YES
all numbers match B14 SOT = YES
unsupported superiority claims = NO
obsolete values used = NO
model retrained = NO
B1-B14 rerun = NO
manuscript modified = NO
B15_STATUS = PASS
```

`B15_STATUS = PASS` means all 13 technical responses were prepared, linked to verified manuscript locations, and numerically cross-checked without modifying the manuscript or rerunning experiments.
