# B13 Reproducibility Commands

These commands reflect the current repository CLI and final artifact provenance. They were audited but **not executed** during B13. Run them from the repository root. Commands that train or benchmark are listed solely for future reproducibility.

## Install dependencies

The documented environment creation sequence is:

```bash
python3 -m venv --clear .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

For an exact recreation of the audited package set, use the committed lock file after creating/activating the virtual environment:

```bash
python3 -m pip install -r requirements_locked.txt
```

`requirements.txt` and `run.sh` describe Python 3.13.2-era setup text, whereas the final B11/B12 interpreter is Python 3.12.3. The lock file matches all requested packages installed in that final virtual environment.

## Train the PaySim production model

```bash
.venv/bin/python run_fraud_flow.py train --source paysim
```

This command retrains the model. It was **not** run in B13.

## Research suite

```bash
.venv/bin/python run_fraud_flow.py research --source paysim --external-data-path data/train_transaction.csv --seeds 42,43,44 --bootstrap-iterations 300
```

This is the repository's general/legacy research-suite entry point. It is not a substitute for the clean final B12 protocol.

## B11 final efficiency and latency audit

The exact command stored by the final B11 artifact is:

```bash
.venv/bin/python scripts/run_b11_efficiency.py --training-repetitions 3 --warmup 100 --min-measured 1000 --min-low 800 --min-medium 100 --min-high 1
```

The benchmark uses the in-memory `FeatureStore`; Redis and network latency are excluded. The deterministic medium replay does not call an external LLM.

## B12 final IEEE-CIS external validation

The exact command stored by all three final B12 result artifacts is:

```bash
.venv/bin/python scripts/run_b12_final.py
```

## API/server

```bash
.venv/bin/python run_fraud_flow.py serve --host 127.0.0.1 --port 8000
```

The full online runner/API path uses `RedisFeatureStore` and starts or connects to Redis through the repository's embedded Redis support. An external LLM is optional: configured ReAct may use it, while a local heuristic fallback exists.

## Tests

```bash
.venv/bin/python -m pytest
```

`pytest.ini` points to `tests/`. Tests were not run in B13 because this task is an implementation-settings audit only.

## `run.sh` caveat

`bash run.sh` remains a convenience workflow, but it installs from `requirements.txt` and invokes training, the general research suite, and an older latency script. It is therefore **not** the exact reproduction command for the final B11 and B12 artifacts and was not run here.
