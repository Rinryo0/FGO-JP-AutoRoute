"""Minimal local notifications with no third-party dependency."""
from __future__ import annotations

import sys


def notify(title: str, message: str) -> None:
    """Emit a non-blocking system beep; UI layers may also show their own notice."""
    if sys.platform == "win32":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
