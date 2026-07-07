# Medium Branch Ablation

- Source: `paysim`
- Selected threshold for score-only baseline: `0.5`
- Medium cases on test split: `138`

| Policy | Approve Rate | Review Rate | Block Rate | Block Precision | Block Recall | Block F1 | Fraud Review Rate | Review Fraud Share | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| score_threshold_block | 0.9844 | 0.0000 | 0.0156 | 0.7143 | 1.0000 | 0.8333 | 0.0000 | 0.0000 | Binary threshold baseline with no routing and no manual review state. |
| route_without_agent | 0.6778 | 0.3067 | 0.0156 | 0.7143 | 1.0000 | 0.8333 | 0.0000 | 0.0000 | Original routing but every medium case is held for human review. |
| route_medium_auto_approve | 0.9844 | 0.0000 | 0.0156 | 0.7143 | 1.0000 | 0.8333 | 0.0000 | 0.0000 | Routing with the medium band auto-approved to show the risk of removing investigation. |
| route_with_medium_agent | 0.6867 | 0.2978 | 0.0156 | 0.7143 | 1.0000 | 0.8333 | 0.0000 | 0.0000 | Routing with the offline replay of the current investigator logic on medium cases. |