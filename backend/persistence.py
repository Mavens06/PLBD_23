"""
persistence.py - stockage SQLite minimal pour l'etat utile du backend.

Le backend garde toujours un etat en memoire pour rester simple et rapide, mais
le plan de mission et l'historique des mesures sont sauvegardes afin de survivre
a un redemarrage du serveur.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / ".agribotics" / "state.sqlite3"


def db_path() -> Path:
    return Path(os.getenv("AGRIBOTICS_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mission_plan (
                position INTEGER PRIMARY KEY,
                label TEXT NOT NULL UNIQUE,
                x REAL NOT NULL,
                y REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                point TEXT NOT NULL,
                humidity REAL NOT NULL,
                ph REAL NOT NULL,
                temp REAL NOT NULL,
                ec REAL NOT NULL,
                timestamp TEXT NOT NULL,
                quality TEXT NOT NULL DEFAULT 'good'
            )
            """
        )


def load_plan() -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT label, x, y FROM mission_plan ORDER BY position"
        ).fetchall()
    return [dict(r) for r in rows]


def _plan_rows(points: Iterable[dict]) -> list[tuple[int, str, float, float]]:
    return [
        (i, str(p["label"]), float(p["x"]), float(p["y"]))
        for i, p in enumerate(points)
    ]


def save_plan(points: Iterable[dict]) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM mission_plan")
        conn.executemany(
            "INSERT INTO mission_plan(position, label, x, y) VALUES (?, ?, ?, ?)",
            _plan_rows(points),
        )


def replace_plan(points: Iterable[dict]) -> None:
    rows = _plan_rows(points)
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM mission_plan")
        conn.executemany(
            "INSERT INTO mission_plan(position, label, x, y) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.execute("DELETE FROM measurements")


def load_measurements() -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT point, humidity, ph, temp, ec, timestamp, quality
            FROM measurements
            ORDER BY id
            """
        ).fetchall()
    return [dict(r) for r in rows]


def save_measurement(measurement: dict) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO measurements(point, humidity, ph, temp, ec, timestamp, quality)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(measurement["point"]),
                float(measurement["humidity"]),
                float(measurement["ph"]),
                float(measurement["temp"]),
                float(measurement["ec"]),
                str(measurement["timestamp"]),
                str(measurement.get("quality") or "good"),
            ),
        )


def clear_measurements() -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM measurements")
