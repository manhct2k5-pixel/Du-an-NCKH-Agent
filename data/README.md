# Dữ liệu đang dùng

Luồng chính dùng `data/paysim.csv`. Các CSV lớn được bỏ qua trong Git.

IEEE-CIS đã chuyển vào `archive/data/ieee-fraud-detection/`, gồm đủ train, test và sample submission. Hai bản `train_transaction.csv` và `train_identity.csv` trùng ở thư mục gốc đã gộp vào bản lưu này sau khi đối chiếu toàn bộ nội dung.

Thử nghiệm IEEE-CIS khi cần:

```bash
python3 run_fraud_flow.py research --source paysim --external-data-path archive/data/ieee-fraud-detection/train_transaction.csv
python3 scripts/run_b12_final.py --transaction-path archive/data/ieee-fraud-detection/train_transaction.csv --identity-path archive/data/ieee-fraud-detection/train_identity.csv
```

Chạy research thông thường với bố cục hiện tại chỉ dùng PaySim. Xem [mục lục lưu trữ](../archive/README.md).
