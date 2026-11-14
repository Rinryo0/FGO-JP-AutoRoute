"""Route planning, AP budgeting, and text parsers."""
from __future__ import annotations

import re

from .catalog import PART_ONE_CHAPTERS


def estimate_affordable_runs(current_ap: int, ap_cost: int, max_runs: int) -> int:
    if current_ap < 0:
        raise ValueError("目前 AP 不可小於 0")
    if ap_cost <= 0:
        raise ValueError("關卡 AP 消耗必須大於 0")
    if max_runs < 0:
        raise ValueError("最大次數不可小於 0")
    return min(max_runs, current_ap // ap_cost)


def parse_ap_text(texts: list[str] | tuple[str, ...]) -> tuple[int, int] | None:
    for text in texts:
        value = str(text).upper().replace("／", "/")
        for pattern in (r"\bAP\s*(\d{1,3})\s*/\s*(\d{1,3})\b",
                        r"\b(\d{1,3})\s*/\s*(\d{1,3})\s*AP\b"):
            match = re.search(pattern, value)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None


def estimate_ap_recovery(current_ap: int, target_ap: int, seconds_per_ap: int = 300) -> int:
    if current_ap < 0 or target_ap < 0 or seconds_per_ap <= 0:
        raise ValueError("AP 與恢復秒數必須是有效非負整數")
    return max(0, target_ap - current_ap) * seconds_per_ap


def make_custom_route(name: str, chapter_id: str, stages: list[str]) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("路線名稱不可空白")
    if chapter_id not in {chapter.chapter_id for chapter in PART_ONE_CHAPTERS}:
        raise ValueError("請選擇第一部章節")
    clean_stages = [stage.strip() for stage in stages if stage.strip()]
    if not clean_stages:
        raise ValueError("至少需要一個關卡名稱")
    route_key = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "custom-route"
    return {
        "route_id": f"custom-{chapter_id}-{route_key}",
        "chapter_id": chapter_id,
        "name": clean_name,
        "stages": clean_stages,
        "executable": False,
        "note": "自訂路線已儲存；需先由 OCR 動態找到對應關卡並通過流程檢查。",
    }
