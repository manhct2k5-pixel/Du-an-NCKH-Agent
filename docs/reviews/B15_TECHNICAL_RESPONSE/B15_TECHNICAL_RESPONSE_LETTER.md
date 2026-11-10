# Technical Point-by-Point Response Letter

Manuscript: `XPayFraDet_B14_Final.docx`  
Manuscript SHA-256: `16313b80fb97192efc8b1b03498d14617fba1b06a0c57001bb2dc69bb4deccbe`  
Technical source of truth: `B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md`  
Prepared for integration by TV5. Page and line numbers are intentionally left as placeholders until the final journal layout is locked.

## Wording policy

Where a prior verification/response note records a reviewer or editor comment, the wording below is reproduced verbatim and its source is identified. Where no original wording was found, the item is explicitly labelled **requirement summarized from revision task sheet (not a verbatim reviewer/editor comment)**. No Reviewer A/B/C identity has been inferred.

## TR-01 – Dataset distribution

**Reviewer/Editor:** Unspecified; requirement summarized from revision task sheet.

**Comment / Technical issue:** Requirement summarized from revision task sheet (not a verbatim reviewer/editor comment): Dataset distribution and reproducibility.

**Response:** Thank you for requesting a complete account of the experimental data. After retaining only `TRANSFER` and `CASH_OUT` transactions, the PaySim analysis contains 460,394 records: 1,142 fraudulent and 459,252 legitimate. The chronological 70/15/15 partition contains 322,275 training, 69,059 validation, and 69,060 test transactions. The corresponding fraud counts are 429, 63, and 650. Every transaction is represented by 25 model features. Reporting both row and class counts makes the strong temporal class imbalance explicit and permits the evaluation denominators to be reproduced.

**Changes made:** The revised manuscript now reports the complete filtered-data distribution, chronological partition sizes, split-specific fraud counts, and final feature count.

**Location in revised manuscript:** Section 3.6; Sections 3.7.2–3.7.3.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Sections 1–2 (`evaluation_report.json` lineage); `XPayFraDet_B14_Final.docx`, Sections 3.6 and 3.7.2–3.7.3.

**Status:** ADDRESSED

## TR-02 – Preprocessing and leakage control

**Reviewer/Editor:** Unspecified; requirement summarized from revision task sheet.

**Comment / Technical issue:** Requirement summarized from revision task sheet (not a verbatim reviewer/editor comment): Preprocessing, chronological evaluation, and leakage control.

**Response:** Thank you for requesting clarification of temporal preprocessing. The pipeline filters PaySim to `TRANSFER` and `CASH_OUT`, orders records chronologically by `step`, applies the 70/15/15 split, and never randomly shuffles the data. Each validation or test transaction is scored from the historical state available before that transaction. Activity history may then be updated sequentially after scoring, but validation/test labels do not update historical fraud-rate statistics before prediction. Thus, the FeatureStore is not described as wholly frozen: activity evolves sequentially, while evaluation labels are excluded from label-based historical-risk updates.

**Changes made:** The revised data-processing and split descriptions now state the lookup-before-update order and distinguish activity-only updates from confirmed-label updates.

**Location in revised manuscript:** Section 3.6; Sections 3.7.2–3.7.3.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 2 (`feature_ablation_b8.json` leakage-protocol and B9 `shuffle=false` lineage); `XPayFraDet_B14_Final.docx`, Sections 3.7.2–3.7.3.

**Status:** ADDRESSED

## TR-03 – Feature engineering transparency

**Reviewer/Editor:** Unspecified; requirement summarized from revision task sheet.

**Comment / Technical issue:** Requirement summarized from revision task sheet (not a verbatim reviewer/editor comment): Feature definitions, grouping, construction, and availability should be reproducible.

**Response:** Thank you for requesting greater feature transparency. The revised manuscript documents all 25 deployed PaySim inputs using their repository names and organizes them into four implementation-aligned groups: six core transaction features, six derived contextual features, eight online behavioral/historical-risk features, and five deterministic rule-derived analysis features. Current-transaction and contextual variables are constructed before scoring; history variables use the pre-transaction lookup state; and the five rule-derived inputs are generated deterministically from the transaction and lookup context. These reported features do not require external LLM inference. The feature table also distinguishes direct current-record variables from sequential historical variables and explicitly records the evaluation-label restriction.

**Changes made:** The complete 25-feature catalog and construction/availability notes were added and terminology was aligned with the final ablation configurations.

**Location in revised manuscript:** Sections 3.7.2–3.7.3; Table 3; Table 9 and Figure 8 for the aligned ablation labels.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Sections 1–2 and 7; `XPayFraDet_B14_Final.docx`, Table 3 and Sections 3.7.2–3.7.3.

**Status:** ADDRESSED

## TR-04 – Architecture and algorithmic workflow

**Reviewer/Editor:** Reviewer; identity not specified in the source note.

**Comment / Technical issue:** Verbatim reviewer comment as recorded in `B6_Architecture_Algorithm_100pct_Verification_and_Response.md`: “The architecture and algorithmic workflow should be described in greater detail so that the proposed framework can be reproduced and the role of each component is clear.”

**Response:** Thank you for this suggestion. The revised architecture now follows the implemented order: pre-decision feature-store lookup and 25-feature assembly; XGBoost raw-probability estimation; top TreeSHAP contributions; validation-derived calibration; low/medium/high routing; Isolation Forest sidecar scoring; branch-specific action, with ReAct investigation restricted to the medium route; auditable result construction; and post-decision activity update. Confirmed-label feedback is handled separately and is not injected into the current prediction. The synchronous algorithm also records the high-route safety rule and the distinction between deterministic evaluation replay and the full runtime ReAct path.

**Changes made:** Figure 1 was aligned with the implemented four-phase flow, and Algorithm 1 was added to specify lookup, scoring, routing, sidecar evaluation, branch action, logging, activity update, and confirmed-label feedback in execution order.

**Location in revised manuscript:** Section 3.5; Figure 1; Algorithm 1; realtime API serving note.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** `XPayFraDet_B14_Final.docx`, Section 3.5, Figure 1, and Algorithm 1; B14 SOT, Sections 2, 4, 8, and 12 for the audited execution boundaries and thresholds.

**Status:** ADDRESSED

## TR-05 – XGBoost hyperparameters and thresholds

**Reviewer/Editor:** Unspecified; requirement summarized from revision task sheet.

**Comment / Technical issue:** Requirement summarized from revision task sheet (not a verbatim reviewer/editor comment): Fully report model configuration, model-selection controls, classification threshold, and routing thresholds.

**Response:** Thank you for requesting the complete selection procedure. The deployed XGBoost configuration is `n_estimators=260`, `max_depth=6`, `learning_rate=0.06`, `subsample=0.90`, `colsample_bytree=0.85`, `scale_pos_weight=750.2238`, `max_delta_step=1`, `tree_method=hist`, `random_state=42`, and `n_jobs=4`. The implementation evaluates four predefined parameter tuples. Each candidate is fitted on training data, its threshold is selected using validation F1, and candidates are ranked by validation AUC plus validation F1. The held-out test set is not used for model or threshold selection. The resulting classification threshold is 0.50. Operational routing is separate: low is below 0.30, high is above 0.85, and a high-route raw-probability safety floor of 0.05 redirects insufficiently supported high-score cases to manual review.

**Changes made:** The selected parameters, tuned/computed/fixed distinction, four-tuple candidate procedure, validation-only threshold rule, and separation between classification and routing thresholds were added.

**Location in revised manuscript:** Sections 3.7.4–3.7.5; Table 4.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Sections 3–4 (`evaluation_report.json` and B9 final lineage); `XPayFraDet_B14_Final.docx`, Sections 3.7.4–3.7.5 and Table 4.

**Status:** ADDRESSED

## TR-06 – ReAct implementation and evaluation boundary

**Reviewer/Editor:** Unspecified; requirement summarized from revision task sheet.

**Comment / Technical issue:** Requirement summarized from revision task sheet (not a verbatim reviewer/editor comment): Clarify the ReAct invocation condition, tools, iteration limit, output validation, failure handling, and experimental scope.

**Response:** Thank you for requesting implementation-level detail. ReAct is invoked only for medium-route transactions with operational score from 0.30 to 0.85 inclusive. The controller exposes four restricted tools: `get_card_history`, `check_ip_blacklist`, `verify_device_id`, and `query_merchant_risk`. The executor uses `max_iterations=5`, produces structured output, validates it with Pydantic, and allows up to three repair retries; persistent parsing failure routes the case to manual review while preserving raw evidence. The manuscript explicitly separates the reported deterministic offline replay of tool-selection and decision logic from a full external-LLM-backed ReAct runtime. No external-LLM accuracy, token-cost, or latency result is claimed.

**Changes made:** The invocation interval, input/output flow, tool set, loop limit, structured schema, Pydantic validation, repair/fallback behavior, and evaluation boundary were added to the medium-risk controller description and configuration table.

**Location in revised manuscript:** Section 3.5; Figure 1; Algorithm 1; ReAct configuration table.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** `XPayFraDet_B14_Final.docx`, Section 3.5 and the ReAct configuration table; B14 SOT, Section 8 for the final deterministic-replay scope and medium-branch result.

**Status:** ADDRESSED

## TR-07 – Baseline comparison and deployment rationale

**Reviewer/Editor:** Reviewer; identity not specified in the source note.

**Comment / Technical issue:** Verbatim reviewer comment as recorded in `B7_Baseline_Comparison_Final_Verification_and_Response.md`: “Please provide a stronger comparative analysis against baseline models and clarify the contribution and model-selection rationale.”

**Response:** Thank you for this suggestion. A controlled comparison now evaluates HistGradientBoosting, Random Forest, XGBoost, Logistic Regression, and Dummy Prior on the same chronological PaySim split. HistGradientBoosting has the highest static held-out AUC and F1 (0.999932 and 0.996914), and Random Forest is also slightly stronger than XGBoost on several static metrics (AUC 0.999843; F1 0.995378). XGBoost has the highest recall among the learned baselines (0.996923, versus 0.993846 for both HistGradientBoosting and Random Forest). We therefore do not claim that XGBoost is the best classifier. It remains the pre-specified deployed backbone because the serving, SHAP, calibration, routing, logging, and ReAct evidence stack was implemented and verified around that persisted artifact; the held-out test comparison is not used for post-hoc model replacement.

**Changes made:** Table 7 and its discussion were revised to report all five baselines objectively, state XGBoost's rank and recall trade-off, and document the non-post-hoc deployment rationale.

**Location in revised manuscript:** Section 4.1; Table 7.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 6 (`baseline_comparison.json` lineage); `XPayFraDet_B14_Final.docx`, Section 4.1 and Table 7.

**Status:** ADDRESSED

## TR-08 – Feature and medium-branch ablations

**Reviewer/Editor:** Reviewer; identity not specified in the source note.

**Comment / Technical issue:** Verbatim reviewer comment as recorded in `B8_Final_100pct_Verification_and_Response.md`: “Please provide a clearer ablation analysis to quantify the contribution of the individual components of the proposed framework.”

**Response:** Thank you for this important suggestion. The final leakage-controlled feature ablation reports seven configurations under fixed XGBoost settings. Test F1 is 0.993103 for the full model; 0.989992 without online/history features; 0.970432 without rule-derived analysis; 0.853081 without contextual features; and 0.811798 for the transaction-core-only model. The combined no-online-plus-rule-derived and no-contextual-plus-rule-derived configurations yield F1 values of 0.975132 and 0.856459. These combined experiments are described as **dependency-aware interaction stress tests**, not as estimates of independent causal contribution. In the medium branch, deterministic replay reduces reviews from 14,181 to 6,383, a reduction of 7,798 cases or 54.99% (55.0% rounded). Block precision is 94.88%, block recall is 99.69%, and there are 35 false-positive blocks. The classifier probability vector remains unchanged, so the result is an operational workflow trade-off rather than a classifier improvement.

**Changes made:** Table 9 and Figure 8 now contain all seven final feature configurations and dependency-aware interpretation. Table 10 and the surrounding Results/Discussion text now contain the final leakage-aligned medium-branch workload and safety results.

**Location in revised manuscript:** Table 9; Figure 8; Table 10; relevant feature-ablation and operational-effectiveness Results/Discussion subsections; Abstract and Conclusion.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Sections 7–8 (`feature_ablation_b8.json` and `medium_branch_ablation_b8.json` lineage); `XPayFraDet_B14_Final.docx`, Tables 9–10 and Figure 8.

**Status:** ADDRESSED

## TR-09 – Robustness and threshold sensitivity

**Reviewer/Editor:** Reviewer; identity not specified in the source note.

**Comment / Technical issue:** Verbatim reviewer comment as recorded in `B9_Final_100pct_Verification_and_Response.md`: “Please provide supplementary robustness experiments to demonstrate the stability of the proposed model.”

**Response:** Thank you for this suggestion. We retrained only the fixed deployed XGBoost configuration using seeds 42, 43, and 44; the data, chronological split, 25-feature schema, class weight, hyperparameters, and threshold remained fixed, and the candidate search was not rerun. The test mean ± population SD is AUC 0.9986486 ± 0.0001887, PR-AUC 0.9972164 ± 0.0002383, F1 0.9913326 ± 0.0012897, precision 0.9858078 ± 0.0025525, and recall 0.9969231 ± 0. Validation F1 reaches 0.9600 at threshold 0.35 and remains tied through 0.70; threshold 0.50 is retained as the tie-preserving default, not presented as uniquely optimal. Test labels are not used for threshold selection.

**Changes made:** The fixed-configuration seed protocol, exact per-seed summary, population-SD convention, and validation-only threshold plateau interpretation were added.

**Location in revised manuscript:** Section 3.7.6; Sections 4.4–4.5; Table 12; Conclusion.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 9 (`b9_repeated_seed_robustness.json` lineage); `XPayFraDet_B14_Final.docx`, Sections 4.4–4.5 and Table 12.

**Status:** ADDRESSED

## TR-10 – Statistical validation

**Reviewer/Editor:** Reviewer; identity not specified in the source note.

**Comment / Technical issue:** Verbatim reviewer comment as recorded in `B10_Final_100pct_Verification_and_Response.md`: “Please provide additional statistical validation, such as mean ± standard deviation or confidence intervals for the main performance metrics.”

**Response:** Thank you for this suggestion. We added 2,000 stratified nonparametric bootstrap replicates of the fixed persisted production prediction vector. The classification threshold remains 0.50 and the model is neither refitted nor rescored. The 95% percentile intervals are 0.995271–1.000000 for AUC, 0.992547–0.999960 for PR-AUC, 0.988523–0.996933 for F1, 0.981735–0.996914 for precision, and 0.992308–1.000000 for recall. These intervals are conditional on the fitted model and observed held-out class composition; they do not quantify retraining, hyperparameter-selection, temporal, or domain-shift uncertainty. The exploratory McNemar p-value is not used for the final inferential claim.

**Changes made:** The bootstrap design, fixed-prediction boundary, no-refit condition, five intervals, conditional interpretation, and separation from across-seed variability were added; the post-hoc McNemar claim was excluded from final inference.

**Location in revised manuscript:** Section 3.7.8; Section 4.6; Table 13; Conclusion.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 10 (`b10_bootstrap_ci.json` lineage); `XPayFraDet_B14_Final.docx`, Sections 3.7.8 and 4.6, Table 13.

**Status:** ADDRESSED

## TR-11 – Computational efficiency and deployment boundary

**Reviewer/Editor:** Reviewer; identity not specified in the source note.

**Comment / Technical issue:** Verbatim reviewer comment as recorded in `B11_Final_100pct_Verification_and_Response.md`: “Please discuss computational efficiency and deployment feasibility, including training time, inference/agent latency, and the implementation environment.”

**Response:** Thank you for this suggestion. The final benchmark reports a 1.669 s mean for fitting the fixed XGBoost configuration. Across 1,332 sequential held-out transactions, local end-to-end mean latency is 14.19 ms, p95 is 28.14 ms, p99 is 46.47 ms, and sequential single-process local throughput is 70.5 transactions/s. Mean component times are 3.55 ms for raw XGBoost, 3.35 ms for TreeSHAP, 6.86 ms for Isolation Forest, and 0.098 ms for deterministic medium replay. Redis/network and external LLM/API latency are excluded. Accordingly, the throughput is a local sequential measurement, not production service capacity, and 0.098 ms is not claimed as external-LLM-backed ReAct latency. The earlier latency benchmark is superseded and is not used as a final result.

**Changes made:** The revised manuscript separates fixed-fit time, component latency, corrected local end-to-end latency, and experimental exclusions, and adds an explicit deployment-capacity limitation.

**Location in revised manuscript:** Section 3.7.1; Section 3.7.7; Section 4.8; Table 15; Abstract and Conclusion.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 12 (`b11_training_time.json` and `b11_latency_components.json` lineage); `XPayFraDet_B14_Final.docx`, Section 4.8 and Table 15.

**Status:** ADDRESSED

## TR-12 – IEEE-CIS external validation and generalization

**Reviewer/Editor:** Reviewer/Editor; identity not specified in the source note.

**Comment / Technical issue:** Verbatim wording as recorded in `B12_Final_100pct_Verification_and_Response.md`: “Please provide broader/external validation and critically discuss generalization.”

**Response:** Thank you for requesting broader external validation. The locked IEEE-CIS study reports three clean branches: frozen PaySim-to-IEEE AUC 0.6260447267, transfer-adapted AUC 0.6525325348, and native IEEE-CIS AUC 0.9063988875. The IEEE sequence is partitioned before label-history construction where adaptation is used, model/threshold selection remains outside the final test set, and the three branches record no test-label leakage. These results indicate substantial domain and schema shift. They do not support strong direct cross-dataset generalization, and the branches are not treated as a controlled classifier-superiority comparison because their feature spaces and adaptation regimes differ.

**Changes made:** The frozen, adapted, and native protocols and results were added with explicit leakage safeguards, transductive/alignment caveats, descriptive native-benchmark scope, and a conservative domain-shift interpretation.

**Location in revised manuscript:** Section 3.7.9; Section 4.9; Table 16; Conclusion.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 13 (`b12_frozen_ieee.json`, `b12_transfer_ieee.json`, and `b12_native_ieee.json` lineage); `XPayFraDet_B14_Final.docx`, Sections 3.7.9 and 4.9, Table 16, Conclusion.

**Status:** ADDRESSED

## TR-13 – Implementation and reproducibility settings

**Reviewer/Editor:** Editor; identity not specified in the source note.

**Comment / Technical issue:** Verbatim editor comment as recorded in `B13_Final_100pct_Verification_and_Response.md`: “Please provide complete implementation settings, including Python and package versions, operating system, hardware, Redis requirements, and exact commands needed to reproduce the experiments.”

**Response:** Thank you for this request. The final audited environment is Linux 6.17.0-20-generic x86_64 with Python 3.12.3 on an AMD Ryzen 7 7435HS system with 16 GB installed RAM. An NVIDIA RTX 4050 was present but not used by XGBoost. The reported model uses XGBoost 3.2.0 on CPU with `tree_method=hist` and `n_jobs=4`. The revised reproducibility description distinguishes execution paths: the full online pipeline requires Redis/`RedisFeatureStore`, whereas research and the B11 benchmark use the in-memory `FeatureStore`. The reported classifier results and deterministic medium replay do not require an external LLM; a full ReAct runtime may use an external backend when configured, but no external-LLM performance is reported.

**Changes made:** The final OS, interpreter, CPU/RAM/GPU boundary, XGBoost execution settings, locked software stack, Redis distinction, external-LLM boundary, and exact repository entry points were added.

**Location in revised manuscript:** Section 3.7.1; Table 2; Section 3.7.6.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 14 (`B13_IMPLEMENTATION_REVIEW/b13_environment.json` lineage); `XPayFraDet_B14_Final.docx`, Section 3.7.1, Table 2, Section 3.7.6.

**Status:** ADDRESSED

## Closing technical statement

All empirical values in these responses were checked against the B14 Technical Single Source of Truth and against their presentation in `XPayFraDet_B14_Final.docx`. The responses do not claim that XGBoost is the strongest standalone classifier, that the deterministic replay measures external-LLM performance, that the local benchmark represents production service capacity, or that the frozen PaySim model generalizes strongly to IEEE-CIS.
