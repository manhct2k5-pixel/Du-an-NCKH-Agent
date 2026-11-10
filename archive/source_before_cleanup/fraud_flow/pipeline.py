from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnableLambda
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

from .agent import ReActInvestigator
from .anomaly import AnomalySidecar
from .calibration import calibrate_operational_score, summarize_numeric_distribution
from .config import APP_CONFIG
from .deployment import DeploymentManager, _normalise_path
from .feature_store import RedisFeatureStore
from .features import (
    assemble_feature_row,
    detect_data_source,
    enrich_transactions,
    event_from_row,
    feature_columns_for_source,
    load_filtered_frame,
)
from .llm_provider import build_high_risk_llm
from .narratives import build_transaction_narrative
from .redis_runtime import EmbeddedRedisServer
from .schema import ModelPrediction, PipelineActionName, PipelineResult, TransactionEvent
from .training import resolve_training_outputs, train_model


HIGH_RISK_PROMPT = PromptTemplate.from_template(
    """Generate a concise asynchronous high-risk log.
HIGH_RISK_CONTEXT_JSON_START
{context}
HIGH_RISK_CONTEXT_JSON_END"""
)


class JsonlLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, payload: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


class MonitoringLoop:
    def __init__(self, train_profile: dict[str, float], feature_columns: list[str]) -> None:
        self.train_profile = train_profile
        self.amount_feature = "transaction_amt_log1p" if "transaction_amt_log1p" in feature_columns else "amount_log1p"
        self.amount_log1p_values: list[float] = []
        self.tx_count_values: list[float] = []
        self.device_count_values: list[float] = []
        self.merchant_risk_values: list[float] = []

    def observe(self, feature_row: dict[str, float | int]) -> list[str]:
        self.amount_log1p_values.append(float(feature_row[self.amount_feature]))
        self.tx_count_values.append(float(feature_row["tx_count_24h"]))
        self.device_count_values.append(float(feature_row["device_tx_count_24h"]))
        self.merchant_risk_values.append(float(feature_row["merchant_fraud_rate"]))

        if len(self.amount_log1p_values) < 50:
            return []

        checks = {
            "amount_shift": (np.mean(self.amount_log1p_values[-50:]), self.train_profile["amount_log1p_mean"], 0.15),
            "tx_velocity_shift": (np.mean(self.tx_count_values[-50:]), self.train_profile["tx_count_24h_mean"], 0.35),
            "device_shift": (np.mean(self.device_count_values[-50:]), self.train_profile["device_tx_count_24h_mean"], 0.35),
            "merchant_risk_shift": (np.mean(self.merchant_risk_values[-50:]), self.train_profile["merchant_fraud_rate_mean"], 0.02),
        }

        flags: list[str] = []
        for name, (current, baseline, tolerance) in checks.items():
            if abs(current - baseline) > tolerance:
                flags.append(name)
        return flags


class AsyncHighRiskLogger:
    def __init__(self, logger: JsonlLogger) -> None:
        self.logger = logger
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="high-risk-log")
        self.futures: list[Future[Any]] = []
        self.chain = HIGH_RISK_PROMPT | build_high_risk_llm() | StrOutputParser()

    def submit(self, payload: dict[str, Any]) -> None:
        self.futures.append(self.executor.submit(self._write_log, payload))

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if hasattr(value, "to_dict"):
                normalized[key] = value.to_dict()
            else:
                normalized[key] = value
        return normalized

    def _write_log(self, payload: dict[str, Any]) -> None:
        normalized = self._normalize_payload(payload)
        tx_id = normalized.get("event", {}).get("tx_id")
        score = normalized.get("prediction", {}).get("score")
        try:
            message = self.chain.invoke({"context": json.dumps(normalized, ensure_ascii=False)})
            record = {
                "tx_id": tx_id,
                "score": score,
                "message": message,
                "status": "ok",
            }
        except Exception as exc:
            record = {
                "tx_id": tx_id,
                "score": score,
                "message": f"high-risk async logging failed: {exc}",
                "status": "error",
            }
        self.logger.append(record)

    def drain(self) -> None:
        if not self.futures:
            return
        futures = self.futures[:]
        self.futures.clear()
        wait(futures)
        for future in futures:
            future.result()

    def close(self) -> None:
        self.drain()
        self.executor.shutdown(wait=True)


class FraudModelService:
    def __init__(self) -> None:
        self.deployment = DeploymentManager()
        self.metadata = self._load_metadata()
        self.source = self.metadata.get("source") or detect_data_source(self.metadata.get("data_path"))
        self.feature_columns = list(self.metadata.get("feature_columns") or feature_columns_for_source(self.source))
        self.routing_thresholds = self._load_routing_thresholds()
        self.anomaly_flag_threshold = self._load_anomaly_flag_threshold()
        self.model = self._load_model()
        self.anomaly_sidecar = self._load_anomaly_sidecar()
        self.explainer = shap.TreeExplainer(self.model)

    def _load_metadata(self) -> dict[str, Any]:
        state = self.deployment.status()
        metadata_path = Path(state["active_metadata_path"]) if state.get("active_metadata_path") else APP_CONFIG.outputs.metadata_path
        if not metadata_path.exists():
            raise FileNotFoundError("Model metadata missing. Run `python3 run_fraud_flow.py train` first.")
        with metadata_path.open("r", encoding="utf-8") as fh:
            metadata = json.load(fh)
        return {k: _normalise_path(v) for k, v in metadata.items()}

    def _load_model(self) -> XGBClassifier:
        state = self.deployment.status()
        model_path = Path(state["active_model_path"]) if state.get("active_model_path") else APP_CONFIG.outputs.model_path
        if not model_path.exists():
            raise FileNotFoundError("Trained model missing. Run `python3 run_fraud_flow.py train` first.")
        model = XGBClassifier()
        model.load_model(model_path)
        return model

    def _load_anomaly_sidecar(self) -> AnomalySidecar | None:
        state = self.deployment.status()
        path_value = state.get("active_anomaly_model_path") or self.metadata.get("anomaly_model_path")
        path = Path(path_value) if path_value else APP_CONFIG.outputs.anomaly_model_path
        if not path.exists():
            return None
        try:
            return AnomalySidecar.load(path)
        except Exception:
            return None

    def _load_routing_thresholds(self) -> dict[str, float]:
        saved_thresholds = self.metadata.get("routing_thresholds") or {}
        low_threshold = float(saved_thresholds.get("low", APP_CONFIG.routing.low))
        high_threshold = float(saved_thresholds.get("high", APP_CONFIG.routing.high))
        if high_threshold <= low_threshold:
            high_threshold = float(APP_CONFIG.routing.high)
        return {
            "low": low_threshold,
            "high": high_threshold,
        }

    def _load_anomaly_flag_threshold(self) -> float:
        threshold = self.metadata.get("anomaly_flag_threshold", APP_CONFIG.anomaly.flag_threshold)
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            threshold = float(APP_CONFIG.anomaly.flag_threshold)
        if not 0.0 < threshold < 1.0:
            return float(APP_CONFIG.anomaly.flag_threshold)
        return threshold

    def predict(self, feature_row: dict[str, float | int]) -> ModelPrediction:
        started = time.perf_counter()
        vector = pd.DataFrame([feature_row], columns=self.feature_columns)
        raw_probability = float(self.model.predict_proba(vector)[0, 1])
        explanation = self.explain(vector)
        score = self._calibrate_operational_score(raw_probability)
        route = self._route(score)

        anomaly_score = self.anomaly_sidecar.score(feature_row) if self.anomaly_sidecar else 0.0
        anomaly_flag = anomaly_score >= self.anomaly_flag_threshold

        latency_ms = (time.perf_counter() - started) * 1000.0
        return ModelPrediction(
            score=score,
            raw_probability=raw_probability,
            route=route,
            explanation=explanation,
            latency_ms=latency_ms,
            anomaly_score=round(anomaly_score, 6),
            anomaly_flag=anomaly_flag,
        )

    def explain(self, vector: pd.DataFrame) -> list[dict[str, float | str]]:
        shap_values = self.explainer.shap_values(vector)[0]
        items: list[dict[str, float | str]] = []
        for feature_name, impact in zip(self.feature_columns, shap_values, strict=True):
            items.append({"feature": feature_name, "impact": float(impact), "weight": abs(float(impact))})
        top_items = sorted(items, key=lambda item: item["weight"], reverse=True)[:3]
        max_weight = max((item["weight"] for item in top_items), default=1.0) or 1.0
        for item in top_items:
            item["weight"] = round(item["weight"] / max_weight, 4)
        return top_items

    def _route(self, score: float) -> str:
        if score < self.routing_thresholds["low"]:
            return "low"
        if score > self.routing_thresholds["high"]:
            return "high"
        return "medium"

    def _calibrate_operational_score(self, raw_probability: float) -> float:
        calibration = self.metadata.get("routing_calibration", {})
        return calibrate_operational_score(raw_probability, calibration)


class FraudFlowRunner:
    def __init__(self) -> None:
        APP_CONFIG.outputs.simulation_report_path.parent.mkdir(parents=True, exist_ok=True)
        APP_CONFIG.outputs.dashboard_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_service = FraudModelService()
        self.redis_server = EmbeddedRedisServer()
        self.redis_client = self.redis_server.client()
        self.feature_store = RedisFeatureStore(self.redis_client)
        self.feature_store.flush()
        self.agent = ReActInvestigator(self.feature_store)
        self.prediction_logger = JsonlLogger(APP_CONFIG.outputs.prediction_log_path)
        self.feedback_logger = JsonlLogger(APP_CONFIG.outputs.feedback_log_path)
        self.manual_review_logger = JsonlLogger(APP_CONFIG.outputs.manual_review_queue_path)
        self.drift_alert_logger = JsonlLogger(APP_CONFIG.outputs.drift_alert_log_path)
        self.high_risk_logger = AsyncHighRiskLogger(JsonlLogger(APP_CONFIG.outputs.high_risk_log_path))
        self.monitor = MonitoringLoop(
            self.model_service.metadata["train_profile"],
            self.model_service.feature_columns,
        )
        self.deployment = DeploymentManager()
        self.review_events: dict[str, TransactionEvent] = {}
        self.applied_feedback: set[str] = set()

        self.router = RunnableBranch(
            (lambda payload: payload["prediction"].route == "low", RunnableLambda(self._handle_low)),
            (lambda payload: payload["prediction"].route == "high", RunnableLambda(self._handle_high)),
            RunnableLambda(self._handle_medium),
        )

    def quick_predict(self, event: TransactionEvent) -> tuple[Any, Any]:
        """Lookup features + XGBoost predict. Không gọi agent."""
        lookup = self.feature_store.lookup(event)
        feature_row = assemble_feature_row(event, lookup)
        prediction = self.model_service.predict(feature_row)
        return lookup, prediction

    def run_medium_agent_task(self, event: TransactionEvent, lookup: Any, prediction: Any) -> None:
        """
        Background task cho giao dịch medium-route.
        Chạy ReAct agent, cập nhật logs và lưu kết quả vào Redis.
        """
        started = time.perf_counter()

        payload = {"event": event, "lookup": lookup, "prediction": prediction}
        route_result = self._handle_medium(payload)
        final_action: PipelineActionName = route_result["final_action"]

        if route_result["agent"] is not None and final_action != "step_up":
            agent_structured = route_result["agent"].get("agent_output", {}).get("structured_output", {})
            reason_codes = list(agent_structured.get("reason_codes", []) or [])
            from .narratives import group_reason_codes
            narrative = {
                "human_readable_explanation": route_result["agent"]["human_readable_explanation"],
                "analyst_report": route_result["agent"]["analyst_report"],
                "dashboard_summary": route_result["agent"]["dashboard_summary"],
                "reason_codes": reason_codes,
                "reason_codes_grouped": group_reason_codes(reason_codes),
                "anomaly_score": prediction.anomaly_score,
                "anomaly_flag": prediction.anomaly_flag,
            }
        else:
            narrative = build_transaction_narrative(
                event=event.to_dict(),
                lookup=lookup.to_dict(),
                prediction=prediction.to_dict(),
                final_action=final_action,
                final_note=route_result["final_note"],
                agent=route_result["agent"],
            )

        result = PipelineResult(
            event=event.to_dict(),
            lookup=lookup.to_dict(),
            prediction=prediction.to_dict(),
            final_action=final_action,
            final_note=route_result["final_note"],
            agent=route_result["agent"],
            narrative=narrative,
            feedback_logged=False,
            monitoring_flags=[],
        )
        result.end_to_end_latency_ms = (time.perf_counter() - started) * 1000.0

        # Cập nhật review_events theo quyết định cuối của agent
        if final_action in ("review", "step_up"):
            self.review_events[event.tx_id] = event
        else:
            self.review_events.pop(event.tx_id, None)

        self.prediction_logger.append(result.to_dict())

        # Lưu kết quả điều tra vào Redis (TTL 24h) để có thể truy xuất sau
        self.redis_client.setex(
            f"investigation:{event.tx_id}",
            86_400,
            json.dumps(result.to_dict(), ensure_ascii=False, default=str),
        )

    def _prepare_simulation_frame(self) -> pd.DataFrame:
        data_path = self.model_service.metadata["data_path"]
        sample_size = self.model_service.metadata["sample_size_used"]
        source = self.model_service.source
        raw = load_filtered_frame(data_path, sample_size=sample_size, source=source)
        return enrich_transactions(raw, source=source)

    def bootstrap_online_history(self, rows: int | None = None) -> int:
        history_frame = self._prepare_simulation_frame()
        if rows:
            history_frame = history_frame.iloc[:rows].copy()
        self.feature_store.warm_start(
            event_from_row(row, source=self.model_service.source)
            for row in history_frame.itertuples(index=False)
        )
        return len(history_frame)

    def _warm_feature_store(self, simulation_frame: pd.DataFrame) -> pd.DataFrame:
        self.feature_store.flush()
        val_end = int(self.model_service.metadata["val_end"])
        warmup = simulation_frame.iloc[:val_end]
        self.feature_store.warm_start(
            event_from_row(row, source=self.model_service.source)
            for row in warmup.itertuples(index=False)
        )
        return simulation_frame.iloc[val_end:].reset_index(drop=True)

    def _handle_low(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "final_action": "approve",
            "final_note": "Nhánh low-risk: giao dịch được thông qua tự động để tối ưu tốc độ và chi phí xử lý.",
            "agent": None,
        }

    def _handle_high(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload["prediction"].raw_probability < APP_CONFIG.routing.high_raw_probability_floor:
            self.manual_review_logger.append(
                {
                    "event": payload["event"].to_dict(),
                    "prediction": payload["prediction"].to_dict(),
                    "agent": None,
                    "reason": "high_score_low_raw_probability",
                }
            )
            return {
                "final_action": "review",
                "final_note": (
                    "Score đã vào vùng cao nhưng xác suất gốc của model còn thấp, "
                    "nên hệ thống chuyển sang review để giảm block nhầm."
                ),
                "agent": None,
            }
        self.high_risk_logger.submit(payload)
        return {
            "final_action": "block",
            "final_note": "Nhánh high-risk: giao dịch bị chặn ngay lập tức và được ghi lại để hậu kiểm bất đồng bộ.",
            "agent": None,
        }

    def _step_up_reason(self, prediction: ModelPrediction, tool_results: dict[str, Any]) -> str | None:
        """
        Trả về lý do step_up nếu giao dịch đủ điều kiện, ngược lại trả None.
        step_up = cần xác minh tăng cường, KHÔNG phải fraud confirmed.

        Điều kiện kích hoạt (ưu tiên theo mức độ):
        1. anomaly_flag bật (giao dịch lệch chuẩn phân bố) → luôn step_up thay vì approve
        2. Thiết bị mới (needs_step_up) + IP rủi ro trung bình → step_up
        """
        device = tool_results.get("verify_device_id", {})
        ip = tool_results.get("check_ip_blacklist", {})

        if prediction.anomaly_flag:
            return (
                f"Anomaly sidecar phát hiện giao dịch lệch chuẩn phân bố "
                f"(anomaly_score={prediction.anomaly_score:.3f}). "
                "Cần xác minh tăng cường — chưa xác nhận là gian lận."
            )
        if device.get("needs_step_up") and ip.get("ip_fraud_rate", 0.0) >= 0.03:
            return (
                "Thiết bị mới kết hợp IP có lịch sử rủi ro. "
                "Cần xác minh tăng cường trước khi thông qua."
            )
        return None

    def _handle_medium(self, payload: dict[str, Any]) -> dict[str, Any]:
        prediction: ModelPrediction = payload["prediction"]
        investigation = self.agent.investigate(payload["event"], payload["lookup"], prediction)
        tool_results = investigation.tool_results

        final_action: PipelineActionName = investigation.action
        final_note = investigation.reviewer_note

        # Step-up override: nếu agent approve nhưng có tín hiệu cần xác minh tăng cường
        if final_action == "approve":
            step_up_reason = self._step_up_reason(prediction, tool_results)
            if step_up_reason:
                final_action = "step_up"
                final_note = step_up_reason

        if final_action in ("review", "step_up") or investigation.fallback_used:
            self.manual_review_logger.append(
                {
                    "event": payload["event"].to_dict(),
                    "prediction": prediction.to_dict(),
                    "agent": investigation.to_dict(),
                    "final_action": final_action,
                    "anomaly_override": prediction.anomaly_flag,
                    "step_up": final_action == "step_up",
                }
            )
        return {
            "final_action": final_action,
            "final_note": final_note,
            "agent": investigation.to_dict(),
        }

    def apply_feedback(self, tx_id: str, actual_label: int | None) -> bool:
        if actual_label is None or tx_id in self.applied_feedback:
            return False
        event = self.review_events.pop(tx_id, None)
        if event is None:
            return False
        self.feature_store.observe_feedback(event, actual_label)
        self.applied_feedback.add(tx_id)
        return True

    def process_event(
        self,
        event: TransactionEvent,
        actual_label: int | None = None,
        *,
        apply_feedback_immediately: bool = False,
    ) -> PipelineResult:
        started = time.perf_counter()
        lookup = self.feature_store.lookup(event)
        feature_row = assemble_feature_row(event, lookup)
        prediction = self.model_service.predict(feature_row)
        monitoring_flags = self.monitor.observe(feature_row)

        payload = {
            "event": event,
            "lookup": lookup,
            "prediction": prediction,
        }
        route_result = self.router.invoke(payload)
        final_action = route_result["final_action"]
        if route_result["agent"] is not None and final_action != "step_up":
            # Lấy text từ agent, bổ sung các trường còn thiếu từ structured output và prediction
            agent_structured = route_result["agent"].get("agent_output", {}).get("structured_output", {})
            reason_codes = list(agent_structured.get("reason_codes", []) or [])
            from .narratives import group_reason_codes
            narrative = {
                "human_readable_explanation": route_result["agent"]["human_readable_explanation"],
                "analyst_report": route_result["agent"]["analyst_report"],
                "dashboard_summary": route_result["agent"]["dashboard_summary"],
                "reason_codes": reason_codes,
                "reason_codes_grouped": group_reason_codes(reason_codes),
                "anomaly_score": prediction.anomaly_score,
                "anomaly_flag": prediction.anomaly_flag,
            }
        else:
            narrative = build_transaction_narrative(
                event=event.to_dict(),
                lookup=lookup.to_dict(),
                prediction=prediction.to_dict(),
                final_action=final_action,
                final_note=route_result["final_note"],
                agent=route_result["agent"],
            )

        self.feature_store.observe_activity(event)
        if final_action in ("review", "step_up"):
            self.review_events[event.tx_id] = event
        if apply_feedback_immediately and actual_label is not None:
            self.feature_store.observe_feedback(event, actual_label)
            self.applied_feedback.add(event.tx_id)
            self.review_events.pop(event.tx_id, None)
        correct = None if actual_label is None else int(final_action == "block") == int(actual_label == 1)

        result = PipelineResult(
            event=event.to_dict(),
            lookup=lookup.to_dict(),
            prediction=prediction.to_dict(),
            final_action=final_action,
            final_note=route_result["final_note"],
            agent=route_result["agent"],
            narrative=narrative,
            actual_label=actual_label,
            correct=correct,
            feedback_logged=actual_label is not None,
            monitoring_flags=monitoring_flags,
        )

        if actual_label is not None:
            self.feedback_logger.append(
                {
                    "tx_id": event.tx_id,
                    "actual_label": actual_label,
                    "predicted_action": final_action,
                    "score": prediction.score,
                }
            )
        if monitoring_flags:
            self.drift_alert_logger.append({"tx_id": event.tx_id, "flags": monitoring_flags})
        result.end_to_end_latency_ms = (time.perf_counter() - started) * 1000.0
        self.prediction_logger.append(result.to_dict())
        return result

    def simulate(self, limit: int | None = None) -> dict[str, Any]:
        simulation_frame = self._prepare_simulation_frame()
        live_frame = self._warm_feature_store(simulation_frame)
        if limit:
            live_frame = live_frame.iloc[:limit].copy()

        results: list[PipelineResult] = []
        for row in live_frame.itertuples(index=False):
            event = event_from_row(row, source=self.model_service.source)
            results.append(self.process_event(event, actual_label=event.is_fraud, apply_feedback_immediately=False))

        self.high_risk_logger.drain()
        report = self._build_simulation_report(results)
        APP_CONFIG.outputs.simulation_report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        APP_CONFIG.outputs.dashboard_snapshot_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return report

    def stream(self, batch_size: int = 1000, pause_seconds: float = 0.0) -> Iterator[dict[str, Any]]:
        if batch_size <= 0:
            raise ValueError("batch_size phải lớn hơn 0.")

        simulation_frame = self._prepare_simulation_frame()
        total_processed = 0
        cycle_index = 0

        while True:
            live_frame = self._warm_feature_store(simulation_frame)
            if live_frame.empty:
                raise ValueError("Không có giao dịch nào trong live frame để stream.")

            cycle_index += 1
            for batch_number, start in enumerate(range(0, len(live_frame), batch_size), start=1):
                stop = min(start + batch_size, len(live_frame))
                batch_frame = live_frame.iloc[start:stop].copy()

                results: list[PipelineResult] = []
                for row in batch_frame.itertuples(index=False):
                    event = event_from_row(row, source=self.model_service.source)
                    results.append(self.process_event(event, actual_label=event.is_fraud, apply_feedback_immediately=False))

                self.high_risk_logger.drain()
                total_processed += len(results)
                report = self._build_simulation_report(results)
                report.update(
                    {
                        "streaming": True,
                        "cycle_index": cycle_index,
                        "batch_index": batch_number,
                        "batch_start": start,
                        "batch_stop": stop,
                        "batch_size": len(results),
                        "total_processed": total_processed,
                    }
                )
                APP_CONFIG.outputs.simulation_report_path.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                APP_CONFIG.outputs.dashboard_snapshot_path.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                yield report

                if pause_seconds > 0:
                    time.sleep(pause_seconds)

    def _build_simulation_report(self, results: list[PipelineResult]) -> dict[str, Any]:
        actions = Counter(result.final_action for result in results)
        routes = Counter(result.prediction["route"] for result in results)
        y_true = np.array([result.actual_label for result in results if result.actual_label is not None], dtype=int)
        y_score = np.array([result.prediction["score"] for result in results if result.actual_label is not None], dtype=float)
        y_pred = np.array([1 if result.final_action == "block" else 0 for result in results if result.actual_label is not None], dtype=int)

        positive_count = int((y_true == 1).sum()) if len(y_true) else 0
        negative_count = int((y_true == 0).sum()) if len(y_true) else 0
        has_labeled_data = len(y_true) > 0
        auc_ready = len(set(y_true)) > 1
        metrics = {
            "evaluation_ready": has_labeled_data,
            "auc_ready": auc_ready,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "auc": float(roc_auc_score(y_true, y_score)) if auc_ready else None,
            "f1_block": float(f1_score(y_true, y_pred, zero_division=0)) if has_labeled_data else None,
            "precision_block": float(precision_score(y_true, y_pred, zero_division=0)) if has_labeled_data else None,
            "recall_block": float(recall_score(y_true, y_pred, zero_division=0)) if has_labeled_data else None,
        }

        drift_flags = Counter(flag for result in results for flag in result.monitoring_flags)
        model_latencies = [result.prediction["latency_ms"] for result in results]
        end_to_end_latencies = [result.end_to_end_latency_ms for result in results]
        latency = {
            "avg_ms": float(np.mean(end_to_end_latencies)) if results else 0.0,
            "p95_ms": float(np.percentile(end_to_end_latencies, 95)) if results else 0.0,
            "model_avg_ms": float(np.mean(model_latencies)) if results else 0.0,
            "model_p95_ms": float(np.percentile(model_latencies, 95)) if results else 0.0,
        }
        raw_probability_values = np.array([result.prediction["raw_probability"] for result in results], dtype=float)
        operational_score_values = np.array([result.prediction["score"] for result in results], dtype=float)

        return {
            "processed_transactions": len(results),
            "routes": dict(routes),
            "actions": dict(actions),
            "metrics": metrics,
            "latency": latency,
            "score_distribution": {
                "raw_probability": summarize_numeric_distribution(raw_probability_values),
                "operational_score": summarize_numeric_distribution(operational_score_values),
            },
            "drift_flags": dict(drift_flags),
            "source": self.model_service.source,
            "deployment": self.deployment.status(),
            "artifacts": {
                "prediction_log": str(APP_CONFIG.outputs.prediction_log_path),
                "feedback_log": str(APP_CONFIG.outputs.feedback_log_path),
                "high_risk_log": str(APP_CONFIG.outputs.high_risk_log_path),
                "manual_review_queue": str(APP_CONFIG.outputs.manual_review_queue_path),
            },
        }

    def retrain(self, sample_size: int | None = None, data_path: str | None = None, source: str | None = None) -> dict[str, Any]:
        previous = self.model_service.metadata
        run_outputs = resolve_training_outputs(sample_size)
        artifacts = train_model(data_path=data_path, sample_size=sample_size, source=source)
        with run_outputs.metadata_path.open("r", encoding="utf-8") as fh:
            current = json.load(fh)

        comparison = {
            "artifact_scope": current.get("artifact_scope", run_outputs.artifact_scope),
            "previous_test_auc": previous["test_metrics"]["auc"],
            "new_test_auc": current["test_metrics"]["auc"],
            "previous_test_f1": previous["test_metrics"]["f1"],
            "new_test_f1": current["test_metrics"]["f1"],
            "eligible_for_promotion": sample_size is None,
            "promoted": sample_size is None and current["test_metrics"]["auc"] >= previous["test_metrics"]["auc"],
            "rows_used": artifacts.sample_size_used,
        }
        if comparison["promoted"]:
            comparison["deployment"] = self.deployment.promote_candidate(
                reason="New model met or exceeded the previous AUC on the holdout test split."
            )
        else:
            comparison["deployment"] = self.deployment.status()
            if sample_size is not None:
                comparison["promotion_skipped_reason"] = (
                    "Sample retraining runs are isolated experiments and are never promoted."
                )
        return comparison

    def close(self) -> None:
        self.high_risk_logger.close()
        self.redis_server.close()
