"""Fail-closed, OCR-driven automation runner for main-story and farming tasks.

This is a UI automation layer: it only uses ADB taps at live OCR bounding boxes
or live CV-detected command-card centers. It never reads game memory or sends
network packets. Unknown screens, weak OCR, AP-recovery prompts, and missing
targets stop the run rather than guessing.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

import cv2

from .battle import BattlePlanner
from .catalog import PART_ONE_CHAPTERS
from .vision import ScreenDetection, TextRegion


@dataclass
class AutomationOptions:
    mode: str = "story"  # story | farm
    chapter_id: str = "london"
    chapter_label: str = "ロンドン"
    quest_name: str = ""
    max_runs: int = 10
    progress_target: int = 5
    skip_story: bool = True
    preferred_servant: str = ""
    preferred_ce: str = ""
    farm_item_name: str = ""
    farm_target_quantity: int = 0
    ap_cost: int = 0
    min_confidence: float = 0.88
    auto_use_skills: bool = False
    auto_use_np: bool = False
    diagnostics_dir: Path | None = None
    all_chapters: bool = True


@dataclass(frozen=True)
class PlannedTap:
    x: int
    y: int
    reason: str


_CHAPTER_TERMS = {
    "fuyuki": ("冬木", "炎上汚染都市"),
    "orleans": ("オルレアン", "邪竜百年戦争"),
    "septem": ("セプテム", "永続狂気帝国"),
    "okeanos": ("オケアノス", "封鎖終局四海"),
    "london": ("ロンドン", "死界魔霧都市"),
    "america": ("北米", "イ・プルーリバス・ウナム"),
    "camelot": ("キャメロット", "神聖円卓領域"),
    "babylonia": ("バビロニア", "絶対魔獣戦線"),
    "solomon": ("ソロモン", "冠位時間神殿"),
}


def _normal(text: str) -> str:
    return re.sub(r"[\s　・：:!！?？]", "", str(text)).casefold()


def find_region(detection: ScreenDetection, terms: tuple[str, ...] | list[str]) -> TextRegion | None:
    wanted = tuple(_normal(term) for term in terms if term)
    for region in detection.regions:
        candidate = _normal(region.text)
        if candidate and any(term in candidate for term in wanted):
            return region
    return None


def parse_ap(texts: tuple[str, ...]) -> tuple[int, int] | None:
    joined = " ".join(str(text) for text in texts).upper().replace("／", "/")
    patterns = (
        r"\bAP\s*(\d{1,3})\s*/\s*(\d{1,3})\b",
        r"\b(\d{1,3})\s*/\s*(\d{1,3})\s*AP\b",
        r"AP\s*(\d{1,3})\b",
    )
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, joined)
        if match:
            if index == 2:
                return int(match.group(1)), 0
            return int(match.group(1)), int(match.group(2))
    return None


def parse_item_quantity(texts: tuple[str, ...], item_name: str) -> int:
    if not item_name:
        return 0
    target = _normal(item_name)
    for index, text in enumerate(texts):
        current = str(text)
        if target not in _normal(current):
            continue
        match = re.search(r"[×xX＊*]\s*(\d+)|(\d+)\s*[個枚本]", current)
        if match:
            return int(match.group(1) or match.group(2))
        if index + 1 < len(texts):
            match = re.search(r"\d+", str(texts[index + 1]))
            if match:
                return int(match.group(0))
    return 0


class AutoRouteRunner:
    """Runs one selected task on a worker thread and exposes stop/pause state."""

    def __init__(
        self,
        capture: Callable[[], Any],
        tap: Callable[[int, int], None],
        detector: Any,
        options: AutomationOptions,
        on_event: Callable[[str], None] | None = None,
        stats: Any | None = None,
        stop_event: threading.Event | None = None,
    ):
        self.capture = capture
        self.tap = tap
        self.detector = detector
        self.options = options
        self.on_event = on_event or (lambda _message: None)
        self.stats = stats
        self.stop_event = stop_event or threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.thread: threading.Thread | None = None
        self.running = False
        self.completed_runs = 0
        self.collected_target = 0
        self.started_at: datetime | None = None
        self.battle_started_at: datetime | None = None
        self._last_action_key = ""
        self._last_action_at = 0.0
        self._action_state = ""
        self._action_state_at = 0.0
        self._last_waiting_state = ""
        self._last_state = ""
        self._result_recorded = False
        self._unknown_since: float | None = None
        self._battle = BattlePlanner()
        self.stop_reason = ""

    def start(self) -> None:
        if self.running:
            raise RuntimeError("自動任務已在執行")
        if self.options.mode not in {"story", "farm"}:
            raise ValueError("任務模式必須是 story 或 farm")
        if self.options.mode == "farm" and not self.options.quest_name.strip():
            raise ValueError("素材刷取必須指定關卡名稱，避免誤刷其他關卡")
        self.stop_event.clear()
        self.pause_event.set()
        self.started_at = datetime.now()
        self.running = True
        self.thread = threading.Thread(target=self._run, name="FGO-AutoRoute", daemon=True)
        self.thread.start()
        self._emit(f"自動任務開始：{'主線推進' if self.options.mode == 'story' else '素材循環'}")

    def pause(self) -> None:
        self.pause_event.clear()
        self._emit("任務已暫停")

    def resume(self) -> None:
        self.pause_event.set()
        self._emit("任務繼續")

    def stop(self, reason: str = "使用者停止") -> None:
        self.stop_reason = reason
        self.stop_event.set()
        self.pause_event.set()
        self._emit(reason)

    def _emit(self, message: str) -> None:
        try:
            self.on_event(message)
        except Exception:
            pass

    def _run(self) -> None:
        self._emit("自動流程啟動；只會點擊即時 OCR/CV 識別到的目標。")
        try:
            while not self.stop_event.is_set():
                self.pause_event.wait()
                if self.stop_event.is_set():
                    break
                frame = self.capture()
                if frame is None:
                    self.stop("無法取得 MuMu 畫面，已停止。")
                    break
                detection = self.detector.detect(frame)
                if detection.state == "unknown" or detection.confidence < self.options.min_confidence:
                    self._save_diagnostic(frame, detection)
                    self.stop("畫面無法可靠辨識，已停止；請確認遊戲畫面後重新開始。")
                    break
                self._emit_state(detection)
                ap = parse_ap(detection.texts)
                if ap and self.options.ap_cost > 0 and ap[0] < self.options.ap_cost:
                    self.stop(f"AP 不足（{ap[0]} AP），不會自動使用任何蘋果或聖晶石。")
                    break
                if detection.state == "ap_recovery":
                    self.stop("偵測到 AP 恢復／付費確認畫面，已停止以避免誤消耗資源。")
                    break
                if self._handle_result(detection):
                    if self._should_finish():
                        break
                action = self._plan_action(detection, frame)
                if action:
                    self._perform(action)
                elif detection.state not in {"battle_command", "battle_cards"} and self._last_waiting_state != detection.state:
                    self._last_waiting_state = detection.state
                    self._emit(f"目前畫面「{detection.label}」沒有找到符合條件的操作目標，保持等待。")
                self.stop_event.wait(0.8)
        except Exception as exc:
            self.stop(f"自動流程發生錯誤，已安全停止：{exc}")
        finally:
            self.running = False
            if self.started_at and self.stats:
                try:
                    self.stats.record_session(
                        f"{self.options.mode}:{self.options.chapter_id}:{self.options.quest_name or 'auto'}",
                        self.started_at, datetime.now(), self.completed_runs,
                        "completed" if self._should_finish() else "stopped_or_incomplete",
                    )
                except Exception as exc:
                    self._emit(f"工作階段統計寫入失敗：{exc}")
            self._emit(f"任務結束：完成 {self.completed_runs} 場；素材目標進度 {self.collected_target}。")

    def _emit_state(self, detection: ScreenDetection) -> None:
        if detection.state != self._last_state:
            self._emit(f"畫面：{detection.label}（{detection.confidence:.0%}）")
            self._last_state = detection.state

    def _handle_result(self, detection: ScreenDetection) -> bool:
        if detection.state != "result":
            self._result_recorded = False
            return False
        if self._result_recorded:
            return False
        self._result_recorded = True
        self.completed_runs += 1
        quantity = parse_item_quantity(detection.texts, self.options.farm_item_name)
        self.collected_target += quantity
        if quantity > 0 and self.stats and self.options.farm_item_name:
            try:
                self.stats.record_drop(
                    f"{self.options.mode}:{self.options.chapter_id}:{self.options.quest_name or 'auto'}",
                    self.options.farm_item_name, quantity,
                )
            except Exception as exc:
                self._emit(f"素材統計寫入失敗：{exc}")
        if self.battle_started_at and self.stats:
            try:
                self.stats.record_battle(
                    f"{self.options.mode}:{self.options.chapter_id}:{self.options.quest_name or 'auto'}",
                    self.battle_started_at, datetime.now(), "completed", self.options.ap_cost,
                    " | ".join(detection.texts),
                )
            except Exception as exc:
                self._emit(f"戰鬥統計寫入失敗：{exc}")
        self.battle_started_at = None
        self._emit(f"戰鬥結算：第 {self.completed_runs} 場；辨識到目標素材 {quantity}。")
        return True

    def _should_finish(self) -> bool:
        if self.completed_runs >= max(1, self.options.max_runs):
            self.stop_reason = "已達設定的最大戰鬥次數"
            self.stop_event.set()
            self._emit(self.stop_reason)
            return True
        if (self.options.mode == "farm" and self.options.farm_target_quantity > 0
                and self.collected_target >= self.options.farm_target_quantity):
            self.stop_reason = "已達成目標素材數量"
            self.stop_event.set()
            self._emit(self.stop_reason)
            return True
        if (self.options.mode == "story" and not self.options.all_chapters
                and self.completed_runs >= max(1, self.options.progress_target)):
            self.stop_reason = "已達設定的主線進度場次上限"
            self.stop_event.set()
            self._emit(self.stop_reason)
            return True
        return False

    def _plan_action(self, detection: ScreenDetection, frame: Any) -> list[PlannedTap]:
        state = detection.state
        if state == "home":
            return self._tap_text(detection, ("クエスト", "QUEST"))
        if state == "chapter_clear":
            if self.options.mode != "story" or not self.options.all_chapters:
                return self._tap_text(detection, ("次へ", "NEXT", "進む"))
            current_index = next(
                (i for i, chapter in enumerate(PART_ONE_CHAPTERS)
                 if chapter.chapter_id == self.options.chapter_id), -1
            )
            if current_index < 0 or current_index + 1 >= len(PART_ONE_CHAPTERS):
                self.stop("第一部九大章節已到最後一章，主線任務完成。")
                return []
            next_chapter = PART_ONE_CHAPTERS[current_index + 1]
            self.options.chapter_id = next_chapter.chapter_id
            self.options.chapter_label = next_chapter.japanese_name
            self._emit(f"章節完成，下一目標：{next_chapter.name}")
            return self._tap_text(detection, ("次へ", "NEXT", "進む"))
        if state == "chapter_map":
            terms = _CHAPTER_TERMS.get(self.options.chapter_id, (self.options.chapter_label,))
            target = find_region(detection, terms)
            if target:
                return [self._region_tap(target, "選擇目標章節")]
            return self._tap_text(detection, ("NEXT", "次へ")) if self.options.mode == "story" else []
        if state == "quest_list":
            if self.options.mode == "farm":
                target = find_region(detection, (self.options.quest_name,))
                return [self._region_tap(target, "選擇指定素材關卡")] if target else []
            target = find_region(detection, (self.options.quest_name, "次へ", "NEXT", "クエスト開始"))
            return [self._region_tap(target, "選擇主線下一步")] if target else []
        if state == "support_select":
            terms = tuple(x for x in (self.options.preferred_servant, self.options.preferred_ce) if x.strip())
            target = find_region(detection, terms) if terms else None
            if target is None and not terms:
                candidates = [
                    region for region in detection.regions
                    if region.y1 >= 90 and region.y2 <= 620
                    and len(_normal(region.text)) >= 2
                    and not any(word in _normal(region.text) for word in
                                ("サポート", "フレンド", "クラス", "決定", "戻る", "更新"))
                ]
                target = min(candidates, key=lambda region: region.y1) if candidates else None
            return [self._region_tap(target, "選擇符合偏好的支援")] if target else []
        if state == "party_confirm":
            return self._tap_text(detection, ("クエスト開始", "QUEST START", "出撃"))
        if state == "story":
            return self._tap_text(detection, ("SKIP", "スキップ")) if self.options.skip_story else []
        if state == "battle_command":
            if self.battle_started_at is None:
                self.battle_started_at = datetime.now()
            return self._tap_text(detection, ("ATTACK", "攻撃"))
        if state == "battle_cards":
            if self.battle_started_at is None:
                self.battle_started_at = datetime.now()
            cards = self._battle.plan_cards(frame)
            if len(cards) != 3:
                self._emit(self._battle.explain(cards))
                return []
            self._emit(self._battle.explain(cards))
            return [PlannedTap(card.x, card.y, f"選擇 {card.color.upper()} 指令卡") for card in cards]
        if state == "result":
            if self.options.mode == "farm":
                return self._tap_text(detection, ("再挑戦", "RETRY", "もう一度挑戦", "クエストへ戻る"))
            return self._tap_text(detection, ("次へ", "NEXT", "進む"))
        return []

    def _tap_text(self, detection: ScreenDetection, terms: tuple[str, ...]) -> list[PlannedTap]:
        target = find_region(detection, terms)
        return [self._region_tap(target, "點擊 " + "/".join(terms))] if target else []

    @staticmethod
    def _region_tap(region: TextRegion, reason: str) -> PlannedTap:
        return PlannedTap(int((region.x1 + region.x2) / 2), int((region.y1 + region.y2) / 2), reason)

    def _perform(self, actions: list[PlannedTap]) -> None:
        if not actions or self.stop_event.is_set():
            return
        now = time.monotonic()
        if self._action_state == self._last_state:
            if now - self._action_state_at > 15.0:
                self.stop(f"畫面「{self._last_state}」在操作後沒有變化，已停止避免重複點擊。")
            return
        for action in actions:
            if self.stop_event.is_set():
                return
            self.tap(action.x, action.y)
            self._last_action_key = f"{self._last_state}:{action.x}:{action.y}:{action.reason}"
            self._last_action_at = time.monotonic()
            self._emit(f"{action.reason}（{action.x}, {action.y}）")
            self.stop_event.wait(0.25)
        self._action_state = self._last_state
        self._action_state_at = time.monotonic()

    def _save_diagnostic(self, frame: Any, detection: ScreenDetection) -> None:
        directory = self.options.diagnostics_dir
        if directory is None:
            return
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"unknown-{datetime.now():%Y%m%d-%H%M%S}.png"
            cv2.imwrite(str(path), frame)
            self._emit(f"已保存辨識診斷截圖：{path}")
            if detection.texts:
                (directory / "last-ocr.txt").write_text(
                    "\n".join(detection.texts), encoding="utf-8"
                )
        except Exception as exc:
            self._emit(f"診斷資料保存失敗：{exc}")
