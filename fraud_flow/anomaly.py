from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import IsolationForest


# Features dùng cho anomaly detector — chỉ dùng transaction core + behavior,
# bỏ LLM features vì chúng có ngữ nghĩa khác và không phải tín hiệu phân bố
ANOMALY_FEATURE_COLUMNS = [
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
]


class AnomalySidecar:
    """
    IsolationForest sidecar huấn luyện trên giao dịch legitimate.
    Trả về anomaly_score trong [0, 1]: càng cao càng bất thường.
    Được dùng như side signal để override routing ở nhánh medium (Cách 2).
    """

    def __init__(self, contamination: float = 0.01, n_estimators: int = 100, random_state: int = 42) -> None:
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self._model: IsolationForest | None = None
        # Dùng để normalize score về [0, 1]
        self._score_min: float = -1.0
        self._score_max: float = 0.0

    def train(self, train_df: pd.DataFrame) -> dict[str, float]:
        """
        Huấn luyện trên tập legitimate (isFraud == 0) của train set.
        Trả về thống kê anomaly score trên toàn bộ train_df để kiểm tra.
        """
        legitimate = train_df[train_df["isFraud"] == 0][ANOMALY_FEATURE_COLUMNS].copy()
        legitimate = legitimate.fillna(0.0)

        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._model.fit(legitimate)

        # Tính min/max score trên toàn train để normalize
        all_features = train_df[ANOMALY_FEATURE_COLUMNS].fillna(0.0)
        raw_scores = self._model.score_samples(all_features)
        self._score_min = float(raw_scores.min())
        self._score_max = float(raw_scores.max())

        # Thống kê để ghi vào report
        fraud_mask = train_df["isFraud"] == 1
        fraud_scores = self._normalize(raw_scores[fraud_mask.values])
        legit_scores = self._normalize(raw_scores[~fraud_mask.values])

        return {
            "train_legitimate_rows": int((~fraud_mask).sum()),
            "train_fraud_rows": int(fraud_mask.sum()),
            "anomaly_score_fraud_mean": float(np.mean(fraud_scores)) if len(fraud_scores) else 0.0,
            "anomaly_score_fraud_p90": float(np.percentile(fraud_scores, 90)) if len(fraud_scores) else 0.0,
            "anomaly_score_legit_mean": float(np.mean(legit_scores)),
            "anomaly_score_legit_p90": float(np.percentile(legit_scores, 90)),
            "score_min_raw": self._score_min,
            "score_max_raw": self._score_max,
        }

    def _normalize(self, raw: np.ndarray) -> np.ndarray:
        """Chuyển score của IsolationForest về [0, 1]: 1 = bất thường nhất."""
        span = self._score_max - self._score_min
        if span == 0:
            return np.zeros_like(raw)
        normalized = (raw - self._score_min) / span
        # Đảo chiều: IsolationForest score thấp hơn = bất thường hơn
        return 1.0 - np.clip(normalized, 0.0, 1.0)

    def score(self, feature_row: dict[str, float | int]) -> float:
        """
        Tính anomaly score cho một giao dịch đơn lẻ.
        Trả về float trong [0, 1]: càng cao càng bất thường.
        """
        if self._model is None:
            return 0.0
        values = [float(feature_row.get(col, 0.0)) for col in ANOMALY_FEATURE_COLUMNS]
        vector = pd.DataFrame([values], columns=ANOMALY_FEATURE_COLUMNS)
        raw = self._model.score_samples(vector)
        return float(self._normalize(raw)[0])

    def score_batch(self, df: pd.DataFrame) -> np.ndarray:
        """Tính anomaly score cho cả DataFrame. Dùng trong evaluate."""
        if self._model is None:
            return np.zeros(len(df))
        features = df[ANOMALY_FEATURE_COLUMNS].fillna(0.0)
        raw = self._model.score_samples(features)
        return self._normalize(raw)

    def compute_adaptive_threshold(self, df: pd.DataFrame, percentile: float = 95.0) -> float:
        """
        Tính ngưỡng tự động từ Percentile thứ `percentile` của anomaly scores trên df.
        Dùng để auto-calibrate thay vì hardcode flag_threshold.
        """
        scores = self.score_batch(df)
        return float(np.percentile(scores, percentile))

    def evaluate(self, df: pd.DataFrame, threshold: float) -> dict[str, object]:
        """
        Đánh giá anomaly sidecar trên tập val/test.
        Trả về phân bố score và số case fraud bị bỏ sót bởi XGBoost
        nhưng có anomaly_score cao.
        """
        scores = self.score_batch(df)
        fraud_mask = df["isFraud"].values == 1

        fraud_scores = scores[fraud_mask]
        legit_scores = scores[~fraud_mask]

        flagged = scores >= threshold
        flagged_fraud = flagged & fraud_mask
        flagged_legit = flagged & ~fraud_mask

        return {
            "threshold": threshold,
            "total_rows": len(df),
            "fraud_rows": int(fraud_mask.sum()),
            "legit_rows": int((~fraud_mask).sum()),
            "anomaly_score_fraud_mean": float(np.mean(fraud_scores)) if len(fraud_scores) else 0.0,
            "anomaly_score_fraud_p50": float(np.percentile(fraud_scores, 50)) if len(fraud_scores) else 0.0,
            "anomaly_score_fraud_p90": float(np.percentile(fraud_scores, 90)) if len(fraud_scores) else 0.0,
            "anomaly_score_legit_mean": float(np.mean(legit_scores)),
            "anomaly_score_legit_p90": float(np.percentile(legit_scores, 90)),
            "flagged_total": int(flagged.sum()),
            "flagged_fraud": int(flagged_fraud.sum()),
            "flagged_legit": int(flagged_legit.sum()),
            "fraud_catch_rate": float(flagged_fraud.sum() / max(fraud_mask.sum(), 1)),
            "false_flag_rate": float(flagged_legit.sum() / max((~fraud_mask).sum(), 1)),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self._model,
                "score_min": self._score_min,
                "score_max": self._score_max,
                "contamination": self.contamination,
                "n_estimators": self.n_estimators,
                "random_state": self.random_state,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> AnomalySidecar:
        data = joblib.load(path)
        instance = cls(
            contamination=data["contamination"],
            n_estimators=data["n_estimators"],
            random_state=data["random_state"],
        )
        instance._model = data["model"]
        instance._score_min = data["score_min"]
        instance._score_max = data["score_max"]
        return instance
