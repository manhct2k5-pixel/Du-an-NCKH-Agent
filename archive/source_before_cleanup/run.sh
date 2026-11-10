#!/usr/bin/env bash
# ============================================================
# FraudFlow — Reproducibility Script
# ============================================================
# Usage: bash run.sh
#
# Chạy 1 lệnh từ clone repo → kết quả khớp với artifacts trong
# artifacts/reports/ (seed=42, data=PaySim toàn bộ).
#
# Yêu cầu:
#   - Python 3.10+
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
echo "[3/5] Running research suite (baseline comparison, feature ablation, robustness)..."
python run_fraud_flow.py research 2>&1 | tail -20
echo "[3/5] Research suite complete. Reports saved to artifacts/reports/"

# --- 4. Chạy latency benchmark ---
echo "[4/5] Running latency benchmark (n=1000, warmup=100)..."
python scripts/benchmark_latency.py --n 1000 --warmup 100 2>&1
echo "[4/5] Latency benchmark complete. Report saved to artifacts/reports/latency_report.json"

# --- 5. Chạy generate plots ---
echo "[5/5] Generating ROC/PR/comparison plots..."
if [ -f "scripts/generate_plots.py" ]; then
    python scripts/generate_plots.py 2>&1
    echo "[5/5] Plots saved to artifacts/reports/plots/"
else
    echo "[5/5] scripts/generate_plots.py not found, skipping."
fi

echo ""
echo "========================================================"
echo " DONE — Tất cả kết quả có thể so sánh với artifacts/"
echo ""
echo " Key results:"
echo "   Training metrics : artifacts/reports/evaluation_report.json"
echo "   Baseline compare : artifacts/reports/baseline_comparison.json"
echo "   Latency report   : artifacts/reports/latency_report.json"
echo "   Plots            : artifacts/reports/plots/"
echo "========================================================"
