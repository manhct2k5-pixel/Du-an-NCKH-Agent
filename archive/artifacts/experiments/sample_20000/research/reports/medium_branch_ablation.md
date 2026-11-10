# Medium Branch Ablation

- Source: `paysim`
- Selected threshold for score-only baseline: `0.5`
- Medium cases on test split: `360`

| Policy | Approve Rate | Review Rate | Block Rate | Block Precision | Block Recall | Block F1 | Fraud Review Rate | Review Fraud Share | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| score_threshold_block | 0.9907 | 0.0000 | 0.0093 | 0.9643 | 0.9643 | 0.9643 | 0.0000 | 0.0000 | Binary threshold baseline with no routing and no manual review state. |
| route_without_agent | 0.8707 | 0.1200 | 0.0093 | 0.9643 | 0.9643 | 0.9643 | 0.0357 | 0.0028 | Original routing but every medium case is held for human review. |
| route_medium_auto_approve | 0.9907 | 0.0000 | 0.0093 | 0.9643 | 0.9643 | 0.9643 | 0.0000 | 0.0000 | Routing with the medium band auto-approved to show the risk of removing investigation. |
| route_with_medium_agent | 0.9297 | 0.0607 | 0.0097 | 0.9310 | 0.9643 | 0.9474 | 0.0357 | 0.0055 | Routing with the offline replay of the current investigator logic on medium cases. |