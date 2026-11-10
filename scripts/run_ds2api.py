"""Run the supplied DS2API binary using its local account configuration."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from dotenv import load_dotenv


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)
    parser = argparse.ArgumentParser(description="Khởi động cầu nối DeepSeek Web → API cho FraudFlow.")
    parser.add_argument("--source", type=Path, help="Thư mục DS2API chứa binary ds2api và config.json.")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    sources = sorted(root.glob("ds2api-main*/ds2api-main"))
    if args.source:
        source = args.source.resolve()
    elif len(sources) == 1:
        source = sources[0]
    else:
        parser.error("Cần chỉ định --source tới thư mục DS2API.")
    binary, config_path = source / "ds2api", source / "config.json"
    if not binary.is_file() or not config_path.is_file():
        parser.error("Không tìm thấy binary ds2api hoặc config.json.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not any(str(account.get("token", "")).strip() for account in config.get("accounts", [])):
        parser.error("Chưa có token phiên web. Chạy scripts/set_ds2api_token.py để nhập token local.")
    parsed = urlsplit(os.getenv("DS2API_API_BASE", "http://127.0.0.1:5001/v1"))
    port = args.port or parsed.port or 5001
    if not 1 <= port <= 65535:
        parser.error("Port phải nằm trong 1..65535.")
    api_key = os.getenv("DS2API_API_KEY", "")
    metadata_keys = [item.get("key", "") for item in config.get("api_keys", []) if item.get("key")]
    keys = metadata_keys or config.get("keys", [])
    if not api_key or api_key not in keys:
        parser.error("DS2API_API_KEY trong .env chưa khớp với khóa client trong config.json.")
    config_path.chmod(0o600)
    binary.chmod(binary.stat().st_mode | 0o100)
    env = dict(os.environ, PORT=str(port), DS2API_CONFIG_PATH=str(config_path),
               DS2API_ADMIN_KEY=os.getenv("DS2API_ADMIN_KEY") or secrets.token_urlsafe(32),
               DS2API_AUTO_BUILD_WEBUI="false", LOG_LEVEL="WARN")
    env.pop("DS2API_CONFIG_JSON", None)
    env.pop("CONFIG_JSON", None)
    print(f"DS2API: http://127.0.0.1:{port}/v1 · Ctrl+C để dừng.", flush=True)
    print("Binary DS2API được cung cấp lắng nghe trên 0.0.0.0; API có xác thực bằng khóa client.", flush=True)
    os.chdir(source)
    os.execve(str(binary), [str(binary)], env)


if __name__ == "__main__":
    main()
