import sqlite3
import os
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
                name    TEXT                    -- optional display name
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
                duration    REAL NOT NULL   -- seconds
            );
        """)


def get_or_create_user(token: str) -> dict:
    """Return user row for the given QR token, creating it if new."""
    raise NotImplementedError


def start_session(user_id: int | None) -> int:
    """Open a new session, return its id."""
    raise NotImplementedError


def end_session(session_id: int):
    raise NotImplementedError


def log_brew(session_id: int | None, started_at: float, ended_at: float):
    raise NotImplementedError


def get_user_stats(user_id: int) -> dict:
    """Return total brews, total brew time, last seen for a user."""
    raise NotImplementedError
