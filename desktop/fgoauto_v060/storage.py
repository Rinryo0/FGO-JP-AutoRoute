"""SQLite statistics store for local sessions and manually confirmed drops."""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import app_data_dir


class StatsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (app_data_dir() / "statistics.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    runs_observed INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS drops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL
                )"""
            )

    def record_session(self, route_id: str, started_at: datetime, ended_at: datetime,
                       runs_observed: int, status: str) -> None:
        duration = max(0, int((ended_at - started_at).total_seconds()))
        with self._connect() as db:
            db.execute(
                """INSERT INTO sessions
                (route_id, started_at, ended_at, runs_observed, status, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (route_id, started_at.isoformat(timespec="seconds"),
                 ended_at.isoformat(timespec="seconds"), max(0, runs_observed),
                 status, duration),
            )

    def record_drop(self, route_id: str, item_name: str, quantity: int) -> None:
        if not item_name.strip() or quantity <= 0:
            raise ValueError("素材名稱不可空白，數量必須大於 0")
        with self._connect() as db:
            db.execute(
                "INSERT INTO drops (route_id, item_name, quantity, recorded_at) VALUES (?, ?, ?, ?)",
                (route_id, item_name.strip(), quantity, datetime.now().isoformat(timespec="seconds")),
            )

    def summary(self) -> dict:
        with self._connect() as db:
            sessions = db.execute(
                "SELECT COUNT(*) AS count, COALESCE(SUM(runs_observed), 0) AS runs FROM sessions"
            ).fetchone()
            drops = db.execute(
                "SELECT COUNT(*) AS count, COALESCE(SUM(quantity), 0) AS quantity FROM drops"
            ).fetchone()
        return {
            "sessions": int(sessions["count"]),
            "runs": int(sessions["runs"]),
            "drop_records": int(drops["count"]),
            "drop_quantity": int(drops["quantity"]),
        }

    def recent_sessions(self, limit: int = 30) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_drops(self, limit: int = 30) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM drops ORDER BY id DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def export_csv(self, path: Path) -> Path:
        rows = self.recent_sessions(limit=10000)
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["id", "route_id", "started_at", "ended_at",
                            "runs_observed", "status", "duration_seconds"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return path
