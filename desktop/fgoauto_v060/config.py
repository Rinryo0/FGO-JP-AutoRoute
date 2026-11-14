"""Local user configuration; settings never leave the user's PC."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def app_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        path = Path(root) / "FGO-JP-AutoRoute"
    else:
        path = Path.home() / ".local" / "share" / "FGO-JP-AutoRoute"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    # Keep the v0.6 filename so existing user settings migrate automatically.
    return app_data_dir() / "v060-settings.json"


@dataclass
class AppConfig:
    adb_serial: str = "auto"
    resolution_width: int = 1280
    resolution_height: int = 720
    selected_chapter: str = "london"
    route_id: str = "jp-london-4th-section-06"
    max_runs: int = 7
    progress_target: int = 5
    skip_story: bool = True
    ap_current: int | None = None
    ap_cost: int | None = None
    preferred_servant: str = ""
    preferred_ce: str = ""
    farm_item_name: str = ""
    farm_target_quantity: int = 0
    custom_routes: list[dict[str, Any]] = field(default_factory=list)
    task_mode: str = "story"
    target_quest_name: str = ""
    min_ocr_confidence: float = 0.88
    auto_use_skills: bool = False
    auto_use_np: bool = False
    allow_apples: bool = False
    allow_quartz: bool = False
    schedule_enabled: bool = False
    schedule_time: str = "08:00"
    schedule_weekdays: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    schedule_last_date: str = ""
    notify_on_finish: bool = True
    ap_regen_seconds: int = 300


def load_config(path: Path | None = None) -> AppConfig:
    target = path or config_path()
    if not target.exists():
        return AppConfig()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        allowed = AppConfig.__dataclass_fields__.keys()
        clean = {key: value for key, value in data.items() if key in allowed}
        return AppConfig(**clean)
    except (OSError, ValueError, TypeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target
