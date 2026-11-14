"""Template-free Japanese OCR screen recognition with live text geometry."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Iterable


@dataclass(frozen=True)
class TextRegion:
    text: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class ScreenDetection:
    state: str
    label: str
    confidence: float
    signals: tuple[str, ...]
    texts: tuple[str, ...]
    elapsed: float = 0.0
    regions: tuple[TextRegion, ...] = ()


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
    "chapter_clear": "章節完成",
    "ap_recovery": "AP 恢復確認",
}


def classify_texts(texts: Iterable[str]) -> ScreenDetection:
    """Classify OCR text conservatively; generic NEXT/AP labels are insufficient."""
    clean = tuple(str(item).strip() for item in texts if str(item).strip())
    compact = "".join(clean).upper().replace(" ", "").replace("　", "")

    def has(*terms: str) -> bool:
        return any(term.upper().replace(" ", "") in compact for term in terms)

    def result(state: str, signals: tuple[str, ...], base: float = 0.86) -> ScreenDetection:
        confidence = min(0.99, base + max(0, len(signals) - 1) * 0.045)
        return ScreenDetection(state, _LABELS[state], confidence, signals, clean)

    if has("AP回復", "聖晶石で回復", "黄金の果実", "金の果実", "銀の果実", "青銅の果実"):
        return result("ap_recovery", ("AP 恢復／資源確認",), 0.94)

    if has("CHAPTER CLEAR", "SINGULARITY COMPLETE", "特異点修復", "人理定礎復元"):
        return result("chapter_clear", ("章節完成",), 0.95)

    result_signals = tuple(
        term for term in ("RESULT", "獲得EXP", "獲得した戦利品", "獲得QP合計", "QUEST CLEAR")
        if has(term)
    )
    if result_signals:
        return result("result", result_signals, 0.94)

    card_signals = tuple(term for term in ("BUSTER", "ARTS", "QUICK") if has(term))
    if len(card_signals) >= 2:
        return result("battle_cards", card_signals, 0.90)

    battle_signals = tuple(term for term in ("BATTLE", "ENEMY", "TURN", "ATTACK", "攻撃") if has(term))
    if (
        ("BATTLE" in battle_signals and "ENEMY" in battle_signals and "TURN" in battle_signals)
        or ("ATTACK" in battle_signals and ("BATTLE" in battle_signals or "ENEMY" in battle_signals))
        or ("攻撃" in battle_signals and ("ENEMY" in battle_signals or "TURN" in battle_signals))
    ):
        return result("battle_command", battle_signals, 0.91)

    if has("サポート選択", "SUPPORT SELECTION") or (
        has("GUEST SERVANT") and has("FORMATION")
    ):
        return result("support_select", ("支援選択画面",), 0.93)

    if has("PARTY") and has("クエスト開始", "QUEST START", "出撃"):
        return result("party_confirm", ("隊伍確認", "開始按鈕"), 0.91)

    if has("SKIP", "スキップ") and has("LOG", "AUTO", "オート", "ログ"):
        return result("story", ("SKIP／劇情操作列",), 0.90)

    if has("AP") and (
        has("MAIN QUEST", "QUEST PROGRESS", "クエスト進行度", "推奨LV", "推奨Lv")
        or ("第" in compact and "節" in compact)
    ):
        return result("quest_list", ("AP", "主線關卡資訊"), 0.86)

    chapter_names = (
        "ロンドン", "冬木", "オルレアン", "セプテム", "オケアノス",
        "北米", "キャメロット", "バビロニア", "ソロモン",
    )
    chapter_hit = next((name for name in chapter_names if name in compact), None)
    if chapter_hit and (has("NEXT", "次へ", "CHAPTER", "特異点") or "A.D." in compact):
        signals = (chapter_hit, "章節導覽")
        return result("chapter_map", signals, 0.87)

    if has("MENU") and has("ターミナル", "カルデアゲート", "お知らせ", "クエスト"):
        return result("home", ("MENU", "主畫面導覽"), 0.87)

    return ScreenDetection("unknown", _LABELS["unknown"], 0.0, (), clean)


class FgoScreenDetector:
    """Lazy RapidOCR wrapper; text boxes are retained for dynamic tap targets."""

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

    @staticmethod
    def _regions(output: Any) -> tuple[TextRegion, ...]:
        boxes = getattr(output, "boxes", None) or ()
        texts = getattr(output, "txts", None) or ()
        scores = getattr(output, "scores", None) or ()
        regions: list[TextRegion] = []
        for index, text in enumerate(texts):
            if index >= len(boxes):
                break
            try:
                points = boxes[index]
                xs = [int(float(point[0])) for point in points]
                ys = [int(float(point[1])) for point in points]
                confidence = float(scores[index]) if index < len(scores) else 0.75
                regions.append(TextRegion(
                    str(text), confidence, min(xs), min(ys), max(xs), max(ys)
                ))
            except (TypeError, ValueError, IndexError):
                continue
        return tuple(regions)

    def detect(self, frame: Any) -> ScreenDetection:
        if frame is None:
            return ScreenDetection("unknown", _LABELS["unknown"], 0.0, (), ())
        output = self._get_engine()(frame)
        texts = tuple(str(item) for item in (getattr(output, "txts", ()) or ()))
        detection = classify_texts(texts)
        return ScreenDetection(
            detection.state,
            detection.label,
            detection.confidence,
            detection.signals,
            detection.texts,
            float(getattr(output, "elapse", 0.0) or 0.0),
            self._regions(output),
        )
