from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def configure_api_environment(env_file: str | None = None) -> None:
    """Load local credentials only for explicitly requested API commands."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        raise SystemExit("Chưa cài SDK. Chạy: .venv/bin/python -m pip install -r requirements-openai.txt") from None

    path = Path(env_file) if env_file else Path(__file__).resolve().parent / ".env"
    if env_file and not path.is_file():
        raise SystemExit("Không tìm thấy file cấu hình --env-file.")
    load_dotenv(path, override=False)
    from fraud_flow.llm_provider import provider_configuration

    try:
        configuration = provider_configuration()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
    if not configuration["api_key_configured"]:
        raise SystemExit(f"Chưa có {configuration['key_env']}. Điền key vào .env tại thư mục gốc dự án rồi chạy lại; không gửi key vào chat.")
    if not configuration["dependency_installed"]:
        raise SystemExit("Chưa cài SDK. Chạy: .venv/bin/python -m pip install -r requirements-openai.txt")


def check_llm_api(env_file: str | None = None) -> None:
    """Make one explicit API request with synthetic text, without runtime logs."""
    configure_api_environment(env_file)
    from langchain_core.output_parsers import StrOutputParser
    from fraud_flow.llm_provider import build_decision_llm
    from fraud_flow.llm_runtime import ModelCallRecorder, execution_summary

    model = build_decision_llm()
    recorder = ModelCallRecorder(model)
    try:
        response = StrOutputParser().invoke(model.invoke(
            "Chỉ trả lời đúng chuỗi: API_OK", config={"callbacks": [recorder]},
        ))
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__,
                          "http_status": getattr(exc, "status_code", None),
                          "execution": execution_summary({"api_check": recorder})}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None
    result = execution_summary({"api_check": recorder})
    print(json.dumps({"status": "ok", "response": response, "execution": result}, ensure_ascii=False, indent=2))
    if not result["external_response_observed"]:
        raise SystemExit(1)


def parse_seed_list(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    items = [item.strip() for item in raw.split(",") if item.strip()]
    if not items:
        return None
    return [int(item) for item in items]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fraud detection flow that mirrors the 4-stage architecture in the provided image."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Run stage 1: offline training and model persistence.")
    train_parser.add_argument("--sample-size", type=int, default=None, help="Optional row limit after filtering.")
    train_parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Optional dataset path. Defaults to the project-preferred dataset (PaySim).",
    )
    train_parser.add_argument(
        "--source",
        type=str,
        choices=["paysim", "ieee"],
        default=None,
        help="Explicit data source type. Required when the file is not named paysim.csv or train_transaction.csv.",
    )

    simulate_parser = subparsers.add_parser("simulate", help="Run stages 2-4 on holdout transactions.")
    simulate_parser.add_argument("--limit", type=int, default=300, help="Number of live transactions to process.")

    stream_parser = subparsers.add_parser("stream", help="Continuously scan PaySim holdout batches until stopped.")
    stream_parser.add_argument("--batch-size", type=int, default=1000, help="Number of transactions per batch.")
    stream_parser.add_argument("--pause", type=float, default=0.0, help="Optional pause in seconds between batches.")

    retrain_parser = subparsers.add_parser("retrain", help="Retrain the model and compare with the previous artifact.")
    retrain_parser.add_argument("--sample-size", type=int, default=None, help="Optional row limit after filtering.")
    retrain_parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Optional dataset path. Defaults to the project-preferred dataset (PaySim).",
    )
    retrain_parser.add_argument(
        "--source",
        type=str,
        choices=["paysim", "ieee"],
        default=None,
        help="Explicit data source type. Required when the file is not named paysim.csv or train_transaction.csv.",
    )

    research_parser = subparsers.add_parser(
        "research",
        help="Run the research suite: baseline comparison, feature ablation, and medium-branch ablation.",
    )
    research_parser.add_argument("--sample-size", type=int, default=None, help="Optional row limit after filtering.")
    research_parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Optional dataset path. Defaults to the project-preferred dataset (PaySim).",
    )
    research_parser.add_argument(
        "--source",
        type=str,
        choices=["paysim", "ieee"],
        default=None,
        help="Explicit data source type. Required when the file is not named paysim.csv or train_transaction.csv.",
    )
    research_parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="Comma-separated random seeds for repeated-run robustness checks. Defaults to the app config values.",
    )
    research_parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=None,
        help="Optional bootstrap iteration count for confidence intervals.",
    )
    research_parser.add_argument(
        "--external-data-path",
        type=str,
        default=None,
        help="Optional secondary dataset path for external validation.",
    )

    adapt_parser = subparsers.add_parser(
        "adapt",
        help="Transfer Learning: tiếp tục huấn luyện PaySim model trên 10%% dữ liệu IEEE-CIS.",
    )
    adapt_parser.add_argument(
        "--ieee-data-path",
        type=str,
        default=None,
        help="Đường dẫn tới file train_transaction.csv của IEEE-CIS.",
    )
    adapt_parser.add_argument(
        "--adapt-fraction",
        type=float,
        default=0.10,
        help="Tỷ lệ dữ liệu IEEE dùng để adapt (mặc định: 0.10).",
    )

    deploy_parser = subparsers.add_parser("deploy", help="Promote the current candidate model to active deployment.")
    deploy_parser.add_argument("--reason", type=str, default="Manual promotion from CLI.", help="Promotion reason.")

    rollback_parser = subparsers.add_parser("rollback", help="Rollback to the previous active model version.")
    rollback_parser.add_argument("--reason", type=str, default="Manual rollback from CLI.", help="Rollback reason.")

    subparsers.add_parser("status", help="Show deployment status and rollout metadata.")

    serve_parser = subparsers.add_parser("serve", help="Run the local payment-gateway and review service.")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--llm-api", action="store_true", help="Load .env and require an API backend; never silently use heuristic.")
    serve_parser.add_argument("--env-file", type=str, default=None, help="Optional .env path; used with --llm-api.")

    llm_check_parser = subparsers.add_parser("llm-check", help="Make one real API request and report observed execution.")
    llm_check_parser.add_argument("--env-file", type=str, default=None)

    all_parser = subparsers.add_parser("all", help="Train first, then simulate the live flow.")
    all_parser.add_argument("--sample-size", type=int, default=None, help="Optional row limit after filtering.")
    all_parser.add_argument("--limit", type=int, default=300, help="Number of live transactions to process.")
    all_parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Optional dataset path. Defaults to the project-preferred dataset (PaySim).",
    )
    all_parser.add_argument(
        "--source",
        type=str,
        choices=["paysim", "ieee"],
        default=None,
        help="Explicit data source type. Required when the file is not named paysim.csv or train_transaction.csv.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "llm-check":
        check_llm_api(args.env_file)
        return

    if args.command == "train":
        from fraud_flow.training import train_model

        artifacts = train_model(data_path=args.data_path, sample_size=args.sample_size, source=args.source)
        print(
            json.dumps(
                {
                    "stage": "training",
                    "rows_used": artifacts.sample_size_used,
                    "selected_params": artifacts.params,
                    "selected_threshold": artifacts.threshold,
                    "metrics": artifacts.metrics,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.command == "simulate":
        from fraud_flow.pipeline import FraudFlowRunner

        runner = FraudFlowRunner()
        try:
            print(json.dumps(runner.simulate(limit=args.limit), indent=2, ensure_ascii=False))
        finally:
            runner.close()
        return

    if args.command == "stream":
        from fraud_flow.pipeline import FraudFlowRunner

        runner = FraudFlowRunner()
        try:
            for report in runner.stream(batch_size=args.batch_size, pause_seconds=args.pause):
                summary = {
                    "stage": "stream",
                    "cycle_index": report["cycle_index"],
                    "batch_index": report["batch_index"],
                    "batch_size": report["batch_size"],
                    "total_processed": report["total_processed"],
                    "fraud_transactions": report["metrics"]["positive_count"],
                    "normal_transactions": report["metrics"]["negative_count"],
                    "routes": report["routes"],
                    "actions": report["actions"],
                    "avg_ms": report["latency"]["avg_ms"],
                    "p95_ms": report["latency"]["p95_ms"],
                }
                print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
        except KeyboardInterrupt:
            print(
                json.dumps(
                    {
                        "stage": "stream",
                        "status": "stopped_by_user",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        finally:
            runner.close()
        return

    if args.command == "retrain":
        from fraud_flow.pipeline import FraudFlowRunner

        runner = FraudFlowRunner()
        try:
            print(json.dumps(runner.retrain(sample_size=args.sample_size, data_path=args.data_path, source=args.source), indent=2, ensure_ascii=False))
        finally:
            runner.close()
        return

    if args.command == "research":
        from fraud_flow.research import run_research_suite

        report = run_research_suite(
            data_path=args.data_path,
            sample_size=args.sample_size,
            seeds=parse_seed_list(args.seeds),
            bootstrap_iterations=args.bootstrap_iterations,
            external_data_path=args.external_data_path,
            source=args.source,
        )
        summary = {
            "stage": "research",
            "source": report["source"],
            "split": report["split"],
            "best_baseline": report["baseline"]["models"][0],
            "best_medium_policy": max(report["medium_branch"]["policies"], key=lambda item: item["block_f1"]),
            "best_multi_seed_model": report["robustness"]["multi_seed_summary"][0],
            "external_validation_source": report["external_validation"].get("source", "skipped"),
            "external_validation_mode": report["external_validation"].get("validation_mode", "skipped"),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    if args.command == "adapt":
        from fraud_flow.training import adapt_model_to_ieee

        artifacts = adapt_model_to_ieee(
            ieee_data_path=args.ieee_data_path,
            adapt_fraction=args.adapt_fraction,
        )
        print(
            json.dumps(
                {
                    "stage": "transfer_learning",
                    "base_model_source": artifacts.base_model_source,
                    "adapt_fraction": artifacts.adapt_fraction,
                    "adapt_rows": artifacts.adapt_rows,
                    "test_rows": artifacts.test_rows,
                    "best_num_boost_round": artifacts.num_boost_round,
                    "adapt_val_metrics": artifacts.adapt_metrics,
                    "test_metrics_90pct_ieee": artifacts.test_metrics,
                    "adapted_model_path": artifacts.adapted_model_path,
                    "adaptation_report_path": artifacts.adaptation_report_path,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.command == "deploy":
        from fraud_flow.deployment import DeploymentManager

        print(json.dumps(DeploymentManager().promote_candidate(reason=args.reason), indent=2, ensure_ascii=False))
        return

    if args.command == "rollback":
        from fraud_flow.deployment import DeploymentManager

        print(json.dumps(DeploymentManager().rollback(reason=args.reason), indent=2, ensure_ascii=False))
        return

    if args.command == "status":
        from fraud_flow.deployment import DeploymentManager

        print(json.dumps(DeploymentManager().status(), indent=2, ensure_ascii=False))
        return

    if args.command == "serve":
        if args.env_file and not args.llm_api:
            parser.error("--env-file cần đi cùng --llm-api.")
        if args.llm_api:
            configure_api_environment(args.env_file)
        import uvicorn

        from fraud_flow.service import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
        return

    if args.command == "all":
        from fraud_flow.deployment import DeploymentManager
        from fraud_flow.pipeline import FraudFlowRunner
        from fraud_flow.training import train_model

        if args.sample_size is not None:
            raise SystemExit(
                "`all --sample-size` is disabled because sample training runs are stored as isolated experiments "
                "and are not promoted automatically. Use `train --sample-size`, `research --sample-size`, "
                "and `simulate` as separate commands."
            )
        artifacts = train_model(data_path=args.data_path, sample_size=args.sample_size, source=args.source)
        DeploymentManager().promote_candidate(reason="Train-and-simulate workflow promoted the freshly trained candidate.")
        runner = FraudFlowRunner()
        try:
            payload = {
                "training": {
                    "rows_used": artifacts.sample_size_used,
                    "selected_params": artifacts.params,
                    "selected_threshold": artifacts.threshold,
                    "metrics": artifacts.metrics,
                },
                "simulation": runner.simulate(limit=args.limit),
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        finally:
            runner.close()
        return


if __name__ == "__main__":
    main()
