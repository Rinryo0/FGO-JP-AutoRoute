"""Template-free Japanese OCR screen recognition for FGO.

This module only identifies the visible screen. It never taps or swipes.
Unknown or ambiguous screens remain UNKNOWN so the caller can fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Iterable


@dataclass(frozen=True)
class ScreenDetection:
    state: str
    label: str
    confidence: float
    signals: tuple[str, ...]
    texts: tuple[str, ...]
    elapsed: float = 0.0


_LABELS = {
    "unknown": "無法判斷",
    "home": "主畫面",
    "chapter_map": "章節地圖",
    "quest_list": "關卡清單",
    "support_select": "支援從者選擇",
    "party_confirm": "隊伍確認",
    "story": "劇情畫面",
    "battle_command": "戰鬥指令",
    "battle_cards": "指令卡選擇",
    "result": "戰鬥結算",
    "ap_recovery": "AP 恢復確認",
}


def classify_texts(texts: Iterable[str]) -> ScreenDetection:
    """Classify OCR text using stable Japanese/English UI labels.

    This is deliberately conservative: generic words such as NEXT or AP are
    never sufficient on their own to trigger a screen classification.
    """
    clean = tuple(str(item).strip() for item in texts if str(item).strip())
    compact = "".join(clean).upper().replace(" ", "").replace("　", "")
    spaced = " ".join(clean).upper()
    
    def has(*terms: str) -> bool:
        return any(term.upper().replace(" ", "") in compact for term in terms)

    def result(state: str, signals: tuple[str, ...], base: float = 0.86) -> ScreenDetection:
        confidence = min(0.99, base + max(0, len(signals) - 1) * 0.045)
        return ScreenDetection(state, _LABELS[state], confidence, signals, clean)

    # Result screens must win over battle UI: battle HUD can remain visible
    # behind the result overlay.
    result_signals = tuple(term for term in ("RESULT", "獲得EXP", "獲得した戦利品", "獲得QP合計") if has(term))
    if result_signals:
        return result("result", result_signals, 0.94)

    card_signals = tuple(term for term in ("BUSTER", "ARTS", "QUICK") if has(term))
    if len(card_signals) >= 2:
        return result("battle_cards", card_signals, 0.90)

    battle_signals = tuple(term for term in ("BATTLE", "ENEMY", "TURN", "ATTACK") if has(term))
    if ("BATTLE" in battle_signals and "ENEMY" in battle_signals and "TURN" in battle_signals) or (
        "ATTACK" in battle_signals and ("BATTLE" in battle_signals or "ENEMY" in battle_signals)
    ):
        return result("battle_command", battle_signals, 0.91)

    if has("サポート選択", "SUPPORT SELECTION") or (
        has("GUEST SERVANT") and has("FORMATION")
    ):
        return result("support_select", ("支援選択画面",), 0.93)

    if has("PARTY") and has("クエスト開始", "QUEST START", "QUEST START!") :
        return result("party_confirm", ("隊伍確認", "開始按鈕"), 0.91)

    if has("SKIP") and has("LOG", "AUTO", "オート"):
        return result("story", ("SKIP", "劇情操作列"), 0.90)

    if has("AP") and (
        has("MAIN QUEST", "QUEST PROGRESS", "クエスト進行度")
        or ("第" in compact and "節" in compact)
    ):
        return result("quest_list", ("AP", "主線關卡資訊"), 0.86)

    chapter_names = (
        "ロンドン", "冬木", "オルレアン", "セプテム", "オケアノス",
        "北米", "キャメロット", "バビロニア", "ソロモン",
    )
    chapter_hit = next((name for name in chapter_names if name in compact), None)
    if has("NEXT") and (has("A.D.") or chapter_hit):
        signals = ("NEXT",) + ((chapter_hit,) if chapter_hit else ("A.D.",))
        return result("chapter_map", signals, 0.84)

    if has("MENU") and has("ターミナル", "カルデアゲート", "お知らせ"):
        return result("home", ("MENU", "主畫面導覽"), 0.85)

    if has("AP回復", "聖晶石で回復", "黄金の果実", "金の果実"):
        return result("ap_recovery", ("AP 恢復確認",), 0.92)

    # Keep unknown screens fail-closed. OCR output is retained for diagnostics.
    return ScreenDetection("unknown", _LABELS["unknown"], 0.0, (), clean)


class FgoScreenDetector:
    """Lazy Japanese OCR wrapper. Model files are bundled with RapidOCR."""

    def __init__(self) -> None:
        self._engine: Any | None = None
        self._lock = Lock()

    def _get_engine(self):
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    from rapidocr import RapidOCR

                    self._engine = RapidOCR(
                        params={
                            "Det.engine_type": "onnxruntime",
                            "Det.lang_type": "multi",
                            "Det.model_type": "small",
                            "Det.ocr_version": "PP-OCRv6",
                            "Rec.engine_type": "onnxruntime",
                            "Rec.lang_type": "japan",
                            "Rec.model_type": "small",
                            "Rec.ocr_version": "PP-OCRv6",
                        }
                    )
        return self._engine

    def detect(self, frame: Any) -> ScreenDetection:
        if frame is None:
            return ScreenDetection("unknown", _LABELS["unknown"], 0.0, (), ())
        engine = self._get_engine()
        output = engine(frame)
        texts = getattr(output, "txts", ()) or ()
        detection = classify_texts(texts)
        return ScreenDetection(
            detection.state,
            detection.label,
            detection.confidence,
            detection.signals,
            detection.texts,
            float(getattr(output, "elapse", 0.0) or 0.0),
        )
