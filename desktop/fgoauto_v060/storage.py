"""SQLite store for sessions, per-battle results, drops, and diagnostic events."""
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
            db.execute(
                """CREATE TABLE IF NOT EXISTS battle_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    ap_spent INTEGER NOT NULL DEFAULT 0,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    raw_result TEXT NOT NULL DEFAULT ''
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
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

    def record_battle(self, route_id: str, started_at: datetime, ended_at: datetime,
                      outcome: str, ap_spent: int = 0, raw_result: str = "") -> None:
        duration = max(0, int((ended_at - started_at).total_seconds()))
        with self._connect() as db:
            db.execute(
                """INSERT INTO battle_runs
                (route_id, started_at, ended_at, outcome, ap_spent, duration_seconds, raw_result)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (route_id, started_at.isoformat(timespec="seconds"),
                 ended_at.isoformat(timespec="seconds"), outcome,
                 max(0, int(ap_spent)), duration, raw_result[:4000]),
            )

    def record_event(self, message: str, level: str = "INFO") -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO events (created_at, level, message) VALUES (?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), level, message[:2000]),
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
            battles = db.execute(
                """SELECT COUNT(*) AS count, COALESCE(SUM(ap_spent), 0) AS ap,
                   SUM(CASE WHEN outcome='completed' THEN 1 ELSE 0 END) AS successes
                   FROM battle_runs"""
            ).fetchone()
        return {
            "sessions": int(sessions["count"]),
            "runs": int(sessions["runs"]),
            "drop_records": int(drops["count"]),
            "drop_quantity": int(drops["quantity"]),
            "battles": int(battles["count"]),
            "ap_spent": int(battles["ap"] or 0),
            "successful_battles": int(battles["successes"] or 0),
        }

    def recent_sessions(self, limit: int = 30) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_battles(self, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM battle_runs ORDER BY id DESC LIMIT ?", (max(1, limit),)
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

    def export_battles_csv(self, path: Path) -> Path:
        rows = self.recent_battles(limit=100000)
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["id", "route_id", "started_at", "ended_at", "outcome",
                            "ap_spent", "duration_seconds", "raw_result"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return path
