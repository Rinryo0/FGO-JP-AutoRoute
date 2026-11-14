"""Crash-safe local progress journal for long-running FGO tasks."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class ProgressJournal:
    """Atomically persist one task checkpoint on the local machine."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @staticmethod
    def task_key(mode: str, start_chapter_id: str, quest_name: str, item_name: str) -> str:
        parts = (mode, start_chapter_id, quest_name.strip().casefold(), item_name.strip().casefold())
        return "|".join(parts)

    def load(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(data, dict) or data.get("schema_version") != self.SCHEMA_VERSION:
            return None
        return data

    def load_for(self, task_key: str) -> dict[str, Any] | None:
        data = self.load()
        if not data or data.get("task_key") != task_key:
            return None
        return data

    def save(self, checkpoint: dict[str, Any]) -> None:
        payload = dict(checkpoint)
        payload["schema_version"] = self.SCHEMA_VERSION
        payload["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
