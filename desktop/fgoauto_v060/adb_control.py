"""Small ADB input adapter for MuMu Player 12."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class AdbCommandError(RuntimeError):
    pass


class AdbController:
    def __init__(self, adb_path: str | Path | None, serial: str, timeout: float = 5.0):
        self.adb_path = str(adb_path) if adb_path else (shutil.which("adb") or "adb")
        self.serial = serial
        self.timeout = timeout

    def _run(self, *args: str) -> str:
        command = [self.adb_path, "-s", self.serial, *args]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdbCommandError(f"ADB 執行失敗：{exc}") from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "unknown ADB error").strip()
            raise AdbCommandError(message)
        return result.stdout.strip()

    def tap(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise ValueError("點擊座標不可為負數")
        self._run("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 350) -> None:
        if min(x1, y1, x2, y2) < 0:
            raise ValueError("滑動座標不可為負數")
        duration_ms = max(100, min(1500, int(duration_ms)))
        self._run(
            "shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(duration_ms),
        )

    def keyevent(self, key: str) -> None:
        if not key.replace("_", "").isalnum():
            raise ValueError("不合法的 Android keyevent")
        self._run("shell", "input", "keyevent", key)
