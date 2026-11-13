from datetime import datetime, timedelta

from fgoauto_v060.catalog import PART_ONE_CHAPTERS, executable_chapter_ids
from fgoauto_v060.config import AppConfig, load_config, save_config
from fgoauto_v060.planner import estimate_affordable_runs, make_custom_route
from fgoauto_v060.storage import StatsStore


def test_first_order_catalog_lists_nine_chapters():
    assert len(PART_ONE_CHAPTERS) == 9
    assert executable_chapter_ids() == {"london"}


def test_ap_budget_is_capped_by_requested_runs():
    assert estimate_affordable_runs(40, 20, 7) == 2
    assert estimate_affordable_runs(200, 20, 3) == 3
    assert estimate_affordable_runs(5, 20, 7) == 0


def test_custom_route_is_saved_as_not_executable():
    route = make_custom_route("我的路線", "london", ["第六節", "第七節"])
    assert route["executable"] is False
    assert route["stages"] == ["第六節", "第七節"]


def test_config_round_trip(tmp_path):
    target = tmp_path / "settings.json"
    config = AppConfig(adb_serial="127.0.0.1:16416", ap_current=120, ap_cost=20)
    save_config(config, target)
    loaded = load_config(target)
    assert loaded.adb_serial == "127.0.0.1:16416"
    assert loaded.ap_current == 120
    assert loaded.resolution_width == 1280


def test_stats_store_records_sessions_and_drops(tmp_path):
    store = StatsStore(tmp_path / "stats.sqlite3")
    started = datetime.now()
    store.record_session("london", started, started + timedelta(minutes=3), 2, "completed")
    store.record_drop("london", "QP", 1000)
    summary = store.summary()
    assert summary["sessions"] == 1
    assert summary["runs"] == 2
    assert summary["drop_quantity"] == 1000
