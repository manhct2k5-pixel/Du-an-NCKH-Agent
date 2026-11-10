# B14 FINAL – Technical Single Source of Truth Audit

Generated at: `2026-10-11T13:39:08Z`

Repository commit: `8ad06aff01a5932d94436df9e34f7fca820c9fea`  
Worktree dirty before B14: `true`

## Scope and controls

- No model was retrained.
- No B1–B13 experiment or benchmark was rerun.
- No manuscript, README, guide, source artifact, or production model was modified.
- B14 only read existing files and created the five requested review files plus the ZIP archive.
- Final artifacts override README, legacy artifacts, review copies, and manuscript values when they conflict.

## Source hierarchy applied

1. `artifacts/reports/evaluation_report.json`
2. `artifacts/reports/b8_final/*`
3. `artifacts/reports/b9_final/*`
4. `artifacts/reports/b10_final/*`
5. `artifacts/reports/b11_final/*`
6. `artifacts/reports/b12_final/*`
7. `B13_IMPLEMENTATION_REVIEW/*`
8. Active code/configuration for a setting absent from artifact metadata, specifically the 0.05 high-route raw-probability safety floor
9. README, guides, legacy artifacts, and manuscript only as consistency/obsolescence audit targets

## Unified-result checks

| Area | Result | Evidence |
|---|---|---|
| Dataset counts and split | YES | Counts reconcile to 460,394 rows and split/class marginals reconcile exactly |
| Production metrics | YES | One final PaySim test vector and confusion matrix from `evaluation_report.json` |
| Model/routing thresholds | YES | Classification 0.5; routing 0.30/0.85; high-route raw floor 0.05 |
| B7 baseline | YES | Five model rows from `baseline_comparison.json` |
| B8 ablation | YES | Seven final configurations and final dependency-aware values captured |
| B8 medium branch | YES | 14,181 → 6,383; reduction 7,798/54.99%; 35 FP blocks |
| B9 robustness | YES | Seeds 42/43/44 and exact mean ± population SD captured |
| B10 statistics | YES | 2,000-replicate stratified bootstrap and five final intervals captured |
| Isolation Forest | YES | Threshold and validation/test flag/catch/false-flag results captured |
| B11 efficiency | YES | Final timing boundary and component metrics captured; old 35.72/51.55 ms marked obsolete |
| B12 IEEE-CIS | YES | Clean frozen/transfer/native AUCs and no-leakage status captured |
| B13 implementation | YES | Final Linux/Python/hardware/dependency boundaries captured |

The machine-readable handoff contains 164 rows: 159 `FINAL` rows and five explicitly non-final rows retained only to prevent accidental reuse.

## Manuscript selection and result

`XPayFraDet_B13_Final.docx` was not present in the repository or adjacent checkout search scope. The most recently modified manuscript found was selected:

```text
handoff_members/Cham/BAO_CAO_NCKH_v2.docx
SHA-256 = 364397e2b4fd3def5da56c703344c0a8abbd950a75e64178b33f86b1666929fa
```

The root `BAO_CAO_NCKH_v2.docx` has the same SHA-256 and is byte-identical. The selected document was parsed read-only through its DOCX XML. No document was edited.

Consistency result: 13 claims matched and 60 claims mismatched or were not stated. Material mismatches include:

- production threshold and PaySim metrics/confusion matrix;
- omission of two final dependency-aware B8 configurations;
- all requested final medium-branch values;
- B9 mean ± SD values;
- bootstrap iteration count and all five B10 confidence intervals;
- an obsolete inferential McNemar claim even though `MCNEMAR_FINAL_USE = NO`;
- absence of final B11 efficiency values;
- replacement of the three final B12 branches by an incompatible older IEEE table;
- absence of the final B13 runtime environment.

Therefore:

```text
manuscript B13 consistent = NO
MANUSCRIPT_CORRECTION_REQUIRED = YES
```

## Obsolete-value audit

Active reader-facing files still contain `6,395`, old IEEE AUC values `0.6285 / 0.6774 / 0.8415`, and Python 3.13.2. The old B11 latency values remain in a historical latency artifact and in explicit old-boundary verification text; those historical references are acceptable to retain when clearly labelled. Contextual searches did not find `33 FP` or `95.15%` in the audited text sources.

The complete file classification is in `obsolete_values_inventory.md`. No historical artifact was deleted.

## Validation performed

- Parsed both generated CSV files with Python's CSV parser.
- Confirmed the required column schemas exactly.
- Cross-checked high-risk PaySim, B8 medium, B10, B11, and B12 values directly against final JSON fields.
- Confirmed all manuscript status cells are exactly `MATCH` or `MISMATCH`.
- Confirmed all SOT status cells are `FINAL`, `OBSOLETE`, or `OBSOLETE / PROVISIONAL`.
- Confirmed requested output files exist before packaging.

## Final disposition

```text
dataset values unified = YES
model metrics unified = YES
thresholds unified = YES
ablation values unified = YES
robustness/statistics unified = YES
latency values unified = YES
IEEE-CIS values unified = YES
implementation values unified = YES
obsolete values identified = YES
manuscript B13 consistent = NO
MANUSCRIPT_CORRECTION_REQUIRED = YES
model retrained = NO
B1-B13 rerun = NO
B14_STATUS = PASS
```

`B14_STATUS = PASS` means the technical source of truth, handoff CSV, manuscript comparison, and obsolete-value inventory were completed and validated. It does not mean that the current manuscript or active documentation is already consistent.
