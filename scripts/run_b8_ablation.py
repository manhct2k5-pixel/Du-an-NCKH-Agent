"""Run only the publication-grade B8 feature and medium-policy ablations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fraud_flow.research import run_b8_ablation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run B8 only; does not run baseline, robustness, external validation, or production training."
    )
    parser.add_argument(
        "--data-path",
        default=None,
        help="Optional PaySim CSV path. Defaults to the configured production PaySim path.",
    )
    args = parser.parse_args()
    print(json.dumps(run_b8_ablation(data_path=args.data_path), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
