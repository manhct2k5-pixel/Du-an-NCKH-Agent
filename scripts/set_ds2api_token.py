"""Save the user's own DeepSeek web-session token locally, with hidden input."""
from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Nhập token DeepSeek bằng bàn phím, lưu vào config.json local.")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--account-index", type=int, default=0)
    args = parser.parse_args()
    paths = sorted(root.glob("ds2api-main*/ds2api-main/config.json"))
    if args.config:
        config_path = args.config
    elif len(paths) == 1:
        config_path = paths[0]
    else:
        parser.error("Cần chỉ định --config tới file config.json của DS2API.")
    if not config_path.is_file():
        parser.error("Không tìm thấy config.json.")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    accounts = data.get("accounts", [])
    if not 0 <= args.account_index < len(accounts):
        parser.error("Không tìm thấy tài khoản tại --account-index.")
    token = getpass.getpass("Dán phần mã sau Bearer rồi nhấn Enter (mã sẽ không hiện): ").strip()
    if token.lower().startswith("authorization:"):
        token = token.split(":", 1)[1].strip()
    if token.lower().startswith("bearer "):
        token = token.split(None, 1)[1].strip()
    if not token or any(char.isspace() for char in token):
        parser.error("Mã chưa hợp lệ. Sao chép giá trị Authorization của phiên DeepSeek đang đăng nhập.")
    accounts[args.account_index]["token"] = token
    config_path.chmod(0o600)
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Đã lưu token vào config.json local. Bạn có thể báo lại để kiểm tra kết nối.")


if __name__ == "__main__":
    main()
