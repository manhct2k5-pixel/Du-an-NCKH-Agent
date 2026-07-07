# Báo cáo NCKH — Phần Cải tiến Hệ thống Phát hiện Gian lận

**Ngày cập nhật tài liệu:** 2026-04-20  
**Bộ số liệu dùng để cập nhật:** train/simulation/transfer adaptive run ngày 2026-04-20; research suite clean run ngày 2026-04-17  
**Model active hiện tại:** `v20260420T053341630222Z`

> Tài liệu này mô tả đầy đủ các cải tiến kỹ thuật được thực hiện trong nghiên cứu,
> bao gồm thiết kế, tích hợp, đánh giá định lượng và case study định tính.
> Có thể dùng trực tiếp làm nội dung cho phần **Phương pháp** và **Kết quả** trong bài NCKH.

---

## 1. Mô tả Baseline — Hệ thống Fraud Detection Nhiều Lớp

Hệ thống baseline được xây dựng theo kiến trúc **pipeline nhiều lớp (multi-layer pipeline)**,
kết hợp học có giám sát, feature store thời gian thực, và tác tử điều tra tự động.

### 1.1 Kiến trúc tổng quan

```
Sự kiện giao dịch
       │
       ▼
Feature Store (Redis)
  - tx_count_24h, avg_amount_7d
  - device/location/merchant fraud rate
       │
       ▼
XGBoost Backbone
  - 25 features (giao dịch + hành vi + LLM-style)
  - Calibrated operational score [0, 1]
  - SHAP explanation
       │
       ▼
Router (3 nhánh)
  ┌────────────────────────────────────┐
  │ Low  (score < 0.30) → Approve      │
  │ High (score > 0.85) → Block        │
  │ Medium (0.30–0.85) → ReAct Agent   │
  └────────────────────────────────────┘
       │
       ▼
Narrative + Output (3 cấp: human / analyst / dashboard)
```

### 1.2 Thông số model production hiện tại

| Thông số | Giá trị |
|---|---|
| Backbone | XGBoost (n_estimators=260, max_depth=6, lr=0.06) |
| Dataset | PaySim (460,394 giao dịch, TRANSFER + CASH_OUT) |
| External validation | IEEE-CIS frozen-vs-native benchmark (train_transaction + train_identity) |
| Split strategy | Chronological theo step |
| Train / Val / Test | 322,275 / 69,059 / 69,060 |
| Selected threshold | 0.50 |
| scale_pos_weight | 750.22 |

### 1.3 Metric baseline trên holdout test (69,060 giao dịch)

| Metric | Giá trị |
|---|---|
| AUC | **0.998383** |
| PR AUC | **0.997002** |
| F1 | **0.993103** |
| Precision | **0.989313** |
| Recall | **0.996923** |

Confusion matrix:

| | Dự đoán: Hợp lệ | Dự đoán: Gian lận |
|---|---|---|
| Thực tế: Hợp lệ | 68,403 (TN) | 7 (FP) |
| Thực tế: Gian lận | **2 (FN)** | 648 (TP) |

### 1.4 Vai trò của hai bộ dữ liệu

Nghiên cứu không lựa chọn giữa PaySim và IEEE-CIS như hai hướng thay thế nhau. PaySim được dùng làm
nguồn chính để đánh giá đầy đủ kiến trúc nhiều lớp vì dữ liệu có timeline, nhãn và cấu trúc giao dịch
phù hợp cho mô phỏng luồng online. IEEE-CIS được dùng làm external validation trên dữ liệu thực tế hơn:
mô hình XGBoost sau khi học trên PaySim được đóng băng, dữ liệu IEEE-CIS được align sang 25 đặc trưng
đầu vào PaySim, rồi chỉ dùng để dự đoán và tính metric cuối. Nhãn IEEE-CIS không tham gia train, chọn
threshold hay cập nhật fraud-rate history trước khi dự đoán.

Trong báo cáo thực nghiệm, kết quả PaySim được trình bày ở các phần baseline comparison, feature
ablation, medium-branch ablation và robustness validation. Kết quả IEEE-CIS được tách riêng trong
`artifacts/reports/external_validation.*` để kiểm tra ngoài phân bố và phân tích domain shift.
Kết quả frozen-model hiện tại đạt AUC `0.6285` trên IEEE-CIS, thấp hơn rất xa PaySim và cho thấy
domain shift/schema shift rất mạnh.
Vì vậy kết quả này cần được trình bày như giới hạn chuyển miền của schema PaySim, không được diễn giải
quá mức là mô hình PaySim đã tổng quát hóa trực tiếp sang IEEE-CIS.
Sau bước transfer learning, model PaySim được adapt bằng 10% IEEE-CIS sau khi align sang 25 PaySim features,
giúp AUC trên phần IEEE-CIS còn lại tăng lên `0.677369`. Kết quả này chứng minh hướng giảm domain shift
một phần, nhưng vẫn thấp hơn IEEE-native retrained benchmark (`0.841506`).

### 1.5 Snapshot kết quả mô hình hiện tại

| Nhóm kết quả | Số liệu chính | Nguồn artifact |
|---|---|---|
| XGBoost PaySim test | AUC `0.998383`, PR-AUC `0.997002`, F1 `0.993103`, Recall `0.996923` | `artifacts/reports/evaluation_report.json` |
| Baseline offline tốt nhất | HistGradientBoosting, test AUC `0.999932`, F1 `0.996914` | `artifacts/reports/baseline_comparison.json` |
| Robustness multi-seed | HistGradientBoosting mean AUC `0.999928 ± 0.000031`; XGBoost AUC CI `0.995236` đến `1.000000` | `artifacts/reports/robustness_validation.json` |
| External validation | Frozen PaySim AUC `0.628517`; IEEE-native retrained AUC `0.841506` | `artifacts/reports/external_validation.json` |
| Transfer learning IEEE-CIS | Adapt 10% IEEE-CIS, test 90% còn lại; AUC `0.677369`, PR-AUC `0.082577`, F1 `0.189437` | `artifacts/reports/transfer_learning_report.json` |
| Anomaly sidecar | Ngưỡng adaptive P95 validation `0.418285`; test flag `344/650` fraud và `4,522/68,410` legitimate | `artifacts/reports/evaluation_report.json` |
| Simulation hiện tại | 5,000 giao dịch; approve `91.58%`, review `7.88%`, step-up `0.50%`, block `0.04%` | `artifacts/reports/simulation_report.json` |
| Deployment | active `v20260420T053341630222Z`, rollback `v20260417T101732307255Z` | `artifacts/deployment/deployment_state.json` |

Tóm tắt để đưa vào báo cáo: mô hình đạt hiệu năng rất cao trong miền PaySim, trong khi IEEE-CIS cho thấy
giới hạn chuyển miền rõ rệt. Vì vậy đóng góp chính nên được trình bày là kiến trúc phát hiện gian lận
có train/evaluation, routing, agent, explainability, monitoring và external validation; không nên kết luận
rằng frozen PaySim model đã tổng quát hóa tốt sang IEEE-CIS.

---

## 2. Khoảng trống Nghiên cứu

Mặc dù model PaySim đạt AUC = 0.998383 và F1 = 0.993103 — mức hiệu năng rất cao — hệ thống vẫn tồn tại
ba khoảng trống nghiệp vụ quan trọng:

### Khoảng trống 1: Blind spot với fraud pattern mới

XGBoost là mô hình học có giám sát (supervised): chỉ nhận biết được các mẫu fraud đã xuất hiện
trong tập huấn luyện. Với **zero-day fraud** (pattern chưa từng thấy), model không có cơ chế phát hiện.
2 case FN trong test set cho thấy vẫn còn giao dịch fraud có pattern hiếm hoặc lệch phân bố mà model
có giám sát chưa bắt được hoàn toàn.

### Khoảng trống 2: Quyết định thiếu giải thích cấu trúc

Hệ thống cũ không có reason codes chuẩn hóa theo ngôn ngữ nghiệp vụ. Analyst và compliance
khó audit quyết định chặn/thông qua mà không có giải thích rõ ràng.

### Khoảng trống 3: Không có action trung gian

Pipeline chỉ có 3 action: `approve`, `review`, `block`. Không có cơ chế yêu cầu xác minh tăng cường
(step-up authentication) — phù hợp hơn cho các ca nghi ngờ nhẹ thay vì chặn cứng.

---

## 3. Giả thuyết Nghiên cứu

> **H1:** Bổ sung một anomaly sidecar (IsolationForest, huấn luyện trên giao dịch hợp lệ)
> vào pipeline sẽ giúp phát hiện thêm fraud bất thường mà backbone XGBoost bỏ sót,
> mà không làm giảm đáng kể hiệu năng tổng thể (AUC, F1, Recall).

> **H2:** Chuẩn hóa reason codes và thêm narrative 3 cấp sẽ tăng tính giải thích
> (explainability) của hệ thống mà không ảnh hưởng đến metric phân loại.

> **H3:** Thêm action `step_up` sẽ giúp tách rõ ca cần xác minh tăng cường
> khỏi block cứng, giảm false positive block trong thực tế vận hành.

---

## 4. Thiết kế Cải tiến

### 4.1 Anomaly Sidecar (IsolationForest)

**Lý do chọn IsolationForest:**
- Không giám sát (unsupervised) — học phân bố bình thường mà không cần nhãn fraud.
- Hiệu quả với dữ liệu chiều cao, phân bố lệch.
- Dễ tích hợp như side signal độc lập với backbone.

**Feature set của sidecar (17 features — loại bỏ LLM features):**

```
amount_log1p, oldbalanceOrg, newbalanceOrig, oldbalanceDest, newbalanceDest,
type_encoded, balance_diff, amount_ratio, org_balance_delta_ratio,
hour_of_day, is_night_tx, recipient_new_flag,
tx_count_24h, avg_amount_7d,
device_tx_count_24h, location_tx_count_24h, merchant_tx_count_24h
```

LLM features bị loại vì ngữ nghĩa khác biệt — không phản ánh phân bố giao dịch thực.

**Cấu hình:**

| Tham số | Giá trị |
|---|---|
| Mô hình | IsolationForest |
| contamination | 0.01 |
| n_estimators | 100 |
| Dữ liệu train | Chỉ giao dịch hợp lệ (321,846 dòng) |
| Ngưỡng flag | adaptive P95 validation = 0.418285; fallback config = 0.70 |

**Cách chuẩn hóa score:**

IsolationForest trả về `score_samples()` trong khoảng âm (thấp hơn = bất thường hơn).
Chuẩn hóa về `[0, 1]` bằng:

```
anomaly_score = 1 - clip((raw - score_min) / (score_max - score_min), 0, 1)
```

Giá trị 1.0 = bất thường nhất, 0.0 = hoàn toàn bình thường.

### 4.2 Explanation và Reason Codes

Reason codes được chuẩn hóa thành **19 mã**, phân nhóm theo 5 nhóm nghiệp vụ:

| Nhóm | Reason codes |
|---|---|
| `transaction_risk` | velocity_spike, amount_anomaly, balance_drain, night_transaction, new_recipient, medium_branch_review |
| `device_risk` | new_device, device_step_up, device_reuse |
| `ip_risk` | ip_risk, ip_blacklisted, ip_high_fraud_rate |
| `merchant_risk` | merchant_risk, merchant_high_risk, card_history_risk, risky_location |
| `anomaly_risk` | anomaly_detected, anomaly_high_score |

Narrative được xuất 3 cấp:
- **human_readable_explanation**: ngôn ngữ tự nhiên cho người dùng cuối.
- **analyst_report**: thông tin kỹ thuật đầy đủ cho analyst/audit.
- **dashboard_summary**: dòng tóm tắt ngắn cho dashboard giám sát.

### 4.3 Step-up Action

Điều kiện kích hoạt `step_up` (thay vì `approve` ở nhánh medium):

1. `anomaly_flag = True` (anomaly_score ≥ ngưỡng adaptive P95 validation, hiện là 0.418285) → ưu tiên cao nhất.
2. `new_device = True` **và** `ip_fraud_rate ≥ 0.03` → kết hợp thiết bị mới + IP rủi ro.

`step_up` **không phải** xác nhận gian lận — chỉ yêu cầu xác minh tăng cường
(OTP, xác nhận thiết bị, MFA) trước khi thông qua.

---

## 5. Tích hợp vào Pipeline

### 5.1 Luồng dữ liệu sau cải tiến

```
Sự kiện giao dịch
       │
       ▼
Feature Store (Redis) ──────────────────┐
       │                                │
       ▼                                │
XGBoost Backbone                        │
  → score, route, SHAP explanation      │
       │                                │
       ▼                                │
Anomaly Sidecar (IsolationForest) ◄─────┘
  → anomaly_score ∈ [0, 1]
  → anomaly_flag = (score ≥ adaptive threshold từ validation)
       │
       ▼
Router (4 nhánh)
  ┌──────────────────────────────────────────┐
  │ Low  → Approve                           │
  │ High → Block (hoặc Review nếu raw < 0.05)│
  │ Medium → ReAct Agent điều tra            │
  │   → Nếu agent approve + step_up trigger  │
  │     → Override thành step_up             │
  └──────────────────────────────────────────┘
       │
       ▼
Narrative (human / analyst / dashboard)
+ reason_codes (5 nhóm nghiệp vụ)
+ anomaly_score, anomaly_flag
```

### 5.2 Điểm tích hợp không xâm lấn

Anomaly sidecar được tích hợp theo **Cách 2 (side signal)**:
- **Không** retrain XGBoost — backbone giữ nguyên.
- Sidecar chạy song song với predict(), sau khi có `feature_row`.
- Chỉ ảnh hưởng đến routing ở nhánh medium (qua `_step_up_reason()`).
- Latency tăng thêm ≈ 1–2 ms mỗi giao dịch (IsolationForest predict đơn lẻ).

### 5.3 Ghi chú về đồng bộ/bất đồng bộ của Agent

Trong prototype hiện tại, nhánh `medium` gọi ReAct Agent theo kiểu **đồng bộ**: pipeline đợi agent
hoàn tất tool calling và JSON validation rồi mới trả `final_action`. Chỉ phần high-risk explanation log
được ghi bất đồng bộ bằng background thread. Cách này phù hợp để chứng minh logic điều tra và audit trail,
nhưng khi scale TPS lớn, LLM/API hoặc local LLM có thể trở thành bottleneck. Hướng phát triển là đưa
medium cases vào async queue, cấu hình timeout/retry budget, cache kết quả tool lookup và fallback sang
rule-based review khi LLM quá tải.

---

## 6. Phương pháp Đánh giá

### 6.1 Thiết kế thực nghiệm (Ablation Study)

5 lượt thực nghiệm tích lũy, mỗi lượt bổ sung một cải tiến:

| Lượt | Cấu hình | Mục tiêu |
|---|---|---|
| A | Baseline XGBoost | Mốc so sánh |
| B | + Anomaly Sidecar (Cách 2 — side signal) | Kiểm tra tác động độc lập của sidecar |
| C | + Anomaly Sidecar (Cách 1 — feature mới, retrain) | So sánh với Cách 2 |
| D | Lượt tốt nhất + Explanation chuẩn hóa | Kiểm tra explainability |
| E | Lượt D + Step-up Action | Kiểm tra tác động operational |

### 6.2 Bộ metric

- **AUC, F1, Precision, Recall** trên holdout test (69,060 giao dịch).
- **Confusion matrix** (TN, FP, FN, TP).
- **FN bắt thêm**: số FN của XGBoost mà anomaly sidecar phát hiện được.
- **Phân bố anomaly score**: fraud mean vs legit mean.
- **Route và action distribution** trong simulation.
- **Latency** (avg và p95).

---

## 7. Kết quả Định lượng

### 7.1 Baseline comparison — Metric chính

Kết quả từ `artifacts/reports/baseline_comparison.json`:

| Model | Test AUC | Test PR AUC | Test F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| HistGradientBoosting | **0.999932** | **0.997849** | **0.996914** | **1.000000** | 0.993846 |
| RandomForest | 0.999843 | 0.997502 | 0.995378 | 0.996914 | 0.993846 |
| XGBoost deploy | 0.998383 | 0.997002 | 0.993103 | 0.989313 | **0.996923** |
| Logistic Regression | 0.996364 | 0.884412 | 0.485748 | 0.325521 | 0.956923 |
| Dummy prior | 0.500000 | 0.009412 | 0.000000 | 0.000000 | 0.000000 |

HistGradientBoosting là baseline mạnh nhất về metric offline, nhưng XGBoost vẫn được chọn làm backbone
triển khai chính vì phù hợp với kiến trúc giải thích SHAP và pipeline hiện tại.

### 7.2 Confusion Matrix của XGBoost deploy

| | Dự đoán: Hợp lệ | Dự đoán: Gian lận |
|---|---:|---:|
| Thực tế: Hợp lệ | 68,403 (TN) | 7 (FP) |
| Thực tế: Gian lận | 2 (FN) | 648 (TP) |

### 7.3 Feature ablation

| Cấu hình | Số feature | Test AUC | Test PR AUC | Test F1 | Delta F1 |
|---|---:|---:|---:|---:|---:|
| Full feature set | 25 | 0.998383 | 0.997002 | 0.993103 | 0.000000 |
| No online behavior | 17 | 0.998409 | 0.996741 | 0.989992 | -0.003111 |
| No LLM-style analysis | 20 | 0.998647 | 0.995205 | 0.970432 | -0.022671 |
| No contextual aggregates | 19 | 0.996902 | 0.920048 | 0.853081 | -0.140023 |
| Transaction core only | 6 | 0.997233 | 0.929678 | 0.811798 | -0.181306 |

Kết quả cho thấy các nhóm feature ngữ cảnh, aggregate và LLM-style không chỉ là phần trang trí:
khi loại bỏ, F1 giảm rõ rệt, đặc biệt với nhóm contextual aggregates và transaction core only.

### 7.4 Anomaly Sidecar — Phân bố score

Trên tập test (69,060 giao dịch, trong đó 650 fraud):

| Nhóm | Anomaly score mean | Anomaly score P50 | Anomaly score P90 |
|------|-------------------:|------------------:|------------------:|
| Fraud (650 ca) | **0.4135** | 0.4282 | 0.6254 |
| Legitimate (68,410 ca) | **0.1798** | — | 0.3649 |

Tại ngưỡng adaptive P95 validation = 0.418285:
- Số fraud bị flagged: 344 / 650 (52.92%).
- Số legitimate bị flagged: 4,522 / 68,410 (6.61%).
- Tổng số giao dịch bị flagged: 4,866 / 69,060 (7.05%).

Diễn giải đúng: anomaly sidecar có tách biệt trung bình giữa fraud và legitimate, nhưng vẫn có overlap.
Ngưỡng adaptive bắt được nhiều fraud hơn ngưỡng cứng cũ `0.70`, nhưng đổi lại làm tăng false flag.
Vì vậy sidecar không thay thế XGBoost và không nên dùng để block cứng; nó phù hợp hơn như side signal
cho `review`/`step_up`.

### 7.5 Medium branch ablation

| Policy | Review rate | Block precision | Block recall | Block F1 | Ghi chú |
|---|---:|---:|---:|---:|---|
| score_threshold_block | 0.0000 | 0.9893 | 0.9969 | 0.9931 | Baseline nhị phân theo threshold |
| route_without_agent | 0.2053 | 0.9893 | 0.9969 | 0.9931 | Toàn bộ medium đưa vào review |
| route_with_medium_agent | 0.0926 | 0.9515 | 0.9969 | 0.9737 | Agent giảm review nhưng giảm precision |

Kết luận trung thực: Agent có giá trị vận hành vì giảm số ca review thủ công, nhưng không nên trình bày
như bằng chứng tăng accuracy so với XGBoost.

### 7.6 Step-up Action — Phân bổ quyết định trong simulation hiện tại

Mô phỏng 5,000 giao dịch gần nhất:

| Action | Số lượng | Tỷ lệ | Ý nghĩa |
|--------|----------:|------:|---------|
| approve | 4,579 | 91.58% | Thông qua tự động |
| review | 394 | 7.88% | Chuyển analyst xem xét |
| block | 2 | 0.04% | Chặn ngay |
| step_up | 25 | 0.50% | Yêu cầu xác minh tăng cường |

Latency end-to-end trung bình khoảng `65.47 ms`, p95 khoảng `76.03 ms` trong simulation hiện tại.

---

## 8. Case Study Định tính

### Case 1 — FN của XGBoost được Anomaly Sidecar bắt được (Lượt B thành công)

**Bối cảnh:** Giao dịch TRANSFER 10,000,000 đơn vị. XGBoost cho score thấp (không vào nhánh high),
nên tự động approve. Đây là giao dịch fraud thực sự.

**Tại sao XGBoost bỏ sót:** Pattern giao dịch số tiền cực lớn không xuất hiện đủ trong train set
để model học được biên quyết định chắc chắn.

**Tại sao Sidecar bắt được:** IsolationForest phát hiện giao dịch này lệch rất xa phân bố
của 321,846 giao dịch hợp lệ → `anomaly_score` cao → kích hoạt `step_up` thay vì approve.

**Kết quả:** Giao dịch được giữ lại để xác minh tăng cường thay vì tự động thông qua.

---

### Case 2 — Medium branch với step_up (Giai đoạn 4)

**Bối cảnh:** Giao dịch tx_0393104 (TRANSFER, 3,000,000 đơn vị), score XGBoost = 0.55 (nhánh medium).
ReAct Agent điều tra và đề xuất `approve`. Tuy nhiên, `anomaly_score = 0.813`.

**Luồng xử lý:**
1. Agent đề xuất `approve` (score trung bình, không thấy dấu hiệu fraud rõ ràng).
2. `_step_up_reason()` kiểm tra: `anomaly_flag = True` → override thành `step_up`.
3. Narrative xuất: `"MEDIUM -> STEP_UP🔐 | TRANSFER 3,000,000.00 | score 0.550 | anomaly 0.813⚠"`.

**Giá trị:** Ngăn approve tự động một giao dịch bất thường mà agent chưa đủ dữ liệu để quyết định đúng.

---

### Case 3 — Low branch với anomaly_score trung bình (hệ thống hoạt động đúng)

**Bối cảnh:** Giao dịch CASH_OUT 70,745 đơn vị. Score XGBoost = 0.259 (nhánh low), `anomaly_score = 0.329`.

**Luồng xử lý:**
1. Route → low → approve ngay, không qua agent.
2. `anomaly_score = 0.329` < ngưỡng adaptive 0.418285 → không flag.
3. Dashboard: `"LOW -> APPROVE | CASH_OUT 70,745.57 | score 0.259 | anomaly 0.329"`.

**Giá trị:** Sidecar không làm chậm nhánh low-risk — giao dịch bình thường vẫn được thông qua nhanh.

---

### Case 4 — Medium branch với reason codes chuẩn hóa (Giai đoạn 3)

**Bối cảnh:** Giao dịch TRANSFER 169,285 đơn vị, score = 0.700 (nhánh medium). Agent điều tra và
đưa ra reason codes: `['device_step_up', 'new_device']`.

**Narrative analyst:**
> "Thiết bị mới chưa có lịch sử giao dịch. Cần xác minh tăng cường thiết bị trước khi thông qua."

**Giá trị:** Analyst đọc được ngay lý do cụ thể thay vì chỉ thấy score số. Phục vụ audit trail và compliance.

---

## 9. Kết luận — Lợi ích và Hạn chế

### 9.1 Lợi ích đã chứng minh

| Cải tiến | Lợi ích định lượng | Lợi ích định tính |
|---|---|---|
| Anomaly Sidecar Cách 2 | Với ngưỡng adaptive P95, flag `4,866` giao dịch test, trong đó có `344/650` fraud (`52.92%`) và `4,522` legitimate (`6.61%` legit) | Không cần retrain, dùng như tín hiệu phụ để ưu tiên kiểm tra |
| Anomaly Sidecar Cách 1 | Feature ablation cho thấy các nhóm feature phụ trợ làm tăng F1, đặc biệt contextual aggregates và LLM-style analysis | Backbone học thêm tín hiệu ngữ cảnh thay vì chỉ dựa vào transaction core |
| Explanation & Reason codes | — (không đổi AUC/F1) | Audit trail rõ ràng, 5 nhóm nghiệp vụ |
| Step-up Action | Simulation hiện tại tạo `25/5,000` step-up (`0.50%`) và `394/5,000` review | Giảm quyết định cứng với các ca cần xác minh thêm |

### 9.2 Hạn chế và điểm cần lưu ý

1. **Anomaly score fraud mean (`0.4135`) chưa tách biệt tuyệt đối với legit (`0.1798`):**
   Fraud có score cao hơn legit trên trung bình, nhưng vùng overlap vẫn lớn. Sidecar không thể thay thế
   backbone, chỉ nên dùng như tín hiệu phụ hoặc tín hiệu ưu tiên review.

2. **Ngưỡng anomaly_flag đã adaptive nhưng còn dùng một percentile chung:**
   Ngưỡng hiện tại là P95 validation (`0.418285`), giúp bắt `344/650` fraud trên test nhưng đồng thời flag
   `4,522` legitimate. Hướng tiếp theo là adaptive threshold theo phân khúc giao dịch để cân bằng fraud catch
   và false flag tốt hơn.

3. **Medium ReAct Agent đang chạy đồng bộ:**
   Pipeline hiện gọi `agent.investigate()` trực tiếp trong nhánh medium. Khi TPS lớn hoặc thay bằng LLM local/API
   chậm hơn, agent có thể thành bottleneck. Cần async queue, timeout/retry budget, cache tool lookup và fallback
   deterministic.

4. **Step-up tăng sau adaptive threshold nhưng vẫn cần theo dõi tải vận hành (`25/5,000` ca):**
   Tần suất step-up tăng từ 0.16% lên 0.50%. Đây là hướng tốt để giảm approve tự động với giao dịch bất thường,
   nhưng cần theo dõi trải nghiệm người dùng và chi phí xác minh bổ sung.

5. **PaySim là dữ liệu tổng hợp, IEEE-CIS là kiểm tra ngoài phân bố:**
   Kết quả rất cao trên PaySim (AUC = `0.998383`) phần nào do dữ liệu tổng hợp dễ phân tách hơn thực tế.
   Frozen-model external validation trên IEEE-CIS hiện đạt AUC `0.6285`, PR-AUC `0.0532` và F1 `0.0201`.
   Mức này tốt hơn đoán mò về ranking nhưng thấp hơn rất xa PaySim, cho thấy domain shift/schema shift rất mạnh.
   Vì vậy phần IEEE-CIS phải được diễn giải trung thực là kiểm tra ngoài phân bố và giới hạn mô hình PaySim,
   không phải bằng chứng rằng cùng một frozen model đã tổng quát hóa trực tiếp.

6. **Transfer learning chỉ giảm domain shift một phần:**
   Adapt 10% IEEE-CIS giúp AUC tăng từ frozen `0.6285` lên `0.6774` trên phần IEEE-CIS còn lại, nhưng vẫn thấp
   hơn IEEE-native retrained AUC `0.8415`. Đây là cải thiện có ý nghĩa thực nghiệm, nhưng chưa đủ để xem là
   giải pháp thay thế cho huấn luyện trong miền dữ liệu thực tế.

---

## 10. Hướng Phát triển Tiếp theo

### 10.1 Trung hạn (6–12 tháng)

- **Adaptive threshold:** Ngưỡng anomaly_flag tự động điều chỉnh theo phân khúc giao dịch
  (amount band, transaction type, merchant category).
- **Async medium agent:** Đưa medium cases vào hàng đợi bất đồng bộ, có timeout, retry budget và fallback
  deterministic để tránh nghẽn pipeline khi TPS tăng.
- **Segment-based routing:** Ngưỡng XGBoost khác nhau cho từng loại merchant hoặc kênh thanh toán.
- **Soft rules kết hợp với model:** Tăng tính kiểm soát nghiệp vụ mà không hy sinh AUC.
- **Graph-based fraud detection:** Phát hiện fraud ring qua quan hệ account → merchant → device.
- **Cải tiến monitoring:** Drift detection tự động theo feature importance, alert threshold động.

### 10.2 Dài hạn (> 12 tháng)

| Hướng | Mô tả | Giá trị kỳ vọng |
|---|---|---|
| **Graph Neural Network** | Phát hiện fraud ring qua mạng quan hệ | Bắt được organized fraud |
| **Behavioral Biometrics** | Login pattern, device trust score, session anomaly | Account takeover detection |
| **NLP pipeline** | Phân tích complaint text, scam message | Phát hiện social engineering |
| **Federated Learning** | Chia sẻ tri thức fraud giữa tổ chức không chia sẻ dữ liệu thô | Privacy-preserving collaboration |
| **Adversarial Robustness** | Chống fraud actor chủ động điều chỉnh hành vi để né model | Robustness against evasion |
| **Conversational Agent** | Thu thập intelligence từ người dùng khi phát hiện scam | Phát hiện fraud ngoài giao dịch |

---

## Phụ lục — File dữ liệu tham chiếu

| File | Nội dung |
|---|---|
| `docs/REPORT_MO_HINH_PAYSIM.md` | Báo cáo mô hình PaySim + IEEE-CIS đã gom số liệu hiện tại |
| `docs/BANG_KET_QUA_BAO_CAO.md` | Bảng kết quả ngắn để chèn vào báo cáo hoặc slide |
| `artifacts/reports/evaluation_report.json` | Metric XGBoost, confusion matrix và anomaly sidecar |
| `artifacts/reports/research_suite.json` | Tổng hợp baseline, ablation, robustness và external validation |
| `artifacts/reports/baseline_comparison.json` | So sánh XGBoost với các baseline offline |
| `artifacts/reports/feature_ablation.json` | Đóng góp của từng nhóm feature |
| `artifacts/reports/medium_branch_ablation.json` | So sánh chính sách xử lý vùng medium |
| `artifacts/reports/robustness_validation.json` | Multi-seed, bootstrap confidence interval và McNemar test |
| `artifacts/reports/external_validation.json` | IEEE-CIS frozen-vs-native benchmark |
| `artifacts/reports/transfer_learning_report.json` | Transfer learning PaySim → IEEE-CIS với 25 PaySim-aligned features |
| `artifacts/reports/simulation_report.json` | Phân bổ route/action và latency trên 5,000 giao dịch mô phỏng |
| `artifacts/deployment/deployment_state.json` | Active, candidate và rollback version hiện tại |
| `artifacts/monitoring/dashboard_snapshot.json` | Snapshot dashboard sau simulation |
| `fraud_flow/anomaly.py` | Mã nguồn AnomalySidecar |
| `fraud_flow/pipeline.py` | Mã nguồn pipeline tích hợp (routing + step_up) |
| `fraud_flow/narratives.py` | Mã nguồn reason codes và narrative generation |
