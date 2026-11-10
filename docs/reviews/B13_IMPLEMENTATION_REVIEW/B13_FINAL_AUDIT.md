# B13 FINAL – Implementation Settings Audit

Generated at: `2026-10-11T13:12:25Z`

Scope: implementation and reproducibility settings for IJ-AI. No B1–B12 experiment was rerun, no model was retrained, and no manuscript file was changed.

## 1. Final environment

The final values below prioritize `artifacts/reports/b11_final/b11_environment.json`, final B12 provenance, and the actual repository virtual environment. README setup text is secondary where it conflicts.

| Field | Final value | Evidence and scope |
|---|---|---|
| OS | `Linux-6.17.0-20-generic-x86_64-with-glibc2.39` | Embedded in B11 final; corroborated on the current final host |
| CPU | AMD Ryzen 7 7435HS | B11 final and current host |
| Physical/logical cores | 8 / 16 | B11 final and current host |
| RAM | 16 GB installed; 15.304630279541016 GiB OS-reported (16,433,221,632 bytes) | B11 final |
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU | Available, but not used by the audited XGBoost runs |
| Python | 3.12.3 | B11 final; same repository `.venv/bin/python` used by final B12 |
| XGBoost execution | 3.2.0; CPU; `tree_method=hist`; `n_jobs=4`; no `device=cuda` | B11, B9, config, and installed environment |

The final B12 JSON records its exact interpreter path but does not independently store an OS string. The OS claim therefore comes directly from B11 and is corroborated on the same current final host; it is not inferred from old README prose.

## 2. Package versions

All requested installed versions match `requirements_locked.txt` exactly. The machine-readable comparison is in `b13_packages.csv`.

| Package | Installed | Locked | Status |
|---|---:|---:|---|
| xgboost | 3.2.0 | 3.2.0 | MATCH |
| scikit-learn | 1.8.0 | 1.8.0 | MATCH |
| pandas | 2.2.3 | 2.2.3 | MATCH |
| numpy | 2.2.5 | 2.2.5 | MATCH |
| shap | 0.51.0 | 0.51.0 | MATCH |
| scipy | 1.17.1 | 1.17.1 | MATCH |
| fastapi | 0.135.3 | 0.135.3 | MATCH |
| uvicorn | 0.44.0 | 0.44.0 | MATCH |
| pydantic | 2.12.5 | 2.12.5 | MATCH |
| redis | 7.4.0 | 7.4.0 | MATCH |
| langchain | 1.2.13 | 1.2.13 | MATCH |
| langchain-core | 1.2.23 | 1.2.23 | MATCH |

## 3. Redis boundary

```text
production/full online pipeline requires Redis = YES
local research benchmark uses Redis = NO
B11 latency benchmark Redis/network included = NO
```

- `FeatureStore` is an in-memory store used by local research and the B11 replay.
- `RedisFeatureStore` is used by the full online `FraudFlowRunner`/API path; that path starts or connects through `EmbeddedRedisServer`.
- Consequently, B11 latency must not be described as end-to-end Redis or network latency.

## 4. External LLM boundary

```text
external LLM required for PaySim reported classifier results = NO
external LLM required for deterministic medium replay = NO
full ReAct runtime may use external LLM/API = YES
full ReAct runtime hard-requires external LLM/API = NO
```

The classifier and deterministic replay paths used for reported B1–B12 metrics are local. The full ReAct path can use an external backend when its optional integration and API key are configured, but `fraud_flow/llm_provider.py` has a local heuristic fallback. B11 records that no external backend was configured and that external-LLM ReAct latency was not measured.

## 5. Seeds and execution controls

```text
main production seed = 42
B9 robustness seeds = 42,43,44
XGBoost n_jobs = 4
tree_method = hist
GPU used = NO
```

The values are consistent across `fraud_flow/config.py`, the B9 final robustness artifact, and B11's fixed benchmark configuration. GPU hardware availability is not evidence of GPU execution.

## 6. Reproducibility commands

Exact, current commands for dependency installation, production training, the research suite, B11, B12, the API, and tests are recorded in `b13_reproducibility_commands.md`.

Important limitation: `run.sh` is not the final B11/B12 reproduction path. It installs the non-lock requirements file and invokes training, general research, and an older latency script. The B11 and B12 commands in the command record come directly from their final artifact provenance/current scripts.

## 7. Conflicting environment values

### Python

```text
FINAL VALUE = Python 3.12.3
OLD/OUTDATED VALUE = Python 3.13.2 in README.md, requirements.txt commentary, and notebook metadata
VALUE TO USE IN PAPER = Python 3.12.3 for the final B11/B12 artifact environment
```

### Operating system

```text
FINAL VALUE = Linux-6.17.0-20-generic-x86_64-with-glibc2.39
OLD/OUTDATED VALUE = Windows 11 for train/research and WSL Ubuntu for full pipeline in README.md
VALUE TO USE IN PAPER = Linux 6.17.0-20-generic x86_64 (glibc 2.39) for the final B11/B12 execution environment
```

Windows 11, WSL, and native Linux are not merged into one environment. The older README entries may describe earlier execution contexts, but they do not identify the final artifact runtime.

### RAM presentation

```text
FINAL VALUE = 15.304630279541016 GiB OS-reported
OLD/OUTDATED VALUE = 16 GB rounded/marketing description without the measured value
VALUE TO USE IN PAPER = 16 GB installed (15.30 GiB OS-reported)
```

Manuscript corrections are required if an existing table currently reports Python 3.13.2 or Windows 11/WSL as the final B11/B12 runtime. This audit does not edit the manuscript.

## 8. Provenance

```text
generated_at = 2026-10-11T13:12:25Z
git_commit = 8ad06aff01a5932d94436df9e34f7fca820c9fea
git_dirty = true
requirements_locked.txt SHA-256 = 8182f237eea1f5d6c47f9a90cb62e716d03cfcb3269a65d1afd56995f06e5b8a
requirements.txt SHA-256 = 9310cdf2b00f5de15cc641e564350be1c6572af7660d818a08d9c50bd0304a95
fraud_flow/config.py SHA-256 = 7ff1a1597e21c700e96a56166115685c4f9db2c357fd664b7c6c4cd9b946a4e1
run_fraud_flow.py SHA-256 = 14faa41106769946b5761fc9a0edec8db0ca879ec4fe740b14f3ca5e5a48746e
```

The repository was already dirty before B13 outputs were created. This is explicitly preserved in the provenance and must not be presented as a clean-checkout run.

## 9. Final disposition

```text
final OS confirmed = YES
final Python confirmed = YES
package versions confirmed = YES
Redis requirement confirmed = YES
external LLM requirement confirmed = YES
exact commands confirmed = YES
conflicting old environment values identified = YES
model retrained = NO
B1-B12 rerun = NO
B13_STATUS = PASS
```

`PASS` means the requested implementation settings and their scope were resolved with explicit evidence. It does not retroactively certify old README environment descriptions, does not claim Redis/network-inclusive B11 latency, and does not make external LLMs a dependency of the reported B1–B12 metrics.
