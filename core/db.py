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
        con.executescript("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id  ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_brews_session_id  ON brews(session_id);
            CREATE INDEX IF NOT EXISTS idx_brews_started_at  ON brews(started_at);
        """)
        # Add new columns for per-brew annotations and ratings (SQLite 3.35+)
        try:
            con.execute("ALTER TABLE brews ADD COLUMN shot_type TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            con.execute("ALTER TABLE brews ADD COLUMN decaf INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            con.execute("ALTER TABLE brews ADD COLUMN rating INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Close any sessions left open by a previous unclean shutdown.
        con.execute(
            "UPDATE sessions SET ended_at=? WHERE ended_at IS NULL",
            (time.time(),),
        )


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


def log_brew(session_id: int | None, started_at: float, ended_at: float, kind: str, shot_type: str | None = None, decaf: int | None = None) -> int:
    """Log a brew and return its id."""
    with get_connection() as con:
        cur = con.execute(
            "INSERT INTO brews (session_id, started_at, ended_at, duration, kind, shot_type, decaf) VALUES (?,?,?,?,?,?,?)",
            (session_id, started_at, ended_at, ended_at - started_at, kind, shot_type, decaf),
        )
        return cur.lastrowid


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


def rate_brew(brew_id: int, rating: int):
    """Set rating (1–5) on a completed brew."""
    with get_connection() as con:
        con.execute("UPDATE brews SET rating=? WHERE id=?", (rating, brew_id))


def get_session_avg_rating(session_id: int) -> float | None:
    """Average rating of rated brews in a session. None if none rated."""
    with get_connection() as con:
        row = con.execute(
            "SELECT AVG(rating) FROM brews WHERE session_id=? AND rating IS NOT NULL",
            (session_id,)
        ).fetchone()
    return row[0]  # None if no rated brews
