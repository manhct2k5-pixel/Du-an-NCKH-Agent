# Bảng ngưỡng (Thresholds) — Fraud Detection System

> **Nguồn tin cậy:** routing lấy từ `fraud_flow/config.py` và model metadata; anomaly threshold lấy từ
> `model_metadata.json` nếu có, fallback về `fraud_flow/config.py`.
> Mọi tài liệu khác phải đồng bộ theo file này.

---

## 1. Ngưỡng phân loại XGBoost (Classification threshold)

| Tên | Giá trị | Nơi định nghĩa | Dùng ở đâu |
|---|---|---|---|
| `selected_threshold` | 0.50 (run hiện tại; chọn tự động theo F1 trên val) | `config.py` → `threshold_grid`, chọn trong `training.py:find_best_threshold()` | Phân loại cuối: `raw_probability >= threshold` → fraud |
| Tập tìm kiếm (`threshold_grid`) | 0.20 → 0.70 (bước 0.05) | `config.py:134` | Grid search khi training |

---

## 2. Ngưỡng routing XGBoost (Operational score)

Pipeline online dùng **operational score** (đã qua `calibrate_operational_score`), không phải raw probability trực tiếp.

| Tên | Giá trị | Nơi định nghĩa | Ý nghĩa |
|---|---|---|---|
| `routing_low` | **0.30** | `config.py:119` (`RoutingThresholds.low`) | score < 0.30 → **auto approve** |
| `routing_high` | **0.85** | `config.py:120` (`RoutingThresholds.high`) | score > 0.85 → **auto block** |
| Vùng medium | 0.30 – 0.85 | — | → ReAct Agent xử lý |
| `high_raw_probability_floor` | 0.05 | `config.py:121` | Nếu vào vùng high nhưng raw_prob < 0.05 → chuyển review thay vì block |

> **Lưu ý:** Routing thresholds được lưu vào model metadata khi train (`training.py:424-426`) và đọc lại trong `pipeline.py:183-188`. Nếu metadata có giá trị khác config, metadata thắng — ngoại trừ `routing_high` luôn bị override về `APP_CONFIG.routing.high` (`pipeline.py:187-188`).

---

## 3. Ngưỡng anomaly sidecar

| Tên | Giá trị | Nơi định nghĩa | Dùng ở đâu |
|---|---|---|---|
| `anomaly_flag_threshold` | **0.418285** hiện tại | `model_metadata.json` → `anomaly_flag_threshold` | Anomaly score >= ngưỡng adaptive → đánh dấu flag trong nhánh medium |
| fallback config | 0.70 | `config.py:178` (`AnomalyConfig.flag_threshold`) | Chỉ dùng khi metadata model cũ chưa có ngưỡng adaptive |

> **Lưu ý calibration:** Test hiện tại có anomaly score fraud mean `0.4135` và legit mean `0.1798`, nhưng hai phân bố vẫn overlap. Ngưỡng adaptive P95 validation `0.418285` flag `4,866/69,060` giao dịch test, trong đó có `344` fraud và `4,522` legitimate. Vì vậy anomaly sidecar là side signal, không phải rule block cứng.

---

## 4. Ngưỡng LLM score (nội bộ `llm_features.py`)

Đây là ngưỡng riêng cho LLM risk score — **không liên quan** đến XGBoost routing threshold.

| Tên | Giá trị | Nơi định nghĩa | Dùng ở đâu |
|---|---|---|---|
| `high_risk_flag` | score >= **0.70** | `llm_features.py:105` | Feature nhị phân cho XGBoost |
| `review_flag` | 0.30 <= score < **0.70** | `llm_features.py:106` | Feature nhị phân cho XGBoost |

---

## 5. Tóm tắt nhanh cho báo cáo

```
selected_threshold  = 0.50   # XGBoost classification (raw probability, run hiện tại)
routing_low         = 0.30   # Operational score — auto approve
routing_high        = 0.85   # Operational score — auto block
anomaly_flag        = 0.418285  # Anomaly sidecar — P95 validation, lưu trong model_metadata.json
```

---

## 6. Ghi chú runtime

- Nhánh `low` và `high` không gọi Medium ReAct Agent.
- Medium ReAct Agent hiện chạy **đồng bộ** trong pipeline, nên latency phụ thuộc vào thời gian agent/tool lookup.
- High-risk explanation log mới là phần **bất đồng bộ** (`artifacts/logs/high_risk_async_llm.jsonl`).
- Khi scale TPS lớn, nên chuyển medium cases sang async queue hoặc dùng timeout/fallback deterministic.

---

## 7. Lịch sử mâu thuẫn đã phát hiện

| File | Lỗi | Trạng thái |
|---|---|---|
| `docs/BANG_KET_QUA_BAO_CAO.md` | `routing_high_threshold = 0.70` (sai, phải là 0.85) | **Đã sửa: 0.85** |
| `docs/REPORT_MO_HINH_PAYSIM.md` | `routing high = 0.85` | Đúng ✓ |
| `HUONG_DAN_CHAY_MO_HINH.md:212` | `high > 0.85` | Đúng ✓ |
| `artifacts/models/model_metadata.json` | `routing_thresholds.high = 0.85` | Đúng ✓ |
