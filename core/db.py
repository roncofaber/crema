import sqlite3
import os
import time
from config import DB_PATH  # noqa: E402 — config lives at repo root


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                token   TEXT UNIQUE NOT NULL,   -- QR code content (e.g. email)
                name    TEXT NOT NULL            -- display name
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER REFERENCES users(id),  -- NULL = anonymous
                started_at  REAL NOT NULL,                 -- Unix timestamp
                ended_at    REAL                           -- NULL = in progress
            );

            CREATE TABLE IF NOT EXISTS brews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER REFERENCES sessions(id),
                started_at  REAL NOT NULL,
                ended_at    REAL NOT NULL,
                duration    REAL NOT NULL,      -- seconds
                kind        TEXT NOT NULL       -- 'brew' or 'noise'
            );
        """)


def get_or_create_user(token: str) -> dict:
    """Return user row for the given QR token, creating it if new."""
    local_part = token.split("@")[0]
    with get_connection() as con:
        con.execute(
            "INSERT OR IGNORE INTO users (token, name) VALUES (?, ?)",
            (token, local_part),
        )
        row = con.execute(
            "SELECT id, token, name FROM users WHERE token=?", (token,)
        ).fetchone()
    return {"id": row[0], "token": row[1], "name": row[2]}


def start_session(user_id: int | None) -> int:
    """Open a new session, return its id."""
    with get_connection() as con:
        cur = con.execute(
            "INSERT INTO sessions (user_id, started_at) VALUES (?, ?)",
            (user_id, time.time()),
        )
        return cur.lastrowid


def end_session(session_id: int):
    with get_connection() as con:
        con.execute(
            "UPDATE sessions SET ended_at=? WHERE id=?",
            (time.time(), session_id),
        )


def log_brew(session_id: int | None, started_at: float, ended_at: float, kind: str):
    with get_connection() as con:
        con.execute(
            "INSERT INTO brews (session_id, started_at, ended_at, duration, kind) VALUES (?,?,?,?,?)",
            (session_id, started_at, ended_at, ended_at - started_at, kind),
        )


def get_user_stats(user_id: int) -> dict:
    """Return total brews and total brew time (kind='brew' only) for a user."""
    with get_connection() as con:
        row = con.execute("""
            SELECT COUNT(*), COALESCE(SUM(b.duration), 0)
            FROM brews b
            JOIN sessions s ON b.session_id = s.id
            WHERE s.user_id = ? AND b.kind = 'brew'
        """, (user_id,)).fetchone()
    return {"total_brews": row[0], "total_time": row[1]}
