#!/usr/bin/env bash
# ============================================================
# FraudFlow — Reproducibility Script
# ============================================================
# Usage: bash run.sh
# Optional: RUN_RESEARCH=1 GENERATE_PLOTS=1 bash run.sh
#
# Chạy 1 lệnh từ clone repo → kết quả khớp với artifacts trong
# artifacts/reports/ (seed=42, data=PaySim toàn bộ).
#
# Yêu cầu:
#   - Python 3.11+
#   - pip install -r requirements.txt (hoặc .venv đã được set up)
#   - File data/paysim.csv tồn tại
#
# Kiểm tra env:
#   python -c "import xgboost, sklearn, pandas, numpy; print('OK')"
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Cố định seed (đã hardcode trong config.py: random_state=42) ---
export PYTHONHASHSEED=42
export CUBLAS_WORKSPACE_CONFIG=:4096:8  # reproducibility trên CUDA nếu dùng GPU

# --- Activate virtualenv nếu tồn tại ---
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "[run.sh] Activated .venv"
elif [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "[run.sh] Using active virtualenv: $VIRTUAL_ENV"
else
    echo "[run.sh] WARNING: No virtualenv detected. Using system Python."
fi

echo "========================================================"
echo " FraudFlow Reproducibility Run"
echo " Date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo " Python: $(python --version)"
echo " Seed: 42 (fixed in config.py)"
echo "========================================================"

# --- 1. Kiểm tra dữ liệu ---
if [ ! -f "data/paysim.csv" ]; then
    echo "[ERROR] data/paysim.csv not found. Download and place it at data/paysim.csv"
    exit 1
fi
echo "[1/5] Data check: data/paysim.csv found."

# --- 2. Train model (toàn bộ PaySim, seed=42) ---
echo "[2/5] Training XGBoost model on full PaySim dataset..."
python run_fraud_flow.py train 2>&1 | tail -30
echo "[2/5] Training complete. Artifacts saved to artifacts/models/ and artifacts/reports/"

# --- 3. Chạy research suite (baseline comparison + feature ablation) ---
if [ "${RUN_RESEARCH:-0}" = "1" ]; then
    echo "[3/5] Running optional research suite (baseline comparison, feature ablation, robustness)..."
    python run_fraud_flow.py research 2>&1 | tail -20
    echo "[3/5] Research suite complete. Reports saved to artifacts/reports/"
else
    echo "[3/5] Research suite skipped. Set RUN_RESEARCH=1 to run baseline experiments."
fi

# --- 4. Chạy latency benchmark ---
echo "[4/5] Running latency benchmark (n=1000, warmup=100)..."
python scripts/benchmark_latency.py --n 1000 --warmup 100 2>&1
echo "[4/5] Latency benchmark complete. Report saved to artifacts/reports/latency_report.json"

# --- 5. Chạy generate plots ---
if [ "${GENERATE_PLOTS:-0}" = "1" ]; then
    echo "[5/5] Generating optional ROC/PR/comparison plots..."
    python scripts/generate_plots.py 2>&1
    echo "[5/5] Plots saved to archive/artifacts/reports/plots/"
else
    echo "[5/5] Plots skipped. Set GENERATE_PLOTS=1 to generate archived figures."
fi

echo ""
echo "========================================================"
echo " DONE — Tất cả kết quả có thể so sánh với artifacts/"
echo ""
echo " Key results:"
echo "   Training metrics : artifacts/reports/evaluation_report.json"
if [ "${RUN_RESEARCH:-0}" = "1" ]; then
    echo "   Baseline compare : artifacts/reports/baseline_comparison.json"
fi
echo "   Latency report   : artifacts/reports/latency_report.json"
if [ "${GENERATE_PLOTS:-0}" = "1" ]; then
    echo "   Plots            : archive/artifacts/reports/plots/"
fi
echo "========================================================"
