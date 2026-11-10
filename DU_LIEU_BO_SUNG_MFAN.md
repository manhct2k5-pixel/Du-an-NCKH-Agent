# DỮ LIỆU BỔ SUNG MFAN

Ngày tổng hợp: 2026-11-07. Nguồn: các file hiện có trong repository tại thời điểm tổng hợp.

> Cập nhật vị trí file ngày 2026-11-09: hồ sơ review đã chuyển vào `docs/reviews/`; tài liệu bàn giao và bản thảo cũ nằm trong `docs/archive/`. Tra [mục lục review](docs/reviews/README.md) và [bảng đường dẫn cũ → mới](docs/cleanup_manifest.csv). Các khối nguyên văn, SHA-256 và số dòng bên dưới thuộc bản chụp ngày tổng hợp, được giữ nguyên để đối chiếu. Ví dụ: `B13_IMPLEMENTATION_REVIEW/b13_environment.json` hiện ở `docs/reviews/B13_IMPLEMENTATION_REVIEW/b13_environment.json`; tương tự với B14 và B15.

> Đợt cất thêm cùng ngày: các báo cáo theo giai đoạn nằm trong `docs/archive/stages/`; kết quả research/baseline cũ, biểu đồ, notebook và dữ liệu IEEE-CIS nằm trong `archive/`. Tra [manifest lưu trữ](archive/manifest.csv) cho các đường dẫn nguồn bên dưới. Các khối trích dẫn vẫn giữ nguyên byte; kết quả final B8–B12 và model PaySim đang dùng giữ ở vị trí chính.

Tài liệu gom đủ bốn nhóm yêu cầu. Các khối nguyên văn giữ nguyên nội dung file, chữ số, ký hiệu, đường dẫn và cách viết số; không định dạng lại JSON. Bảng tra cứu phía trước chỉ bổ sung cách đọc và chuyển tỷ lệ sang %. Mọi phép tính bổ sung đều được ghi rõ. Không chạy lại mô phỏng hoặc huấn luyện để thay thế số liệu gốc.

Các bộ số liệu thuộc nhiều đợt chạy. Đặc biệt, số liệu Markdown, JSON mô phỏng, ablation gốc và B8/B11 final không được ghép thành một đợt thực nghiệm duy nhất. Các khối nguồn đầy đủ dưới đây là căn cứ đối chiếu.

## 1. Mục 2.4.6 và 3.3.1–3.3.3 — Thống kê mô phỏng và phân luồng

### 1.1. Mô phỏng 5.000 giao dịch

Nguồn: `artifacts/reports/simulation_report.json`. Mẫu số: `processed_transactions = 5000`. Phần trăm trong bảng được tính chính xác bằng `count / 5000 × 100`.

| Nhóm | Nhánh / hành động | Số lượng gốc | Tỷ lệ trên 5000 |
|---|---|---:|---:|
| routes | `low` | 3950 | 79.00% |
| routes | `medium` | 1048 | 20.96% |
| routes | `high` | 2 | 0.04% |
| actions | `approve` | 4579 | 91.58% |
| actions | `review` | 394 | 7.88% |
| actions | `step_up` | 25 | 0.50% |
| actions | `block` | 2 | 0.04% |

Route là nhánh đầu vào; action là quyết định cuối. Hai nhóm cùng có mẫu số 5000 nhưng không cộng lẫn. Có `25` action `step_up` (0.50% toàn bộ mô phỏng).

| Chỉ số vận hành | Giá trị gốc |
|---|---:|
| `metrics.evaluation_ready` | `true` |
| `metrics.auc_ready` | `true` |
| `metrics.positive_count` | `2` |
| `metrics.negative_count` | `4998` |
| `metrics.auc` | `0.9999999999999999` |
| `metrics.f1_block` | `1.0` |
| `metrics.precision_block` | `1.0` |
| `metrics.recall_block` | `1.0` |
| `latency.avg_ms` | `59.95092252819595` |
| `latency.p95_ms` | `78.19841785003518` |
| `latency.model_avg_ms` | `55.81866408719688` |
| `latency.model_p95_ms` | `69.39765844981594` |
| `drift_flags.amount_shift` | `2778` |
| `drift_flags.device_shift` | `4951` |

Đơn vị của bốn trường latency là ms. `amount_shift` và `device_shift` là số cờ cảnh báo; một giao dịch có thể mang nhiều cờ. Phân bố raw probability/operational score, deployment version và các đường dẫn log được giữ đầy đủ trong JSON nguyên văn tại mục 1.6.

Báo cáo không ghi tổng thời gian wall-clock của toàn bộ đợt 5000 giao dịch hoặc throughput của đợt đó; không coi `avg_ms × 5000` là thời gian wall-clock đã đo.

### 1.2. Phân luồng trên tập test 69060 giao dịch

Nguồn: `research_suite.json → split.test_rows` và `medium_branch_ablation.json → policies[policy_name=route_without_agent]`. Theo định nghĩa policy trong nguồn và `fraud_flow/research.py:run_medium_branch_ablation`, low → approve, medium → review, high → block. Vì vậy số lượng của policy này cho biết số giao dịch đầu vào từng nhánh. Không dùng action sau agent để thay thế số nhánh.

| Nhánh | Số lượng gốc | Trường rate gốc | % chuyển từ rate gốc | Công thức % chính xác từ số lượng |
|---|---:|---:|---:|---|
| low | 54224 | 0.785172 | 78.517200% | `100 × 54224 / 69060 %` |
| medium | 14181 | 0.205343 | 20.534300% | `100 × 14181 / 69060 %` |
| high | 655 | 0.009485 | 0.948500% | `100 × 655 / 69060 %` |

Các rate trong JSON đã được làm tròn ở nguồn; cột % chuyển đổi giữ đúng giá trị ấy, không tự thay bằng tỷ lệ được tính lại. Tổng số nhánh: `54224 + 14181 + 655 = 69060`.

### 1.3. Toàn bộ chính sách và chỉ số vận hành test trong ablation gốc

Nguồn: `artifacts/reports/medium_branch_ablation.json`. Mọi rate dưới đây dùng đúng giá trị gốc; % là rate × 100. Các chỉ số precision, recall, F1 và chỉ số vận hành còn lại được giữ đủ trong bảng dọc và JSON nguyên văn.

| Policy | Approve count | Approve rate / % | Review count | Review rate / % | Block count | Block rate / % |
|---|---:|---|---:|---|---:|---|
| `score_threshold_block` | 68405 | 0.990515 / 99.051500% | 0 | 0.0 / 0.0% | 655 | 0.009485 / 0.948500% |
| `route_without_agent` | 54224 | 0.785172 / 78.517200% | 14181 | 0.205343 / 20.534300% | 655 | 0.009485 / 0.948500% |
| `route_medium_auto_approve` | 68405 | 0.990515 / 99.051500% | 0 | 0.0 / 0.0% | 655 | 0.009485 / 0.948500% |
| `route_with_medium_agent` | 61984 | 0.897538 / 89.753800% | 6395 | 0.092601 / 9.260100% | 681 | 0.009861 / 0.986100% |

| Policy | Chỉ số | Giá trị gốc |
|---|---|---:|
| `score_threshold_block` | `block_precision` | `0.9893129770992366` |
| `score_threshold_block` | `block_recall` | `0.9969230769230769` |
| `score_threshold_block` | `block_f1` | `0.993103448275862` |
| `score_threshold_block` | `fraud_review_rate` | `0.0` |
| `score_threshold_block` | `review_fraud_share` | `0.0` |
| `score_threshold_block` | `false_positive_block_rate` | `0.000102` |
| `score_threshold_block` | `medium_case_count` | `14181` |
| `score_threshold_block` | `medium_case_share` | `0.205343` |
| `route_without_agent` | `block_precision` | `0.9893129770992366` |
| `route_without_agent` | `block_recall` | `0.9969230769230769` |
| `route_without_agent` | `block_f1` | `0.993103448275862` |
| `route_without_agent` | `fraud_review_rate` | `0.001538` |
| `route_without_agent` | `review_fraud_share` | `0.000071` |
| `route_without_agent` | `false_positive_block_rate` | `0.000102` |
| `route_without_agent` | `medium_case_count` | `14181` |
| `route_without_agent` | `medium_case_share` | `0.205343` |
| `route_medium_auto_approve` | `block_precision` | `0.9893129770992366` |
| `route_medium_auto_approve` | `block_recall` | `0.9969230769230769` |
| `route_medium_auto_approve` | `block_f1` | `0.993103448275862` |
| `route_medium_auto_approve` | `fraud_review_rate` | `0.0` |
| `route_medium_auto_approve` | `review_fraud_share` | `0.0` |
| `route_medium_auto_approve` | `false_positive_block_rate` | `0.000102` |
| `route_medium_auto_approve` | `medium_case_count` | `14181` |
| `route_medium_auto_approve` | `medium_case_share` | `0.205343` |
| `route_with_medium_agent` | `block_precision` | `0.9515418502202643` |
| `route_with_medium_agent` | `block_recall` | `0.9969230769230769` |
| `route_with_medium_agent` | `block_f1` | `0.9737039819684448` |
| `route_with_medium_agent` | `fraud_review_rate` | `0.001538` |
| `route_with_medium_agent` | `review_fraud_share` | `0.000156` |
| `route_with_medium_agent` | `false_positive_block_rate` | `0.000482` |
| `route_with_medium_agent` | `medium_case_count` | `14181` |
| `route_with_medium_agent` | `medium_case_share` | `0.205343` |

Hai file được yêu cầu có cùng nội dung đối tượng `medium_branch`. Bản gốc ghi `route_with_medium_agent`: approve `61984`, review `6395`, block `681`. So với policy chuyển toàn bộ medium sang review, giảm `14181 − 6395 = 7786` ca review (phép tính bổ sung); đây là deterministic offline investigation replay, không phải phép đo full ReAct runtime.

**Step-up trên toàn bộ tập test:** các báo cáo ablation này không có trường `step_up_count` hoặc thống kê action `step_up` riêng. Không có đủ dữ liệu trong báo cáo để kết luận số step-up là 0; cũng không suy ra từ các dòng log được lấy mẫu.

**Latency trên toàn bộ tập test:** hai JSON yêu cầu không có tổng thời gian hoặc latency end-to-end cho cả 69060 giao dịch. `research_suite.json` có `train_seconds` và `inference_ms_per_1k_rows` cho từng baseline; đó là các chỉ số riêng, được giữ nguyên dưới đây. B11 đo trên một mẫu test riêng ở mục 1.8.

### 1.4. Phân luồng validation — không nhầm với test

Nguồn: `routing_calibration.validation_route_share`. Tập validation có `69059` dòng. JSON chỉ ghi tỷ lệ nhánh, không ghi số lượng nhánh; không làm tròn tỷ lệ ngược lại để coi là count gốc.

| Nhánh | Tỷ lệ gốc | % chuyển từ tỷ lệ gốc |
|---|---:|---:|
| low | 0.849998 | 84.999800% |
| medium | 0.149104 | 14.910400% |
| high | 0.000898 | 0.089800% |

### 1.5. Toàn văn hai báo cáo được yêu cầu

Nguồn: `artifacts/reports/research_suite.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "source": "paysim",
  "data_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
  "identity_data_path": null,
  "artifact_scope": "production",
  "random_state": 42,
  "split_strategy": "chronological_by_step_after_TRANSFER_CASH_OUT_filter",
  "split": {
    "total_rows": 460394,
    "train_rows": 322275,
    "validation_rows": 69059,
    "test_rows": 69060
  },
  "baseline": {
    "source": "paysim",
    "data_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "identity_data_path": null,
    "artifact_scope": "production",
    "random_state": 42,
    "split_strategy": "chronological_by_step_after_TRANSFER_CASH_OUT_filter",
    "split": {
      "total_rows": 460394,
      "train_rows": 322275,
      "validation_rows": 69059,
      "test_rows": 69060
    },
    "models": [
      {
        "model_name": "hist_gradient_boosting",
        "family": "HistGradientBoostingClassifier",
        "feature_count": 25,
        "selected_threshold": 0.5,
        "params": {
          "learning_rate": 0.08,
          "max_iter": 220,
          "max_depth": 6,
          "min_samples_leaf": 80
        },
        "train_seconds": 0.7903,
        "inference_ms_per_1k_rows": 0.422,
        "validation": {
          "metrics": {
            "auc": 0.9928392444190461,
            "f1": 0.975609756097561,
            "precision": 1.0,
            "recall": 0.9523809523809523
          },
          "pr_auc": 0.9693418576509796,
          "confusion_matrix": {
            "true_negative": 68996,
            "false_positive": 0,
            "false_negative": 3,
            "true_positive": 60
          }
        },
        "test": {
          "metrics": {
            "auc": 0.9999321511699818,
            "f1": 0.9969135802469136,
            "precision": 1.0,
            "recall": 0.9938461538461538
          },
          "pr_auc": 0.997849385204436,
          "confusion_matrix": {
            "true_negative": 68410,
            "false_positive": 0,
            "false_negative": 4,
            "true_positive": 646
          }
        }
      },
      {
        "model_name": "random_forest",
        "family": "RandomForestClassifier",
        "feature_count": 25,
        "selected_threshold": 0.5,
        "params": {
          "n_estimators": 120,
          "max_depth": 12,
          "min_samples_leaf": 40,
          "class_weight": "balanced_subsample",
          "imputer": "median"
        },
        "train_seconds": 15.7268,
        "inference_ms_per_1k_rows": 0.8725,
        "validation": {
          "metrics": {
            "auc": 0.9994876629609077,
            "f1": 0.975609756097561,
            "precision": 1.0,
            "recall": 0.9523809523809523
          },
          "pr_auc": 0.9685896724545978,
          "confusion_matrix": {
            "true_negative": 68996,
            "false_positive": 0,
            "false_negative": 3,
            "true_positive": 60
          }
        },
        "test": {
          "metrics": {
            "auc": 0.9998431740748653,
            "f1": 0.9953775038520801,
            "precision": 0.9969135802469136,
            "recall": 0.9938461538461538
          },
          "pr_auc": 0.9975016124891384,
          "confusion_matrix": {
            "true_negative": 68408,
            "false_positive": 2,
            "false_negative": 4,
            "true_positive": 646
          }
        }
      },
      {
        "model_name": "xgboost",
        "family": "XGBClassifier",
        "feature_count": 25,
        "selected_threshold": 0.5,
        "params": {
          "n_estimators": 260,
          "max_depth": 6,
          "learning_rate": 0.06,
          "subsample": 0.9,
          "colsample_bytree": 0.85
        },
        "train_seconds": 8.1904,
        "inference_ms_per_1k_rows": 0.922,
        "validation": {
          "metrics": {
            "auc": 0.9994133545353906,
            "f1": 0.96,
            "precision": 0.967741935483871,
            "recall": 0.9523809523809523
          },
          "pr_auc": 0.961260409954726,
          "confusion_matrix": {
            "true_negative": 68994,
            "false_positive": 2,
            "false_negative": 3,
            "true_positive": 60
          },
          "ranking_score": 1.9594133545353905
        },
        "test": {
          "metrics": {
            "auc": 0.9983827150776428,
            "f1": 0.993103448275862,
            "precision": 0.9893129770992366,
            "recall": 0.9969230769230769
          },
          "pr_auc": 0.9970017406400512,
          "confusion_matrix": {
            "true_negative": 68403,
            "false_positive": 7,
            "false_negative": 2,
            "true_positive": 648
          }
        },
        "search_mode": "candidate_grid"
      },
      {
        "model_name": "logistic_regression",
        "family": "LogisticRegression",
        "feature_count": 25,
        "selected_threshold": 0.7,
        "params": {
          "scaler": "StandardScaler",
          "solver": "lbfgs",
          "class_weight": "balanced",
          "max_iter": 500,
          "tol": 0.0001
        },
        "train_seconds": 3.0148,
        "inference_ms_per_1k_rows": 0.2334,
        "validation": {
          "metrics": {
            "auc": 0.9894848976752275,
            "f1": 0.08249027237354085,
            "precision": 0.04337152209492635,
            "recall": 0.8412698412698413
          },
          "pr_auc": 0.45954526140358637,
          "confusion_matrix": {
            "true_negative": 67827,
            "false_positive": 1169,
            "false_negative": 10,
            "true_positive": 53
          }
        },
        "test": {
          "metrics": {
            "auc": 0.9963643641842734,
            "f1": 0.4857477547832878,
            "precision": 0.32548403976975404,
            "recall": 0.9569230769230769
          },
          "pr_auc": 0.8844123778149597,
          "confusion_matrix": {
            "true_negative": 67121,
            "false_positive": 1289,
            "false_negative": 28,
            "true_positive": 622
          }
        }
      },
      {
        "model_name": "dummy_prior",
        "family": "DummyClassifier",
        "feature_count": 25,
        "selected_threshold": 0.5,
        "params": {
          "strategy": "prior"
        },
        "train_seconds": 0.0159,
        "inference_ms_per_1k_rows": 0.0266,
        "validation": {
          "metrics": {
            "auc": 0.5,
            "f1": 0.0,
            "precision": 0.0,
            "recall": 0.0
          },
          "pr_auc": 0.0009122634269248034,
          "confusion_matrix": {
            "true_negative": 68996,
            "false_positive": 0,
            "false_negative": 63,
            "true_positive": 0
          }
        },
        "test": {
          "metrics": {
            "auc": 0.5,
            "f1": 0.0,
            "precision": 0.0,
            "recall": 0.0
          },
          "pr_auc": 0.009412105415580654,
          "confusion_matrix": {
            "true_negative": 68410,
            "false_positive": 0,
            "false_negative": 650,
            "true_positive": 0
          }
        }
      }
    ]
  },
  "feature_ablation": {
    "source": "paysim",
    "data_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "identity_data_path": null,
    "artifact_scope": "production",
    "random_state": 42,
    "split_strategy": "chronological_by_step_after_TRANSFER_CASH_OUT_filter",
    "fixed_xgboost_params": {
      "n_estimators": 260,
      "max_depth": 6,
      "learning_rate": 0.06,
      "subsample": 0.9,
      "colsample_bytree": 0.85
    },
    "ablations": [
      {
        "name": "full_feature_set",
        "feature_count": 25,
        "feature_columns": [
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
          "llm_risk_score",
          "llm_reason_count",
          "llm_high_risk_flag",
          "llm_review_flag",
          "llm_category_hash"
        ],
        "note": "Full engineered feature set.",
        "selected_threshold": 0.5,
        "validation_metrics": {
          "auc": 0.9994133545353906,
          "f1": 0.96,
          "precision": 0.967741935483871,
          "recall": 0.9523809523809523
        },
        "validation_pr_auc": 0.961260409954726,
        "test_metrics": {
          "auc": 0.9983827150776428,
          "f1": 0.993103448275862,
          "precision": 0.9893129770992366,
          "recall": 0.9969230769230769
        },
        "test_pr_auc": 0.9970017406400512,
        "train_seconds": 2.2298,
        "delta_vs_full": {
          "auc": 0.0,
          "f1": 0.0,
          "pr_auc": 0.0
        }
      },
      {
        "name": "no_online_behavior",
        "feature_count": 17,
        "feature_columns": [
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
          "llm_risk_score",
          "llm_reason_count",
          "llm_high_risk_flag",
          "llm_review_flag",
          "llm_category_hash"
        ],
        "note": "Removes velocity and historical risk lookup features.",
        "selected_threshold": 0.65,
        "validation_metrics": {
          "auc": 0.9994730543385538,
          "f1": 0.9375,
          "precision": 0.9230769230769231,
          "recall": 0.9523809523809523
        },
        "validation_pr_auc": 0.9661858157666408,
        "test_metrics": {
          "auc": 0.9984086559544827,
          "f1": 0.9899923017705927,
          "precision": 0.9907550077041603,
          "recall": 0.9892307692307692
        },
        "test_pr_auc": 0.9967407558963038,
        "train_seconds": 1.8488,
        "delta_vs_full": {
          "auc": 2.6e-05,
          "f1": -0.003111,
          "pr_auc": -0.000261
        }
      },
      {
        "name": "no_llm_analysis",
        "feature_count": 20,
        "feature_columns": [
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
          "merchant_fraud_rate"
        ],
        "note": "Removes the LLM-style risk, review, and semantic category features.",
        "selected_threshold": 0.5,
        "validation_metrics": {
          "auc": 0.99726669224901,
          "f1": 0.8391608391608392,
          "precision": 0.75,
          "recall": 0.9523809523809523
        },
        "validation_pr_auc": 0.9206890889659554,
        "test_metrics": {
          "auc": 0.9986469589466227,
          "f1": 0.9704321455648218,
          "precision": 0.9566517189835575,
          "recall": 0.9846153846153847
        },
        "test_pr_auc": 0.9952047809970387,
        "train_seconds": 1.9949,
        "delta_vs_full": {
          "auc": 0.000264,
          "f1": -0.022671,
          "pr_auc": -0.001797
        }
      },
      {
        "name": "no_contextual_aggregates",
        "feature_count": 19,
        "feature_columns": [
          "amount_log1p",
          "oldbalanceOrg",
          "newbalanceOrig",
          "oldbalanceDest",
          "newbalanceDest",
          "type_encoded",
          "tx_count_24h",
          "avg_amount_7d",
          "device_tx_count_24h",
          "location_tx_count_24h",
          "merchant_tx_count_24h",
          "location_fraud_rate",
          "ip_fraud_rate",
          "merchant_fraud_rate",
          "llm_risk_score",
          "llm_reason_count",
          "llm_high_risk_flag",
          "llm_review_flag",
          "llm_category_hash"
        ],
        "note": "Removes aggregate context and entity-hash context features.",
        "selected_threshold": 0.7,
        "validation_metrics": {
          "auc": 0.9913201777512752,
          "f1": 0.4392523364485981,
          "precision": 0.31125827814569534,
          "recall": 0.746031746031746
        },
        "validation_pr_auc": 0.7400000093668835,
        "test_metrics": {
          "auc": 0.996902297234997,
          "f1": 0.8530805687203792,
          "precision": 0.8766233766233766,
          "recall": 0.8307692307692308
        },
        "test_pr_auc": 0.9200482675822834,
        "train_seconds": 1.954,
        "delta_vs_full": {
          "auc": -0.00148,
          "f1": -0.140023,
          "pr_auc": -0.076953
        }
      },
      {
        "name": "transaction_core_only",
        "feature_count": 6,
        "feature_columns": [
          "amount_log1p",
          "oldbalanceOrg",
          "newbalanceOrig",
          "oldbalanceDest",
          "newbalanceDest",
          "type_encoded"
        ],
        "note": "Keeps only direct transaction-side features.",
        "selected_threshold": 0.7,
        "validation_metrics": {
          "auc": 0.9968712241887498,
          "f1": 0.33540372670807456,
          "precision": 0.2084942084942085,
          "recall": 0.8571428571428571
        },
        "validation_pr_auc": 0.7433411657370148,
        "test_metrics": {
          "auc": 0.9972326920265819,
          "f1": 0.8117977528089888,
          "precision": 0.7467700258397932,
          "recall": 0.8892307692307693
        },
        "test_pr_auc": 0.9296777640918964,
        "train_seconds": 1.4211,
        "delta_vs_full": {
          "auc": -0.00115,
          "f1": -0.181306,
          "pr_auc": -0.067324
        }
      }
    ]
  },
  "medium_branch": {
    "source": "paysim",
    "data_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "identity_data_path": null,
    "artifact_scope": "production",
    "selected_threshold": 0.5,
    "routing_calibration": {
      "low_quantile": 0.85,
      "high_quantile": 0.98,
      "low_quantile_score": 8.068120223470032e-05,
      "high_quantile_score": 0.0003051041276194155,
      "raw_probability_summary": {
        "min": 6.935265446372796e-07,
        "max": 0.9999958276748657,
        "mean": 0.000979467062279582,
        "std": 0.029942866414785385,
        "p50": 2.1707206542487256e-05,
        "p90": 0.00011097176320618019,
        "p95": 0.00017510111501906067,
        "p99": 0.0004990110755898058
      },
      "operational_score_summary": {
        "min": 0.002579,
        "max": 0.999,
        "mean": 0.1429459853458637,
        "std": 0.15316397071122506,
        "p50": 0.080715,
        "p90": 0.353988,
        "p95": 0.46828949999999986,
        "p99": 0.70005842
      },
      "validation_route_share": {
        "low": 0.849998,
        "medium": 0.149104,
        "high": 0.000898
      }
    },
    "medium_case_count": 14181,
    "policies": [
      {
        "policy_name": "score_threshold_block",
        "note": "Binary threshold baseline with no routing and no manual review state.",
        "approve_count": 68405,
        "review_count": 0,
        "block_count": 655,
        "approve_rate": 0.990515,
        "review_rate": 0.0,
        "block_rate": 0.009485,
        "block_precision": 0.9893129770992366,
        "block_recall": 0.9969230769230769,
        "block_f1": 0.993103448275862,
        "fraud_review_rate": 0.0,
        "review_fraud_share": 0.0,
        "false_positive_block_rate": 0.000102,
        "medium_case_count": 14181,
        "medium_case_share": 0.205343
      },
      {
        "policy_name": "route_without_agent",
        "note": "Original routing but every medium case is held for human review.",
        "approve_count": 54224,
        "review_count": 14181,
        "block_count": 655,
        "approve_rate": 0.785172,
        "review_rate": 0.205343,
        "block_rate": 0.009485,
        "block_precision": 0.9893129770992366,
        "block_recall": 0.9969230769230769,
        "block_f1": 0.993103448275862,
        "fraud_review_rate": 0.001538,
        "review_fraud_share": 7.1e-05,
        "false_positive_block_rate": 0.000102,
        "medium_case_count": 14181,
        "medium_case_share": 0.205343
      },
      {
        "policy_name": "route_medium_auto_approve",
        "note": "Routing with the medium band auto-approved to show the risk of removing investigation.",
        "approve_count": 68405,
        "review_count": 0,
        "block_count": 655,
        "approve_rate": 0.990515,
        "review_rate": 0.0,
        "block_rate": 0.009485,
        "block_precision": 0.9893129770992366,
        "block_recall": 0.9969230769230769,
        "block_f1": 0.993103448275862,
        "fraud_review_rate": 0.0,
        "review_fraud_share": 0.0,
        "false_positive_block_rate": 0.000102,
        "medium_case_count": 14181,
        "medium_case_share": 0.205343
      },
      {
        "policy_name": "route_with_medium_agent",
        "note": "Routing with the offline replay of the current investigator logic on medium cases.",
        "approve_count": 61984,
        "review_count": 6395,
        "block_count": 681,
        "approve_rate": 0.897538,
        "review_rate": 0.092601,
        "block_rate": 0.009861,
        "block_precision": 0.9515418502202643,
        "block_recall": 0.9969230769230769,
        "block_f1": 0.9737039819684448,
        "fraud_review_rate": 0.001538,
        "review_fraud_share": 0.000156,
        "false_positive_block_rate": 0.000482,
        "medium_case_count": 14181,
        "medium_case_share": 0.205343
      }
    ]
  },
  "robustness": {
    "source": "paysim",
    "data_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "identity_data_path": null,
    "artifact_scope": "production",
    "seeds": [
      42,
      43,
      44
    ],
    "bootstrap_iterations": 300,
    "best_baseline": {
      "model_name": "hist_gradient_boosting",
      "family": "HistGradientBoostingClassifier"
    },
    "multi_seed_runs": [
      {
        "model_name": "xgboost",
        "family": "XGBClassifier",
        "random_state": 42,
        "selected_threshold": 0.5,
        "test_metrics": {
          "auc": 0.9983827150776428,
          "f1": 0.993103448275862,
          "precision": 0.9893129770992366,
          "recall": 0.9969230769230769,
          "pr_auc": 0.9970017406400512
        }
      },
      {
        "model_name": "hist_gradient_boosting",
        "family": "HistGradientBoostingClassifier",
        "random_state": 42,
        "selected_threshold": 0.5,
        "test_metrics": {
          "auc": 0.9999321511699818,
          "f1": 0.9969135802469136,
          "precision": 1.0,
          "recall": 0.9938461538461538,
          "pr_auc": 0.997849385204436
        }
      },
      {
        "model_name": "xgboost",
        "family": "XGBClassifier",
        "random_state": 43,
        "selected_threshold": 0.7,
        "test_metrics": {
          "auc": 0.9987623266953773,
          "f1": 0.99079754601227,
          "precision": 0.9877675840978594,
          "recall": 0.9938461538461538,
          "pr_auc": 0.9970987605238817
        }
      },
      {
        "model_name": "hist_gradient_boosting",
        "family": "HistGradientBoostingClassifier",
        "random_state": 43,
        "selected_threshold": 0.5,
        "test_metrics": {
          "auc": 0.9998875445560143,
          "f1": 0.9953632148377125,
          "precision": 1.0,
          "recall": 0.9907692307692307,
          "pr_auc": 0.9961997632554482
        }
      },
      {
        "model_name": "xgboost",
        "family": "XGBClassifier",
        "random_state": 44,
        "selected_threshold": 0.7,
        "test_metrics": {
          "auc": 0.9988008051004689,
          "f1": 0.9923312883435583,
          "precision": 0.9892966360856269,
          "recall": 0.9953846153846154,
          "pr_auc": 0.9975486999259158
        }
      },
      {
        "model_name": "hist_gradient_boosting",
        "family": "HistGradientBoostingClassifier",
        "random_state": 44,
        "selected_threshold": 0.5,
        "test_metrics": {
          "auc": 0.999963466879561,
          "f1": 0.9984591679506933,
          "precision": 1.0,
          "recall": 0.9969230769230769,
          "pr_auc": 0.9982831244538842
        }
      }
    ],
    "multi_seed_summary": [
      {
        "model_name": "hist_gradient_boosting",
        "family": "HistGradientBoostingClassifier",
        "seeds": [
          42,
          43,
          44
        ],
        "test_metrics": {
          "auc": {
            "mean": 0.999928,
            "std": 3.1e-05,
            "min": 0.999888,
            "max": 0.999963
          },
          "f1": {
            "mean": 0.996912,
            "std": 0.001264,
            "min": 0.995363,
            "max": 0.998459
          },
          "precision": {
            "mean": 1.0,
            "std": 0.0,
            "min": 1.0,
            "max": 1.0
          },
          "recall": {
            "mean": 0.993846,
            "std": 0.002512,
            "min": 0.990769,
            "max": 0.996923
          },
          "pr_auc": {
            "mean": 0.997444,
            "std": 0.000898,
            "min": 0.9962,
            "max": 0.998283
          }
        }
      },
      {
        "model_name": "xgboost",
        "family": "XGBClassifier",
        "seeds": [
          42,
          43,
          44
        ],
        "test_metrics": {
          "auc": {
            "mean": 0.998649,
            "std": 0.000189,
            "min": 0.998383,
            "max": 0.998801
          },
          "f1": {
            "mean": 0.992077,
            "std": 0.000958,
            "min": 0.990798,
            "max": 0.993103
          },
          "precision": {
            "mean": 0.988792,
            "std": 0.000725,
            "min": 0.987768,
            "max": 0.989313
          },
          "recall": {
            "mean": 0.995385,
            "std": 0.001256,
            "min": 0.993846,
            "max": 0.996923
          },
          "pr_auc": {
            "mean": 0.997216,
            "std": 0.000238,
            "min": 0.997002,
            "max": 0.997549
          }
        }
      }
    ],
    "confidence_intervals": {
      "xgboost": {
        "auc": {
          "mean": 0.998521,
          "std": 0.001411,
          "ci95_low": 0.995236,
          "ci95_high": 1.0
        },
        "pr_auc": {
          "mean": 0.997184,
          "std": 0.001865,
          "ci95_low": 0.993166,
          "ci95_high": 0.99995
        },
        "f1": {
          "mean": 0.993245,
          "std": 0.002095,
          "ci95_low": 0.98913,
          "ci95_high": 0.996811
        },
        "precision": {
          "mean": 0.989416,
          "std": 0.003791,
          "ci95_low": 0.982163,
          "ci95_high": 0.995663
        },
        "recall": {
          "mean": 0.997113,
          "std": 0.001971,
          "ci95_low": 0.99287,
          "ci95_high": 1.0
        }
      },
      "hist_gradient_boosting": {
        "auc": {
          "mean": 0.999933,
          "std": 4.5e-05,
          "ci95_low": 0.999827,
          "ci95_high": 1.0
        },
        "pr_auc": {
          "mean": 0.99787,
          "std": 0.001407,
          "ci95_low": 0.994689,
          "ci95_high": 1.0
        },
        "f1": {
          "mean": 0.996945,
          "std": 0.001627,
          "ci95_low": 0.993251,
          "ci95_high": 0.999257
        },
        "precision": {
          "mean": 1.0,
          "std": 0.0,
          "ci95_low": 1.0,
          "ci95_high": 1.0
        },
        "recall": {
          "mean": 0.993915,
          "std": 0.00323,
          "ci95_low": 0.986593,
          "ci95_high": 0.998514
        }
      }
    },
    "mcnemar_test": {
      "baseline_model": "hist_gradient_boosting",
      "better_for_xgboost": 2,
      "better_for_baseline": 7,
      "discordant": 9,
      "chi_square": 1.777778,
      "p_value": 0.182422
    }
  },
  "external_validation": {
    "available": true,
    "validation_mode": "frozen_vs_native_benchmark",
    "source": "ieee",
    "data_path": "data/train_transaction.csv",
    "identity_data_path": "data/train_identity.csv",
    "artifact_scope": "production",
    "random_state": 42,
    "split_strategy": "external_all_rows_no_ieee_fit (frozen) / ieee_chronological_70_15_15 (native)",
    "split": {
      "evaluation_rows": 590540,
      "train_rows": 413378,
      "validation_rows": 88581,
      "test_rows": 88581
    },
    "feature_alignment": {
      "method": "semantic_proxy_with_mfield_balance_diff",
      "target_feature_count": 25,
      "target_features": [
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
        "llm_risk_score",
        "llm_reason_count",
        "llm_high_risk_flag",
        "llm_review_flag",
        "llm_category_hash"
      ],
      "ieee_label_usage": "labels_used_only_after_prediction_for_metrics"
    },
    "models": [
      {
        "model_name": "xgboost_ieee_retrained",
        "family": "XGBClassifier",
        "feature_count": 42,
        "selected_threshold": 0.7,
        "frozen_model_source": "ieee_native",
        "evaluation_mode": "ieee_native_retrained",
        "params": {
          "n_estimators": 260,
          "max_depth": 6,
          "learning_rate": 0.06,
          "subsample": 0.9,
          "colsample_bytree": 0.85
        },
        "test": {
          "metrics": {
            "auc": 0.8415061172159675,
            "f1": 0.33284407813029243,
            "precision": 0.25528229996536195,
            "recall": 0.47810574116120663
          },
          "pr_auc": 0.32623864397226787,
          "confusion_matrix": {
            "true_negative": 81198,
            "false_positive": 4300,
            "false_negative": 1609,
            "true_positive": 1474
          }
        }
      },
      {
        "model_name": "xgboost_frozen_paysim",
        "family": "XGBClassifier",
        "feature_count": 25,
        "selected_threshold": 0.5,
        "frozen_model_source": "paysim",
        "frozen_model_train_rows": 322275,
        "evaluation_mode": "frozen_model_external_validation",
        "params": {
          "n_estimators": 260,
          "max_depth": 6,
          "learning_rate": 0.06,
          "subsample": 0.9,
          "colsample_bytree": 0.85
        },
        "test": {
          "metrics": {
            "auc": 0.6285168244881104,
            "f1": 0.020140247879973906,
            "precision": 0.06390685640362224,
            "recall": 0.011953733726951556
          },
          "pr_auc": 0.05315292936646154,
          "confusion_matrix": {
            "true_negative": 566259,
            "false_positive": 3618,
            "false_negative": 20416,
            "true_positive": 247
          }
        }
      }
    ]
  },
  "artifacts": {
    "baseline_comparison_json": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/baseline_comparison.json",
    "feature_ablation_json": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/feature_ablation.json",
    "medium_branch_ablation_json": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/medium_branch_ablation.json",
    "robustness_validation_json": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/robustness_validation.json",
    "external_validation_json": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/external_validation.json"
  }
}
````

Nguồn: `artifacts/reports/medium_branch_ablation.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "source": "paysim",
  "data_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
  "identity_data_path": null,
  "artifact_scope": "production",
  "selected_threshold": 0.5,
  "routing_calibration": {
    "low_quantile": 0.85,
    "high_quantile": 0.98,
    "low_quantile_score": 8.068120223470032e-05,
    "high_quantile_score": 0.0003051041276194155,
    "raw_probability_summary": {
      "min": 6.935265446372796e-07,
      "max": 0.9999958276748657,
      "mean": 0.000979467062279582,
      "std": 0.029942866414785385,
      "p50": 2.1707206542487256e-05,
      "p90": 0.00011097176320618019,
      "p95": 0.00017510111501906067,
      "p99": 0.0004990110755898058
    },
    "operational_score_summary": {
      "min": 0.002579,
      "max": 0.999,
      "mean": 0.1429459853458637,
      "std": 0.15316397071122506,
      "p50": 0.080715,
      "p90": 0.353988,
      "p95": 0.46828949999999986,
      "p99": 0.70005842
    },
    "validation_route_share": {
      "low": 0.849998,
      "medium": 0.149104,
      "high": 0.000898
    }
  },
  "medium_case_count": 14181,
  "policies": [
    {
      "policy_name": "score_threshold_block",
      "note": "Binary threshold baseline with no routing and no manual review state.",
      "approve_count": 68405,
      "review_count": 0,
      "block_count": 655,
      "approve_rate": 0.990515,
      "review_rate": 0.0,
      "block_rate": 0.009485,
      "block_precision": 0.9893129770992366,
      "block_recall": 0.9969230769230769,
      "block_f1": 0.993103448275862,
      "fraud_review_rate": 0.0,
      "review_fraud_share": 0.0,
      "false_positive_block_rate": 0.000102,
      "medium_case_count": 14181,
      "medium_case_share": 0.205343
    },
    {
      "policy_name": "route_without_agent",
      "note": "Original routing but every medium case is held for human review.",
      "approve_count": 54224,
      "review_count": 14181,
      "block_count": 655,
      "approve_rate": 0.785172,
      "review_rate": 0.205343,
      "block_rate": 0.009485,
      "block_precision": 0.9893129770992366,
      "block_recall": 0.9969230769230769,
      "block_f1": 0.993103448275862,
      "fraud_review_rate": 0.001538,
      "review_fraud_share": 7.1e-05,
      "false_positive_block_rate": 0.000102,
      "medium_case_count": 14181,
      "medium_case_share": 0.205343
    },
    {
      "policy_name": "route_medium_auto_approve",
      "note": "Routing with the medium band auto-approved to show the risk of removing investigation.",
      "approve_count": 68405,
      "review_count": 0,
      "block_count": 655,
      "approve_rate": 0.990515,
      "review_rate": 0.0,
      "block_rate": 0.009485,
      "block_precision": 0.9893129770992366,
      "block_recall": 0.9969230769230769,
      "block_f1": 0.993103448275862,
      "fraud_review_rate": 0.0,
      "review_fraud_share": 0.0,
      "false_positive_block_rate": 0.000102,
      "medium_case_count": 14181,
      "medium_case_share": 0.205343
    },
    {
      "policy_name": "route_with_medium_agent",
      "note": "Routing with the offline replay of the current investigator logic on medium cases.",
      "approve_count": 61984,
      "review_count": 6395,
      "block_count": 681,
      "approve_rate": 0.897538,
      "review_rate": 0.092601,
      "block_rate": 0.009861,
      "block_precision": 0.9515418502202643,
      "block_recall": 0.9969230769230769,
      "block_f1": 0.9737039819684448,
      "fraud_review_rate": 0.001538,
      "review_fraud_share": 0.000156,
      "false_positive_block_rate": 0.000482,
      "medium_case_count": 14181,
      "medium_case_share": 0.205343
    }
  ]
}
````

### 1.6. Toàn văn báo cáo mô phỏng và đánh giá test

Nguồn: `artifacts/reports/simulation_report.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "processed_transactions": 5000,
  "routes": {
    "low": 3950,
    "medium": 1048,
    "high": 2
  },
  "actions": {
    "approve": 4579,
    "review": 394,
    "step_up": 25,
    "block": 2
  },
  "metrics": {
    "evaluation_ready": true,
    "auc_ready": true,
    "positive_count": 2,
    "negative_count": 4998,
    "auc": 0.9999999999999999,
    "f1_block": 1.0,
    "precision_block": 1.0,
    "recall_block": 1.0
  },
  "latency": {
    "avg_ms": 59.95092252819595,
    "p95_ms": 78.19841785003518,
    "model_avg_ms": 55.81866408719688,
    "model_p95_ms": 69.39765844981594
  },
  "score_distribution": {
    "raw_probability": {
      "min": 9.84164898909512e-07,
      "max": 0.9995884299278259,
      "mean": 0.0004590178645667947,
      "std": 0.019122481828016687,
      "p50": 3.0669712941744365e-05,
      "p90": 0.00014149154012557138,
      "p95": 0.0002138010706403294,
      "p99": 0.000537212090566758
    },
    "operational_score": {
      "min": 0.003659,
      "max": 0.999,
      "mean": 0.1767517596,
      "std": 0.16577761149630252,
      "p50": 0.11404,
      "p90": 0.40838490000000033,
      "p95": 0.5372659500000002,
      "p99": 0.70007005
    }
  },
  "drift_flags": {
    "amount_shift": 2778,
    "device_shift": 4951
  },
  "source": "paysim",
  "deployment": {
    "last_trained_version": "v20260424T074126106494Z",
    "candidate_version": "v20260424T074126106494Z",
    "candidate_model_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/versions/v20260424T074126106494Z/xgboost_fraud.json",
    "candidate_metadata_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/versions/v20260424T074126106494Z/model_metadata.json",
    "rollback_version": "v20260424T065818461239Z",
    "updated_at": "2026-04-24T07:43:58.050233+00:00",
    "active_version": "v20260424T074126106494Z",
    "active_model_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/versions/v20260424T074126106494Z/xgboost_fraud.json",
    "active_metadata_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/versions/v20260424T074126106494Z/model_metadata.json",
    "deployment_strategy": "canary_then_full_rollout",
    "promotion_reason": "Full PaySim production model; IEEE-CIS frozen validation documents domain shift",
    "candidate_anomaly_model_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/versions/v20260424T074126106494Z/anomaly_sidecar.joblib",
    "active_anomaly_model_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/versions/v20260424T074126106494Z/anomaly_sidecar.joblib"
  },
  "artifacts": {
    "prediction_log": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/logs/predictions.jsonl",
    "feedback_log": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/logs/feedback.jsonl",
    "high_risk_log": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/logs/high_risk_async_llm.jsonl",
    "manual_review_queue": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/logs/manual_review_queue.jsonl"
  }
}
````

Nguồn: `artifacts/reports/evaluation_report.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "source": "paysim",
  "data_path": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
  "identity_data_path": null,
  "artifact_scope": "production",
  "anomaly_model_path": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/anomaly_sidecar.joblib",
  "sample_size_used": 460394,
  "feature_columns": [
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
    "llm_risk_score",
    "llm_reason_count",
    "llm_high_risk_flag",
    "llm_review_flag",
    "llm_category_hash"
  ],
  "routing_thresholds": {
    "low": 0.3,
    "high": 0.85
  },
  "train_end": 322275,
  "val_end": 391334,
  "selected_threshold": 0.5,
  "selected_params": {
    "n_estimators": 260,
    "max_depth": 6,
    "learning_rate": 0.06,
    "subsample": 0.9,
    "colsample_bytree": 0.85
  },
  "training_controls": {
    "max_delta_step": 1
  },
  "class_balance": {
    "positive_count": 429,
    "negative_count": 321846,
    "scale_pos_weight": 750.2237762237762
  },
  "routing_calibration": {
    "low_quantile": 0.85,
    "high_quantile": 0.98,
    "low_quantile_score": 8.068120223470032e-05,
    "high_quantile_score": 0.0003051041276194155,
    "raw_probability_summary": {
      "min": 6.935265446372796e-07,
      "max": 0.9999958276748657,
      "mean": 0.000979467062279582,
      "std": 0.029942866414785385,
      "p50": 2.1707206542487256e-05,
      "p90": 0.00011097176320618019,
      "p95": 0.00017510111501906067,
      "p99": 0.0004990110755898058
    },
    "operational_score_summary": {
      "min": 0.002579,
      "max": 0.999,
      "mean": 0.1429459853458637,
      "std": 0.15316397071122506,
      "p50": 0.080715,
      "p90": 0.353988,
      "p95": 0.46828949999999986,
      "p99": 0.70005842
    },
    "validation_route_share": {
      "low": 0.849998,
      "medium": 0.149104,
      "high": 0.000898
    }
  },
  "validation_metrics": {
    "auc": 0.9994133545353906,
    "f1": 0.96,
    "precision": 0.967741935483871,
    "recall": 0.9523809523809523
  },
  "test_metrics": {
    "auc": 0.9983827150776428,
    "f1": 0.993103448275862,
    "precision": 0.9893129770992366,
    "recall": 0.9969230769230769
  },
  "train_profile": {
    "amount_log1p_mean": 11.964039394332165,
    "tx_count_24h_mean": 7.136762082072764e-05,
    "device_tx_count_24h_mean": 7.547960592661547,
    "merchant_fraud_rate_mean": 0.0018938930199363891,
    "fraud_rate": 0.0013311612753083546
  },
  "split": {
    "total_rows": 460394,
    "train_rows": 322275,
    "validation_rows": 69059,
    "test_rows": 69060,
    "train_end": 322275,
    "val_end": 391334
  },
  "random_state": 42,
  "split_strategy": "chronological_by_step_after_TRANSFER_CASH_OUT_filter",
  "validation": {
    "metrics": {
      "auc": 0.9994133545353906,
      "f1": 0.96,
      "precision": 0.967741935483871,
      "recall": 0.9523809523809523
    },
    "confusion_matrix": {
      "true_negative": 68994,
      "false_positive": 2,
      "false_negative": 3,
      "true_positive": 60
    },
    "roc_auc": 0.9994133545353906,
    "pr_auc": 0.961260409954726
  },
  "test": {
    "metrics": {
      "auc": 0.9983827150776428,
      "f1": 0.993103448275862,
      "precision": 0.9893129770992366,
      "recall": 0.9969230769230769
    },
    "confusion_matrix": {
      "true_negative": 68403,
      "false_positive": 7,
      "false_negative": 2,
      "true_positive": 648
    },
    "roc_auc": 0.9983827150776428,
    "pr_auc": 0.9970017406400512
  },
  "artifacts": {
    "validation_roc_curve": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/validation_roc_curve.csv",
    "validation_pr_curve": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/validation_pr_curve.csv",
    "test_roc_curve": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/test_roc_curve.csv",
    "test_pr_curve": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/test_pr_curve.csv",
    "threshold_sweep": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/reports/validation_threshold_sweep.csv",
    "anomaly_sidecar_model": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/anomaly_sidecar.joblib"
  },
  "anomaly_sidecar": {
    "model": "IsolationForest",
    "feature_count": 17,
    "flag_threshold": 0.41828539293549033,
    "flag_threshold_method": "percentile_95_val",
    "flag_threshold_hardcoded_fallback": 0.7,
    "train_stats": {
      "train_legitimate_rows": 321846,
      "train_fraud_rows": 429,
      "anomaly_score_fraud_mean": 0.4032886977897447,
      "anomaly_score_fraud_p90": 0.6232399105316436,
      "anomaly_score_legit_mean": 0.18542102946736835,
      "anomaly_score_legit_p90": 0.3794753350011813,
      "score_min_raw": -0.7614994705324069,
      "score_max_raw": -0.3428741911159553
    },
    "val_eval": {
      "threshold": 0.41828539293549033,
      "total_rows": 69059,
      "fraud_rows": 63,
      "legit_rows": 68996,
      "anomaly_score_fraud_mean": 0.34372938568155254,
      "anomaly_score_fraud_p50": 0.353014623703098,
      "anomaly_score_fraud_p90": 0.5716246048608559,
      "anomaly_score_legit_mean": 0.16404972056232575,
      "anomaly_score_legit_p90": 0.3266136363459057,
      "flagged_total": 3453,
      "flagged_fraud": 22,
      "flagged_legit": 3431,
      "fraud_catch_rate": 0.3492063492063492,
      "false_flag_rate": 0.0497275204359673
    },
    "test_eval": {
      "threshold": 0.41828539293549033,
      "total_rows": 69060,
      "fraud_rows": 650,
      "legit_rows": 68410,
      "anomaly_score_fraud_mean": 0.41345979570282376,
      "anomaly_score_fraud_p50": 0.42820506263064123,
      "anomaly_score_fraud_p90": 0.6253633536302265,
      "anomaly_score_legit_mean": 0.17982392051556154,
      "anomaly_score_legit_p90": 0.3648857093846522,
      "flagged_total": 4866,
      "flagged_fraud": 344,
      "flagged_legit": 4522,
      "fraud_catch_rate": 0.5292307692307693,
      "false_flag_rate": 0.06610144715684842
    },
    "model_path": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/anomaly_sidecar.joblib"
  },
  "anomaly_flag_threshold": 0.41828539293549033
}
````

### 1.7. Đối chiếu khác biệt số liệu trong Markdown và bản ablation mới hơn

Hai tài liệu Markdown bên dưới ghi end-to-end avg `65.465 ms`, p95 `76.030 ms`, model avg `61.555 ms`, model p95 `67.138 ms`. JSON mô phỏng hiện có lần lượt là `59.95092252819595`, `78.19841785003518`, `55.81866408719688`, `69.39765844981594` ms. Giữ nguyên cả hai bộ theo nguồn; chưa có bằng chứng xác nhận chúng thuộc cùng một lần chạy.

Nguồn: `docs/BANG_KET_QUA_BAO_CAO.md` — dòng 128–148; sao chép nguyên văn.

````markdown
## 10. Simulation 5,000 giao dịch

| Route/Action | Count | Tỷ lệ |
|---|---:|---:|
| Route low | 3,950 | 79.00% |
| Route medium | 1,048 | 20.96% |
| Route high | 2 | 0.04% |
| Approve | 4,579 | 91.58% |
| Review | 394 | 7.88% |
| Step-up | 25 | 0.50% |
| Block | 2 | 0.04% |

| Latency | Giá trị |
|---|---:|
| End-to-end avg | 65.465 ms |
| End-to-end p95 | 76.030 ms |
| Model avg | 61.555 ms |
| Model p95 | 67.138 ms |

---

````

Nguồn: `docs/REPORT_MO_HINH_PAYSIM.md` — dòng 255–281; sao chép nguyên văn.

````markdown
## 13. Simulation và latency

Nguồn: `artifacts/reports/simulation_report.json`.

Simulation hiện tại chạy trên 5,000 giao dịch:

| Route/Action | Count | Tỷ lệ |
|---|---:|---:|
| Route low | 3,950 | 79.00% |
| Route medium | 1,048 | 20.96% |
| Route high | 2 | 0.04% |
| Approve | 4,579 | 91.58% |
| Review | 394 | 7.88% |
| Step-up | 25 | 0.50% |
| Block | 2 | 0.04% |

Latency end-to-end:

| Metric | Giá trị |
|---|---:|
| Avg | 65.465 ms |
| P95 | 76.030 ms |
| Model avg | 61.555 ms |
| Model P95 | 67.138 ms |

---

````

Bản B8 final bên dưới có review `6383`, approve `61994`, block `683`, khác bản ablation gốc (`6395`, `61984`, `681`). Đây là nguồn bổ sung được tách riêng; không sửa số gốc theo bản mới.

Nguồn: `artifacts/reports/b8_final/medium_branch_ablation_b8.md` — toàn bộ file; sao chép nguyên văn.

````markdown
# B8 Final Medium-Branch Policy Ablation

- Generated at: `2026-10-10T14:42:29.119846+00:00`
- Git commit: `8ad06aff01a5932d94436df9e34f7fca820c9fea`
- Git dirty: `true`
- Experiment version: `b8-v2-dependency-aware-leakage-aligned`
- Dataset: `paysim` / `460394` rows
- Split: `322275 / 69059 / 69060`
- Split strategy: `chronological_by_step_after_TRANSFER_CASH_OUT_filter`
- Random state: `42`
- Leakage control: Chronological PaySim split after TRANSFER+CASH_OUT filtering. Training rows update activity and label-based historical risk state. Validation and test rows update activity sequentially only; their labels never update historical fraud-rate state before feature construction or policy decisions.
- Experiment meaning: deterministic offline medium-branch investigation replay.
- Full ReAct runtime executed: `false`.
- Classifier predictions changed: `false`.
- Low/high route actions fixed across policies: `true`.

| Policy | Medium cases | Approve | Approve rate | Review | Review rate | Block | Block rate | Block precision | Block recall | Block F1 | Fraud reviewed | Fraud review rate | FP blocks | FP block rate | Review reduction | Review reduction rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_medium_manual_review | 14181 | 54224 | 0.785172 | 14181 | 0.205343 | 655 | 0.009485 | 0.9893129770992366 | 0.9969230769230769 | 0.993103448275862 | 1 | 0.001538 | 7 | 0.000102 | 0 | 0.0 |
| deterministic_offline_investigation_replay | 14181 | 61994 | 0.897683 | 6383 | 0.092427 | 683 | 0.00989 | 0.9487554904831625 | 0.9969230769230769 | 0.9722430607651913 | 1 | 0.001538 | 35 | 0.000512 | 7798 | 0.549891 |
````

Nguồn: `artifacts/reports/b8_final/medium_branch_ablation_b8.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "provenance": {
    "generated_at": "2026-10-10T14:42:29.119846+00:00",
    "git_commit": "8ad06aff01a5932d94436df9e34f7fca820c9fea",
    "git_dirty": true,
    "code_sha256": {
      "fraud_flow/research.py": "b4084e86b8657df99a87be403e3dba3324d6b688c1c53c6c30a608bd1c686a6a",
      "scripts/run_b8_ablation.py": "2c303d7f638a0f25c3572202e94437c277d32823ec613bfcd377a4b965a64c2b"
    },
    "random_state": 42,
    "dataset_source": "paysim",
    "dataset_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "dataset_sha256": "437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498",
    "dataset_rows": 460394,
    "train_rows": 322275,
    "validation_rows": 69059,
    "test_rows": 69060,
    "split_strategy": "chronological_by_step_after_TRANSFER_CASH_OUT_filter",
    "leakage_control_protocol": "Chronological PaySim split after TRANSFER+CASH_OUT filtering. Training rows update activity and label-based historical risk state. Validation and test rows update activity sequentially only; their labels never update historical fraud-rate state before feature construction or policy decisions.",
    "experiment_version": "b8-v2-dependency-aware-leakage-aligned"
  },
  "experiment_name": "deterministic offline medium-branch investigation replay",
  "full_react_runtime_executed": false,
  "classifier_predictions_changed": false,
  "classifier_test_probability_sha256": "a1f3d7710a18ee615cac9ec944aa7351905ec33c2a7efadf6cdfdfd384361e13",
  "same_held_out_test_set": true,
  "low_high_route_actions_fixed": true,
  "selected_classifier_threshold": 0.5,
  "routing_calibration": {
    "low_quantile": 0.85,
    "high_quantile": 0.98,
    "low_quantile_score": 8.068120223470032e-05,
    "high_quantile_score": 0.0003051041276194155,
    "raw_probability_summary": {
      "min": 6.935265446372796e-07,
      "max": 0.9999958276748657,
      "mean": 0.000979467062279582,
      "std": 0.029942866414785385,
      "p50": 2.1707206542487256e-05,
      "p90": 0.00011097176320618019,
      "p95": 0.00017510111501906067,
      "p99": 0.0004990110755898058
    },
    "operational_score_summary": {
      "min": 0.002579,
      "max": 0.999,
      "mean": 0.1429459853458637,
      "std": 0.15316397071122506,
      "p50": 0.080715,
      "p90": 0.353988,
      "p95": 0.46828949999999986,
      "p99": 0.70005842
    },
    "validation_route_share": {
      "low": 0.849998,
      "medium": 0.149104,
      "high": 0.000898
    }
  },
  "history_protocol": {
    "training": "activity and labels warm-start FeatureStore",
    "validation": "activity-only warm-start; validation labels are not consumed",
    "test": "lookup and decision first, then activity-only update; test labels are never consumed"
  },
  "medium_case_count": 14181,
  "policies": [
    {
      "policy": "all_medium_manual_review",
      "approve_count": 54224,
      "review_count": 14181,
      "block_count": 655,
      "approve_rate": 0.785172,
      "review_rate": 0.205343,
      "block_rate": 0.009485,
      "block_precision": 0.9893129770992366,
      "block_recall": 0.9969230769230769,
      "block_f1": 0.993103448275862,
      "fraud_review_count": 1,
      "fraud_review_rate": 0.001538,
      "review_fraud_share": 7.1e-05,
      "false_positive_blocks": 7,
      "false_positive_block_rate": 0.000102,
      "medium_case_count": 14181,
      "medium_case_share": 0.205343,
      "manual_review_reduction_count": 0,
      "manual_review_reduction_rate": 0.0,
      "classifier_predictions_changed": false,
      "note": "All medium-risk cases are sent to manual review; low/high actions remain fixed."
    },
    {
      "policy": "deterministic_offline_investigation_replay",
      "approve_count": 61994,
      "review_count": 6383,
      "block_count": 683,
      "approve_rate": 0.897683,
      "review_rate": 0.092427,
      "block_rate": 0.00989,
      "block_precision": 0.9487554904831625,
      "block_recall": 0.9969230769230769,
      "block_f1": 0.9722430607651913,
      "fraud_review_count": 1,
      "fraud_review_rate": 0.001538,
      "review_fraud_share": 0.000157,
      "false_positive_blocks": 35,
      "false_positive_block_rate": 0.000512,
      "medium_case_count": 14181,
      "medium_case_share": 0.205343,
      "manual_review_reduction_count": 7798,
      "manual_review_reduction_rate": 0.549891,
      "classifier_predictions_changed": false,
      "note": "Deterministic offline investigator policy runs only on medium cases; this does not execute ReActInvestigator."
    }
  ]
}
````

### 1.8. Thời gian xử lý trên mẫu test của B11 và benchmark lịch sử

B11 đo `1332` giao dịch test sau `100` giao dịch warm-up; có low `1072`, medium `259`, high `1`. Đây là mẫu test đo latency, không phải toàn bộ `69060` giao dịch và không phải đợt mô phỏng `5000`. Tỷ lệ theo số lượng được biểu diễn chính xác: low `100 × 1072 / 1332 %`, medium `100 × 259 / 1332 %`, high `100 × 1 / 1332 %`.

Giữ đầy đủ mean/p50/p95/p99/max, thời gian thành phần, thời gian training, throughput và ranh giới đo. B11 loại Redis/network, logging và API/LLM bên ngoài khỏi thời gian đo. Báo cáo cũ `latency_report.json` đo `1000` giao dịch, được B11 đánh dấu `OLD_BENCHMARK_REUSABLE = NO`; giữ ở đây để đối chiếu lịch sử.

Nguồn: `artifacts/reports/b11_final/b11_efficiency_summary.md` — toàn bộ file; sao chép nguyên văn.

````markdown
# B11 Computational Efficiency and Deployment Feasibility

## Environment

- CPU: `AMD Ryzen 7 7435HS`
- Cores: physical=8, logical=16
- RAM: 15.304630279541016 GiB
- OS: `Linux-6.17.0-20-generic-x86_64-with-glibc2.39`
- Python: `3.12.3`
- XGBoost: `3.2.0`; scikit-learn: `1.8.0`; pandas: `2.2.3`; NumPy: `2.2.5`; SHAP: `0.51.0`
- GPU available: `true` (NVIDIA GeForce RTX 4050 Laptop GPU)
- Redis mode: `not used; in-memory FeatureStore; Redis/network overhead excluded`

## Fixed-configuration model fitting time

This is fixed-configuration model fitting time, not full hyperparameter-search time. Models were temporary in-memory objects and were not saved.

- Training rows: 322275; features: 25; repetitions: 3
- Individual seconds: `[1.823165555999367, 1.586516784998821, 1.5975049919998128]`
- Mean/median/min/max seconds: 1.669062444332667 / 1.5975049919998128 / 1.586516784998821 / 1.823165555999367

## Local component latency

Measured 1332 sequential held-out test transactions after 100 stateful warm-up transactions. Route counts: `{'low': 1072, 'medium': 259, 'high': 1}`.

| Component | n | Mean ms | p50 ms | p95 ms | p99 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| feature_store_lookup_ms | 1332 | 0.02259052630083292 | 0.022170999727677554 | 0.028833499254687926 | 0.03406769021239601 | 0.04259900015313178 |
| feature_assembly_ms | 1332 | 0.020794278509139997 | 0.020337999558250885 | 0.024724999639147427 | 0.028847109297203133 | 0.035876999390893616 |
| xgboost_predict_proba_ms | 1332 | 3.550239045042334 | 1.5914599998723133 | 16.636054500486352 | 18.446936149248362 | 20.35675499973877 |
| shap_explanation_ms | 1332 | 3.3466839083969475 | 2.7176789999430184 | 5.15295645082006 | 20.47196220933986 | 40.94133100079489 |
| calibration_and_routing_ms | 1332 | 0.004271492511802248 | 0.004237999746692367 | 0.005249999958323315 | 0.005738599447795425 | 0.009617999239708297 |
| anomaly_sidecar_ms | 1332 | 6.859352249277064 | 6.818486000156554 | 7.132253950294398 | 7.441498969619715 | 9.714522999274777 |
| model_service_total_ms | 1332 | 14.108352302564008 | 11.535494501003996 | 28.061725400038995 | 46.38491170078854 | 67.6028319994657 |
| deterministic_medium_investigation_ms | 259 | 0.09786381843594455 | 0.09679100003268104 | 0.11407909987610765 | 0.11974102020758437 | 0.13084300007903948 |
| activity_state_update_ms | 1332 | 0.015819686239836726 | 0.015443500160472468 | 0.022089999674790306 | 0.024217100544774443 | 0.030627001251559705 |
| local_end_to_end_ms | 1332 | 14.192055347616355 | 11.61940650035831 | 28.13968635018682 | 46.46767077978442 | 67.69028499911656 |

Sequential single-process local throughput: **70.46195744776011 tx/s**. This is not production capacity.

## Local end-to-end latency by route

| Route | n | Mean ms | p50 ms | p95 ms | p99 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 1072 | 14.165578430053566 | 11.602710500483226 | 28.09144905022549 | 43.27854960998579 | 67.69028499911656 |
| medium | 259 | 14.312091235546296 | 11.679162000291399 | 28.43165310077893 | 50.82025867955962 | 65.11029600005713 |
| high | 1 | 11.48601600107213 | 11.48601600107213 | 11.48601600107213 | 11.48601600107213 | 11.48601600107213 |

## Medium branch and deployment boundary

Deterministic offline investigation replay takes mean=0.09786381843594455 ms locally (n=259, p95=0.11407909987610765 ms). This is not a measurement of external LLM-backed ReAct latency.

```ini
external_llm_react_latency = NOT MEASURED
Redis/network overhead = excluded
```

## Timing boundary

For each measured transaction, local_end_to_end_ms starts immediately before the in-memory FeatureStore lookup and stops immediately after activity-only state update. It includes feature lookup, feature assembly, one-row DataFrame construction, raw XGBoost predict_proba, TreeSHAP explanation, calibration/routing, anomaly-sidecar scoring, deterministic offline investigation replay for medium routes, and observe_activity. Event parsing, dataset loading, model/explainer loading, training, external LLM/API calls, Redis, network, logging, and concurrency are outside this boundary.

## Old benchmark audit

The old report is reproduced as mean=35.716 ms, p50=35.795 ms, p95=44.463 ms, p99=51.546 ms, sample=1000, routes={'low': 887, 'medium': 113, 'high': 0}.

Its timer starts after FeatureStore lookup and feature assembly; warm-up events do not advance FeatureStore state. It therefore cannot support a local end-to-end claim.

```ini
OLD_BENCHMARK_REUSABLE = NO
```
````

Nguồn: `artifacts/reports/b11_final/b11_latency_components.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "schema_version": "b11-latency-components-v1",
  "source": "PaySim held-out chronological test stream",
  "warmup_count": 100,
  "measured_count": 1332,
  "route_counts": {
    "low": 1072,
    "medium": 259,
    "high": 1
  },
  "route_targets": {
    "minimum_total": 1000,
    "minimum_low": 800,
    "minimum_medium": 100,
    "minimum_high": 1
  },
  "test_rows_consumed_including_warmup": 1432,
  "chronological_no_shuffle": true,
  "overall": {
    "feature_store_lookup_ms": {
      "n": 1332,
      "mean_ms": 0.02259052630083292,
      "p50_ms": 0.022170999727677554,
      "p95_ms": 0.028833499254687926,
      "p99_ms": 0.03406769021239601,
      "max_ms": 0.04259900015313178
    },
    "feature_assembly_ms": {
      "n": 1332,
      "mean_ms": 0.020794278509139997,
      "p50_ms": 0.020337999558250885,
      "p95_ms": 0.024724999639147427,
      "p99_ms": 0.028847109297203133,
      "max_ms": 0.035876999390893616
    },
    "xgboost_predict_proba_ms": {
      "n": 1332,
      "mean_ms": 3.550239045042334,
      "p50_ms": 1.5914599998723133,
      "p95_ms": 16.636054500486352,
      "p99_ms": 18.446936149248362,
      "max_ms": 20.35675499973877
    },
    "shap_explanation_ms": {
      "n": 1332,
      "mean_ms": 3.3466839083969475,
      "p50_ms": 2.7176789999430184,
      "p95_ms": 5.15295645082006,
      "p99_ms": 20.47196220933986,
      "max_ms": 40.94133100079489
    },
    "calibration_and_routing_ms": {
      "n": 1332,
      "mean_ms": 0.004271492511802248,
      "p50_ms": 0.004237999746692367,
      "p95_ms": 0.005249999958323315,
      "p99_ms": 0.005738599447795425,
      "max_ms": 0.009617999239708297
    },
    "anomaly_sidecar_ms": {
      "n": 1332,
      "mean_ms": 6.859352249277064,
      "p50_ms": 6.818486000156554,
      "p95_ms": 7.132253950294398,
      "p99_ms": 7.441498969619715,
      "max_ms": 9.714522999274777
    },
    "model_service_total_ms": {
      "n": 1332,
      "mean_ms": 14.108352302564008,
      "p50_ms": 11.535494501003996,
      "p95_ms": 28.061725400038995,
      "p99_ms": 46.38491170078854,
      "max_ms": 67.6028319994657
    },
    "deterministic_medium_investigation_ms": {
      "n": 259,
      "mean_ms": 0.09786381843594455,
      "p50_ms": 0.09679100003268104,
      "p95_ms": 0.11407909987610765,
      "p99_ms": 0.11974102020758437,
      "max_ms": 0.13084300007903948
    },
    "activity_state_update_ms": {
      "n": 1332,
      "mean_ms": 0.015819686239836726,
      "p50_ms": 0.015443500160472468,
      "p95_ms": 0.022089999674790306,
      "p99_ms": 0.024217100544774443,
      "max_ms": 0.030627001251559705
    },
    "local_end_to_end_ms": {
      "n": 1332,
      "mean_ms": 14.192055347616355,
      "p50_ms": 11.61940650035831,
      "p95_ms": 28.13968635018682,
      "p99_ms": 46.46767077978442,
      "max_ms": 67.69028499911656,
      "throughput_tx_per_second": 70.46195744776011,
      "throughput_label": "sequential single-process local throughput"
    }
  },
  "by_route": {
    "low": {
      "feature_store_lookup_ms": {
        "n": 1072,
        "mean_ms": 0.022637986029988483,
        "p50_ms": 0.022171999262354802,
        "p95_ms": 0.028921999728481747,
        "p99_ms": 0.03502459061564877,
        "max_ms": 0.04259900015313178
      },
      "feature_assembly_ms": {
        "n": 1072,
        "mean_ms": 0.0207505914004151,
        "p50_ms": 0.0203180006792536,
        "p95_ms": 0.02428500010864809,
        "p99_ms": 0.02816460091707995,
        "max_ms": 0.03141900015179999
      },
      "xgboost_predict_proba_ms": {
        "n": 1072,
        "mean_ms": 3.5837152406707875,
        "p50_ms": 1.5918409999358119,
        "p95_ms": 16.654100750201906,
        "p99_ms": 18.413992639561908,
        "max_ms": 20.35675499973877
      },
      "shap_explanation_ms": {
        "n": 1072,
        "mean_ms": 3.30252121547,
        "p50_ms": 2.7178844993613893,
        "p95_ms": 5.077918800088807,
        "p99_ms": 18.700873179422995,
        "max_ms": 40.94133100079489
      },
      "calibration_and_routing_ms": {
        "n": 1072,
        "mean_ms": 0.004230548521304423,
        "p50_ms": 0.004202999662084039,
        "p95_ms": 0.005059450813860167,
        "p99_ms": 0.005638989350700284,
        "max_ms": 0.009617999239708297
      },
      "anomaly_sidecar_ms": {
        "n": 1072,
        "mean_ms": 6.862203680043422,
        "p50_ms": 6.816697499743896,
        "p95_ms": 7.141663450602208,
        "p99_ms": 7.518755740638879,
        "max_ms": 9.714522999274777
      },
      "model_service_total_ms": {
        "n": 1072,
        "mean_ms": 14.100109812504153,
        "p50_ms": 11.539068499587302,
        "p95_ms": 28.013626750089312,
        "p99_ms": 43.20640697091207,
        "max_ms": 67.6028319994657
      },
      "deterministic_medium_investigation_ms": {
        "n": 0,
        "mean_ms": null,
        "p50_ms": null,
        "p95_ms": null,
        "p99_ms": null,
        "max_ms": null
      },
      "activity_state_update_ms": {
        "n": 1072,
        "mean_ms": 0.016641088676018923,
        "p50_ms": 0.01610000072105322,
        "p95_ms": 0.022402048853109584,
        "p99_ms": 0.02450179918014328,
        "max_ms": 0.030627001251559705
      },
      "local_end_to_end_ms": {
        "n": 1072,
        "mean_ms": 14.165578430053566,
        "p50_ms": 11.602710500483226,
        "p95_ms": 28.09144905022549,
        "p99_ms": 43.27854960998579,
        "max_ms": 67.69028499911656,
        "throughput_tx_per_second": 70.59365806611954,
        "throughput_label": "sequential single-process local throughput"
      }
    },
    "medium": {
      "feature_store_lookup_ms": {
        "n": 259,
        "mean_ms": 0.022402015476409815,
        "p50_ms": 0.022010999600752257,
        "p95_ms": 0.028254099925106854,
        "p99_ms": 0.03111443991656414,
        "max_ms": 0.03306100006739143
      },
      "feature_assembly_ms": {
        "n": 259,
        "mean_ms": 0.020974810784073587,
        "p50_ms": 0.02042800042545423,
        "p95_ms": 0.02572209959907923,
        "p99_ms": 0.03052283987926784,
        "max_ms": 0.035876999390893616
      },
      "xgboost_predict_proba_ms": {
        "n": 259,
        "mean_ms": 3.419516046318164,
        "p50_ms": 1.5888400012045167,
        "p95_ms": 16.432516500572092,
        "p99_ms": 18.50028949895204,
        "max_ms": 19.843981001031352
      },
      "shap_explanation_ms": {
        "n": 259,
        "mean_ms": 3.5319507027045005,
        "p50_ms": 2.7176139992661774,
        "p95_ms": 5.883602200628954,
        "p99_ms": 25.460648219705007,
        "max_ms": 37.5278999999864
      },
      "calibration_and_routing_ms": {
        "n": 259,
        "mean_ms": 0.0044429845982442455,
        "p50_ms": 0.004359000740805641,
        "p95_ms": 0.0055460997828049585,
        "p99_ms": 0.00588520044402685,
        "max_ms": 0.006210999345057644
      },
      "anomaly_sidecar_ms": {
        "n": 259,
        "mean_ms": 6.8475470927865425,
        "p50_ms": 6.822072000431945,
        "p95_ms": 7.081241300875263,
        "p99_ms": 7.232737560661917,
        "max_ms": 7.285675999810337
      },
      "model_service_total_ms": {
        "n": 259,
        "mean_ms": 14.152835984592127,
        "p50_ms": 11.514619000081439,
        "p95_ms": 28.268825699160516,
        "p99_ms": 50.63726505952217,
        "max_ms": 64.91669599927263
      },
      "deterministic_medium_investigation_ms": {
        "n": 259,
        "mean_ms": 0.09786381843594455,
        "p50_ms": 0.09679100003268104,
        "p95_ms": 0.11407909987610765,
        "p99_ms": 0.11974102020758437,
        "max_ms": 0.13084300007903948
      },
      "activity_state_update_ms": {
        "n": 259,
        "mean_ms": 0.012416077261571736,
        "p50_ms": 0.012302998584345914,
        "p95_ms": 0.015797099331393838,
        "p99_ms": 0.017571019998285916,
        "max_ms": 0.01862399949459359
      },
      "local_end_to_end_ms": {
        "n": 259,
        "mean_ms": 14.312091235546296,
        "p50_ms": 11.679162000291399,
        "p95_ms": 28.43165310077893,
        "p99_ms": 50.82025867955962,
        "max_ms": 65.11029600005713,
        "throughput_tx_per_second": 69.87099114602799,
        "throughput_label": "sequential single-process local throughput"
      }
    },
    "high": {
      "feature_store_lookup_ms": {
        "n": 1,
        "mean_ms": 0.020538000171654858,
        "p50_ms": 0.020538000171654858,
        "p95_ms": 0.020538000171654858,
        "p99_ms": 0.020538000171654858,
        "max_ms": 0.020538000171654858
      },
      "feature_assembly_ms": {
        "n": 1,
        "mean_ms": 0.020868999854428694,
        "p50_ms": 0.020868999854428694,
        "p95_ms": 0.020868999854428694,
        "p99_ms": 0.020868999854428694,
        "max_ms": 0.020868999854428694
      },
      "xgboost_predict_proba_ms": {
        "n": 1,
        "mean_ms": 1.5210140009003226,
        "p50_ms": 1.5210140009003226,
        "p95_ms": 1.5210140009003226,
        "p99_ms": 1.5210140009003226,
        "max_ms": 1.5210140009003226
      },
      "shap_explanation_ms": {
        "n": 1,
        "mean_ms": 2.704991000427981,
        "p50_ms": 2.704991000427981,
        "p95_ms": 2.704991000427981,
        "p99_ms": 2.704991000427981,
        "max_ms": 2.704991000427981
      },
      "calibration_and_routing_ms": {
        "n": 1,
        "mean_ms": 0.003746999936993234,
        "p50_ms": 0.003746999936993234,
        "p95_ms": 0.003746999936993234,
        "p99_ms": 0.003746999936993234,
        "max_ms": 0.003746999936993234
      },
      "anomaly_sidecar_ms": {
        "n": 1,
        "mean_ms": 6.8601539987867,
        "p50_ms": 6.8601539987867,
        "p95_ms": 6.8601539987867,
        "p99_ms": 6.8601539987867,
        "max_ms": 6.8601539987867
      },
      "model_service_total_ms": {
        "n": 1,
        "mean_ms": 11.423028001445346,
        "p50_ms": 11.423028001445346,
        "p95_ms": 11.423028001445346,
        "p99_ms": 11.423028001445346,
        "max_ms": 11.423028001445346
      },
      "deterministic_medium_investigation_ms": {
        "n": 0,
        "mean_ms": null,
        "p50_ms": null,
        "p95_ms": null,
        "p99_ms": null,
        "max_ms": null
      },
      "activity_state_update_ms": {
        "n": 1,
        "mean_ms": 0.01681100002315361,
        "p50_ms": 0.01681100002315361,
        "p95_ms": 0.01681100002315361,
        "p99_ms": 0.01681100002315361,
        "max_ms": 0.01681100002315361
      },
      "local_end_to_end_ms": {
        "n": 1,
        "mean_ms": 11.48601600107213,
        "p50_ms": 11.48601600107213,
        "p95_ms": 11.48601600107213,
        "p99_ms": 11.48601600107213,
        "max_ms": 11.48601600107213,
        "throughput_tx_per_second": 87.06238959676338,
        "throughput_label": "sequential single-process local throughput"
      }
    }
  },
  "timing_boundary": "For each measured transaction, local_end_to_end_ms starts immediately before the in-memory FeatureStore lookup and stops immediately after activity-only state update. It includes feature lookup, feature assembly, one-row DataFrame construction, raw XGBoost predict_proba, TreeSHAP explanation, calibration/routing, anomaly-sidecar scoring, deterministic offline investigation replay for medium routes, and observe_activity. Event parsing, dataset loading, model/explainer loading, training, external LLM/API calls, Redis, network, logging, and concurrency are outside this boundary.",
  "external_llm_react_latency": "NOT MEASURED",
  "redis_network_overhead": "excluded; in-memory FeatureStore",
  "throughput_interpretation": "sequential single-process local throughput; not production capacity",
  "provenance": {
    "generated_at": "2026-10-10T16:56:07.448476+00:00",
    "git_commit": "8ad06aff01a5932d94436df9e34f7fca820c9fea",
    "git_dirty": true,
    "code_sha256": "6b75e946682fcd73812b33a3598e20316c90bb63befbe1832737e851db7ab80c",
    "code_file_sha256": {
      "scripts/run_b11_efficiency.py": "4f082675cfca2f3ccf4a58925e337d5d3940070dd327d3493ea5fccc57a98a65",
      "scripts/benchmark_latency.py": "b1f2fbf3248f68c34e21d696983499252ce34d3566ba7ba6d48a1cad18e9ddf5",
      "fraud_flow/pipeline.py": "8d6ae0f7cbf4d058c4826161ca62d60eb788f0169ebfe7d21e4037b29a034893",
      "fraud_flow/features.py": "83ddb3f634daed961a216ea1cac053aac38d2e6272e2db3fb5eba4fa385ad1a9",
      "fraud_flow/feature_store.py": "f524dd2e43a5aec7a161af2e642de4478c556d07f2abbcaf7b19c31a6cb8bd5e",
      "fraud_flow/research.py": "b4084e86b8657df99a87be403e3dba3324d6b688c1c53c6c30a608bd1c686a6a",
      "fraud_flow/anomaly.py": "722736ebd83a547b64c49d62dbbf4382cdca466672845e2b716dd5d037015a07",
      "fraud_flow/calibration.py": "7082e17e167761d36a2c681965d6b5a2cb0eef7c1694a8f4f7a6e89cea8e16dc",
      "fraud_flow/config.py": "7ff1a1597e21c700e96a56166115685c4f9db2c357fd664b7c6c4cd9b946a4e1"
    },
    "dataset_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "dataset_sha256": "437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498",
    "model_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/xgboost_fraud.json",
    "model_sha256": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
    "metadata_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/model_metadata.json",
    "metadata_sha256": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
    "anomaly_sidecar_sha256": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658",
    "evaluation_report_sha256": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
    "old_latency_report_sha256": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
    "protected_hashes_before": {
      "artifacts/models/xgboost_fraud.json": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
      "artifacts/models/model_metadata.json": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
      "artifacts/reports/evaluation_report.json": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
      "artifacts/reports/latency_report.json": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
      "artifacts/models/anomaly_sidecar.joblib": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658"
    },
    "protected_hashes_after": {
      "artifacts/models/xgboost_fraud.json": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
      "artifacts/models/model_metadata.json": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
      "artifacts/reports/evaluation_report.json": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
      "artifacts/reports/latency_report.json": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
      "artifacts/models/anomaly_sidecar.joblib": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658"
    },
    "benchmark_command": "'/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python' scripts/run_b11_efficiency.py --training-repetitions 3 --warmup 100 --min-measured 1000 --min-low 800 --min-medium 100 --min-high 1",
    "sample_count": 1332,
    "warmup_count": 100,
    "timing_boundary": "For each measured transaction, local_end_to_end_ms starts immediately before the in-memory FeatureStore lookup and stops immediately after activity-only state update. It includes feature lookup, feature assembly, one-row DataFrame construction, raw XGBoost predict_proba, TreeSHAP explanation, calibration/routing, anomaly-sidecar scoring, deterministic offline investigation replay for medium routes, and observe_activity. Event parsing, dataset loading, model/explainer loading, training, external LLM/API calls, Redis, network, logging, and concurrency are outside this boundary.",
    "machine_environment": {
      "cpu_model": "AMD Ryzen 7 7435HS",
      "physical_cores": 8,
      "logical_cores": 16,
      "ram_total_bytes": 16433221632,
      "ram_total_gib": 15.304630279541016,
      "operating_system": "Linux-6.17.0-20-generic-x86_64-with-glibc2.39",
      "python_version": "3.12.3",
      "python_executable": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python",
      "packages": {
        "xgboost": "3.2.0",
        "scikit-learn": "1.8.0",
        "pandas": "2.2.3",
        "numpy": "2.2.5",
        "shap": "0.51.0"
      },
      "gpu": {
        "available": true,
        "devices": [
          "NVIDIA GeForce RTX 4050 Laptop GPU"
        ],
        "detection": "nvidia-smi query"
      },
      "xgboost_benchmark_device": "CPU; tree_method=hist and no device=cuda parameter",
      "redis_mode": "not used; in-memory FeatureStore; Redis/network overhead excluded",
      "external_llm_backend_configured": false,
      "external_llm_react_latency": "NOT MEASURED",
      "external_llm_reason": "External network/API execution was excluded to avoid dependency and cost.",
      "clock": "time.perf_counter"
    }
  }
}
````

Nguồn: `artifacts/reports/b11_final/b11_route_latency.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "schema_version": "b11-route-latency-v1",
  "route_counts": {
    "low": 1072,
    "medium": 259,
    "high": 1
  },
  "measured_count": 1332,
  "warmup_count": 100,
  "chronological_no_shuffle": true,
  "by_route": {
    "low": {
      "feature_store_lookup_ms": {
        "n": 1072,
        "mean_ms": 0.022637986029988483,
        "p50_ms": 0.022171999262354802,
        "p95_ms": 0.028921999728481747,
        "p99_ms": 0.03502459061564877,
        "max_ms": 0.04259900015313178
      },
      "feature_assembly_ms": {
        "n": 1072,
        "mean_ms": 0.0207505914004151,
        "p50_ms": 0.0203180006792536,
        "p95_ms": 0.02428500010864809,
        "p99_ms": 0.02816460091707995,
        "max_ms": 0.03141900015179999
      },
      "xgboost_predict_proba_ms": {
        "n": 1072,
        "mean_ms": 3.5837152406707875,
        "p50_ms": 1.5918409999358119,
        "p95_ms": 16.654100750201906,
        "p99_ms": 18.413992639561908,
        "max_ms": 20.35675499973877
      },
      "shap_explanation_ms": {
        "n": 1072,
        "mean_ms": 3.30252121547,
        "p50_ms": 2.7178844993613893,
        "p95_ms": 5.077918800088807,
        "p99_ms": 18.700873179422995,
        "max_ms": 40.94133100079489
      },
      "calibration_and_routing_ms": {
        "n": 1072,
        "mean_ms": 0.004230548521304423,
        "p50_ms": 0.004202999662084039,
        "p95_ms": 0.005059450813860167,
        "p99_ms": 0.005638989350700284,
        "max_ms": 0.009617999239708297
      },
      "anomaly_sidecar_ms": {
        "n": 1072,
        "mean_ms": 6.862203680043422,
        "p50_ms": 6.816697499743896,
        "p95_ms": 7.141663450602208,
        "p99_ms": 7.518755740638879,
        "max_ms": 9.714522999274777
      },
      "model_service_total_ms": {
        "n": 1072,
        "mean_ms": 14.100109812504153,
        "p50_ms": 11.539068499587302,
        "p95_ms": 28.013626750089312,
        "p99_ms": 43.20640697091207,
        "max_ms": 67.6028319994657
      },
      "deterministic_medium_investigation_ms": {
        "n": 0,
        "mean_ms": null,
        "p50_ms": null,
        "p95_ms": null,
        "p99_ms": null,
        "max_ms": null
      },
      "activity_state_update_ms": {
        "n": 1072,
        "mean_ms": 0.016641088676018923,
        "p50_ms": 0.01610000072105322,
        "p95_ms": 0.022402048853109584,
        "p99_ms": 0.02450179918014328,
        "max_ms": 0.030627001251559705
      },
      "local_end_to_end_ms": {
        "n": 1072,
        "mean_ms": 14.165578430053566,
        "p50_ms": 11.602710500483226,
        "p95_ms": 28.09144905022549,
        "p99_ms": 43.27854960998579,
        "max_ms": 67.69028499911656,
        "throughput_tx_per_second": 70.59365806611954,
        "throughput_label": "sequential single-process local throughput"
      }
    },
    "medium": {
      "feature_store_lookup_ms": {
        "n": 259,
        "mean_ms": 0.022402015476409815,
        "p50_ms": 0.022010999600752257,
        "p95_ms": 0.028254099925106854,
        "p99_ms": 0.03111443991656414,
        "max_ms": 0.03306100006739143
      },
      "feature_assembly_ms": {
        "n": 259,
        "mean_ms": 0.020974810784073587,
        "p50_ms": 0.02042800042545423,
        "p95_ms": 0.02572209959907923,
        "p99_ms": 0.03052283987926784,
        "max_ms": 0.035876999390893616
      },
      "xgboost_predict_proba_ms": {
        "n": 259,
        "mean_ms": 3.419516046318164,
        "p50_ms": 1.5888400012045167,
        "p95_ms": 16.432516500572092,
        "p99_ms": 18.50028949895204,
        "max_ms": 19.843981001031352
      },
      "shap_explanation_ms": {
        "n": 259,
        "mean_ms": 3.5319507027045005,
        "p50_ms": 2.7176139992661774,
        "p95_ms": 5.883602200628954,
        "p99_ms": 25.460648219705007,
        "max_ms": 37.5278999999864
      },
      "calibration_and_routing_ms": {
        "n": 259,
        "mean_ms": 0.0044429845982442455,
        "p50_ms": 0.004359000740805641,
        "p95_ms": 0.0055460997828049585,
        "p99_ms": 0.00588520044402685,
        "max_ms": 0.006210999345057644
      },
      "anomaly_sidecar_ms": {
        "n": 259,
        "mean_ms": 6.8475470927865425,
        "p50_ms": 6.822072000431945,
        "p95_ms": 7.081241300875263,
        "p99_ms": 7.232737560661917,
        "max_ms": 7.285675999810337
      },
      "model_service_total_ms": {
        "n": 259,
        "mean_ms": 14.152835984592127,
        "p50_ms": 11.514619000081439,
        "p95_ms": 28.268825699160516,
        "p99_ms": 50.63726505952217,
        "max_ms": 64.91669599927263
      },
      "deterministic_medium_investigation_ms": {
        "n": 259,
        "mean_ms": 0.09786381843594455,
        "p50_ms": 0.09679100003268104,
        "p95_ms": 0.11407909987610765,
        "p99_ms": 0.11974102020758437,
        "max_ms": 0.13084300007903948
      },
      "activity_state_update_ms": {
        "n": 259,
        "mean_ms": 0.012416077261571736,
        "p50_ms": 0.012302998584345914,
        "p95_ms": 0.015797099331393838,
        "p99_ms": 0.017571019998285916,
        "max_ms": 0.01862399949459359
      },
      "local_end_to_end_ms": {
        "n": 259,
        "mean_ms": 14.312091235546296,
        "p50_ms": 11.679162000291399,
        "p95_ms": 28.43165310077893,
        "p99_ms": 50.82025867955962,
        "max_ms": 65.11029600005713,
        "throughput_tx_per_second": 69.87099114602799,
        "throughput_label": "sequential single-process local throughput"
      }
    },
    "high": {
      "feature_store_lookup_ms": {
        "n": 1,
        "mean_ms": 0.020538000171654858,
        "p50_ms": 0.020538000171654858,
        "p95_ms": 0.020538000171654858,
        "p99_ms": 0.020538000171654858,
        "max_ms": 0.020538000171654858
      },
      "feature_assembly_ms": {
        "n": 1,
        "mean_ms": 0.020868999854428694,
        "p50_ms": 0.020868999854428694,
        "p95_ms": 0.020868999854428694,
        "p99_ms": 0.020868999854428694,
        "max_ms": 0.020868999854428694
      },
      "xgboost_predict_proba_ms": {
        "n": 1,
        "mean_ms": 1.5210140009003226,
        "p50_ms": 1.5210140009003226,
        "p95_ms": 1.5210140009003226,
        "p99_ms": 1.5210140009003226,
        "max_ms": 1.5210140009003226
      },
      "shap_explanation_ms": {
        "n": 1,
        "mean_ms": 2.704991000427981,
        "p50_ms": 2.704991000427981,
        "p95_ms": 2.704991000427981,
        "p99_ms": 2.704991000427981,
        "max_ms": 2.704991000427981
      },
      "calibration_and_routing_ms": {
        "n": 1,
        "mean_ms": 0.003746999936993234,
        "p50_ms": 0.003746999936993234,
        "p95_ms": 0.003746999936993234,
        "p99_ms": 0.003746999936993234,
        "max_ms": 0.003746999936993234
      },
      "anomaly_sidecar_ms": {
        "n": 1,
        "mean_ms": 6.8601539987867,
        "p50_ms": 6.8601539987867,
        "p95_ms": 6.8601539987867,
        "p99_ms": 6.8601539987867,
        "max_ms": 6.8601539987867
      },
      "model_service_total_ms": {
        "n": 1,
        "mean_ms": 11.423028001445346,
        "p50_ms": 11.423028001445346,
        "p95_ms": 11.423028001445346,
        "p99_ms": 11.423028001445346,
        "max_ms": 11.423028001445346
      },
      "deterministic_medium_investigation_ms": {
        "n": 0,
        "mean_ms": null,
        "p50_ms": null,
        "p95_ms": null,
        "p99_ms": null,
        "max_ms": null
      },
      "activity_state_update_ms": {
        "n": 1,
        "mean_ms": 0.01681100002315361,
        "p50_ms": 0.01681100002315361,
        "p95_ms": 0.01681100002315361,
        "p99_ms": 0.01681100002315361,
        "max_ms": 0.01681100002315361
      },
      "local_end_to_end_ms": {
        "n": 1,
        "mean_ms": 11.48601600107213,
        "p50_ms": 11.48601600107213,
        "p95_ms": 11.48601600107213,
        "p99_ms": 11.48601600107213,
        "max_ms": 11.48601600107213,
        "throughput_tx_per_second": 87.06238959676338,
        "throughput_label": "sequential single-process local throughput"
      }
    }
  },
  "high_route_note": "All high routes encountered before the stopping conditions were met are reported; n=1. No transactions were shuffled or fabricated.",
  "provenance": {
    "generated_at": "2026-10-10T16:56:07.448476+00:00",
    "git_commit": "8ad06aff01a5932d94436df9e34f7fca820c9fea",
    "git_dirty": true,
    "code_sha256": "6b75e946682fcd73812b33a3598e20316c90bb63befbe1832737e851db7ab80c",
    "code_file_sha256": {
      "scripts/run_b11_efficiency.py": "4f082675cfca2f3ccf4a58925e337d5d3940070dd327d3493ea5fccc57a98a65",
      "scripts/benchmark_latency.py": "b1f2fbf3248f68c34e21d696983499252ce34d3566ba7ba6d48a1cad18e9ddf5",
      "fraud_flow/pipeline.py": "8d6ae0f7cbf4d058c4826161ca62d60eb788f0169ebfe7d21e4037b29a034893",
      "fraud_flow/features.py": "83ddb3f634daed961a216ea1cac053aac38d2e6272e2db3fb5eba4fa385ad1a9",
      "fraud_flow/feature_store.py": "f524dd2e43a5aec7a161af2e642de4478c556d07f2abbcaf7b19c31a6cb8bd5e",
      "fraud_flow/research.py": "b4084e86b8657df99a87be403e3dba3324d6b688c1c53c6c30a608bd1c686a6a",
      "fraud_flow/anomaly.py": "722736ebd83a547b64c49d62dbbf4382cdca466672845e2b716dd5d037015a07",
      "fraud_flow/calibration.py": "7082e17e167761d36a2c681965d6b5a2cb0eef7c1694a8f4f7a6e89cea8e16dc",
      "fraud_flow/config.py": "7ff1a1597e21c700e96a56166115685c4f9db2c357fd664b7c6c4cd9b946a4e1"
    },
    "dataset_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "dataset_sha256": "437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498",
    "model_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/xgboost_fraud.json",
    "model_sha256": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
    "metadata_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/model_metadata.json",
    "metadata_sha256": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
    "anomaly_sidecar_sha256": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658",
    "evaluation_report_sha256": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
    "old_latency_report_sha256": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
    "protected_hashes_before": {
      "artifacts/models/xgboost_fraud.json": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
      "artifacts/models/model_metadata.json": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
      "artifacts/reports/evaluation_report.json": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
      "artifacts/reports/latency_report.json": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
      "artifacts/models/anomaly_sidecar.joblib": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658"
    },
    "protected_hashes_after": {
      "artifacts/models/xgboost_fraud.json": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
      "artifacts/models/model_metadata.json": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
      "artifacts/reports/evaluation_report.json": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
      "artifacts/reports/latency_report.json": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
      "artifacts/models/anomaly_sidecar.joblib": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658"
    },
    "benchmark_command": "'/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python' scripts/run_b11_efficiency.py --training-repetitions 3 --warmup 100 --min-measured 1000 --min-low 800 --min-medium 100 --min-high 1",
    "sample_count": 1332,
    "warmup_count": 100,
    "timing_boundary": "For each measured transaction, local_end_to_end_ms starts immediately before the in-memory FeatureStore lookup and stops immediately after activity-only state update. It includes feature lookup, feature assembly, one-row DataFrame construction, raw XGBoost predict_proba, TreeSHAP explanation, calibration/routing, anomaly-sidecar scoring, deterministic offline investigation replay for medium routes, and observe_activity. Event parsing, dataset loading, model/explainer loading, training, external LLM/API calls, Redis, network, logging, and concurrency are outside this boundary.",
    "machine_environment": {
      "cpu_model": "AMD Ryzen 7 7435HS",
      "physical_cores": 8,
      "logical_cores": 16,
      "ram_total_bytes": 16433221632,
      "ram_total_gib": 15.304630279541016,
      "operating_system": "Linux-6.17.0-20-generic-x86_64-with-glibc2.39",
      "python_version": "3.12.3",
      "python_executable": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python",
      "packages": {
        "xgboost": "3.2.0",
        "scikit-learn": "1.8.0",
        "pandas": "2.2.3",
        "numpy": "2.2.5",
        "shap": "0.51.0"
      },
      "gpu": {
        "available": true,
        "devices": [
          "NVIDIA GeForce RTX 4050 Laptop GPU"
        ],
        "detection": "nvidia-smi query"
      },
      "xgboost_benchmark_device": "CPU; tree_method=hist and no device=cuda parameter",
      "redis_mode": "not used; in-memory FeatureStore; Redis/network overhead excluded",
      "external_llm_backend_configured": false,
      "external_llm_react_latency": "NOT MEASURED",
      "external_llm_reason": "External network/API execution was excluded to avoid dependency and cost.",
      "clock": "time.perf_counter"
    }
  }
}
````

Nguồn: `artifacts/reports/b11_final/b11_training_time.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "schema_version": "b11-fixed-training-time-v1",
  "description": "fixed-configuration model fitting time; not full hyperparameter-search time",
  "source": "PaySim",
  "split": {
    "total_rows": 460394,
    "train_rows": 322275,
    "validation_rows": 69059,
    "test_rows": 69060,
    "train_end": 322275,
    "val_end": 391334
  },
  "train_rows": 322275,
  "feature_count": 25,
  "feature_columns": [
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
    "llm_risk_score",
    "llm_reason_count",
    "llm_high_risk_flag",
    "llm_review_flag",
    "llm_category_hash"
  ],
  "class_balance": {
    "positive_count": 429,
    "negative_count": 321846,
    "scale_pos_weight": 750.2237762237762
  },
  "fixed_parameters": {
    "n_estimators": 260,
    "max_depth": 6,
    "learning_rate": 0.06,
    "subsample": 0.9,
    "colsample_bytree": 0.85,
    "max_delta_step": 1,
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 4,
    "scale_pos_weight": 750.2237762237762
  },
  "repetitions": 3,
  "timing_boundary": "time.perf_counter immediately before and after temporary_model.fit(X_train, y_train)",
  "timing": {
    "individual_seconds": [
      1.823165555999367,
      1.586516784998821,
      1.5975049919998128
    ],
    "mean_seconds": 1.669062444332667,
    "median_seconds": 1.5975049919998128,
    "min_seconds": 1.586516784998821,
    "max_seconds": 1.823165555999367
  },
  "temporary_models_saved": false,
  "candidate_search": false,
  "provenance": {
    "generated_at": "2026-10-10T16:56:07.448476+00:00",
    "git_commit": "8ad06aff01a5932d94436df9e34f7fca820c9fea",
    "git_dirty": true,
    "code_sha256": "6b75e946682fcd73812b33a3598e20316c90bb63befbe1832737e851db7ab80c",
    "code_file_sha256": {
      "scripts/run_b11_efficiency.py": "4f082675cfca2f3ccf4a58925e337d5d3940070dd327d3493ea5fccc57a98a65",
      "scripts/benchmark_latency.py": "b1f2fbf3248f68c34e21d696983499252ce34d3566ba7ba6d48a1cad18e9ddf5",
      "fraud_flow/pipeline.py": "8d6ae0f7cbf4d058c4826161ca62d60eb788f0169ebfe7d21e4037b29a034893",
      "fraud_flow/features.py": "83ddb3f634daed961a216ea1cac053aac38d2e6272e2db3fb5eba4fa385ad1a9",
      "fraud_flow/feature_store.py": "f524dd2e43a5aec7a161af2e642de4478c556d07f2abbcaf7b19c31a6cb8bd5e",
      "fraud_flow/research.py": "b4084e86b8657df99a87be403e3dba3324d6b688c1c53c6c30a608bd1c686a6a",
      "fraud_flow/anomaly.py": "722736ebd83a547b64c49d62dbbf4382cdca466672845e2b716dd5d037015a07",
      "fraud_flow/calibration.py": "7082e17e167761d36a2c681965d6b5a2cb0eef7c1694a8f4f7a6e89cea8e16dc",
      "fraud_flow/config.py": "7ff1a1597e21c700e96a56166115685c4f9db2c357fd664b7c6c4cd9b946a4e1"
    },
    "dataset_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
    "dataset_sha256": "437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498",
    "model_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/xgboost_fraud.json",
    "model_sha256": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
    "metadata_path": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/model_metadata.json",
    "metadata_sha256": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
    "anomaly_sidecar_sha256": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658",
    "evaluation_report_sha256": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
    "old_latency_report_sha256": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
    "protected_hashes_before": {
      "artifacts/models/xgboost_fraud.json": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
      "artifacts/models/model_metadata.json": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
      "artifacts/reports/evaluation_report.json": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
      "artifacts/reports/latency_report.json": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
      "artifacts/models/anomaly_sidecar.joblib": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658"
    },
    "protected_hashes_after": {
      "artifacts/models/xgboost_fraud.json": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
      "artifacts/models/model_metadata.json": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2",
      "artifacts/reports/evaluation_report.json": "b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4",
      "artifacts/reports/latency_report.json": "15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345",
      "artifacts/models/anomaly_sidecar.joblib": "ac3cb88780dad0f81e0b029f88da94a83ca10deeb27be5115f04ef5c74690658"
    },
    "benchmark_command": "'/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python' scripts/run_b11_efficiency.py --training-repetitions 3 --warmup 100 --min-measured 1000 --min-low 800 --min-medium 100 --min-high 1",
    "sample_count": 1332,
    "warmup_count": 100,
    "timing_boundary": "For each measured transaction, local_end_to_end_ms starts immediately before the in-memory FeatureStore lookup and stops immediately after activity-only state update. It includes feature lookup, feature assembly, one-row DataFrame construction, raw XGBoost predict_proba, TreeSHAP explanation, calibration/routing, anomaly-sidecar scoring, deterministic offline investigation replay for medium routes, and observe_activity. Event parsing, dataset loading, model/explainer loading, training, external LLM/API calls, Redis, network, logging, and concurrency are outside this boundary.",
    "machine_environment": {
      "cpu_model": "AMD Ryzen 7 7435HS",
      "physical_cores": 8,
      "logical_cores": 16,
      "ram_total_bytes": 16433221632,
      "ram_total_gib": 15.304630279541016,
      "operating_system": "Linux-6.17.0-20-generic-x86_64-with-glibc2.39",
      "python_version": "3.12.3",
      "python_executable": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python",
      "packages": {
        "xgboost": "3.2.0",
        "scikit-learn": "1.8.0",
        "pandas": "2.2.3",
        "numpy": "2.2.5",
        "shap": "0.51.0"
      },
      "gpu": {
        "available": true,
        "devices": [
          "NVIDIA GeForce RTX 4050 Laptop GPU"
        ],
        "detection": "nvidia-smi query"
      },
      "xgboost_benchmark_device": "CPU; tree_method=hist and no device=cuda parameter",
      "redis_mode": "not used; in-memory FeatureStore; Redis/network overhead excluded",
      "external_llm_backend_configured": false,
      "external_llm_react_latency": "NOT MEASURED",
      "external_llm_reason": "External network/API execution was excluded to avoid dependency and cost.",
      "clock": "time.perf_counter"
    }
  }
}
````

Nguồn: `artifacts/reports/latency_report.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "description": "FraudFlow pipeline latency benchmark (post leakage fix)",
  "timestamp": "2026-04-15T16:05:55Z",
  "config": {
    "n_benchmark": 1000,
    "warmup": 100,
    "source": "paysim"
  },
  "route_distribution": {
    "low": 887,
    "medium": 113,
    "high": 0
  },
  "overall": {
    "n": 1000,
    "mean_ms": 35.716,
    "p50_ms": 35.795,
    "p95_ms": 44.463,
    "p99_ms": 51.546,
    "max_ms": 71.081,
    "throughput_tps": 28.0
  },
  "by_route": {
    "low": {
      "n": 887,
      "mean_ms": 35.757,
      "p50_ms": 35.802,
      "p95_ms": 44.512,
      "p99_ms": 51.959,
      "max_ms": 71.081,
      "throughput_tps": 28.0
    },
    "medium": {
      "n": 113,
      "mean_ms": 35.392,
      "p50_ms": 35.593,
      "p95_ms": 43.32,
      "p99_ms": 49.621,
      "max_ms": 51.281,
      "throughput_tps": 28.3
    },
    "high": {
      "n": 0,
      "note": "no samples"
    }
  }
}
````

## 2. Mục 2.5.8 và 2.6 — Môi trường thực nghiệm và thư viện

### 2.1. Toàn bộ requirements

Giữ nguyên cả chú thích và từng phiên bản thư viện. `requirements.txt` ghi tested on Python `3.13.2`, trong khi môi trường B11/B13 ghi Python `3.12.3`; đây là khác biệt đã được B13 ghi nhận, không tự sửa nội dung requirements.

Nguồn: `requirements.txt` — toàn bộ file; sao chép nguyên văn.

````text
# Python >= 3.11 required (tested on 3.13.2)
#
# NOTE: redislite (Linux/macOS only) is needed only for the online simulation
# commands (simulate, stream, serve). For train + research it is NOT required.
# On Windows, use WSL or provide REDIS_URL env var pointing to a Redis instance.

# Core ML
numpy==2.2.5
pandas==2.2.3
scikit-learn==1.8.0
xgboost==3.2.0
shap==0.51.0
scipy==1.17.1
joblib==1.5.3

# LangChain (heuristic agent -- no external LLM calls required)
langchain==1.2.13
langchain-core==1.2.23
langchain-community==0.4.1
langchain-classic==1.0.3

# API & validation
pydantic==2.12.5
fastapi==0.135.3
uvicorn==0.44.0
jinja2==3.1.6

# Redis client (required for online pipeline)
redis==7.4.0
redislite==6.2.912183  # Linux/macOS only; used by simulate/stream/serve when REDIS_URL is not set

# Testing
pytest==8.4.1
````

Nguồn: `requirements_locked.txt` — toàn bộ file; sao chép nguyên văn.

````text
aiohappyeyeballs==2.6.1
aiohttp==3.13.5
aiosignal==1.4.0
annotated-doc==0.0.4
annotated-types==0.7.0
anyio==4.13.0
attrs==26.1.0
certifi==2026.2.25
charset-normalizer==3.4.7
click==8.3.2
cloudpickle==3.1.2
dataclasses-json==0.6.7
fastapi==0.135.3
frozenlist==1.8.0
greenlet==3.4.0
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
httpx-sse==0.4.3
idna==3.11
iniconfig==2.3.0
Jinja2==3.1.6
joblib==1.5.3
jsonpatch==1.33
jsonpointer==3.1.1
langchain==1.2.13
langchain-classic==1.0.3
langchain-community==0.4.1
langchain-core==1.2.23
langchain-text-splitters==1.1.1
langgraph==1.1.6
langgraph-checkpoint==4.0.2
langgraph-prebuilt==1.0.10
langgraph-sdk==0.3.13
langsmith==0.7.32
llvmlite==0.47.0
MarkupSafe==3.0.3
marshmallow==3.26.2
multidict==6.7.1
mypy_extensions==1.1.0
numba==0.65.0
numpy==2.2.5
nvidia-nccl-cu12==2.29.7
orjson==3.11.8
ormsgpack==1.12.2
packaging==26.1
pandas==2.2.3
pluggy==1.6.0
propcache==0.4.1
psutil==7.2.2
pydantic==2.12.5
pydantic-settings==2.14.0
pydantic_core==2.41.5
Pygments==2.20.0
pytest==8.4.1
python-dateutil==2.9.0.post0
python-dotenv==1.2.2
pytz==2026.1.post1
PyYAML==6.0.3
redis==7.4.0
redislite==6.2.912183
requests==2.33.1
requests-toolbelt==1.0.0
scikit-learn==1.8.0
scipy==1.17.1
setuptools==82.0.1
shap==0.51.0
six==1.17.0
slicer==0.0.8
SQLAlchemy==2.0.49
starlette==1.0.0
tenacity==9.1.4
threadpoolctl==3.6.0
tqdm==4.67.3
typing-inspect==0.9.0
typing-inspection==0.4.2
typing_extensions==4.15.0
tzdata==2026.1
urllib3==2.6.3
uuid_utils==0.14.1
uvicorn==0.44.0
xgboost==3.2.0
xxhash==3.6.0
yarl==1.23.0
zstandard==0.25.0
````

### 2.2. Cấu hình phần cứng và bảng môi trường có sẵn

Không tìm thấy bảng cấu hình CPU/RAM/GPU/OS trong hai file `docs/REPORT_MO_HINH_PAYSIM.md` và `docs/BANG_KET_QUA_BAO_CAO.md`. Tìm thấy bảng trong `docs/experiments_setup.md` và dữ liệu môi trường trong báo cáo B11/B13:

- CPU AMD Ryzen 7 7435HS; 8 physical cores / 16 logical cores.
- Tài liệu setup ghi RAM 16 GB DDR5, NVMe SSD, Ubuntu 24.04 LTS (kernel 6.17). B11 ghi RAM `16433221632` bytes / `15.304630279541016` GiB và OS `Linux-6.17.0-20-generic-x86_64-with-glibc2.39`.
- GPU NVIDIA GeForce RTX 4050 Laptop GPU có sẵn; XGBoost benchmark dùng CPU. B13 ghi driver `580.126.09`.
- `redis==7.4.0` là phiên bản thư viện Python client; `redislite==6.2.912183` là phiên bản gói. Không tìm thấy phiên bản Redis server được ghi rõ trong các tài liệu/báo cáo đã rà soát; không coi hai phiên bản package trên là phiên bản server.

Bảng và metadata nguyên văn:

Nguồn: `docs/experiments_setup.md` — dòng 5–22; sao chép nguyên văn.

````markdown
### 4.1.1 Hardware

| Component | Specification |
|---|---|
| **CPU** | AMD Ryzen 7 7435HS (8 cores / 16 threads) |
| **RAM** | 16 GB DDR5 |
| **Storage** | NVMe SSD |
| **OS** | Ubuntu 24.04 LTS (kernel 6.17) |
| **Python** | 3.12.3 |
| **XGBoost** | 3.2.0 (tree_method="hist", n_jobs=4) |
| **scikit-learn** | 1.8.0 |
| **pandas** | 2.2.3 |
| **numpy** | 2.2.5 |

All experiments run on CPU only. No GPU acceleration. Training time ≈ 2–8 seconds per XGBoost run on the full PaySim dataset (460,394 rows).

---

````

Nguồn: `artifacts/reports/b11_final/b11_environment.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "schema_version": "b11-environment-v1",
  "generated_at": "2026-10-10T16:56:07.448476+00:00",
  "cpu_model": "AMD Ryzen 7 7435HS",
  "physical_cores": 8,
  "logical_cores": 16,
  "ram_total_bytes": 16433221632,
  "ram_total_gib": 15.304630279541016,
  "operating_system": "Linux-6.17.0-20-generic-x86_64-with-glibc2.39",
  "python_version": "3.12.3",
  "python_executable": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python",
  "packages": {
    "xgboost": "3.2.0",
    "scikit-learn": "1.8.0",
    "pandas": "2.2.3",
    "numpy": "2.2.5",
    "shap": "0.51.0"
  },
  "gpu": {
    "available": true,
    "devices": [
      "NVIDIA GeForce RTX 4050 Laptop GPU"
    ],
    "detection": "nvidia-smi query"
  },
  "xgboost_benchmark_device": "CPU; tree_method=hist and no device=cuda parameter",
  "redis_mode": "not used; in-memory FeatureStore; Redis/network overhead excluded",
  "external_llm_backend_configured": false,
  "external_llm_react_latency": "NOT MEASURED",
  "external_llm_reason": "External network/API execution was excluded to avoid dependency and cost.",
  "clock": "time.perf_counter",
  "benchmark_command": "'/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python' scripts/run_b11_efficiency.py --training-repetitions 3 --warmup 100 --min-measured 1000 --min-low 800 --min-medium 100 --min-high 1",
  "provenance_hashes": {
    "code_sha256": "6b75e946682fcd73812b33a3598e20316c90bb63befbe1832737e851db7ab80c",
    "dataset_sha256": "437a7d591b68460292d092b5bbf7f7ab9b432534e2a974f0d6413c029eb56498",
    "model_sha256": "bb162f4d671ed3c7d68d19fed888d87e4b86a2b1d6c337bfc2e6b0793f9f1ebf",
    "metadata_sha256": "accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2"
  }
}
````

Nguồn: `B13_IMPLEMENTATION_REVIEW/b13_environment.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "schema_version": "b13-implementation-settings-v1",
  "generated_at": "2026-10-11T13:12:25Z",
  "audit_scope": "Implementation and reproducibility settings only; no B1-B12 experiment was rerun and no model was retrained.",
  "evidence_priority": [
    "artifacts/reports/b11_final/b11_environment.json",
    "artifacts/reports/b11_final/B11_FINAL_AUDIT.md",
    "artifacts/reports/b12_final/*.json",
    "current repository code and lockfiles",
    "README and run guides, treated as secondary when they conflict with final artifacts"
  ],
  "final_environment": {
    "operating_system": "Linux-6.17.0-20-generic-x86_64-with-glibc2.39",
    "cpu_model": "AMD Ryzen 7 7435HS",
    "physical_cores": 8,
    "logical_cores": 16,
    "ram_total_bytes": 16433221632,
    "ram_total_gib": 15.304630279541016,
    "gpu": {
      "available": true,
      "device": "NVIDIA GeForce RTX 4050 Laptop GPU",
      "driver_version_observed_during_b13": "580.126.09",
      "actually_used_by_xgboost": false
    },
    "python_version": "3.12.3",
    "python_executable": "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection/.venv/bin/python",
    "confirmation": {
      "b11": "Exact environment is embedded in the final B11 artifact.",
      "b12": "B12 provenance records the same repository virtual-environment interpreter and was produced on the currently corroborated final host; its JSON does not independently embed an OS string.",
      "current_host": "OS, CPU, core counts, RAM, GPU and interpreter were corroborated read-only during B13."
    }
  },
  "xgboost_execution": {
    "version": "3.2.0",
    "tree_method": "hist",
    "n_jobs": 4,
    "device_parameter": null,
    "gpu_actually_used": false,
    "evidence": "B11 records CPU execution with tree_method=hist and no device=cuda; config.py and B9 final artifacts record n_jobs=4."
  },
  "random_seeds": {
    "main_production_seed": 42,
    "b9_robustness_seeds": [42, 43, 44]
  },
  "redis": {
    "production_full_online_pipeline_requires_redis": true,
    "local_research_benchmark_uses_redis": false,
    "b11_latency_includes_redis_or_network": false,
    "in_memory_feature_store": "fraud_flow.feature_store.FeatureStore; used by local research and B11 replay.",
    "redis_feature_store": "fraud_flow.feature_store.RedisFeatureStore; used by the full online FraudFlowRunner/API pipeline.",
    "embedded_server": "The CLI full online pipeline starts EmbeddedRedisServer when needed."
  },
  "external_llm": {
    "required_for_paysim_reported_classifier_results": false,
    "required_for_deterministic_medium_replay": false,
    "full_react_runtime_may_use_external_llm_api": true,
    "full_react_runtime_hard_requires_external_llm_api": false,
    "explanation": "The reported classifier and deterministic replay paths are local. Full ReAct can use an external OpenAI-compatible backend when the optional integration and API key are configured, but the code falls back to a local heuristic LLM.",
    "current_external_backend_configured_in_b11": false
  },
  "environment_conflicts": {
    "python": {
      "final_value": "3.12.3",
      "old_or_outdated_value": "3.13.2 in README.md, requirements.txt commentary, and notebook metadata",
      "value_to_use_in_paper": "Python 3.12.3 for the final B11/B12 artifact environment"
    },
    "operating_system": {
      "final_value": "Linux-6.17.0-20-generic-x86_64-with-glibc2.39",
      "old_or_outdated_value": "Windows 11 for train/research and WSL Ubuntu for full pipeline in README.md",
      "value_to_use_in_paper": "Linux 6.17.0-20-generic x86_64 (glibc 2.39) for the final B11/B12 execution environment"
    },
    "ram": {
      "final_value": "15.304630279541016 GiB OS-reported",
      "old_or_outdated_value": "16 GB marketing/rounded description",
      "value_to_use_in_paper": "16 GB installed (15.30 GiB OS-reported)"
    }
  },
  "provenance": {
    "git_commit": "8ad06aff01a5932d94436df9e34f7fca820c9fea",
    "git_dirty": true,
    "requirements_locked_sha256": "8182f237eea1f5d6c47f9a90cb62e716d03cfcb3269a65d1afd56995f06e5b8a",
    "requirements_sha256": "9310cdf2b00f5de15cc641e564350be1c6572af7660d818a08d9c50bd0304a95",
    "config_py_sha256": "7ff1a1597e21c700e96a56166115685c4f9db2c357fd664b7c6c4cd9b946a4e1",
    "run_fraud_flow_py_sha256": "14faa41106769946b5761fc9a0edec8db0ca879ec4fe740b14f3ca5e5a48746e",
    "b12_code_composite_sha256": "085e7c78d3114350bea597d0fbe50c0165228845c371cd14339920f91e0a76b3",
    "note": "The worktree was already dirty before B13 outputs were created; provenance must not be described as a clean checkout."
  },
  "execution_guardrails": {
    "model_retrained": false,
    "b1_b12_rerun": false,
    "manuscript_modified": false
  }
}
````

### 2.3. Kiểm tra tên bảng “Table 2”

`docs/report_content.md` có “Table 2: Feature Ablation — Test F1 Impact (XGBoost, seed=42)”, là bảng ablation, không phải bảng môi trường. Thư phản hồi B15 nhắc Table 2 của bản thảo `XPayFraDet_B14_Final.docx` là vị trí mô tả môi trường; đoạn nhắc này được giữ nguyên dưới đây. Bảng môi trường thực tế tìm thấy trong Markdown đã trích tại mục 2.2, không tự đổi số bảng của nguồn.

Nguồn: `B15_TECHNICAL_RESPONSE/B15_TECHNICAL_RESPONSE_LETTER.md` — dòng 228–245; sao chép nguyên văn.

````markdown
## TR-13 – Implementation and reproducibility settings

**Reviewer/Editor:** Editor; identity not specified in the source note.

**Comment / Technical issue:** Verbatim editor comment as recorded in `B13_Final_100pct_Verification_and_Response.md`: “Please provide complete implementation settings, including Python and package versions, operating system, hardware, Redis requirements, and exact commands needed to reproduce the experiments.”

**Response:** Thank you for this request. The final audited environment is Linux 6.17.0-20-generic x86_64 with Python 3.12.3 on an AMD Ryzen 7 7435HS system with 16 GB installed RAM. An NVIDIA RTX 4050 was present but not used by XGBoost. The reported model uses XGBoost 3.2.0 on CPU with `tree_method=hist` and `n_jobs=4`. The revised reproducibility description distinguishes execution paths: the full online pipeline requires Redis/`RedisFeatureStore`, whereas research and the B11 benchmark use the in-memory `FeatureStore`. The reported classifier results and deterministic medium replay do not require an external LLM; a full ReAct runtime may use an external backend when configured, but no external-LLM performance is reported.

**Changes made:** The final OS, interpreter, CPU/RAM/GPU boundary, XGBoost execution settings, locked software stack, Redis distinction, external-LLM boundary, and exact repository entry points were added.

**Location in revised manuscript:** Section 3.7.1; Table 2; Section 3.7.6.  
Page: `[to be inserted after final layout]`  
Line: `[to be inserted after final layout]`

**Evidence / artifact:** B14 SOT, Section 14 (`B13_IMPLEMENTATION_REVIEW/b13_environment.json` lineage); `XPayFraDet_B14_Final.docx`, Section 3.7.1, Table 2, Section 3.7.6.

**Status:** ADDRESSED

````

## 3. Mục 3.3.4 — Toàn văn 3 case study điển hình

Khối sau sao chép 100% nội dung `docs/CASE_STUDY_3_GIAO_DICH.md`, bao gồm mọi bảng, số liệu và phần diễn giải. Các score và ví dụ thuộc tài liệu case study gốc, không suy diễn rằng chúng lấy từ đợt mô phỏng 5000 đang được báo cáo.

Nguồn: `docs/CASE_STUDY_3_GIAO_DICH.md` — toàn bộ file; sao chép nguyên văn.

````markdown
# Case Study 3 Giao Dịch

File này chọn 3 giao dịch đại diện cho 3 nhánh trong luồng mới:
- `low` -> tự động approve
- `medium` -> đưa qua agent để review
- `high` -> tự động block

## 1. Tóm tắt nhanh

| Case | Tx ID | Loại giao dịch | Số tiền | Score | Route | Kết quả cuối | Nhãn thật |
|---|---|---|---:|---:|---|---|---:|
| Case 1 | `tx_0102000` | CASH_OUT | 194,026.15 | 0.000003 | Low | Approve | 0 |
| Case 2 | `tx_0025517` | TRANSFER | 564,314.98 | 0.428375 | Medium | Review | 0 |
| Case 3 | `tx_0106432` | TRANSFER | 2,093,951.47 | 0.999983 | High | Block | 1 |

## 2. Case 1: Low-risk -> Auto Approve

### Thông tin giao dịch

| Trường | Giá trị |
|---|---|
| Tx ID | `tx_0102000` |
| Thời điểm | `2025-01-01T14:00:00` |
| Loại | `CASH_OUT` |
| Số tiền | `194,026.15` |
| Device | `device_12869` |
| Location | `zone_014` |
| Nhãn thật | `0` |

### Lookup online

| Đặc trưng lookup | Giá trị |
|---|---:|
| `tx_count_24h` | 0 |
| `device_tx_count_24h` | 3 |
| `location_tx_count_24h` | 467 |
| `merchant_tx_count_24h` | 8 |
| `location_fraud_rate` | 0.004283 |
| `ip_fraud_rate` | 0.000000 |
| `merchant_fraud_rate` | 0.000000 |

### Giải thích mô hình

Top 3 đặc trưng có tác động mạnh nhất:

| Thứ hạng | Đặc trưng | Tác động SHAP |
|---|---|---:|
| 1 | `balance_diff` | -5.0252 |
| 2 | `oldbalanceDest` | -1.4955 |
| 3 | `location_tx_count_24h` | -1.4597 |

### Quyết định cuối

- Score rất thấp: `0.000003`
- Route: `low`
- Action: `approve`
- Ghi chú hệ thống: giao dịch được thông qua tự động, không tốn chi phí agent/LLM

### Diễn giải

Đây là một giao dịch nằm trong vùng rủi ro rất thấp:
- không có dấu hiệu bất thường mạnh ở lookup online
- top SHAP đều kéo score xuống
- hệ thống xử lý đúng theo triết lý tối ưu chi phí: `low` thì không gọi agent

## 3. Case 2: Medium-risk -> ReAct Agent giữ lại để review

### Thông tin giao dịch

| Trường | Giá trị |
|---|---|
| Tx ID | `tx_0025517` |
| Thời điểm | `2025-01-01T09:00:00` |
| Loại | `TRANSFER` |
| Số tiền | `564,314.98` |
| Device | `device_17601` |
| Location | `zone_118` |
| Nhãn gốc trong log | `0` |

### Tín hiệu từ mô hình

| Chỉ số | Giá trị |
|---|---:|
| Score | 0.428375 |
| Route | `medium` |
| Latency | 21.84 ms |

Top 3 đặc trưng có ảnh hưởng mạnh:

| Thứ hạng | Đặc trưng | Tác động SHAP |
|---|---|---:|
| 1 | `amount_ratio` | -3.5148 |
| 2 | `newbalanceOrig` | -1.9711 |
| 3 | `balance_diff` | -1.8693 |

### Tool mà agent đã gọi

| Tool | Kết quả chính |
|---|---|
| `get_card_history` | Không có lịch sử 24h, chưa có lịch sử gian lận |
| `verify_device_id` | Thiết bị mới, cần step-up verification |
| `query_merchant_risk` | Merchant chưa có lịch sử rủi ro đáng kể |

### Kết quả agent

| Thuộc tính | Giá trị |
|---|---|
| Recommended action | `review` |
| Confidence | `0.5784` |
| Reason codes | `device_step_up`, `new_device` |

Evidence chính:
- thiết bị chưa có giao dịch trước đó trong cửa sổ 24h
- tool xác nhận `needs_step_up = true`
- mô hình chưa đủ mạnh để auto-block, nhưng cũng chưa đủ an toàn để auto-approve

### Quyết định cuối

- Route: `medium`
- Action: `review`
- Reviewer note: giữ giao dịch để xác minh thêm

### Diễn giải

Case này thể hiện đúng vai trò của nhánh `medium`:
- mô hình lõi chưa đẩy lên `high`
- nhưng thông tin về thiết bị mới khiến hệ thống không cho approve ngay
- agent bổ sung tầng giải thích và đưa giao dịch sang review có kiểm soát

## 4. Case 3: High-risk -> Auto Block

### Thông tin giao dịch

| Trường | Giá trị |
|---|---|
| Tx ID | `tx_0106432` |
| Thời điểm | `2025-01-01T14:00:00` |
| Loại | `TRANSFER` |
| Số tiền | `2,093,951.47` |
| Device | `device_12732` |
| Location | `zone_113` |
| Nhãn thật | `1` |

### Lookup online

| Đặc trưng lookup | Giá trị |
|---|---:|
| `tx_count_24h` | 0 |
| `device_tx_count_24h` | 8 |
| `location_tx_count_24h` | 555 |
| `merchant_tx_count_24h` | 0 |
| `location_fraud_rate` | 0.000000 |
| `ip_fraud_rate` | 0.000000 |
| `merchant_fraud_rate` | 0.000000 |

### Giải thích mô hình

| Thứ hạng | Đặc trưng | Tác động SHAP |
|---|---|---:|
| 1 | `balance_diff` | 5.6282 |
| 2 | `amount_log1p` | 1.3199 |
| 3 | `org_balance_delta_ratio` | 0.8511 |

Monitoring flag:
- `device_shift`

### Quyết định cuối

- Raw probability: `0.999983`
- Route: `high`
- Action: `block`
- Ghi chú hệ thống: chặn ngay và lưu explanation log bất đồng bộ
- Kết quả thực tế: nhãn thật là `fraud`

### Diễn giải

Đây là case tiêu biểu cho khả năng phát hiện gian lận của mô hình:
- số tiền rất lớn
- biến động balance rất mạnh
- score gần như tuyệt đối
- hệ thống chặn ngay mà không cần qua agent
- quyết định cuối khớp với nhãn thật

## 5. Kết luận từ 3 case study

Ba case trên minh họa đúng triết lý thiết kế của mô hình mới:
- `low`: tối ưu tốc độ và chi phí
- `medium`: thêm lớp điều tra và giải thích
- `high`: ưu tiên an toàn, chặn tức thì

Khi trình bày trong báo cáo hoặc slide, bạn có thể dùng đúng 3 case này để minh họa toàn bộ luồng hệ thống mà không cần giải thích lại code.
````

## 4. Mục 24 — Tài liệu tham khảo và phụ lục

### 4.1. Mẫu 10 dòng log thực tế trong repository

Mỗi bản ghi dưới đây là một dòng JSONL nguyên vẹn, không cắt bớt trường và không chuyển thành JSON nhiều dòng. Mẫu gồm 4 prediction (low, medium/review, medium/step_up, high), 2 manual review queue, 2 feedback, 1 high-risk async và 1 drift alert. Đây là log thực tế do phần mềm lưu trong repository, không phải khẳng định dữ liệu giao dịch ngân hàng thực; các event mẫu có nguồn PaySim. Không coi các mẫu từ các file khác nhau là cùng một lần chạy hoặc cùng giao dịch.

#### Log 1 — medium/review

Nguồn: `artifacts/logs/predictions.jsonl`, dòng `1`.

````jsonl
{"event": {"tx_id": "tx_0454957", "step": 93, "timestamp": "2025-01-04T21:00:00", "tx_type": "CASH_OUT", "amount": 188149.04, "card_id": "C1468286929", "merchant_id": "merchant_27982", "device_id": "device_01297", "ip_address": "10.236.210.218", "location_id": "zone_058", "oldbalanceOrg": 0.0, "newbalanceOrig": 0.0, "oldbalanceDest": 440232.11, "newbalanceDest": 628381.15, "is_fraud": 0, "is_flagged_fraud": 0, "extras": {"source": "paysim"}}, "lookup": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "device_tx_count_24h": 0, "location_tx_count_24h": 3, "merchant_tx_count_24h": 0, "location_fraud_rate": 0.001982, "ip_fraud_rate": 0.0, "merchant_fraud_rate": 0.0}, "prediction": {"score": 0.321412, "raw_probability": 0.00010337324056308717, "route": "medium", "explanation": [{"feature": "balance_diff", "impact": -4.495396614074707, "weight": 1.0}, {"feature": "oldbalanceDest", "impact": -2.7490456104278564, "weight": 0.6115}, {"feature": "amount_log1p", "impact": -0.9312873482704163, "weight": 0.2072}], "latency_ms": 14.328198999464803}, "final_action": "review", "final_note": "Tác tử điều tra tạm giữ giao dịch để analyst xác minh thêm.", "agent": {"action": "review", "reviewer_note": "Tác tử điều tra tạm giữ giao dịch để analyst xác minh thêm.", "tool_results": {"verify_device_id": {"device_tx_count_24h": 0, "historical_tx_count": 23, "labeled_tx_count": 19, "historical_fraud_rate": 0.0, "is_new_device": false, "needs_step_up": true, "tool": "verify_device_id"}, "query_merchant_risk": {"merchant_tx_count_24h": 0, "historical_tx_count": 8, "labeled_tx_count": 5, "historical_fraud_count": 0, "merchant_fraud_rate": 0.0, "tool": "query_merchant_risk"}}, "agent_output": {"structured_output": {"recommended_action": "review", "confidence": 0.4714, "summary": "Tools completed; consolidating evidence.", "reason_codes": ["device_step_up", "new_device"], "evidence": ["Device has no prior transactions in the 24h window.", "Device verification suggests step-up authentication.", "SHAP signal: balance_diff impact -4.4954.", "SHAP signal: oldbalanceDest impact -2.7490.", "SHAP signal: amount_log1p impact -0.9313."], "human_readable_explanation": "Giao dịch tx_0454957 (CASH_OUT, 188,149.04) nằm ở vùng rủi ro trung gian với score 0.321412, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: thiết bị cần step-up verification, thiết bị mới chưa có lịch sử. Tín hiệu từ feature store: Thiết bị hiện tại chưa có lịch sử giao dịch trong 24 giờ gần nhất. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-4.4954). số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.7490). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0454957: route=medium, final_action=review, score=0.321412. Loại giao dịch: CASH_OUT; số tiền: 188,149.04. Reason codes: thiết bị cần step-up verification, thiết bị mới chưa có lịch sử. Evidence: Device has no prior transactions in the 24h window. | Device verification suggests step-up authentication. | SHAP signal: balance_diff impact -4.4954.", "dashboard_summary": "tx_0454957: MEDIUM -> REVIEW | CASH_OUT 188,149.04 | score 0.321"}, "agent_summary": "Tools completed; consolidating evidence.", "intermediate_steps": [{"tool": "verify_device_id", "tool_input": "device_01297", "observation": {"device_tx_count_24h": 0, "historical_tx_count": 23, "labeled_tx_count": 19, "historical_fraud_rate": 0.0, "is_new_device": false, "needs_step_up": true, "tool": "verify_device_id"}}, {"tool": "query_merchant_risk", "tool_input": "merchant_27982", "observation": {"merchant_tx_count_24h": 0, "historical_tx_count": 8, "labeled_tx_count": 5, "historical_fraud_count": 0, "merchant_fraud_rate": 0.0, "tool": "query_merchant_risk"}}]}, "validation_attempts": 1, "fallback_used": false, "human_readable_explanation": "Giao dịch tx_0454957 (CASH_OUT, 188,149.04) nằm ở vùng rủi ro trung gian với score 0.321412, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: thiết bị cần step-up verification, thiết bị mới chưa có lịch sử. Tín hiệu từ feature store: Thiết bị hiện tại chưa có lịch sử giao dịch trong 24 giờ gần nhất. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-4.4954). số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.7490). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0454957: route=medium, final_action=review, score=0.321412. Loại giao dịch: CASH_OUT; số tiền: 188,149.04. Reason codes: thiết bị cần step-up verification, thiết bị mới chưa có lịch sử. Evidence: Device has no prior transactions in the 24h window. | Device verification suggests step-up authentication. | SHAP signal: balance_diff impact -4.4954.", "dashboard_summary": "tx_0454957: MEDIUM -> REVIEW | CASH_OUT 188,149.04 | score 0.321"}, "narrative": {"human_readable_explanation": "Giao dịch tx_0454957 (CASH_OUT, 188,149.04) nằm ở vùng rủi ro trung gian với score 0.321412, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: thiết bị cần step-up verification, thiết bị mới chưa có lịch sử. Tín hiệu từ feature store: Thiết bị hiện tại chưa có lịch sử giao dịch trong 24 giờ gần nhất. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-4.4954). số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.7490). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0454957: route=medium, final_action=review, score=0.321412. Loại giao dịch: CASH_OUT; số tiền: 188,149.04. Reason codes: thiết bị cần step-up verification, thiết bị mới chưa có lịch sử. Evidence: Device has no prior transactions in the 24h window. | Device verification suggests step-up authentication. | SHAP signal: balance_diff impact -4.4954.", "dashboard_summary": "tx_0454957: MEDIUM -> REVIEW | CASH_OUT 188,149.04 | score 0.321"}, "actual_label": 0, "correct": true, "feedback_logged": true, "end_to_end_latency_ms": 43.37094699985755, "monitoring_flags": ["device_shift"]}
````

#### Log 2 — low

Nguồn: `artifacts/logs/predictions.jsonl`, dòng `2`.

````jsonl
{"event": {"tx_id": "tx_0454958", "step": 93, "timestamp": "2025-01-04T21:00:00", "tx_type": "CASH_OUT", "amount": 387564.47, "card_id": "C1094179993", "merchant_id": "merchant_15758", "device_id": "device_13882", "ip_address": "10.35.201.218", "location_id": "zone_193", "oldbalanceOrg": 0.0, "newbalanceOrig": 0.0, "oldbalanceDest": 764054.29, "newbalanceDest": 1151618.76, "is_fraud": 0, "is_flagged_fraud": 0, "extras": {"source": "paysim"}}, "lookup": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "device_tx_count_24h": 0, "location_tx_count_24h": 2, "merchant_tx_count_24h": 0, "location_fraud_rate": 0.002427, "ip_fraud_rate": 0.111111, "merchant_fraud_rate": 0.0}, "prediction": {"score": 0.155041, "raw_probability": 4.7029599954839796e-05, "route": "low", "explanation": [{"feature": "balance_diff", "impact": -5.328797817230225, "weight": 1.0}, {"feature": "oldbalanceDest", "impact": -2.4003121852874756, "weight": 0.4504}, {"feature": "org_balance_delta_ratio", "impact": -1.0841565132141113, "weight": 0.2035}], "latency_ms": 14.938020999579749}, "final_action": "approve", "final_note": "Nhánh low-risk: giao dịch được thông qua tự động để tối ưu tốc độ và chi phí xử lý.", "agent": null, "narrative": {"human_readable_explanation": "Giao dịch tx_0454958 (CASH_OUT, 387,564.47) được xếp vào vùng rủi ro thấp với score 0.155041, nên hệ thống tự động thông qua. Tín hiệu từ feature store: Thiết bị hiện tại chưa có lịch sử giao dịch trong 24 giờ gần nhất. IP đang có tỷ lệ fraud khoảng 11.11%. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-5.3288). số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.4003). Nhánh low-risk: giao dịch được thông qua tự động để tối ưu tốc độ và chi phí xử lý.", "analyst_report": "Tx tx_0454958: route=low, final_action=approve, score=0.155041. Loại giao dịch: CASH_OUT; số tiền: 387,564.47. Model signals: độ lệch biến động số dư đang giảm điểm rủi ro (-5.3288). | số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.4003). | tỷ lệ thay đổi số dư tài khoản nguồn đang giảm điểm rủi ro (-1.0842).", "dashboard_summary": "tx_0454958: LOW -> APPROVE | CASH_OUT 387,564.47 | score 0.155"}, "actual_label": 0, "correct": true, "feedback_logged": true, "end_to_end_latency_ms": 24.165437999727146, "monitoring_flags": ["device_shift"]}
````

#### Log 3 — high

Nguồn: `artifacts/logs/predictions.jsonl`, dòng `192`.

````jsonl
{"event": {"tx_id": "tx_0455148", "step": 93, "timestamp": "2025-01-04T21:00:00", "tx_type": "TRANSFER", "amount": 4120.14, "card_id": "C2002472710", "merchant_id": "merchant_05346", "device_id": "device_16643", "ip_address": "10.83.26.90", "location_id": "zone_077", "oldbalanceOrg": 4120.14, "newbalanceOrig": 0.0, "oldbalanceDest": 0.0, "newbalanceDest": 0.0, "is_fraud": 1, "is_flagged_fraud": 0, "extras": {"source": "paysim"}}, "lookup": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "device_tx_count_24h": 0, "location_tx_count_24h": 6, "merchant_tx_count_24h": 0, "location_fraud_rate": 0.002209, "ip_fraud_rate": 0.0, "merchant_fraud_rate": 0.0}, "prediction": {"score": 0.999, "raw_probability": 0.999815046787262, "route": "high", "explanation": [{"feature": "balance_diff", "impact": 6.0164103507995605, "weight": 1.0}, {"feature": "llm_risk_score", "impact": 1.3229434490203857, "weight": 0.2199}, {"feature": "org_balance_delta_ratio", "impact": 0.9501742124557495, "weight": 0.1579}], "latency_ms": 18.05630899980315}, "final_action": "block", "final_note": "Nhánh high-risk: giao dịch bị chặn ngay lập tức và được ghi lại để hậu kiểm bất đồng bộ.", "agent": null, "narrative": {"human_readable_explanation": "Giao dịch tx_0455148 (TRANSFER, 4,120.14) rơi vào vùng rủi ro cao với score 0.999000, nên hệ thống chặn ngay để bảo toàn an toàn giao dịch. Tín hiệu từ feature store: Thiết bị hiện tại chưa có lịch sử giao dịch trong 24 giờ gần nhất. Tín hiệu từ mô hình: độ lệch biến động số dư đang tăng điểm rủi ro (+6.0164). điểm phân tích rủi ro kiểu LLM đang tăng điểm rủi ro (+1.3229). Nhánh high-risk: giao dịch bị chặn ngay lập tức và được ghi lại để hậu kiểm bất đồng bộ.", "analyst_report": "Tx tx_0455148: route=high, final_action=block, score=0.999000. Loại giao dịch: TRANSFER; số tiền: 4,120.14. Model signals: độ lệch biến động số dư đang tăng điểm rủi ro (+6.0164). | điểm phân tích rủi ro kiểu LLM đang tăng điểm rủi ro (+1.3229). | tỷ lệ thay đổi số dư tài khoản nguồn đang tăng điểm rủi ro (+0.9502).", "dashboard_summary": "tx_0455148: HIGH -> BLOCK | TRANSFER 4,120.14 | score 0.999"}, "actual_label": 1, "correct": true, "feedback_logged": true, "end_to_end_latency_ms": 31.162235999545373, "monitoring_flags": ["amount_shift", "device_shift"]}
````

#### Log 4 — medium/step_up

Nguồn: `artifacts/logs/predictions.jsonl`, dòng `27775`.

````jsonl
{"event": {"tx_id": "tx_0393104", "step": 42, "timestamp": "2025-01-02T18:00:00", "tx_type": "TRANSFER", "amount": 3022217.98, "card_id": "C888823828", "merchant_id": "merchant_47632", "device_id": "device_03257", "ip_address": "10.198.239.90", "location_id": "zone_028", "oldbalanceOrg": 0.0, "newbalanceOrig": 0.0, "oldbalanceDest": 5150110.56, "newbalanceDest": 8172328.54, "is_fraud": 0, "is_flagged_fraud": 0, "extras": {"source": "paysim"}}, "lookup": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "device_tx_count_24h": 9, "location_tx_count_24h": 1037, "merchant_tx_count_24h": 6, "location_fraud_rate": 0.002312, "ip_fraud_rate": 0.0, "merchant_fraud_rate": 0.0}, "prediction": {"score": 0.343692, "raw_probability": 0.00011624676699284464, "route": "medium", "explanation": [{"feature": "balance_diff", "impact": -2.886601448059082, "weight": 1.0}, {"feature": "oldbalanceDest", "impact": -2.727354049682617, "weight": 0.9448}, {"feature": "llm_risk_score", "impact": -2.2126033306121826, "weight": 0.7665}], "latency_ms": 30.770267999969292, "anomaly_score": 0.813297, "anomaly_flag": true}, "final_action": "step_up", "final_note": "Anomaly sidecar phát hiện giao dịch lệch chuẩn phân bố (anomaly_score=0.813). Cần xác minh tăng cường — chưa xác nhận là gian lận.", "agent": {"action": "approve", "reviewer_note": "Tác tử điều tra xác nhận có thể thông qua giao dịch sau khi rà soát các bằng chứng từ tool.", "tool_results": {"get_card_history": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "historical_tx_count": 0, "labeled_tx_count": 0, "historical_fraud_count": 0, "historical_fraud_rate": 0.0, "tool": "get_card_history"}}, "agent_output": {"structured_output": {"recommended_action": "approve", "confidence": 0.4937, "summary": "Tools completed; consolidating evidence.", "reason_codes": ["medium_branch_review", "anomaly_high_score"], "evidence": ["SHAP signal: balance_diff impact -2.8866.", "SHAP signal: oldbalanceDest impact -2.7274.", "SHAP signal: llm_risk_score impact -2.2126."], "human_readable_explanation": "Giao dịch tx_0393104 (TRANSFER, 3,022,217.98) nằm ở vùng rủi ro trung gian với score 0.343692, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: giao dịch nằm trong vùng cần đánh giá thêm, điểm bất thường vượt ngưỡng cảnh báo của anomaly sidecar. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-2.8866). số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.7274). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0393104: route=medium, final_action=approve, score=0.343692. Loại giao dịch: TRANSFER; số tiền: 3,022,217.98. Anomaly score: 0.8133 | Flagged: True. [transaction_risk] giao dịch nằm trong vùng cần đánh giá thêm. [anomaly_risk] điểm bất thường vượt ngưỡng cảnh báo của anomaly sidecar. Evidence: SHAP signal: balance_diff impact -2.8866. | SHAP signal: oldbalanceDest impact -2.7274. | SHAP signal: llm_risk_score impact -2.2126.", "dashboard_summary": "tx_0393104: MEDIUM -> APPROVE | TRANSFER 3,022,217.98 | score 0.344 | anomaly 0.813⚠"}, "agent_summary": "Tools completed; consolidating evidence.", "intermediate_steps": [{"tool": "get_card_history", "tool_input": "C888823828", "observation": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "historical_tx_count": 0, "labeled_tx_count": 0, "historical_fraud_count": 0, "historical_fraud_rate": 0.0, "tool": "get_card_history"}}]}, "validation_attempts": 1, "fallback_used": false, "human_readable_explanation": "Giao dịch tx_0393104 (TRANSFER, 3,022,217.98) nằm ở vùng rủi ro trung gian với score 0.343692, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: giao dịch nằm trong vùng cần đánh giá thêm, điểm bất thường vượt ngưỡng cảnh báo của anomaly sidecar. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-2.8866). số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.7274). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0393104: route=medium, final_action=approve, score=0.343692. Loại giao dịch: TRANSFER; số tiền: 3,022,217.98. Anomaly score: 0.8133 | Flagged: True. [transaction_risk] giao dịch nằm trong vùng cần đánh giá thêm. [anomaly_risk] điểm bất thường vượt ngưỡng cảnh báo của anomaly sidecar. Evidence: SHAP signal: balance_diff impact -2.8866. | SHAP signal: oldbalanceDest impact -2.7274. | SHAP signal: llm_risk_score impact -2.2126.", "dashboard_summary": "tx_0393104: MEDIUM -> APPROVE | TRANSFER 3,022,217.98 | score 0.344 | anomaly 0.813⚠"}, "narrative": {"human_readable_explanation": "Giao dịch tx_0393104 (TRANSFER, 3,022,217.98) nằm ở vùng rủi ro trung gian với score 0.343692, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: giao dịch nằm trong vùng cần đánh giá thêm, điểm bất thường vượt ngưỡng cảnh báo của anomaly sidecar. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-2.8866). số dư tài khoản đích trước giao dịch đang giảm điểm rủi ro (-2.7274). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0393104: route=medium, final_action=approve, score=0.343692. Loại giao dịch: TRANSFER; số tiền: 3,022,217.98. Anomaly score: 0.8133 | Flagged: True. [transaction_risk] giao dịch nằm trong vùng cần đánh giá thêm. [anomaly_risk] điểm bất thường vượt ngưỡng cảnh báo của anomaly sidecar. Evidence: SHAP signal: balance_diff impact -2.8866. | SHAP signal: oldbalanceDest impact -2.7274. | SHAP signal: llm_risk_score impact -2.2126.", "dashboard_summary": "tx_0393104: MEDIUM -> APPROVE | TRANSFER 3,022,217.98 | score 0.344 | anomaly 0.813⚠"}, "actual_label": 0, "correct": true, "feedback_logged": true, "end_to_end_latency_ms": 70.55178600001, "monitoring_flags": ["amount_shift", "device_shift"]}
````

#### Log 5 — manual_review_queue

Nguồn: `artifacts/logs/manual_review_queue.jsonl`, dòng `1`.

````jsonl
{"event": {"tx_id": "tx_0391347", "step": 42, "timestamp": "2025-01-02T18:00:00", "tx_type": "CASH_OUT", "amount": 119061.07, "card_id": "C940447496", "merchant_id": "merchant_13678", "device_id": "device_10593", "ip_address": "10.5.181.218", "location_id": "zone_063", "oldbalanceOrg": 23183.0, "newbalanceOrig": 0.0, "oldbalanceDest": 2351461.37, "newbalanceDest": 2470522.44, "is_fraud": 0, "is_flagged_fraud": 0, "extras": {"source": "paysim"}}, "prediction": {"score": 0.454101, "raw_probability": 0.000143876182846725, "route": "medium", "explanation": [{"feature": "balance_diff", "impact": -4.945868492126465, "weight": 1.0}, {"feature": "org_balance_delta_ratio", "impact": -1.1634498834609985, "weight": 0.2352}, {"feature": "oldbalanceDest", "impact": -1.104936957359314, "weight": 0.2234}], "latency_ms": 13.695112000277732}, "agent": {"action": "review", "reviewer_note": "Tác tử điều tra tạm giữ giao dịch để analyst xác minh thêm.", "tool_results": {"get_card_history": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "historical_tx_count": 0, "historical_fraud_count": 0, "historical_fraud_rate": 0.0, "tool": "get_card_history"}}, "agent_output": {"structured_output": {"recommended_action": "review", "confidence": 0.6041, "summary": "Tools completed; consolidating evidence.", "reason_codes": ["medium_branch_review"], "evidence": ["SHAP signal: balance_diff impact -4.9459.", "SHAP signal: org_balance_delta_ratio impact -1.1634.", "SHAP signal: oldbalanceDest impact -1.1049."], "human_readable_explanation": "Giao dịch tx_0391347 (CASH_OUT, 119,061.07) nằm ở vùng rủi ro trung gian với score 0.454101, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: giao dịch nằm trong vùng cần đánh giá thêm. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-4.9459). tỷ lệ thay đổi số dư tài khoản nguồn đang giảm điểm rủi ro (-1.1634). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0391347: route=medium, final_action=review, score=0.454101. Loại giao dịch: CASH_OUT; số tiền: 119,061.07. Reason codes: giao dịch nằm trong vùng cần đánh giá thêm. Evidence: SHAP signal: balance_diff impact -4.9459. | SHAP signal: org_balance_delta_ratio impact -1.1634. | SHAP signal: oldbalanceDest impact -1.1049.", "dashboard_summary": "tx_0391347: MEDIUM -> REVIEW | CASH_OUT 119,061.07 | score 0.454"}, "agent_summary": "Tools completed; consolidating evidence.", "intermediate_steps": [{"tool": "get_card_history", "tool_input": "C940447496", "observation": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "historical_tx_count": 0, "historical_fraud_count": 0, "historical_fraud_rate": 0.0, "tool": "get_card_history"}}]}, "validation_attempts": 1, "fallback_used": false, "human_readable_explanation": "Giao dịch tx_0391347 (CASH_OUT, 119,061.07) nằm ở vùng rủi ro trung gian với score 0.454101, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: giao dịch nằm trong vùng cần đánh giá thêm. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-4.9459). tỷ lệ thay đổi số dư tài khoản nguồn đang giảm điểm rủi ro (-1.1634). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0391347: route=medium, final_action=review, score=0.454101. Loại giao dịch: CASH_OUT; số tiền: 119,061.07. Reason codes: giao dịch nằm trong vùng cần đánh giá thêm. Evidence: SHAP signal: balance_diff impact -4.9459. | SHAP signal: org_balance_delta_ratio impact -1.1634. | SHAP signal: oldbalanceDest impact -1.1049.", "dashboard_summary": "tx_0391347: MEDIUM -> REVIEW | CASH_OUT 119,061.07 | score 0.454"}}
````

#### Log 6 — manual_review_queue

Nguồn: `artifacts/logs/manual_review_queue.jsonl`, dòng `2`.

````jsonl
{"event": {"tx_id": "tx_0391361", "step": 42, "timestamp": "2025-01-02T18:00:00", "tx_type": "CASH_OUT", "amount": 193514.86, "card_id": "C2080016535", "merchant_id": "merchant_15555", "device_id": "device_02853", "ip_address": "10.63.183.218", "location_id": "zone_010", "oldbalanceOrg": 20705.0, "newbalanceOrig": 0.0, "oldbalanceDest": 1865987.26, "newbalanceDest": 2059502.11, "is_fraud": 0, "is_flagged_fraud": 0, "extras": {"source": "paysim"}}, "prediction": {"score": 0.562476, "raw_probability": 0.00019569559663068503, "route": "medium", "explanation": [{"feature": "balance_diff", "impact": -5.255662441253662, "weight": 1.0}, {"feature": "org_balance_delta_ratio", "impact": -1.1407169103622437, "weight": 0.217}, {"feature": "amount_log1p", "impact": -0.9788385033607483, "weight": 0.1862}], "latency_ms": 13.206083998738904}, "agent": {"action": "review", "reviewer_note": "Tác tử điều tra tạm giữ giao dịch để analyst xác minh thêm.", "tool_results": {"get_card_history": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "historical_tx_count": 0, "historical_fraud_count": 0, "historical_fraud_rate": 0.0, "tool": "get_card_history"}, "check_ip_blacklist": {"historical_tx_count": 4, "historical_fraud_count": 0, "ip_fraud_rate": 0.0, "blacklisted": false, "tool": "check_ip_blacklist"}}, "agent_output": {"structured_output": {"recommended_action": "review", "confidence": 0.7125, "summary": "Tools completed; consolidating evidence.", "reason_codes": ["medium_branch_review"], "evidence": ["SHAP signal: balance_diff impact -5.2557.", "SHAP signal: org_balance_delta_ratio impact -1.1407.", "SHAP signal: amount_log1p impact -0.9788."], "human_readable_explanation": "Giao dịch tx_0391361 (CASH_OUT, 193,514.86) nằm ở vùng rủi ro trung gian với score 0.562476, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: giao dịch nằm trong vùng cần đánh giá thêm. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-5.2557). tỷ lệ thay đổi số dư tài khoản nguồn đang giảm điểm rủi ro (-1.1407). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0391361: route=medium, final_action=review, score=0.562476. Loại giao dịch: CASH_OUT; số tiền: 193,514.86. Reason codes: giao dịch nằm trong vùng cần đánh giá thêm. Evidence: SHAP signal: balance_diff impact -5.2557. | SHAP signal: org_balance_delta_ratio impact -1.1407. | SHAP signal: amount_log1p impact -0.9788.", "dashboard_summary": "tx_0391361: MEDIUM -> REVIEW | CASH_OUT 193,514.86 | score 0.562"}, "agent_summary": "Tools completed; consolidating evidence.", "intermediate_steps": [{"tool": "get_card_history", "tool_input": "C2080016535", "observation": {"tx_count_24h": 0, "avg_amount_7d": 0.0, "historical_tx_count": 0, "historical_fraud_count": 0, "historical_fraud_rate": 0.0, "tool": "get_card_history"}}, {"tool": "check_ip_blacklist", "tool_input": "10.63.183.218", "observation": {"historical_tx_count": 4, "historical_fraud_count": 0, "ip_fraud_rate": 0.0, "blacklisted": false, "tool": "check_ip_blacklist"}}]}, "validation_attempts": 1, "fallback_used": false, "human_readable_explanation": "Giao dịch tx_0391361 (CASH_OUT, 193,514.86) nằm ở vùng rủi ro trung gian với score 0.562476, nên được chuyển sang tác tử điều tra để xem xét thêm. Các lý do chính gồm: giao dịch nằm trong vùng cần đánh giá thêm. Tín hiệu từ mô hình: độ lệch biến động số dư đang giảm điểm rủi ro (-5.2557). tỷ lệ thay đổi số dư tài khoản nguồn đang giảm điểm rủi ro (-1.1407). Tools completed; consolidating evidence.", "analyst_report": "Tx tx_0391361: route=medium, final_action=review, score=0.562476. Loại giao dịch: CASH_OUT; số tiền: 193,514.86. Reason codes: giao dịch nằm trong vùng cần đánh giá thêm. Evidence: SHAP signal: balance_diff impact -5.2557. | SHAP signal: org_balance_delta_ratio impact -1.1407. | SHAP signal: amount_log1p impact -0.9788.", "dashboard_summary": "tx_0391361: MEDIUM -> REVIEW | CASH_OUT 193,514.86 | score 0.562"}}
````

#### Log 7 — feedback

Nguồn: `artifacts/logs/feedback.jsonl`, dòng `1`.

````jsonl
{"tx_id": "tx_0391334", "actual_label": 0, "predicted_action": "approve", "score": 0.332903}
````

#### Log 8 — feedback

Nguồn: `artifacts/logs/feedback.jsonl`, dòng `2`.

````jsonl
{"tx_id": "tx_0391335", "actual_label": 0, "predicted_action": "approve", "score": 0.247828}
````

#### Log 9 — high_risk_async_llm

Nguồn: `artifacts/logs/high_risk_async_llm.jsonl`, dòng `1`.

````jsonl
{"tx_id": "tx_0392723", "score": 0.999, "message": "tx_id=tx_0392723 auto_block score=0.999 reasons=medium_branch_review summary=Transaction tx_0392723 was reviewed on the medium path with score=0.999.", "status": "ok"}
````

#### Log 10 — drift_alerts

Nguồn: `artifacts/logs/drift_alerts.jsonl`, dòng `1`.

````jsonl
{"tx_id": "tx_0391383", "flags": ["amount_shift", "device_shift"]}
````

### 4.2. Toàn bộ cấu hình ngưỡng

Nguồn: `THRESHOLDS.md` — toàn bộ file; sao chép nguyên văn.

````markdown
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
````

### 4.3. Toàn bộ metadata mô hình

Nguồn: `artifacts/models/model_metadata.json` — toàn bộ file; sao chép nguyên văn.

````json
{
  "source": "paysim",
  "data_path": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/data/paysim.csv",
  "identity_data_path": null,
  "artifact_scope": "production",
  "anomaly_model_path": "/home/phan-van-manh/B\u1ea3n t\u1ea3i v\u1ec1/fraud_detection-20260417T022402Z-3-001/fraud_detection/artifacts/models/anomaly_sidecar.joblib",
  "sample_size_used": 460394,
  "feature_columns": [
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
    "llm_risk_score",
    "llm_reason_count",
    "llm_high_risk_flag",
    "llm_review_flag",
    "llm_category_hash"
  ],
  "routing_thresholds": {
    "low": 0.3,
    "high": 0.85
  },
  "train_end": 322275,
  "val_end": 391334,
  "selected_threshold": 0.5,
  "selected_params": {
    "n_estimators": 260,
    "max_depth": 6,
    "learning_rate": 0.06,
    "subsample": 0.9,
    "colsample_bytree": 0.85
  },
  "training_controls": {
    "max_delta_step": 1
  },
  "class_balance": {
    "positive_count": 429,
    "negative_count": 321846,
    "scale_pos_weight": 750.2237762237762
  },
  "routing_calibration": {
    "low_quantile": 0.85,
    "high_quantile": 0.98,
    "low_quantile_score": 8.068120223470032e-05,
    "high_quantile_score": 0.0003051041276194155,
    "raw_probability_summary": {
      "min": 6.935265446372796e-07,
      "max": 0.9999958276748657,
      "mean": 0.000979467062279582,
      "std": 0.029942866414785385,
      "p50": 2.1707206542487256e-05,
      "p90": 0.00011097176320618019,
      "p95": 0.00017510111501906067,
      "p99": 0.0004990110755898058
    },
    "operational_score_summary": {
      "min": 0.002579,
      "max": 0.999,
      "mean": 0.1429459853458637,
      "std": 0.15316397071122506,
      "p50": 0.080715,
      "p90": 0.353988,
      "p95": 0.46828949999999986,
      "p99": 0.70005842
    },
    "validation_route_share": {
      "low": 0.849998,
      "medium": 0.149104,
      "high": 0.000898
    }
  },
  "validation_metrics": {
    "auc": 0.9994133545353906,
    "f1": 0.96,
    "precision": 0.967741935483871,
    "recall": 0.9523809523809523
  },
  "test_metrics": {
    "auc": 0.9983827150776428,
    "f1": 0.993103448275862,
    "precision": 0.9893129770992366,
    "recall": 0.9969230769230769
  },
  "train_profile": {
    "amount_log1p_mean": 11.964039394332165,
    "tx_count_24h_mean": 7.136762082072764e-05,
    "device_tx_count_24h_mean": 7.547960592661547,
    "merchant_fraud_rate_mean": 0.0018938930199363891,
    "fraud_rate": 0.0013311612753083546
  },
  "split": {
    "total_rows": 460394,
    "train_rows": 322275,
    "validation_rows": 69059,
    "test_rows": 69060
  },
  "anomaly_flag_threshold": 0.41828539293549033
}
````

### 4.4. Kiểm tra danh mục tài liệu tham khảo đã soạn sẵn

Đã rà soát các file Markdown trong repository (gồm `docs/`, báo cáo, các thư mục review và handoff; loại thư mục môi trường Python và `.git`) theo các cụm `Tài liệu tham khảo`, `tham khảo`, `References`, `Bibliography`, `Citation`, DOI/arXiv và danh mục đánh số `[n]`.

**Không tìm thấy danh mục tài liệu tham khảo học thuật đã soạn sẵn trong các file Markdown đã rà soát.** Không bổ sung tài liệu từ Internet hoặc tự dựng citation.

Tìm thấy danh sách tham chiếu artifact nội bộ, khác với bibliography học thuật. Trích toàn bộ các mục có sẵn này để dùng cho phụ lục:

Nguồn: `docs/REPORT_MO_HINH_PAYSIM.md` — dòng 290–304; sao chép nguyên văn.

````markdown
## 15. Artifact tham chiếu

| File | Nội dung |
|---|---|
| `artifacts/reports/evaluation_report.json` | Metric XGBoost, confusion matrix, anomaly sidecar |
| `artifacts/reports/research_suite.json` | Tổng hợp baseline, ablation, robustness, external validation |
| `artifacts/reports/baseline_comparison.json` | So sánh model baseline |
| `artifacts/reports/feature_ablation.json` | Ablation theo nhóm feature |
| `artifacts/reports/medium_branch_ablation.json` | Ablation chính sách vùng medium |
| `artifacts/reports/robustness_validation.json` | Multi-seed, bootstrap CI, McNemar test |
| `artifacts/reports/external_validation.json` | IEEE-CIS frozen-vs-native benchmark |
| `artifacts/reports/transfer_learning_report.json` | Transfer learning PaySim → IEEE-CIS với 25 PaySim-aligned features |
| `artifacts/reports/simulation_report.json` | Route/action/latency trong simulation |
| `artifacts/deployment/deployment_state.json` | Active, candidate và rollback version |
| `artifacts/monitoring/dashboard_snapshot.json` | Snapshot dashboard sau simulation |
````

Nguồn: `B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md` — dòng 213–228; sao chép nguyên văn.

````markdown
## 15. Artifact integrity references

| Artifact | SHA-256 |
|---|---|
| `artifacts/reports/evaluation_report.json` | `b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4` |
| `artifacts/reports/baseline_comparison.json` | `4e2b248b742e17a480f8e0b0f18d34173061f31a2a6ee16d018c54649f2d6f43` |
| `artifacts/reports/b8_final/feature_ablation_b8.json` | `e1ec71ebed71e71107234d44cc4e31f08127bf970190a31ae1d82b9f177c01d9` |
| `artifacts/reports/b8_final/medium_branch_ablation_b8.json` | `e985779737da22ed1a27631746492ab37e770d103e0a9f536e143ffe880bd803` |
| `artifacts/reports/b9_final/b9_repeated_seed_robustness.json` | `4af1ab990a75846bc47a3149337ba57ad7e33cfc7b4a9d5ce1dfef8b8e90e3bb` |
| `artifacts/reports/b10_final/b10_bootstrap_ci.json` | `717f2b83905bd7ee818319c7f17e4bd1c5eff01ae23b09ea8a553d826dde73a8` |
| `artifacts/reports/b11_final/b11_training_time.json` | `7ea49b0a88a5bc972f4581905b85b7364802a828c009746528850b5d75da9062` |
| `artifacts/reports/b11_final/b11_latency_components.json` | `30ac5a55fe158e1a817f64865952f9d8f23761eaca62245a289d8b49c469715f` |
| `artifacts/reports/b12_final/b12_comparison.csv` | `253d7415788fdbc1b1cc5afb0d8f84aa9d2f1ed8b6027d989227cc2d2869947f` |
| `B13_IMPLEMENTATION_REVIEW/b13_environment.json` | `a28f37e9f8fbf6f73cc1a20bc4d9c199d0cd055f6452f3090fdad7e5ff59c62c` |

The worktree was dirty before B14. No clean-checkout claim is made.
````

### 4.5. Đối chiếu tính nguyên vẹn các nội dung đã sao chép

SHA-256 dưới đây được tính từ đúng byte nội dung nguồn được chép vào khối, trước khi thêm hàng rào Markdown. Với “toàn bộ file”, đây là SHA-256 của file nguồn; với trích đoạn, là SHA-256 của đoạn ghi rõ. Các dòng log có đường dẫn và số dòng để tra cứu trực tiếp.

| Nguồn | Phạm vi | Số byte | SHA-256 |
|---|---|---:|---|
| `artifacts/reports/research_suite.json` | toàn bộ file | 29320 | `c7b223c0323e0a9d8d16562e1ba484a5fd84f9fd1923786221afc4d7a6cd4ae4` |
| `artifacts/reports/medium_branch_ablation.json` | toàn bộ file | 3712 | `5d379d9d272559938cf285d77f5de51f386d6206f2c64c156fd7efae2adf3d97` |
| `artifacts/reports/simulation_report.json` | toàn bộ file | 3544 | `30acdbee37f8e79253af506a394966006720bd742225755ddaa25dd9732bac5a` |
| `artifacts/reports/evaluation_report.json` | toàn bộ file | 7037 | `b7641803edb35d450f27b2de3c6bd4f74406f75d58bced8311f2deb109a95bf4` |
| `docs/BANG_KET_QUA_BAO_CAO.md` | dòng 128–148 | 440 | `f3e8edfccad28f951955cded637b3a2f1b2178e6448501fab7e379022b38575c` |
| `docs/REPORT_MO_HINH_PAYSIM.md` | dòng 255–281 | 543 | `c5d0da350d8fe5bddf511a46d3604741cdc0f6875364ef9c07b19db2226d3e34` |
| `artifacts/reports/b8_final/medium_branch_ablation_b8.md` | toàn bộ file | 1694 | `e8c207c37bcbc4ac720876ab7146ec9ea530689777f5d69bd60c4ef85a6c6d85` |
| `artifacts/reports/b8_final/medium_branch_ablation_b8.json` | toàn bộ file | 4583 | `e985779737da22ed1a27631746492ab37e770d103e0a9f536e143ffe880bd803` |
| `artifacts/reports/b11_final/b11_efficiency_summary.md` | toàn bộ file | 4540 | `0a76ffbaf31cd6c63a411620162e78d028cc91652db1eda9e9a57c5e67a2e684` |
| `artifacts/reports/b11_final/b11_latency_components.json` | toàn bộ file | 17304 | `30ac5a55fe158e1a817f64865952f9d8f23761eaca62245a289d8b49c469715f` |
| `artifacts/reports/b11_final/b11_route_latency.json` | toàn bộ file | 13866 | `917e22ab1e661b3ccb84e6888109f46235ca851420d308af2048489319b08a32` |
| `artifacts/reports/b11_final/b11_training_time.json` | toàn bộ file | 7469 | `7ea49b0a88a5bc972f4581905b85b7364802a828c009746528850b5d75da9062` |
| `artifacts/reports/latency_report.json` | toàn bộ file | 958 | `15be52ad936ce31101071db7e2f77040f31cfe10abb78826ca49d11eca921345` |
| `requirements.txt` | toàn bộ file | 825 | `9310cdf2b00f5de15cc641e564350be1c6572af7660d818a08d9c50bd0304a95` |
| `requirements_locked.txt` | toàn bộ file | 1555 | `8182f237eea1f5d6c47f9a90cb62e716d03cfcb3269a65d1afd56995f06e5b8a` |
| `docs/experiments_setup.md` | dòng 5–22 | 517 | `60c231784bdf97a1c77c6445c7ff7e599b4d6ab181cc51f7d4b9e25a50879c45` |
| `artifacts/reports/b11_final/b11_environment.json` | toàn bộ file | 1822 | `517ab73b62cb16458823d01115b354ff7a2fe89d597f2ab6e9b548ab4cca5769` |
| `B13_IMPLEMENTATION_REVIEW/b13_environment.json` | toàn bộ file | 4765 | `a28f37e9f8fbf6f73cc1a20bc4d9c199d0cd055f6452f3090fdad7e5ff59c62c` |
| `B15_TECHNICAL_RESPONSE/B15_TECHNICAL_RESPONSE_LETTER.md` | dòng 228–245 | 1758 | `b9aa187c1404475b58958e797efda5aa88d5e7f852450ebde295b3ebd8bb9efc` |
| `docs/CASE_STUDY_3_GIAO_DICH.md` | toàn bộ file | 5637 | `5192209488cb767e1a747f1d75acac4b912c688fee1cc9d24f40eea39ec235dd` |
| `THRESHOLDS.md` | toàn bộ file | 4354 | `ca1fe19301682bea07846d2e6c431046c5dfa6d1b3c2a6c8251d68d433282f41` |
| `artifacts/models/model_metadata.json` | toàn bộ file | 3114 | `accf3619d88e9c60553d6909e86c75dcc1a2c34127e59e342e37574ffb54baf2` |
| `docs/REPORT_MO_HINH_PAYSIM.md` | dòng 290–304 | 1082 | `5ff943273e81e01c6f0b68c2bda533c2d10fb2b1c25a2d4080a1544393525a64` |
| `B14_SINGLE_SOURCE_OF_TRUTH/TECHNICAL_SINGLE_SOURCE_OF_TRUTH.md` | dòng 213–228 | 1395 | `9f6fffda4015efcc7eea98fe9ebb38e5bbe61ab4f5ec88c77570c467b67f8550` |
