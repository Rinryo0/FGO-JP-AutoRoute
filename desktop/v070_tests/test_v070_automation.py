from datetime import date, datetime, timedelta

import cv2
import numpy as np

from fgoauto_v060.analytics import ap_efficiency, remaining_quantity, runs_per_hour, target_progress
from fgoauto_v060.automation import (
    AutomationOptions,
    AutoRouteRunner,
    find_region,
    parse_ap,
    parse_item_quantity,
)
from fgoauto_v060.battle import BattlePlanner, detect_command_cards, detect_enemy_classes
from fgoauto_v060.backup import export_settings, import_settings
from fgoauto_v060.scheduler import DailySchedule, next_start, should_start
from fgoauto_v060.storage import StatsStore
from fgoauto_v060.vision import ScreenDetection, TextRegion, classify_texts


def test_ap_parser_joins_separate_ocr_regions():
    assert parse_ap(("AP", "120/140")) == (120, 140)
    assert parse_ap(("AP 35 / 140",)) == (35, 140)
    assert parse_ap(("random text",)) is None


def test_drop_parser_handles_separate_quantity_region():
    assert parse_item_quantity(("英雄之證", "× 3"), "英雄之證") == 3
    assert parse_item_quantity(("QP", "1000"), "QP") == 1000


def test_find_region_uses_live_ocr_bounding_box():
    region = TextRegion("クエスト開始", 0.98, 100, 200, 300, 240)
    detection = ScreenDetection("party_confirm", "隊伍確認", 0.95, (), ("クエスト開始",), regions=(region,))
    assert find_region(detection, ("クエスト開始",)) == region


def test_party_confirm_action_uses_ocr_box_not_fixed_coordinates():
    region = TextRegion("クエスト開始", 0.98, 100, 200, 300, 240)
    detection = ScreenDetection("party_confirm", "隊伍確認", 0.95, (), ("クエスト開始",), regions=(region,))
    runner = AutoRouteRunner(lambda: None, lambda _x, _y: None, None, AutomationOptions())
    actions = runner._plan_action(detection, None)
    assert len(actions) == 1
    assert (actions[0].x, actions[0].y) == (200, 220)


def test_story_chapter_clear_advances_to_next_singularity():
    region = TextRegion("次へ", 0.99, 900, 600, 1020, 650)
    detection = ScreenDetection("chapter_clear", "章節完成", 0.95, (), ("次へ",), regions=(region,))
    options = AutomationOptions(mode="story", chapter_id="fuyuki", all_chapters=True)
    runner = AutoRouteRunner(lambda: None, lambda _x, _y: None, None, options)
    actions = runner._plan_action(detection, None)
    assert options.chapter_id == "orleans"
    assert len(actions) == 1


def test_story_all_chapters_does_not_stop_at_legacy_progress_target():
    runner = AutoRouteRunner(
        lambda: None, lambda _x, _y: None, None,
        AutomationOptions(mode="story", max_runs=100, progress_target=2, all_chapters=True),
    )
    runner.completed_runs = 5
    assert runner._should_finish() is False


def test_live_card_detector_finds_three_colour_cards():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(frame, (100, 450), (230, 690), (0, 0, 230), -1)
    cv2.rectangle(frame, (350, 450), (480, 690), (230, 0, 0), -1)
    cv2.rectangle(frame, (600, 450), (730, 690), (0, 230, 0), -1)
    cards = detect_command_cards(frame)
    assert len(cards) == 3
    assert {card.color for card in cards} == {"buster", "arts", "quick"}
    assert len(BattlePlanner().plan_cards(frame)) == 3


def test_daily_scheduler_fires_once_per_day():
    schedule = DailySchedule(True, "08:00", (0, 1, 2, 3, 4, 5, 6))
    now = datetime(2026, 11, 16, 9, 0)
    assert should_start(schedule, now)
    assert not should_start(schedule, now, date(2026, 11, 16))
    assert next_start(schedule, datetime(2026, 11, 16, 7, 0)) == datetime(2026, 11, 16, 8, 0)


def test_farming_analytics():
    assert runs_per_hour(10, 1800) == 20.0
    assert ap_efficiency(6, 40) == 0.15
    assert target_progress(5, 10) == 0.5
    assert remaining_quantity(5, 10) == 5


def test_stats_store_records_battle_and_ap(tmp_path):
    store = StatsStore(tmp_path / "stats.sqlite3")
    started = datetime.now()
    store.record_battle("farm:quest", started, started + timedelta(minutes=2), "completed", 40, "素材 × 2")
    summary = store.summary()
    assert summary["battles"] == 1
    assert summary["ap_spent"] == 40
    assert summary["successful_battles"] == 1


def test_settings_backup_round_trip(tmp_path):
    source = tmp_path / "settings.json"
    source.write_text('{"task_mode":"farm","target_quest_name":"修練場"}', encoding="utf-8")
    backup = tmp_path / "backup.json"
    restored = tmp_path / "restored.json"
    export_settings(source, backup)
    import_settings(backup, restored)
    assert '"task_mode": "farm"' in restored.read_text(encoding="utf-8")


def test_ocr_classifier_detects_main_record_part_and_free_quest():
    assert classify_texts(["メインストーリー"]).state == "main_record_select"
    assert classify_texts(["第1部"]).state == "part_select"
    assert classify_texts(["フリークエスト"]).state == "free_quest_select"


def test_np_card_priority_requires_opt_in_and_ocr_label():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(frame, (100, 450), (230, 690), (0, 0, 230), -1)
    cv2.rectangle(frame, (350, 450), (480, 690), (230, 0, 0), -1)
    cv2.rectangle(frame, (600, 450), (730, 690), (0, 230, 0), -1)
    region = TextRegion("宝具", 0.99, 360, 500, 420, 530)
    detection = ScreenDetection("battle_cards", "指令卡選擇", 0.95, (), ("宝具",), regions=(region,))
    cards = BattlePlanner().plan_cards(frame, detection, use_np=True)
    assert len(cards) == 3
    assert cards[0].color == "np"


def test_enemy_class_ocr_analysis():
    assert detect_enemy_classes(["セイバー", "バーサーカー"]) == ("Saber", "Berserker")
