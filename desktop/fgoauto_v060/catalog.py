"""First Order chapter catalog.

Only routes with a tested automation profile are executable. The catalog is
intentionally broader than the current route engine so additional chapters
can be added without changing the UI architecture.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Chapter:
    chapter_id: str
    name: str
    japanese_name: str
    route_status: str
    note: str = ""


PART_ONE_CHAPTERS = (
    Chapter("fuyuki", "特異點F・冬木", "炎上汚染都市 冬木", "planned"),
    Chapter("orleans", "第一特異點・奧爾良", "邪竜百年戦争 オルレアン", "planned"),
    Chapter("septem", "第二特異點・七丘之城", "永続狂気帝国 セプテム", "planned"),
    Chapter("okeanos", "第三特異點・俄刻阿諾斯", "封鎖終局四海 オケアノス", "planned"),
    Chapter(
        "london",
        "第四特異點・倫敦",
        "死界魔霧都市 ロンドン",
        "partial",
        "目前僅有第六節範例路線可呼叫既有引擎。",
    ),
    Chapter("america", "第五特異點・北美", "北米神話大戦 イ・プルーリバス・ウナム", "planned"),
    Chapter("camelot", "第六特異點・卡美洛", "神聖円卓領域 キャメロット", "planned"),
    Chapter("babylonia", "第七特異點・巴比倫尼亞", "絶対魔獣戦線 バビロニア", "planned"),
    Chapter("solomon", "終局特異點・所羅門", "冠位時間神殿 ソロモン", "planned"),
)

LONDON_ROUTE_ID = "jp-london-4th-section-06"


def get_chapter(chapter_id: str) -> Chapter | None:
    return next((chapter for chapter in PART_ONE_CHAPTERS if chapter.chapter_id == chapter_id), None)


def executable_chapter_ids() -> set[str]:
    # Keep this allow-list strict until each chapter has its own verified route profile.
    return {"london"}
