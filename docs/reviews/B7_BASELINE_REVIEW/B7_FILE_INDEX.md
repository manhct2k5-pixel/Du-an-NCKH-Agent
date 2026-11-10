# B7 – Baseline comparison artifact index

## Danh sách artifact

| File trong gói review | Đường dẫn gốc | Thời gian sửa cuối |
|---|---|---|
| `baseline_comparison.json` | `artifacts/reports/baseline_comparison.json` | `2026-04-24 14:35:21.902279168 +0700` |
| `baseline_comparison.csv` | `artifacts/reports/baseline_comparison.csv` | `2026-04-24 14:35:21.901422953 +0700` |
| `baseline_comparison.md` | `artifacts/reports/baseline_comparison.md` | `2026-04-24 14:35:21.902393724 +0700` |
| `research_suite.json` | `artifacts/reports/research_suite.json` | `2026-04-24 14:40:45.018477196 +0700` |
| `research_suite.md` | `artifacts/reports/research_suite.md` | `2026-04-24 14:40:45.018655502 +0700` |

## Kết quả baseline

- Artifact chứa bảng baseline chính: `artifacts/reports/baseline_comparison.json`
- Model có Test AUC cao nhất: `hist_gradient_boosting` — `0.9999321511699818`
- XGBoost đứng thứ `3` theo Test AUC — `0.9983827150776428`

## Bảng tóm tắt từ `baseline_comparison.json`

| Model | Family | Selected threshold | Validation AUC | Test AUC | Test PR-AUC | Test F1 | Test Precision | Test Recall | Training time |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hist_gradient_boosting | HistGradientBoostingClassifier | 0.5 | 0.9928392444190461 | 0.9999321511699818 | 0.997849385204436 | 0.9969135802469136 | 1.0 | 0.9938461538461538 | 0.7903 |
| random_forest | RandomForestClassifier | 0.5 | 0.9994876629609077 | 0.9998431740748653 | 0.9975016124891384 | 0.9953775038520801 | 0.9969135802469136 | 0.9938461538461538 | 15.7268 |
| xgboost | XGBClassifier | 0.5 | 0.9994133545353906 | 0.9983827150776428 | 0.9970017406400512 | 0.993103448275862 | 0.9893129770992366 | 0.9969230769230769 | 8.1904 |
| logistic_regression | LogisticRegression | 0.7 | 0.9894848976752275 | 0.9963643641842734 | 0.8844123778149597 | 0.4857477547832878 | 0.32548403976975404 | 0.9569230769230769 | 3.0148 |
| dummy_prior | DummyClassifier | 0.5 | 0.5 | 0.5 | 0.009412105415580654 | 0.0 | 0.0 | 0.0 | 0.0159 |

`Training time` giữ nguyên giá trị trường `train_seconds` trong JSON nguồn.
