from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import redis

from .config import APP_CONFIG


REDIS_BIN_CANDIDATES = [
    Path.home() / ".local" / "lib" / "python3.12" / "site-packages" / "redislite" / "bin" / "redis-server",
    Path(__file__).resolve().parents[1] / ".venv" / "bin" / "redis-server",
]


def _find_free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _redis_config_path(path: Path) -> str:
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class EmbeddedRedisServer:
    """Start a local Redis server process when REDIS_URL is not provided."""

    def __init__(self) -> None:
        self.runtime_dir = APP_CONFIG.outputs.redis_runtime_dir
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.redis_url = os.getenv("REDIS_URL")
        self.process: subprocess.Popen[str] | None = None
        self.port: int | None = None
        self.conf_path: Path | None = None
        self.log_path: Path | None = None

        if not self.redis_url:
            self._start_local_server()

        atexit.register(self.close)

    def _resolve_redis_bin(self) -> Path:
        system_redis = shutil.which("redis-server")
        if system_redis:
            return Path(system_redis)
        for candidate in REDIS_BIN_CANDIDATES:
            if candidate.exists() and os.access(candidate, os.X_OK):
                return candidate
        raise FileNotFoundError(
            "No redis-server binary found. Install redis-server/redislite or provide REDIS_URL."
        )

    def _start_local_server(self) -> None:
        redis_bin = self._resolve_redis_bin()
        for _ in range(10):
            runtime_dir = self.runtime_dir / f"run-{os.getpid()}-{time.time_ns()}"
            runtime_dir.mkdir(parents=True, exist_ok=True)

            self.port = _find_free_port()
            self.conf_path = runtime_dir / "redis.conf"
            self.log_path = runtime_dir / "redis.stdout.log"
            pid_path = runtime_dir / "redis.pid"

            config = "\n".join(
                [
                    f"port {self.port}",
                    "bind 127.0.0.1",
                    "save \"\"",
                    "appendonly no",
                    "daemonize no",
                    f"dir {_redis_config_path(runtime_dir)}",
                    f"pidfile {_redis_config_path(pid_path)}",
                    "loglevel warning",
                ]
            )
            self.conf_path.write_text(config, encoding="utf-8")

            log_handle = self.log_path.open("w", encoding="utf-8")
            self.process = subprocess.Popen(
                [str(redis_bin), str(self.conf_path)],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.redis_url = f"redis://127.0.0.1:{self.port}/0"
            client = self.client()

            for _ in range(20):
                if self.process.poll() is not None:
                    break
                try:
                    if client.ping():
                        return
                except redis.RedisError:
                    time.sleep(0.25)

            self.close()

        raise RuntimeError("Embedded Redis did not start successfully.")

    def client(self, decode_responses: bool = True) -> redis.Redis:
        if not self.redis_url:
            raise RuntimeError("Redis URL is not initialized.")
        return redis.Redis.from_url(self.redis_url, decode_responses=decode_responses)

    def close(self) -> None:
        if not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
