"""Import/export local JSON settings backup."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_settings(source: Path, destination: Path) -> Path:
    data = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def import_settings(source: Path, destination: Path) -> Path:
    data: Any = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("設定檔格式錯誤：根節點必須是 JSON 物件")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination
