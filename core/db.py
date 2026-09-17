import sqlite3
import os
import time
from datetime import datetime
from config import BACKUP_DIR, DB_PATH

SCHEMA_VERSION = 1


def _ensure_parent(path: str):
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def get_connection(path: str | None = None, *, check_same_thread: bool = True):
    database = path or DB_PATH
    _ensure_parent(database)
    con = sqlite3.connect(database, timeout=5, check_same_thread=check_same_thread)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def init_db():
    with get_connection() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                token   TEXT UNIQUE NOT NULL,   -- QR code content (e.g. email)
                name    TEXT UNIQUE NOT NULL     -- display name
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
                kind        TEXT NOT NULL,      -- 'brew' or 'noise'
                shot_type   TEXT,
                decaf       INTEGER,
                rating      INTEGER
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     INTEGER PRIMARY KEY,
                applied_at  REAL NOT NULL
            );
        """)
        con.executescript("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id  ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_brews_session_id  ON brews(session_id);
            CREATE INDEX IF NOT EXISTS idx_brews_started_at  ON brews(started_at);
        """)
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(brews)").fetchall()
        }
        if "shot_type" not in columns:
            con.execute("ALTER TABLE brews ADD COLUMN shot_type TEXT")
        if "decaf" not in columns:
            con.execute("ALTER TABLE brews ADD COLUMN decaf INTEGER")
        if "rating" not in columns:
            con.execute("ALTER TABLE brews ADD COLUMN rating INTEGER")
        rows = con.execute("SELECT id, name FROM users ORDER BY id").fetchall()
        used_names = set()
        for user_id, name in rows:
            candidate = name
            suffix = 2
            while candidate in used_names:
                candidate = f"{name}-{suffix}"
                suffix += 1
            if candidate != name:
                con.execute("UPDATE users SET name=? WHERE id=?", (candidate, user_id))
            used_names.add(candidate)
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_name ON users(name)")
        con.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, time.time()),
        )
        con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        # Close any sessions left open by a previous unclean shutdown.
        con.execute(
            "UPDATE sessions SET ended_at=? WHERE ended_at IS NULL",
            (time.time(),),
        )


def backup_database(destination: str | None = None) -> str:
    if destination is None:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destination = os.path.join(BACKUP_DIR, f"espresso-{stamp}.db")
    _ensure_parent(destination)
    with get_connection() as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination


def integrity_check(path: str | None = None) -> list[str]:
    database = path or DB_PATH
    if not os.path.isfile(database):
        return ["database file does not exist"]
    with sqlite3.connect(database) as con:
        return [row[0] for row in con.execute("PRAGMA integrity_check").fetchall()]


def restore_database(source: str):
    results = integrity_check(source)
    if results != ["ok"]:
        raise ValueError(f"backup failed integrity check: {', '.join(results)}")
    _ensure_parent(DB_PATH)
    with sqlite3.connect(source) as backup, get_connection() as target:
        backup.backup(target)
        target.execute("PRAGMA journal_mode=WAL")


def get_or_create_user(token: str) -> dict:
    """Return user row for the given QR token, creating it if new."""
    base_name = token.split("@")[0]
    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT id, token, name FROM users WHERE token=?", (token,)
        ).fetchone()
        if row is None:
            name = base_name
            suffix = 2
            while con.execute("SELECT 1 FROM users WHERE name=?", (name,)).fetchone():
                name = f"{base_name}-{suffix}"
                suffix += 1
            cur = con.execute(
                "INSERT INTO users (token, name) VALUES (?, ?)",
                (token, name),
            )
            row = (cur.lastrowid, token, name)
    return {"id": row[0], "token": row[1], "name": row[2]}


def start_session(user_id: int | None, started_at: float | None = None) -> int:
    """Open a new session, return its id."""
    with get_connection() as con:
        cur = con.execute(
            "INSERT INTO sessions (user_id, started_at) VALUES (?, ?)",
            (user_id, time.time() if started_at is None else started_at),
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


def rate_brew(brew_id: int, rating: int) -> bool:
    """Set rating (1–5) on a completed brew."""
    with get_connection() as con:
        cursor = con.execute(
            "UPDATE brews SET rating=? WHERE id=? AND kind='brew'",
            (rating, brew_id),
        )
    return cursor.rowcount == 1


def get_session_avg_rating(session_id: int) -> float | None:
    """Average rating of rated brews in a session. None if none rated."""
    with get_connection() as con:
        row = con.execute(
            "SELECT AVG(rating) FROM brews WHERE session_id=? AND rating IS NOT NULL",
            (session_id,)
        ).fetchone()
    return row[0]  # None if no rated brews
