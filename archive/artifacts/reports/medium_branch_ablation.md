# Medium Branch Ablation

- Source: `paysim`
- Selected threshold for score-only baseline: `0.5`
- Medium cases on test split: `14181`

| Policy | Approve Rate | Review Rate | Block Rate | Block Precision | Block Recall | Block F1 | Fraud Review Rate | Review Fraud Share | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| score_threshold_block | 0.9905 | 0.0000 | 0.0095 | 0.9893 | 0.9969 | 0.9931 | 0.0000 | 0.0000 | Binary threshold baseline with no routing and no manual review state. |
| route_without_agent | 0.7852 | 0.2053 | 0.0095 | 0.9893 | 0.9969 | 0.9931 | 0.0015 | 0.0001 | Original routing but every medium case is held for human review. |
| route_medium_auto_approve | 0.9905 | 0.0000 | 0.0095 | 0.9893 | 0.9969 | 0.9931 | 0.0000 | 0.0000 | Routing with the medium band auto-approved to show the risk of removing investigation. |
| route_with_medium_agent | 0.8975 | 0.0926 | 0.0099 | 0.9515 | 0.9969 | 0.9737 | 0.0015 | 0.0002 | Routing with the offline replay of the current investigator logic on medium cases. |