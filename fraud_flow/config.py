from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "paysim.csv"
TRANSACTION_DATA_PATH = ROOT_DIR / "data" / "train_transaction.csv"
IDENTITY_DATA_PATH = ROOT_DIR / "data" / "train_identity.csv"
ARTIFACT_DIR = ROOT_DIR / "artifacts"
MODEL_DIR = ARTIFACT_DIR / "models"
LOG_DIR = ARTIFACT_DIR / "logs"
REPORT_DIR = ARTIFACT_DIR / "reports"
REDIS_DIR = ARTIFACT_DIR / "redis"
DEPLOYMENT_DIR = ARTIFACT_DIR / "deployment"
MONITORING_DIR = ARTIFACT_DIR / "monitoring"

RAW_COLUMNS = [
    "step",
    "type",
    "amount",
    "nameOrig",
    "oldbalanceOrg",
    "newbalanceOrig",
    "nameDest",
    "oldbalanceDest",
    "newbalanceDest",
    "isFraud",
    "isFlaggedFraud",
]

TYPE_ENCODING = {
    "PAYMENT": 0,
    "TRANSFER": 1,
    "CASH_OUT": 2,
    "DEBIT": 3,
    "CASH_IN": 4,
}

LLM_FEATURE_COLUMNS = [
    "llm_risk_score",
    "llm_reason_count",
    "llm_high_risk_flag",
    "llm_review_flag",
    "llm_category_hash",
]

PAYSIM_FEATURE_COLUMNS = [
    "amount_log1p",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "type_encoded",
    "balance_diff",
    "amount_ratio",
    "org_balance_delta_ratio",
    "hour_of_day",
    "is_night_tx",
    "recipient_new_flag",
    "tx_count_24h",
    "avg_amount_7d",
    "device_tx_count_24h",
    "location_tx_count_24h",
    "merchant_tx_count_24h",
    "location_fraud_rate",
    "ip_fraud_rate",
    "merchant_fraud_rate",
    *LLM_FEATURE_COLUMNS,
]

IEEE_FEATURE_COLUMNS = [
    "transaction_amt_log1p",
    "tx_hour",
    "tx_day",
    "product_cd_hash",
    "card1",
    "card2",
    "card3",
    "card5",
    "addr1",
    "addr2",
    "dist1",
    "dist2",
    "card4_hash",
    "card6_hash",
    "p_email_hash",
    "r_email_hash",
    "device_type_hash",
    "device_info_hash",
    "id30_hash",
    "id31_hash",
    "id33_hash",
    "card_id_hash",
    "merchant_id_hash",
    "location_id_hash",
    "c_sum",
    "d_sum",
    "missing_ratio",
    "email_match",
    "is_mobile",
    "tx_count_24h",
    "avg_amount_7d",
    "device_tx_count_24h",
    "location_tx_count_24h",
    "merchant_tx_count_24h",
    "location_fraud_rate",
    "ip_fraud_rate",
    "merchant_fraud_rate",
    *LLM_FEATURE_COLUMNS,
]

FEATURE_COLUMNS = PAYSIM_FEATURE_COLUMNS


@dataclass(frozen=True)
class RoutingThresholds:
    low: float = 0.30
    high: float = 0.85
    high_raw_probability_floor: float = 0.05


@dataclass(frozen=True)
class TrainingConfig:
    random_state: int = 42
    train_frac: float = 0.70
    val_frac: float = 0.15
    test_frac: float = 0.15
    n_jobs: int = 4
    max_delta_step: int = 1
    calibration_low_quantile: float = 0.85
    calibration_high_quantile: float = 0.98
    threshold_grid: tuple[float, ...] = tuple(round(x, 2) for x in [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7])
    candidate_params: tuple[dict[str, float | int], ...] = (
        {
            "n_estimators": 160,
            "max_depth": 4,
            "learning_rate": 0.08,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
        },
        {
            "n_estimators": 220,
            "max_depth": 5,
            "learning_rate": 0.08,
            "subsample": 0.95,
            "colsample_bytree": 0.90,
        },
        {
            "n_estimators": 260,
            "max_depth": 6,
            "learning_rate": 0.06,
            "subsample": 0.90,
            "colsample_bytree": 0.85,
        },
        {
            "n_estimators": 180,
            "max_depth": 5,
            "learning_rate": 0.10,
            "subsample": 1.00,
            "colsample_bytree": 1.00,
        },
    )


@dataclass(frozen=True)
class ResearchConfig:
    repeated_seed_values: tuple[int, ...] = (42, 43, 44)
    bootstrap_iterations: int = 300


@dataclass(frozen=True)
class AnomalyConfig:
    contamination: float = 0.01
    n_estimators: int = 100
    # Ngưỡng anomaly_score để kích hoạt flag ở nhánh medium (0-1)
    flag_threshold: float = 0.70


@dataclass(frozen=True)
class OutputPaths:
    anomaly_model_path: Path = MODEL_DIR / "anomaly_sidecar.joblib"
    model_path: Path = MODEL_DIR / "xgboost_fraud.json"
    adapted_model_path: Path = MODEL_DIR / "xgboost_adapted_ieee.json"
    metadata_path: Path = MODEL_DIR / "model_metadata.json"
    model_versions_dir: Path = MODEL_DIR / "versions"
    experiments_dir: Path = ARTIFACT_DIR / "experiments"
    training_report_path: Path = REPORT_DIR / "training_report.json"
    evaluation_report_path: Path = REPORT_DIR / "evaluation_report.json"
    evaluation_markdown_path: Path = REPORT_DIR / "evaluation_report.md"
    validation_roc_curve_path: Path = REPORT_DIR / "validation_roc_curve.csv"
    validation_pr_curve_path: Path = REPORT_DIR / "validation_pr_curve.csv"
    test_roc_curve_path: Path = REPORT_DIR / "test_roc_curve.csv"
    test_pr_curve_path: Path = REPORT_DIR / "test_pr_curve.csv"
    threshold_sweep_path: Path = REPORT_DIR / "validation_threshold_sweep.csv"
    baseline_comparison_path: Path = REPORT_DIR / "baseline_comparison.json"
    baseline_comparison_csv_path: Path = REPORT_DIR / "baseline_comparison.csv"
    baseline_comparison_markdown_path: Path = REPORT_DIR / "baseline_comparison.md"
    feature_ablation_path: Path = REPORT_DIR / "feature_ablation.json"
    feature_ablation_csv_path: Path = REPORT_DIR / "feature_ablation.csv"
    feature_ablation_markdown_path: Path = REPORT_DIR / "feature_ablation.md"
    medium_branch_ablation_path: Path = REPORT_DIR / "medium_branch_ablation.json"
    medium_branch_ablation_csv_path: Path = REPORT_DIR / "medium_branch_ablation.csv"
    medium_branch_ablation_markdown_path: Path = REPORT_DIR / "medium_branch_ablation.md"
    robustness_validation_path: Path = REPORT_DIR / "robustness_validation.json"
    robustness_validation_csv_path: Path = REPORT_DIR / "robustness_validation.csv"
    robustness_validation_markdown_path: Path = REPORT_DIR / "robustness_validation.md"
    transfer_learning_report_path: Path = REPORT_DIR / "transfer_learning_report.json"
    external_validation_path: Path = REPORT_DIR / "external_validation.json"
    external_validation_csv_path: Path = REPORT_DIR / "external_validation.csv"
    external_validation_markdown_path: Path = REPORT_DIR / "external_validation.md"
    research_suite_path: Path = REPORT_DIR / "research_suite.json"
    research_suite_markdown_path: Path = REPORT_DIR / "research_suite.md"
    simulation_report_path: Path = REPORT_DIR / "simulation_report.json"
    dashboard_snapshot_path: Path = MONITORING_DIR / "dashboard_snapshot.json"
    prediction_log_path: Path = LOG_DIR / "predictions.jsonl"
    feedback_log_path: Path = LOG_DIR / "feedback.jsonl"
    high_risk_log_path: Path = LOG_DIR / "high_risk_async_llm.jsonl"
    manual_review_queue_path: Path = LOG_DIR / "manual_review_queue.jsonl"
    manual_review_decisions_path: Path = LOG_DIR / "manual_review_decisions.jsonl"
    drift_alert_log_path: Path = LOG_DIR / "drift_alerts.jsonl"
    redis_runtime_dir: Path = REDIS_DIR
    deployment_state_path: Path = DEPLOYMENT_DIR / "deployment_state.json"
    deployment_history_path: Path = DEPLOYMENT_DIR / "deployment_history.jsonl"
    rollout_plan_path: Path = DEPLOYMENT_DIR / "rollout_plan.json"
    dashboard_html_path: Path = MONITORING_DIR / "dashboard.html"


@dataclass(frozen=True)
class AppConfig:
    data_path: Path = DATA_PATH
    transaction_data_path: Path = TRANSACTION_DATA_PATH
    identity_data_path: Path = IDENTITY_DATA_PATH
    default_source: str = "paysim"
    routing: RoutingThresholds = field(default_factory=RoutingThresholds)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    outputs: OutputPaths = field(default_factory=OutputPaths)


APP_CONFIG = AppConfig()
