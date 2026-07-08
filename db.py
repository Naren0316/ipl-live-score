"""
db.py
-----
SQLite persistence layer. This is the ONLY file that knows SQL exists —
same principle as cricket_api.py isolating HTTP. Everything else talks to
this module through plain function calls and gets/returns model objects.

Two jobs:
1. Log every detected Ball permanently (score history survives restarts,
   can be queried later, e.g. by history.py or a future website).
2. Let the app RESUME correctly after a restart — reconstruct the last
   known Match state from the DB instead of starting blind and wrongly
   re-announcing "innings started".
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import config
from models import Ball, EventType, Innings, Match

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    match_id    TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS balls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT NOT NULL,
    innings_index   INTEGER NOT NULL,
    team            TEXT NOT NULL,
    over            REAL NOT NULL,
    runs_scored     INTEGER NOT NULL,
    wickets_added   INTEGER NOT NULL,
    total_runs      INTEGER NOT NULL,
    total_wickets   INTEGER NOT NULL,
    balls_covered   INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
);

CREATE INDEX IF NOT EXISTS idx_balls_match_innings
    ON balls (match_id, innings_index, id);
"""


@contextmanager
def _connect(db_path: str = config.DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = config.DB_PATH) -> None:
    """Create tables if they don't already exist. Safe to call every startup."""
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def ensure_match(match_id: str, db_path: str = config.DB_PATH) -> None:
    """Insert a matches row if this match_id hasn't been seen before."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO matches (match_id, created_at) VALUES (?, ?)",
            (match_id, datetime.now(timezone.utc).isoformat()),
        )


def save_ball(match_id: str, ball: Ball, db_path: str = config.DB_PATH) -> None:
    """Persist one detected Ball event."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO balls (
                match_id, innings_index, team, over, runs_scored,
                wickets_added, total_runs, total_wickets, balls_covered,
                event_type, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id, ball.innings_index, ball.team, ball.over,
                ball.runs_scored, ball.wickets_added, ball.total_runs,
                ball.total_wickets, ball.balls_covered, ball.event_type.value,
                ball.timestamp.isoformat(),
            ),
        )


def get_last_match_state(match_id: str, db_path: str = config.DB_PATH) -> Match | None:
    """
    Reconstruct the last known Match state (one Innings per innings_index)
    from the most recent ball row per innings. Returns None if we have no
    history for this match yet — caller should treat that as a fresh start.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT b.*
            FROM balls b
            INNER JOIN (
                SELECT innings_index, MAX(id) AS max_id
                FROM balls
                WHERE match_id = ?
                GROUP BY innings_index
            ) latest
            ON b.innings_index = latest.innings_index AND b.id = latest.max_id
            WHERE b.match_id = ?
            """,
            (match_id, match_id),
        ).fetchall()

    if not rows:
        return None

    match = Match(match_id=match_id)
    for row in rows:
        match.innings[row["innings_index"]] = Innings(
            index=row["innings_index"],
            team=row["team"],
            runs=row["total_runs"],
            wickets=row["total_wickets"],
            overs=row["over"],
        )
    return match


def get_ball_history(match_id: str, db_path: str = config.DB_PATH) -> list[Ball]:
    """Return every ball ever logged for this match, in chronological order."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM balls WHERE match_id = ? ORDER BY id ASC",
            (match_id,),
        ).fetchall()

    return [
        Ball(
            innings_index=row["innings_index"],
            team=row["team"],
            over=row["over"],
            runs_scored=row["runs_scored"],
            wickets_added=row["wickets_added"],
            total_runs=row["total_runs"],
            total_wickets=row["total_wickets"],
            balls_covered=row["balls_covered"],
            event_type=EventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
        for row in rows
    ]


def list_known_matches(db_path: str = config.DB_PATH) -> list[str]:
    """Return all match_ids we have any history for."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT match_id FROM matches ORDER BY created_at DESC").fetchall()
    return [row["match_id"] for row in rows]
