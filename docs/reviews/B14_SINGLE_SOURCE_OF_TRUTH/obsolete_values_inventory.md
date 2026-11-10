# Obsolete Values Inventory

Generated at: `2026-10-11T13:39:08Z`

Search scope: repository text sources (`.md`, `.json`, `.csv`, `.txt`, `.py`, `.sh`) excluding datasets, curve CSVs, binary model/image files, and the new B14 output. The selected manuscript was searched by extracting `word/document.xml` from `handoff_members/Cham/BAO_CAO_NCKH_v2.docx`. Historical files are not deleted.

## Classification rule

- **Historical artifact — okay to retain:** an old result preserved for traceability, or code/final-audit text that explicitly identifies the old value as obsolete.
- **Active README/manuscript/documentation — should update:** a reader-facing current source that states the value as current or final.
- **Not found:** the requested literal/contextual stale value was not present in the searched sources.

## Requested stale-value search

| Searched value | Final replacement | Where found | Classification |
|---|---|---|---|
| `6,395` / `6395` medium reviews | 6,383 | Active root `CHECKLIST_CHUNG_MINH_4_LOP_NCKH.md`; `artifacts/reports/CLEAN_RUN_RESULTS.md`; replicated member handoffs | Active/handoff copies should update |
| same | 6,383 | `artifacts/reports/medium_branch_ablation.*`, `artifacts/reports/research_suite.json`, `artifacts/reports/b8_before_rerun/*`, B7/B8/B9/B10/B12 review copies | Historical artifact — okay to retain, but never cite as final |
| `33 FP` | 35 FP blocks | No contextual `33 FP`, `FP 33`, or `false_positive_blocks: 33` occurrence found | Not found |
| `95.15%` | 94.88% block precision | No occurrence found in audited text sources | Not found |
| `35.72 ms` mean | 14.19 ms local end-to-end mean | `artifacts/reports/latency_report.json` stores exact 35.716 ms | Historical artifact — okay to retain |
| `51.55 ms` p99 | 46.47 ms local end-to-end p99 | `artifacts/reports/latency_report.json` stores exact 51.546 ms | Historical artifact — okay to retain |
| `35.72/51.55 ms` | 14.19/46.47 ms | `artifacts/reports/b11_final/B11_FINAL_AUDIT.md` and `scripts/run_b11_efficiency.py` mention them only to verify the old boundary | Correctly labelled historical reference — retain |
| `0.6285` frozen IEEE AUC | 0.6260447267256386 | `README.md`, `HUONG_DAN_CHAY_MO_HINH.md`, `CHECKLIST_CHUNG_MINH_4_LOP_NCKH.md`, `BAO_CAO_NCKH_PHAN_CAI_TIEN.md`, `docs/BANG_KET_QUA_BAO_CAO.md`, `docs/REPORT_MO_HINH_PAYSIM.md`, `docs/report_content.md`, and member handoff copies | Active documentation should update |
| same | 0.6260447267256386 | Legacy `artifacts/reports/external_validation.*`, `research_suite.*`, review bundles, and copied handoff artifacts | Historical artifact — okay to retain |
| `0.6774` transfer AUC | 0.6525325347771955 | `README.md`, `HUONG_DAN_CHAY_MO_HINH.md`, `BAO_CAO_NCKH_PHAN_CAI_TIEN.md`, `docs/BANG_KET_QUA_BAO_CAO.md`, `docs/REPORT_MO_HINH_PAYSIM.md`, and member handoff copies | Active documentation should update |
| same | 0.6525325347771955 | B12 pre-final audit package and legacy transfer/research reports | Historical/provisional artifact — okay to retain |
| `0.8415` native IEEE AUC | 0.9063988875252156 | `README.md`, `HUONG_DAN_CHAY_MO_HINH.md`, `CHECKLIST_CHUNG_MINH_4_LOP_NCKH.md`, `BAO_CAO_NCKH_PHAN_CAI_TIEN.md`, `docs/BANG_KET_QUA_BAO_CAO.md`, `docs/REPORT_MO_HINH_PAYSIM.md`, `docs/report_content.md`, and member handoff copies | Active documentation should update |
| same | 0.9063988875252156 | Legacy 42-feature external-validation/research artifacts and review bundles | Historical artifact — okay to retain; it is a different, superseded native profile |
| `Python 3.13.2` | Python 3.12.3 | `README.md:123`, `requirements.txt:1`, copied README/requirements, and notebook metadata | Active environment documentation should update |
| same | Python 3.12.3 | `B13_IMPLEMENTATION_REVIEW/*` mentions 3.13.2 only as the old conflicting value | Correctly labelled audit reference — retain |

## Additional active-document mismatches

The newest repository manuscript found was `handoff_members/Cham/BAO_CAO_NCKH_v2.docx` (identical SHA-256 to the root copy). It does not contain the requested literal `0.6285 / 0.6774 / 0.8415` trio, but it contains other superseded results:

| Manuscript claim | Final value | Location | Classification |
|---|---|---|---|
| PaySim threshold 0.70 | 0.50 | §3.3.1 and Table 5.1 caption | Active manuscript — should update |
| PaySim AUC/F1 = 0.9985/0.9923 | 0.9983827151/0.9931034483 | Abstract, Table 5.1, discussion, conclusion | Active manuscript — should update |
| Confusion matrix 68,404/6/4/646 | 68,403/7/2/648 | Table 5.1 and following prose | Active manuscript — should update |
| Five B8 ablations with old F1/ΔF1 | Seven final configurations | §4.3.1 and Table 5.3 | Active manuscript — should update |
| Medium 14,435 → 6,211; reduction 8,224 (57%) | 14,181 → 6,383; reduction 7,798 (54.99%) | Table 5.4 and following prose | Active manuscript — should update |
| B9 F1 0.9926 ± 0.0004 | 0.9913326304 ± 0.0012897245 | Table 5.5 | Active manuscript — should update |
| Bootstrap B=300 and old intervals | B=2,000 and final B10 intervals | §4.4 and Table 5.6 | Active manuscript — should update |
| McNemar p=0.0133 used inferentially | `MCNEMAR_FINAL_USE = NO`; no final p-values | Paragraph following Table 5.6 | Active manuscript — remove/update claim |
| IEEE table XGBoost AUC 0.8907 / HGB 0.8876 | Frozen 0.6260447267; transfer 0.6525325348; native 0.9063988875 | Table 5.7 | Active manuscript — replace with the three clean B12 branches |
| No B11 final latency values | Add 14.19 ms mean, 28.14 ms p95, 46.47 ms p99, 70.5 tx/s with boundary caveat | No efficiency table found | Active manuscript — should add if required |
| No B13 OS/Python settings | Linux 6.17.0-20-generic; Python 3.12.3 | No implementation section found | Active manuscript — should add if required |

Full claim-by-claim details are in `b14_manuscript_consistency.csv`.

## Active files requiring follow-up

At minimum, the following reader-facing sources contain current-sounding obsolete values and should be synchronized from B14 in a later, explicitly authorized edit step:

- `README.md`
- `requirements.txt` environment comment
- `HUONG_DAN_CHAY_MO_HINH.md`
- `CHECKLIST_CHUNG_MINH_4_LOP_NCKH.md`
- `BAO_CAO_NCKH_PHAN_CAI_TIEN.md`
- `docs/BANG_KET_QUA_BAO_CAO.md`
- `docs/REPORT_MO_HINH_PAYSIM.md`
- `docs/report_content.md`
- `handoff_members/Cham/BAO_CAO_NCKH_v2.docx` and its identical root copy
- Replicated handoff documentation under `handoff_members/`

No file in this list was modified by B14.
