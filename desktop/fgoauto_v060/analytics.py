"""Derived farming metrics for the local dashboard."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable


def runs_per_hour(runs: int, duration_seconds: int) -> float:
    if runs <= 0 or duration_seconds <= 0:
        return 0.0
    return round(runs * 3600.0 / duration_seconds, 2)


def ap_efficiency(quantity: int, ap_spent: int) -> float:
    if quantity <= 0 or ap_spent <= 0:
        return 0.0
    return round(quantity / ap_spent, 4)


def target_progress(current: int, target: int) -> float:
    if target <= 0:
        return 0.0
    return min(1.0, max(0.0, current / target))


def remaining_quantity(current: int, target: int) -> int:
    return max(0, target - current)


def elapsed_seconds(started_at: datetime, ended_at: datetime) -> int:
    return max(0, int((ended_at - started_at).total_seconds()))
