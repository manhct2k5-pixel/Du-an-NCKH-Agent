# CHECKLIST CHUNG MINH 4 LOP VA DANH GIA DO TIN CAY CHO NCKH

## STATUS UPDATE 2026-04-17

Da bo sung vao codebase:

- repeated runs nhieu seed trong `research`
- bao cao `mean +/- std` cho cac metric chinh
- bootstrap confidence interval 95%
- kiem dinh thong ke McNemar giua XGBoost va baseline manh nhat
- frozen-model external validation tren IEEE-CIS neu du lieu co san
- bo `pytest` gom unit test va sample integration test

Artifact moi sau khi chay `research`:

- `artifacts/reports/robustness_validation.json`
- `artifacts/reports/robustness_validation.md`
- `artifacts/reports/external_validation.json`
- `artifacts/reports/external_validation.md`

Test suite:

- `tests/test_research_statistics.py`
- `tests/test_research_integration.py`
- `pytest.ini`

Cap nhat dien giai:
- PaySim dung de chung minh hieu nang kien truc trong mien mo phong.
- IEEE-CIS dung de kiem tra ngoai phan bo/domain shift cho model PaySim da dong bang.
- Ket qua frozen IEEE-CIS hien tai AUC `0.6285`, PR AUC `0.0532`, F1 `0.0201`; day la domain-shift analysis, khong phai bang chung tong quat hoa truc tiep.

## 1. Muc tieu cua file nay

File nay dung de chung minh he thong fraud detection chay dung theo 4 lop thiet ke:

1. Lop huan luyen offline
2. Lop xu ly giao dich realtime
3. Lop agent va ra quyet dinh
4. Lop giam sat, feedback, retrain, deploy

Dong thoi, file nay tong hop cac bang chung cho thay mo hinh hien tai co do chinh xac offline rat cao va co nen tang tot de viet bai bao thuc nghiem. Huong trinh bay hien tai la khong chon mot trong hai dataset: PaySim dung de chung minh hieu nang kien truc, IEEE-CIS dung lam frozen-model external validation de giam rui ro ket luan do overfitting tren du lieu mo phong.

## 2. Lenh chay de thu thap bang chung

```bash
cd "/home/phan-van-manh/Bản tải về/fraud_detection-20260417T022402Z-3-001/fraud_detection"
source .venv/bin/activate

python3 run_fraud_flow.py train --data-path data/paysim.csv --source paysim
python3 run_fraud_flow.py research --source paysim --external-data-path data/train_transaction.csv --seeds 42,43,44 --bootstrap-iterations 300
python3 run_fraud_flow.py simulate --limit 5000
python3 run_fraud_flow.py status
python3 run_fraud_flow.py serve
```

Neu can kiem tra deploy:

```bash
python3 run_fraud_flow.py deploy --reason "Full PaySim production model; IEEE-CIS frozen validation documents domain shift"
python3 run_fraud_flow.py rollback --reason "Verification rollback"
```

## 3. Checklist chung minh 4 lop

### Lop 1. Huan luyen offline chay dung

Muc tieu:
- Chung minh du lieu duoc chia dung, model duoc train dung, artifact duoc luu dung, metric duoc tinh dung.

Can kiem tra:
- Chay `python3 run_fraud_flow.py train` thanh cong.
- Tao ra model o `artifacts/models/xgboost_fraud.json`.
- Tao ra metadata o `artifacts/models/model_metadata.json`.
- Tao ra bao cao o `artifacts/reports/evaluation_report.json`.
- Bao cao co day du:
  - `validation_metrics`
  - `test_metrics`
  - `confusion_matrix`
  - `roc/pr curve`
  - `threshold sweep`
- Chia du lieu theo thu tu thoi gian, khong tron train/test ngau nhien.
- Co `random_state = 42` de tai lap ket qua.

Bang chung trong code:
- Chia train/validation/test o `fraud_flow/training.py`, doan `train_df`, `val_df`, `test_df`.
- Sinh metric test/validation o `fraud_flow/training.py`.
- Ghi report va artifact o `fraud_flow/training.py`.

Artifact can nop:
- `artifacts/reports/evaluation_report.json`
- `artifacts/reports/evaluation_report.md`
- `artifacts/reports/validation_roc_curve.csv`
- `artifacts/reports/validation_pr_curve.csv`
- `artifacts/reports/test_roc_curve.csv`
- `artifacts/reports/test_pr_curve.csv`
- `artifacts/reports/validation_threshold_sweep.csv`

Dieu kien pass:
- Model train thanh cong.
- Metric test duoc tinh tren holdout test.
- Artifact va metadata duoc sinh day du.

### Lop 2. Xu ly giao dich realtime chay dung

Muc tieu:
- Chung minh giao dich moi vao he thong se duoc lookup feature, tinh score, route dung, tra ket qua dung, va ghi log dung.

Can kiem tra:
- Chay `python3 run_fraud_flow.py simulate --limit 5000` thanh cong.
- Chay `python3 run_fraud_flow.py serve` thanh cong.
- Goi `POST /gateway/transaction` tra ve day du:
  - `prediction.score`
  - `prediction.raw_probability`
  - `prediction.route`
  - `final_action`
  - `end_to_end_latency_ms`
- Giao dich duoc ghi vao log du doan.
- Bao cao mo phong duoc cap nhat.
- Route `low / medium / high` phu hop voi threshold cua model active trong metadata.

Artifact can nop:
- `artifacts/reports/simulation_report.json`
- `artifacts/logs/predictions.jsonl`
- `artifacts/monitoring/dashboard_snapshot.json`

Dieu kien pass:
- API nhan du lieu va tra ket qua thanh cong.
- Pipeline thuc su tao score va final action.
- Latency va route duoc ghi lai.

### Lop 3. Agent va ra quyet dinh chay dung

Muc tieu:
- Chung minh agent chi can thiep vao nhung ca medium, goi tool dung, tao output dung schema, va dua ra quyet dinh co the truy vet.

Can kiem tra:
- Ca `low` thi auto approve, `high` thi auto block, chi `medium` moi goi agent.
- Agent tao duoc `recommended_action`, `confidence`, `reason_codes`, `evidence`.
- Output agent duoc validate schema.
- Cac case `review` duoc dua vao hang doi manual review.
- Analyst co the gui feedback lai he thong.

Artifact can nop:
- `artifacts/logs/manual_review_queue.jsonl`
- `artifacts/logs/high_risk_async_llm.jsonl`
- `artifacts/logs/feedback.jsonl`
- `artifacts/reports/medium_branch_ablation.json`

Dieu kien pass:
- Agent chi chay dung nhanh medium.
- Output agent dung format.
- Co review queue, feedback va trace quyet dinh.

Luu y khoa hoc:
- Agent trong he thong nay khong duoc thiet ke de lap lai 100% XGBoost.
- Agent la lop ho tro nghiep vu cho nhung ca medium.
- Medium Agent hien tai chay dong bo trong pipeline; high-risk explanation log moi la bat dong bo.
- Vi vay agent phai duoc danh gia bang trade-off van hanh, khong duoc thoi phong thanh bang chung "accuracy cao hon XGBoost" neu report khong cho thay dieu do.

### Lop 4. Giam sat, feedback, retrain, deploy chay dung

Muc tieu:
- Chung minh he thong khong chi du doan, ma con theo doi, cap nhat, trien khai, va rollback duoc.

Can kiem tra:
- Chay `python3 run_fraud_flow.py status` xem active version, candidate version, rollback version.
- Chay `python3 run_fraud_flow.py retrain` de train lai va so sanh model moi voi model cu.
- Chay `python3 run_fraud_flow.py deploy --reason "..."` de promote candidate.
- Chay `python3 run_fraud_flow.py rollback --reason "..."` de quay ve version truoc.
- Dashboard doc duoc metrics offline, route share, drift, review queue, deployment state.
- Drift alert, review log, feedback log deu duoc sinh.

Artifact can nop:
- `artifacts/deployment/deployment_state.json`
- `artifacts/deployment/deployment_history.jsonl`
- `artifacts/deployment/rollout_plan.json`
- `artifacts/logs/drift_alerts.jsonl`
- `artifacts/monitoring/dashboard.html`
- `artifacts/monitoring/dashboard_snapshot.json`

Dieu kien pass:
- He thong co versioning, promote, rollback.
- Co drift log, feedback log, dashboard.
- Co the chung minh vong lap cai thien lien tuc.

## 4. Ket qua hien tai cua mo hinh

Nguon du lieu va thiet lap:
- Dataset: PaySim
- Tong so dong sau loc: `460,394`
- Train: `322,275`
- Validation: `69,059`
- Test: `69,060`
- Random seed: `42`

Nguon bang chung:
- `artifacts/reports/evaluation_report.json`
- `artifacts/reports/baseline_comparison.json`
- `artifacts/reports/feature_ablation.json`
- `artifacts/reports/medium_branch_ablation.json`
- `artifacts/reports/research_suite.json`

### 4.1. Ket qua XGBoost tren holdout test

Validation:
- AUC: `0.999413`
- F1: `0.960000`
- Precision: `0.967742`
- Recall: `0.952381`

Test:
- AUC: `0.998383`
- PR AUC: `0.997002`
- F1: `0.993103`
- Precision: `0.989313`
- Recall: `0.996923`
- Confusion matrix: `TN=68403, FP=7, FN=2, TP=648`

Nhan xet:
- Day la bo chi so offline rat cao cho bai toan fraud detection.
- Precision va recall deu cao, cho thay mo hinh vua bat duoc gian lan, vua giu muc false positive thap.

### 4.2. Bang chung feature engineering co y nghia

Tu `feature_ablation.json`:

- Full feature set:
  - Test AUC: `0.998383`
  - Test F1: `0.993103`
  - Test PR AUC: `0.997002`

- Bo online behavior:
  - Test F1 giam `0.003111`

- Bo nhom LLM-style analysis:
  - Test F1 giam `0.022671`
  - Test PR AUC giam `0.001797`

- Bo contextual aggregates:
  - Test F1 giam `0.140023`
  - Test PR AUC giam `0.076953`

- Chi giu transaction core:
  - Test F1 giam `0.181306`
  - Test PR AUC giam `0.067324`

Nhan xet:
- Nhung nhom feature bo sung khong phai la "trang tri".
- Cac nhom context va aggregate dong vai tro rat lon trong viec nang F1.
- Day la bang chung tot cho phan dong gop hoc thuat cua he thong.

### 4.3. Bang chung cho lop agent

Tu `medium_branch_ablation.json`:

- `score_threshold_block`:
  - Block precision: `0.989313`
  - Block recall: `0.996923`
  - Block F1: `0.993103`
  - Review count: `0`

- `route_without_agent`:
  - Block precision: `0.989313`
  - Block recall: `0.996923`
  - Block F1: `0.993103`
  - Review count: `14,181`

- `route_with_medium_agent`:
  - Block precision: `0.951542`
  - Block recall: `0.996923`
  - Block F1: `0.973704`
  - Review count: `6,395`

Nhan xet trung thuc:
- Agent giup giam manual review tu `14,181` xuong `6,395`, tuong duong giam khoang `54.9%`.
- Tuy nhien, block precision va block F1 giam.
- Vi vay, ket luan dung cho bai bao la:
  - XGBoost la backbone du doan chinh.
  - Agent la lop ho tro dieu tra va tu dong hoa quy trinh medium.
  - Agent hien tai chung minh duoc gia tri van hanh, khong phai bang chung tang accuracy.

## 5. Co the noi "do chuan cao" den muc nao

Co the khang dinh:
- Mo hinh XGBoost hien tai co do chinh xac offline rat cao tren holdout test.
- He thong da co baseline comparison, feature ablation, medium-branch ablation, simulation log, dashboard, deploy state.
- He thong da co cau truc gan voi mot pipeline co the dua vao nghien cuu va trien khai demo.

Khong nen khang dinh qua tay:
- "He thong dung 100%"
- "Agent tot hon XGBoost tren moi mat"
- "Chac chan duoc dang bao" neu chua bo sung cac thuc nghiem bo sung ben duoi

## 6. Muc ket luan an toan cho NCKH va bai bao

### 6.1. Cach ket luan an toan

Co the viet:

"Tren tap holdout test gom 69,060 giao dich, mo hinh XGBoost dat AUC 0.998383, PR AUC 0.997002, F1 0.993103, Precision 0.989313 va Recall 0.996923. He thong duoc danh gia bo sung bang baseline comparison, feature ablation, medium-branch ablation va robustness validation. Cac ket qua nay cho thay PaySim la moi truong tot de chung minh hieu nang kien truc. Rieng IEEE-CIS duoc dung lam frozen-model external validation: frozen PaySim model dat AUC 0.6285 tren IEEE-CIS, trong khi IEEE-native retrained benchmark dat AUC 0.8415. Chenh lech nay phan anh domain shift/schema shift manh; vi vay khong nen ket luan qua muc rang model PaySim da tong quat hoa truc tiep sang IEEE-CIS."

### 6.2. Dieu kien nen bo sung truoc khi nop bai bao nghiem ngat

Nen bo sung them:
- Chay lai voi nhieu seed, vi du `3` hoac `5` seed neu can mo rong hon ket qua hien tai
- Bao cao mean +- std cho AUC, F1, Precision, Recall
- Dung IEEE-CIS frozen-model external validation trong `artifacts/reports/external_validation.*`: dong bang XGBoost PaySim, align IEEE-CIS sang 25 PaySim features, va chi dung nhan IEEE-CIS de tinh metric cuoi
- Trinh bay ket qua IEEE-CIS nhu mot domain-shift analysis: frozen PaySim AUC `0.6285` thap hon nhieu so voi PaySim va IEEE-native AUC `0.8415`, khong phai bang chung tong quat hoa truc tiep
- Bo test tu dong cho training, pipeline, service, deploy
- Them mot bang phan tich false positive va false negative tieu bieu

### 6.3. Ket luan thuc te

Ket luan hop ly nhat hien tai:
- Du manh de bao ve NCKH va viet phan thuc nghiem co chat luong.
- Du co so de huong toi bai bao thuc nghiem.
- De noi "du dieu kien dang bao" mot cach rat chat che, nen bo sung them test tu dong sau hon, bang FP/FN tieu bieu, va neu co the them dataset noi bo thuc te.

## 7. Loi thoai ngan gon de noi truoc thay

"Em chung minh he thong chay dung theo 4 lop. Lop 1 co train, validation, test, baseline, ablation, robustness va frozen-model external validation. Lop 2 co pipeline realtime, API response, simulation report va prediction log. Lop 3 co agent chi xu ly nhanh medium, co schema validation, review queue va medium-branch ablation; agent medium hien chay dong bo nen em trinh bay ro gioi han latency khi scale. Lop 4 co dashboard, drift log, feedback log, deploy state va rollback. Em khong chon mot trong hai giua PaySim va IEEE-CIS: PaySim dung de lam ro hieu nang kien truc, IEEE-CIS dung de kiem tra ngoai phan bo. Ket qua PaySim dat AUC 0.998383 va F1 0.993103 tren holdout test 69,060 giao dich; ket qua frozen IEEE-CIS AUC 0.6285 thap hon nhieu so voi IEEE-native retrained AUC 0.8415, nen em trinh bay trung thuc day la domain shift/gioi han chuyen mien, khong thoi phong thanh bang chung tong quat hoa truc tiep."
