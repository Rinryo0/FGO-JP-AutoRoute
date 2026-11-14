"""Conservative FGO command-card analysis.

The detector uses live image geometry and colour segmentation rather than
saved screenshots/templates. It intentionally refuses to tap when fewer than
three plausible command cards are found.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class CardTarget:
    x: int
    y: int
    color: str
    confidence: float


_PRIORITY = {"np": 4, "buster": 3, "arts": 2, "quick": 1}

_ENEMY_CLASSES = {
    "セイバー": "Saber",
    "アーチャー": "Archer",
    "ランサー": "Lancer",
    "ライダー": "Rider",
    "キャスター": "Caster",
    "アサシン": "Assassin",
    "バーサーカー": "Berserker",
    "ルーラー": "Ruler",
    "アヴェンジャー": "Avenger",
    "ムーンキャンサー": "Moon Cancer",
    "アルターエゴ": "Alter Ego",
    "フォーリナー": "Foreigner",
    "プリテンダー": "Pretender",
    "ビースト": "Beast",
}


def detect_enemy_classes(texts: Iterable[str]) -> tuple[str, ...]:
    joined = "".join(str(text) for text in texts)
    return tuple(label for token, label in _ENEMY_CLASSES.items() if token in joined)


def detect_command_cards(frame: np.ndarray) -> list[CardTarget]:
    """Find the three best FGO command-card candidates in a 16:9 frame."""
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        return []
    height, width = frame.shape[:2]
    if width < 640 or height < 360:
        return []

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_region_y = int(height * 0.43)
    candidates: list[CardTarget] = []
    masks = {
        "buster": cv2.inRange(hsv, np.array([0, 75, 65]), np.array([14, 255, 255]))
                  | cv2.inRange(hsv, np.array([166, 75, 65]), np.array([180, 255, 255])),
        "arts": cv2.inRange(hsv, np.array([88, 65, 55]), np.array([135, 255, 255])),
        "quick": cv2.inRange(hsv, np.array([34, 55, 45]), np.array([88, 255, 255])),
    }

    for color, full_mask in masks.items():
        mask = full_mask.copy()
        mask[:lower_region_y, :] = 0
        kernel = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            ratio = w / max(1, h)
            if h < height * 0.19 or w < width * 0.055:
                continue
            if not 0.36 <= ratio <= 0.92 or area < width * height * 0.012:
                continue
            fill = cv2.countNonZero(mask[y:y + h, x:x + w]) / max(1, area)
            if fill < 0.22:
                continue
            confidence = min(0.96, 0.55 + fill * 0.4)
            candidates.append(CardTarget(x + w // 2, y + h // 2, color, confidence))

    # Different colour masks can produce duplicate candidates for one card.
    unique: list[CardTarget] = []
    for item in sorted(candidates, key=lambda c: c.confidence, reverse=True):
        if all(abs(item.x - old.x) > width * 0.055 for old in unique):
            unique.append(item)

    if len(unique) < 3:
        return []
    selected = sorted(unique, key=lambda c: (_PRIORITY[c.color], c.confidence), reverse=True)[:3]
    # Tap order: high-priority Buster first, then Arts, then Quick.
    return selected


class BattlePlanner:
    """Stable-first card selector; never guesses skill or NP button positions."""

    def plan_cards(self, frame: np.ndarray, detection=None, use_np: bool = False) -> list[CardTarget]:
        cards = detect_command_cards(frame)
        if not use_np or len(cards) != 3 or detection is None:
            return cards
        height = frame.shape[0]
        np_regions = [
            region for region in getattr(detection, "regions", ())
            if ("宝具" in region.text or "NOBLE PHANTASM" in region.text.upper())
            and region.y1 >= height * 0.42
        ]
        if not np_regions:
            return cards
        target = max(np_regions, key=lambda region: region.confidence)
        center_x = (target.x1 + target.x2) // 2
        nearest = min(cards, key=lambda card: abs(card.x - center_x))
        marked = [
            CardTarget(card.x, card.y, "np" if card == nearest else card.color,
                       min(0.99, card.confidence + 0.02) if card == nearest else card.confidence)
            for card in cards
        ]
        return sorted(marked, key=lambda card: (_PRIORITY[card.color], card.confidence), reverse=True)

    def enemy_summary(self, texts: Iterable[str]) -> str:
        classes = detect_enemy_classes(texts)
        return "敵方職階：" + "、".join(classes) if classes else "未辨識到敵方職階文字"

    @staticmethod
    def explain(cards: Iterable[CardTarget]) -> str:
        chosen = list(cards)
        if len(chosen) != 3:
            return "未找到三張可信指令卡，停止本回合自動操作。"
        return "指令卡順序：" + " → ".join(card.color.upper() for card in chosen)
