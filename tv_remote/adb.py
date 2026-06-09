"""Minimal ADB wrapper for Mi TV control."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADB = ROOT / "tools" / "platform-tools" / "adb.exe"
CONFIG = ROOT / "config" / "tv.json"


def _load_config() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [str(ADB), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def connect() -> str:
    cfg = _load_config()
    host, port = cfg["host"], cfg["port"]
    result = run("connect", f"{host}:{port}", check=False)
    return result.stdout.strip() or result.stderr.strip()


def devices() -> str:
    return run("devices", check=False).stdout.strip()


def is_connected() -> bool:
    cfg = _load_config()
    target = f"{cfg['host']}:{cfg['port']}"
    lines = devices().splitlines()[1:]
    return any(target in line and "\tdevice" in line for line in lines)


def keyevent(code: int) -> None:
    run("shell", "input", "keyevent", str(code))


def shell(cmd: str, check: bool = True) -> str:
    result = run("shell", cmd, check=check)
    return result.stdout.strip()


def pull(remote: str, local: str) -> None:
    run("pull", remote, local)


def ensure_connected() -> None:
    if is_connected():
        return
    msg = connect()
    if not is_connected():
        raise RuntimeError(f"Could not connect: {msg}")
