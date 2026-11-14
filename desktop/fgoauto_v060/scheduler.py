"""Local daily scheduler; no background network service is used."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable


@dataclass(frozen=True)
class DailySchedule:
    enabled: bool = False
    start_time: str = "08:00"
    weekdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)


def parse_start_time(value: str) -> time:
    try:
        hour, minute = value.strip().split(":", 1)
        return time(int(hour), int(minute))
    except (ValueError, TypeError) as exc:
        raise ValueError("排程時間必須使用 HH:MM 格式") from exc


def should_start(
    schedule: DailySchedule,
    now: datetime,
    last_started: date | None = None,
) -> bool:
    if not schedule.enabled or now.weekday() not in schedule.weekdays:
        return False
    if last_started == now.date():
        return False
    return now.time().replace(tzinfo=None) >= parse_start_time(schedule.start_time)


def next_start(schedule: DailySchedule, now: datetime) -> datetime | None:
    if not schedule.enabled:
        return None
    target = parse_start_time(schedule.start_time)
    for offset in range(8):
        day = now.date()
        from datetime import timedelta
        day = day + timedelta(days=offset)
        if day.weekday() in schedule.weekdays:
            candidate = datetime.combine(day, target, tzinfo=now.tzinfo)
            if candidate > now:
                return candidate
    return None
