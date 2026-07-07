from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import (
    APP_CONFIG,
    IDENTITY_DATA_PATH,
    IEEE_FEATURE_COLUMNS,
    PAYSIM_FEATURE_COLUMNS,
    RAW_COLUMNS,
    TRANSACTION_DATA_PATH,
    TYPE_ENCODING,
)
from .feature_store import FeatureStore
from .llm_features import build_transaction_llm_analysis
from .schema import FeatureLookup, TransactionEvent


BASE_TIMESTAMP = datetime(2025, 1, 1, 0, 0, 0)

IEEE_TRANSACTION_COLUMNS = [
    "TransactionID",
    "isFraud",
    "TransactionDT",
    "TransactionAmt",
    "ProductCD",
    "card1",
    "card2",
    "card3",
    "card4",
    "card5",
    "card6",
    "addr1",
    "addr2",
    "dist1",
    "dist2",
    "P_emaildomain",
    "R_emaildomain",
    *[f"C{i}" for i in range(1, 15)],
    *[f"D{i}" for i in range(1, 16)],
    *[f"M{i}" for i in range(1, 10)],
]

IEEE_IDENTITY_COLUMNS = [
    "TransactionID",
    "id_01",
    "id_02",
    "id_05",
    "id_06",
    "id_11",
    "id_13",
    "id_14",
    "id_17",
    "id_19",
    "id_20",
    "id_30",
    "id_31",
    "id_33",
    "DeviceType",
    "DeviceInfo",
]

IEEE_NUMERIC_EXTRA_COLUMNS = [
    "TransactionAmt",
    "TransactionDT",
    "card1",
    "card2",
    "card3",
    "card5",
    "addr1",
    "addr2",
    "dist1",
    "dist2",
    "id_01",
    "id_02",
    "id_05",
    "id_06",
    "id_11",
    "id_13",
    "id_14",
    "id_17",
    "id_19",
    "id_20",
    *[f"C{i}" for i in range(1, 15)],
    *[f"D{i}" for i in range(1, 16)],
]

IEEE_CATEGORICAL_EXTRA_COLUMNS = [
    "ProductCD",
    "card4",
    "card6",
    "P_emaildomain",
    "R_emaildomain",
    *[f"M{i}" for i in range(1, 10)],
    "id_30",
    "id_31",
    "id_33",
    "DeviceType",
    "DeviceInfo",
]


def infer_source_from_columns(columns: list[str] | pd.Index | tuple[str, ...]) -> str | None:
    names = {str(column) for column in columns}
    if {"TransactionID", "TransactionDT", "TransactionAmt"}.issubset(names):
        return "ieee"
    if {"step", "type", "amount", "nameOrig", "nameDest"}.issubset(names):
        return "paysim"
    return None


@lru_cache(maxsize=None)
def stable_bucket(value: str, salt: str, modulo: int) -> int:
    raw = f"{salt}:{value}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest(), 16) % modulo


def normalize_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float, np.integer, np.floating)):
        if pd.isna(value):
            return default
        return float(value)
    text = normalize_text(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def join_parts(*parts: Any) -> str:
    cleaned = [normalize_text(part) for part in parts if normalize_text(part)]
    return "|".join(cleaned) if cleaned else "unknown"


def detect_data_source(data_path: str | None = None, source: str | None = None) -> str:
    if source in ("paysim", "ieee"):
        return source
    candidate = normalize_text(data_path)
    if candidate.endswith("paysim.csv"):
        return "paysim"
    if "train_transaction" in candidate or "train_identity" in candidate:
        return "ieee"
    if APP_CONFIG.default_source == "paysim" and APP_CONFIG.data_path.exists():
        return "paysim"
    if APP_CONFIG.default_source == "ieee" and APP_CONFIG.transaction_data_path.exists() and APP_CONFIG.identity_data_path.exists():
        return "ieee"
    if APP_CONFIG.data_path.exists():
        return "paysim"
    if APP_CONFIG.transaction_data_path.exists() and APP_CONFIG.identity_data_path.exists():
        return "ieee"
    return APP_CONFIG.default_source


def resolve_ieee_transaction_path(data_path: str | Path | None = None) -> Path:
    if data_path:
        return Path(data_path)

    nested_transaction_path = APP_CONFIG.data_path.parent / "ieee-fraud-detection" / "train_transaction.csv"
    if TRANSACTION_DATA_PATH.exists():
        return TRANSACTION_DATA_PATH
    if nested_transaction_path.exists():
        return nested_transaction_path
    return TRANSACTION_DATA_PATH


def resolve_ieee_identity_path(transaction_path: str | Path | None = None) -> Path:
    if transaction_path:
        return Path(transaction_path).with_name("train_identity.csv")

    candidates = [
        IDENTITY_DATA_PATH,
        APP_CONFIG.data_path.parent / "ieee-fraud-detection" / "train_identity.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return IDENTITY_DATA_PATH


def feature_columns_for_source(source: str) -> list[str]:
    return IEEE_FEATURE_COLUMNS if source == "ieee" else PAYSIM_FEATURE_COLUMNS


def numeric_column(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def quantile_project_to_reference(source: pd.Series, reference: pd.Series) -> np.ndarray:
    source_values = pd.to_numeric(source, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if source_values.isna().all():
        source_values = pd.Series(0.0, index=source.index)
    else:
        source_values = source_values.fillna(float(source_values.median()))

    reference_values = pd.to_numeric(reference, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if len(reference_values) == 0:
        return np.zeros(len(source_values), dtype=float)
    if len(reference_values) == 1 or float(np.nanstd(reference_values)) == 0.0:
        return np.full(len(source_values), float(reference_values[0]), dtype=float)

    ranks = source_values.rank(method="average", pct=True).to_numpy(dtype=float)
    quantiles = np.clip(ranks, 0.0, 1.0)
    return np.quantile(reference_values, quantiles)


def align_ieee_dataset_to_paysim_features(ieee_dataset: pd.DataFrame, paysim_train_df: pd.DataFrame) -> pd.DataFrame:
    transaction_amt = numeric_column(ieee_dataset, "TransactionAmt")
    amount_log_proxy = np.log1p(np.maximum(transaction_amt.to_numpy(dtype=float), 0.0))
    amount_log1p = quantile_project_to_reference(pd.Series(amount_log_proxy, index=ieee_dataset.index), paysim_train_df["amount_log1p"])
    amount = np.expm1(amount_log1p)

    product_cd = ieee_dataset.get("ProductCD", pd.Series("", index=ieee_dataset.index)).astype(str).str.upper()
    type_encoded = np.where(product_cd == "W", 2, 1)

    hour_of_day = (numeric_column(ieee_dataset, "step") % 24).astype(int)
    avg_amount_7d_col = numeric_column(ieee_dataset, "avg_amount_7d")
    tx_count_24h_col = numeric_column(ieee_dataset, "tx_count_24h")
    source_balance_proxy = avg_amount_7d_col * (tx_count_24h_col + 1.0) + numeric_column(ieee_dataset, "card1")
    oldbalance_org = quantile_project_to_reference(source_balance_proxy, paysim_train_df["oldbalanceOrg"])
    newbalance_orig = np.maximum(oldbalance_org - amount, 0.0)

    c2 = numeric_column(ieee_dataset, "C2")
    dist1 = numeric_column(ieee_dataset, "dist1")
    dest_proxy = c2 * np.maximum(transaction_amt, 1.0) + dist1
    oldbalance_dest = quantile_project_to_reference(dest_proxy, paysim_train_df["oldbalanceDest"])
    newbalance_dest = oldbalance_dest + amount

    m_false_count = sum(
        (ieee_dataset.get(f"M{i}", pd.Series("", index=ieee_dataset.index))
         .astype(str).str.strip().str.upper() == "F").astype(float)
        for i in range(1, 10)
    )
    balance_diff = -amount * (m_false_count / 9.0)

    amount_ratio = amount / (oldbalance_org + 1.0)
    org_balance_delta_ratio = balance_diff / (oldbalance_org + 1.0)
    if "D2" in ieee_dataset.columns:
        d2_raw = pd.to_numeric(ieee_dataset["D2"], errors="coerce")
    else:
        d2_raw = pd.Series(np.nan, index=ieee_dataset.index)
    recipient_new_flag = (d2_raw.isna() | (d2_raw > 365)).astype(int)

    aligned = pd.DataFrame(
        {
            "amount_log1p": amount_log1p,
            "oldbalanceOrg": oldbalance_org,
            "newbalanceOrig": newbalance_orig,
            "oldbalanceDest": oldbalance_dest,
            "newbalanceDest": newbalance_dest,
            "type_encoded": type_encoded,
            "balance_diff": balance_diff,
            "amount_ratio": amount_ratio,
            "org_balance_delta_ratio": org_balance_delta_ratio,
            "hour_of_day": hour_of_day,
            "is_night_tx": (hour_of_day < 6).astype(int),
            "recipient_new_flag": recipient_new_flag,
            "tx_count_24h": tx_count_24h_col,
            "avg_amount_7d": avg_amount_7d_col,
            "device_tx_count_24h": numeric_column(ieee_dataset, "device_tx_count_24h"),
            "location_tx_count_24h": numeric_column(ieee_dataset, "location_tx_count_24h"),
            "merchant_tx_count_24h": numeric_column(ieee_dataset, "merchant_tx_count_24h"),
            "location_fraud_rate": numeric_column(ieee_dataset, "location_fraud_rate"),
            "ip_fraud_rate": numeric_column(ieee_dataset, "ip_fraud_rate"),
            "merchant_fraud_rate": numeric_column(ieee_dataset, "merchant_fraud_rate"),
            "llm_risk_score": numeric_column(ieee_dataset, "llm_risk_score"),
            "llm_reason_count": numeric_column(ieee_dataset, "llm_reason_count"),
            "llm_high_risk_flag": numeric_column(ieee_dataset, "llm_high_risk_flag"),
            "llm_review_flag": numeric_column(ieee_dataset, "llm_review_flag"),
            "llm_category_hash": numeric_column(ieee_dataset, "llm_category_hash"),
        },
        index=ieee_dataset.index,
    )
    aligned = aligned.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return aligned[PAYSIM_FEATURE_COLUMNS].astype(np.float32)


def enforce_feature_schema(
    feature_row: dict[str, float | int],
    source: str,
) -> dict[str, float | int]:
    expected_columns = feature_columns_for_source(source)
    missing = [column for column in expected_columns if column not in feature_row]
    extra = [column for column in feature_row if column not in expected_columns]
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise ValueError(
            f"Feature schema mismatch for source '{source}': " + "; ".join(details)
        )
    return {column: feature_row[column] for column in expected_columns}


def deterministic_time_sample(frame: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    if sample_size >= len(frame):
        return frame.reset_index(drop=True)
    positions = np.linspace(0, len(frame) - 1, num=sample_size, dtype=int)
    return frame.iloc[positions].copy().reset_index(drop=True)


def load_filtered_frame(
    data_path: str | None = None,
    sample_size: int | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    resolved_source = source or detect_data_source(data_path)

    if resolved_source == "ieee":
        transaction_path = resolve_ieee_transaction_path(data_path)
        identity_path = resolve_ieee_identity_path(transaction_path)

        missing_paths = [path for path in (transaction_path, identity_path) if not path.exists()]
        if missing_paths:
            missing_text = ", ".join(str(path) for path in missing_paths)
            raise FileNotFoundError(
                "IEEE-CIS data requires train_transaction.csv and train_identity.csv. "
                f"Missing: {missing_text}"
            )

        transaction_df = pd.read_csv(transaction_path, usecols=IEEE_TRANSACTION_COLUMNS)
        identity_df = pd.read_csv(identity_path, usecols=IEEE_IDENTITY_COLUMNS)
        frame = transaction_df.merge(identity_df, on="TransactionID", how="left")
        frame = frame.sort_values(["TransactionDT", "TransactionID"]).reset_index(drop=True)
        if sample_size and sample_size < len(frame):
            frame = deterministic_time_sample(frame, sample_size)
        return frame.reset_index(drop=True)

    frame = pd.read_csv(data_path or str(APP_CONFIG.data_path), usecols=RAW_COLUMNS)
    frame = frame[frame["type"].isin(["TRANSFER", "CASH_OUT"])].copy()
    frame = frame.sort_values(["step"]).reset_index(drop=True)
    if sample_size and sample_size < len(frame):
        frame = deterministic_time_sample(frame, sample_size)
    return frame.reset_index(drop=True)


def enrich_transactions(frame: pd.DataFrame, source: str | None = None) -> pd.DataFrame:
    resolved_source = source or infer_source_from_columns(frame.columns) or detect_data_source()
    if resolved_source == "ieee":
        enriched = frame.copy()
        enriched["tx_id"] = enriched["TransactionID"].astype(str)
        enriched["step"] = (enriched["TransactionDT"] // 3600).astype(int)
        enriched["timestamp"] = enriched["TransactionDT"].map(
            lambda value: (BASE_TIMESTAMP + timedelta(seconds=int(value))).isoformat()
        )
        enriched["card_id"] = enriched.apply(
            lambda row: join_parts(row["card1"], row["card2"], row["card3"], row["card5"], row["card6"]),
            axis=1,
        )
        enriched["merchant_id"] = enriched.apply(
            lambda row: join_parts(row["ProductCD"], row["P_emaildomain"], row["R_emaildomain"], row["addr1"], row["addr2"]),
            axis=1,
        )
        enriched["device_id"] = enriched.apply(
            lambda row: join_parts(row["DeviceType"], row["DeviceInfo"], row["id_30"], row["id_31"], row["id_33"]),
            axis=1,
        )
        enriched["location_id"] = enriched.apply(
            lambda row: join_parts(row["addr1"], row["addr2"], row["dist1"], row["dist2"]),
            axis=1,
        )
        enriched["ip_address"] = enriched.apply(
            lambda row: (
                f"10."
                f"{stable_bucket(join_parts(row['addr1'], row['addr2']), 'ieee-ip-a', 250) + 1}."
                f"{stable_bucket(join_parts(row['id_31'], row['DeviceType']), 'ieee-ip-b', 250) + 1}."
                f"{stable_bucket(join_parts(row['ProductCD'], row['P_emaildomain']), 'ieee-ip-c', 250) + 1}"
            ),
            axis=1,
        )
        return enriched

    enriched = frame.copy()
    enriched["tx_id"] = [f"tx_{idx:07d}" for idx in range(len(enriched))]
    enriched["timestamp"] = enriched["step"].map(lambda step: (BASE_TIMESTAMP + timedelta(hours=int(step))).isoformat())
    enriched["card_id"] = enriched["nameOrig"]
    enriched["merchant_id"] = enriched["nameDest"].map(
        lambda value: f"merchant_{stable_bucket(str(value), 'merchant', 50000):05d}"
    )
    enriched["device_id"] = enriched["nameOrig"].map(
        lambda value: f"device_{stable_bucket(str(value), 'device', 20000):05d}"
    )
    enriched["location_id"] = enriched["nameDest"].map(
        lambda value: f"zone_{stable_bucket(str(value), 'location', 200):03d}"
    )
    enriched["ip_address"] = enriched.apply(
        lambda row: (
            f"10."
            f"{stable_bucket(str(row['nameOrig']), 'ip-a', 250) + 1}."
            f"{stable_bucket(str(row['nameDest']), 'ip-b', 250) + 1}."
            f"{stable_bucket(str(row['type']), 'ip-c', 250) + 1}"
        ),
        axis=1,
    )
    return enriched


def event_from_row(row: pd.Series | object, source: str | None = None) -> TransactionEvent:
    resolved_source = source or getattr(row, "source", None)
    if resolved_source is None:
        row_fields = set(getattr(row, "_fields", ()))
        if {"TransactionID", "TransactionDT", "TransactionAmt"}.issubset(row_fields):
            resolved_source = "ieee"
        elif {"step", "type", "amount", "nameOrig", "nameDest"}.issubset(row_fields):
            resolved_source = "paysim"
        else:
            resolved_source = detect_data_source()
    if resolved_source == "ieee":
        extras = {"source": "ieee"}
        for column in IEEE_NUMERIC_EXTRA_COLUMNS:
            extras[column] = safe_float(getattr(row, column, None))
        for column in IEEE_CATEGORICAL_EXTRA_COLUMNS:
            extras[column] = normalize_text(getattr(row, column, None))

        return TransactionEvent(
            tx_id=str(getattr(row, "tx_id")),
            step=int(getattr(row, "step")),
            timestamp=str(getattr(row, "timestamp")),
            tx_type=normalize_text(getattr(row, "ProductCD")),
            amount=safe_float(getattr(row, "TransactionAmt")),
            card_id=normalize_text(getattr(row, "card_id")),
            merchant_id=normalize_text(getattr(row, "merchant_id")),
            device_id=normalize_text(getattr(row, "device_id")),
            ip_address=normalize_text(getattr(row, "ip_address")),
            location_id=normalize_text(getattr(row, "location_id")),
            oldbalanceOrg=0.0,
            newbalanceOrig=0.0,
            oldbalanceDest=0.0,
            newbalanceDest=0.0,
            is_fraud=None if pd.isna(getattr(row, "isFraud", None)) else int(getattr(row, "isFraud")),
            is_flagged_fraud=0,
            extras=extras,
        )

    return TransactionEvent(
        tx_id=str(getattr(row, "tx_id")),
        step=int(getattr(row, "step")),
        timestamp=str(getattr(row, "timestamp")),
        tx_type=str(getattr(row, "type")),
        amount=float(getattr(row, "amount")),
        card_id=str(getattr(row, "card_id")),
        merchant_id=str(getattr(row, "merchant_id")),
        device_id=str(getattr(row, "device_id")),
        ip_address=str(getattr(row, "ip_address")),
        location_id=str(getattr(row, "location_id")),
        oldbalanceOrg=float(getattr(row, "oldbalanceOrg")),
        newbalanceOrig=float(getattr(row, "newbalanceOrig")),
        oldbalanceDest=float(getattr(row, "oldbalanceDest")),
        newbalanceDest=float(getattr(row, "newbalanceDest")),
        is_fraud=None if pd.isna(getattr(row, "isFraud", None)) else int(getattr(row, "isFraud")),
        is_flagged_fraud=None if pd.isna(getattr(row, "isFlaggedFraud", None)) else int(getattr(row, "isFlaggedFraud")),
        extras={"source": "paysim"},
    )


def assemble_feature_row(event: TransactionEvent, lookup: FeatureLookup) -> dict[str, float | int]:
    source = event.extras.get("source", "paysim")
    llm_analysis = build_transaction_llm_analysis(event, lookup)
    llm_features = {
        "llm_risk_score": llm_analysis["risk_score"],
        "llm_reason_count": llm_analysis["reason_count"],
        "llm_high_risk_flag": llm_analysis["high_risk_flag"],
        "llm_review_flag": llm_analysis["review_flag"],
        "llm_category_hash": stable_bucket(llm_analysis["category"], "llm-category", 2048),
    }
    if source == "ieee":
        extras = event.extras
        missing_ratio = sum(
            1 for key, value in extras.items()
            if key != "source" and (value == "" or value == 0.0)
        ) / max(len(extras) - 1, 1)

        c_sum = sum(safe_float(extras.get(f"C{i}", 0.0)) for i in range(1, 15))
        d_sum = sum(safe_float(extras.get(f"D{i}", 0.0)) for i in range(1, 16))

        return enforce_feature_schema({
            "transaction_amt_log1p": float(np.log1p(event.amount)),
            "tx_hour": event.step % 24,
            "tx_day": event.step // 24,
            "product_cd_hash": stable_bucket(normalize_text(extras.get("ProductCD")), "product", 5000),
            "card1": safe_float(extras.get("card1")),
            "card2": safe_float(extras.get("card2")),
            "card3": safe_float(extras.get("card3")),
            "card5": safe_float(extras.get("card5")),
            "addr1": safe_float(extras.get("addr1")),
            "addr2": safe_float(extras.get("addr2")),
            "dist1": safe_float(extras.get("dist1")),
            "dist2": safe_float(extras.get("dist2")),
            "card4_hash": stable_bucket(normalize_text(extras.get("card4")), "card4", 5000),
            "card6_hash": stable_bucket(normalize_text(extras.get("card6")), "card6", 5000),
            "p_email_hash": stable_bucket(normalize_text(extras.get("P_emaildomain")), "pemail", 10000),
            "r_email_hash": stable_bucket(normalize_text(extras.get("R_emaildomain")), "remail", 10000),
            "device_type_hash": stable_bucket(normalize_text(extras.get("DeviceType")), "dtype", 1000),
            "device_info_hash": stable_bucket(normalize_text(extras.get("DeviceInfo")), "dinfo", 50000),
            "id30_hash": stable_bucket(normalize_text(extras.get("id_30")), "os", 10000),
            "id31_hash": stable_bucket(normalize_text(extras.get("id_31")), "browser", 10000),
            "id33_hash": stable_bucket(normalize_text(extras.get("id_33")), "screen", 10000),
            "card_id_hash": stable_bucket(event.card_id, "card_id", 50000),
            "merchant_id_hash": stable_bucket(event.merchant_id, "merchant_id", 50000),
            "location_id_hash": stable_bucket(event.location_id, "location_id", 50000),
            "c_sum": c_sum,
            "d_sum": d_sum,
            "missing_ratio": round(missing_ratio, 6),
            "email_match": int(
                bool(normalize_text(extras.get("P_emaildomain")))
                and normalize_text(extras.get("P_emaildomain")) == normalize_text(extras.get("R_emaildomain"))
            ),
            "is_mobile": int(normalize_text(extras.get("DeviceType")).lower() == "mobile"),
            "tx_count_24h": lookup.tx_count_24h,
            "avg_amount_7d": lookup.avg_amount_7d,
            "device_tx_count_24h": lookup.device_tx_count_24h,
            "location_tx_count_24h": lookup.location_tx_count_24h,
            "merchant_tx_count_24h": lookup.merchant_tx_count_24h,
            "location_fraud_rate": lookup.location_fraud_rate,
            "ip_fraud_rate": lookup.ip_fraud_rate,
            "merchant_fraud_rate": lookup.merchant_fraud_rate,
            **llm_features,
        }, source)

    balance_diff = event.oldbalanceOrg - event.newbalanceOrig - event.amount
    hour_of_day = event.step % 24
    return enforce_feature_schema({
        "amount_log1p": float(np.log1p(event.amount)),
        "oldbalanceOrg": event.oldbalanceOrg,
        "newbalanceOrig": event.newbalanceOrig,
        "oldbalanceDest": event.oldbalanceDest,
        "newbalanceDest": event.newbalanceDest,
        "type_encoded": TYPE_ENCODING.get(event.tx_type, -1),
        "balance_diff": balance_diff,
        "amount_ratio": event.amount / (event.oldbalanceOrg + 1.0),
        "org_balance_delta_ratio": balance_diff / (event.oldbalanceOrg + 1.0),
        "hour_of_day": hour_of_day,
        "is_night_tx": int(hour_of_day < 6),
        "recipient_new_flag": int(event.oldbalanceDest == 0),
        "tx_count_24h": lookup.tx_count_24h,
        "avg_amount_7d": lookup.avg_amount_7d,
        "device_tx_count_24h": lookup.device_tx_count_24h,
        "location_tx_count_24h": lookup.location_tx_count_24h,
        "merchant_tx_count_24h": lookup.merchant_tx_count_24h,
        "location_fraud_rate": lookup.location_fraud_rate,
        "ip_fraud_rate": lookup.ip_fraud_rate,
        "merchant_fraud_rate": lookup.merchant_fraud_rate,
        **llm_features,
    }, source)


def build_feature_frame(
    enriched: pd.DataFrame,
    source: str | None = None,
    freeze_risk_labels: bool = False,
    store: FeatureStore | None = None,
) -> tuple[pd.DataFrame, list[TransactionEvent], FeatureStore]:
    resolved_source = source or infer_source_from_columns(enriched.columns) or detect_data_source()
    if store is None:
        store = FeatureStore()
    feature_rows: list[dict[str, float | int]] = []
    events: list[TransactionEvent] = []

    for row in enriched.itertuples(index=False):
        event = event_from_row(row, source=resolved_source)
        lookup = store.lookup(event)
        feature_rows.append(assemble_feature_row(event, lookup))
        if freeze_risk_labels:
            store.observe_activity(event)   # chỉ đếm số lượng, không cập nhật fraud rate
        else:
            store.observe(event, event.is_fraud)  # train: cập nhật đầy đủ
        events.append(event)

    feature_df = pd.DataFrame(feature_rows)
    feature_df = feature_df[feature_columns_for_source(resolved_source)]
    return feature_df, events, store
