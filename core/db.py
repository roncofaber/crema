import errno
import fcntl
import sqlite3
import os
import re
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime
from config import BACKUP_DIR, BACKUP_RETENTION_COUNT, DB_PATH
from core.identity import validate_token

SCHEMA_VERSION = 2

_DEFAULT_SHOT_TYPE = "double"
_DEFAULT_DECAF = False

_REQUIRED_TABLES = {"users", "sessions", "brews"}
_REQUIRED_COLUMNS = {
    "users": {"id", "token", "name", "preferred_shot_type", "preferred_decaf"},
    "sessions": {"id", "user_id", "started_at", "ended_at"},
    "brews": {
        "id", "session_id", "started_at", "ended_at", "duration", "kind",
        "shot_type", "decaf", "rating",
    },
    "schema_migrations": {"version", "applied_at"},
}


class MaintenanceLockError(RuntimeError):
    pass


def _ensure_parent(path: str):
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def get_connection(path: str | None = None, *, check_same_thread: bool = True):
    database = path or DB_PATH
    _ensure_parent(database)
    con = sqlite3.connect(database, timeout=5, check_same_thread=check_same_thread)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=5000")
        return con
    except Exception:
        con.close()
        raise


@contextmanager
def _connection(path: str | None = None, *, check_same_thread: bool = True):
    with closing(get_connection(path, check_same_thread=check_same_thread)) as con:
        with con:
            yield con


@contextmanager
def maintenance_lock(path: str | None = None):
    """Hold the database's nonblocking exclusive service or maintenance lock."""
    database = os.fspath(path or DB_PATH)
    lock_path = f"{database}.lock"
    _ensure_parent(lock_path)
    lock_file = open(lock_path, "a+b")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        lock_file.close()
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            raise MaintenanceLockError(f"database is in use: {database}") from exc
        raise
    try:
        yield lock_file
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def init_db(path: str | None = None):
    with _connection(path) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                token                TEXT UNIQUE NOT NULL,   -- QR code content (e.g. email)
                name                 TEXT UNIQUE NOT NULL,   -- display name
                preferred_shot_type  TEXT NOT NULL DEFAULT 'double',
                preferred_decaf      INTEGER NOT NULL DEFAULT 0
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
            row[1] for row in con.execute("PRAGMA table_info(users)").fetchall()
        }
        if "preferred_shot_type" not in columns:
            con.execute(
                "ALTER TABLE users ADD COLUMN preferred_shot_type TEXT NOT NULL DEFAULT 'double'"
            )
        if "preferred_decaf" not in columns:
            con.execute(
                "ALTER TABLE users ADD COLUMN preferred_decaf INTEGER NOT NULL DEFAULT 0"
            )
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


def recover_open_sessions(ended_at: float | None = None) -> int:
    with _connection() as con:
        cursor = con.execute(
            "UPDATE sessions SET ended_at=? WHERE ended_at IS NULL",
            (time.time() if ended_at is None else ended_at,),
        )
        return cursor.rowcount


_BACKUP_NAME = re.compile(r"espresso-\d{8}-\d{6}-\d{6}\.db")


def backup_database(destination: str | None = None) -> str:
    if destination is None:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destination = os.path.join(BACKUP_DIR, f"espresso-{stamp}.db")
    destination = os.path.abspath(os.fspath(destination))
    if destination == os.path.abspath(DB_PATH):
        raise ValueError("backup destination must differ from the live database")
    _ensure_parent(destination)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{os.path.basename(destination)}.backup-",
        suffix=".db",
        dir=os.path.dirname(destination),
    )
    os.close(fd)
    try:
        with _connection() as source, _connection(temporary) as target:
            source.backup(target)
        results = integrity_check(temporary)
        if results != ["ok"]:
            raise RuntimeError(f"backup failed integrity check: {', '.join(results)}")
        os.replace(temporary, destination)
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(f"{temporary}{suffix}")
            except FileNotFoundError:
                pass
    return destination


def prune_backups(
    directory: str | None = None,
    *,
    keep: int = BACKUP_RETENTION_COUNT,
    max_age_days: int | None = None,
) -> list[str]:
    if keep < 1:
        raise ValueError("backup retention count must be at least 1")
    if max_age_days is not None and max_age_days < 0:
        raise ValueError("backup retention days cannot be negative")
    root = os.path.abspath(os.fspath(directory or BACKUP_DIR))
    try:
        entries = list(os.scandir(root))
    except FileNotFoundError:
        return []
    candidates = []
    for entry in entries:
        if not _BACKUP_NAME.fullmatch(entry.name):
            continue
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
            stat = entry.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        candidates.append((stat.st_mtime_ns, entry.name, entry.path, stat.st_mtime))
    candidates.sort(reverse=True)
    threshold = None if max_age_days in {None, 0} else time.time() - max_age_days * 86400
    removed = []
    for index, (_, _, path, modified) in enumerate(candidates):
        expired = threshold is not None and modified < threshold
        if index < keep and not expired:
            continue
        try:
            os.remove(path)
        except FileNotFoundError:
            continue
        removed.append(path)
    return removed


def integrity_check(path: str | None = None) -> list[str]:
    database = path or DB_PATH
    if not os.path.isfile(database):
        return ["database file does not exist"]
    with _connection(database) as con:
        return [row[0] for row in con.execute("PRAGMA integrity_check").fetchall()]


def _validate_version(con) -> None:
    user_version = con.execute("PRAGMA user_version").fetchone()[0]
    if user_version > SCHEMA_VERSION:
        raise ValueError(
            f"backup schema version {user_version} is newer than {SCHEMA_VERSION}"
        )
    tables = {
        row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "schema_migrations" in tables:
        latest = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        if latest is not None:
            try:
                latest = int(latest)
            except (TypeError, ValueError) as exc:
                raise ValueError("backup has an invalid schema version") from exc
            if latest > SCHEMA_VERSION:
                raise ValueError(
                    f"backup schema version {latest} is newer than {SCHEMA_VERSION}"
                )


def _validate_restore_source(path: str) -> None:
    with _connection(path) as con:
        tables = {
            row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = _REQUIRED_TABLES - tables
        if missing:
            raise ValueError(
                f"backup is not a CREMA database; missing tables: {', '.join(sorted(missing))}"
            )
        _validate_version(con)


def _validate_restored_schema(path: str) -> None:
    with _connection(path) as con:
        for table, required in _REQUIRED_COLUMNS.items():
            columns = {
                row[1] for row in con.execute(f"PRAGMA table_info({table})")
            }
            missing = required - columns
            if missing:
                raise ValueError(
                    f"backup has incompatible {table} table; missing columns: "
                    f"{', '.join(sorted(missing))}"
                )
        _validate_version(con)


def restore_database(source: str):
    temp_path = None
    try:
        try:
            results = integrity_check(source)
            if results != ["ok"]:
                raise ValueError(f"backup failed integrity check: {', '.join(results)}")
            _validate_restore_source(source)
            _ensure_parent(DB_PATH)
            target_path = os.path.abspath(DB_PATH)
            fd, temp_path = tempfile.mkstemp(
                prefix=f".{os.path.basename(target_path)}.restore-",
                suffix=".db",
                dir=os.path.dirname(target_path),
            )
            os.close(fd)
            with _connection(source) as backup, _connection(temp_path) as target:
                backup.backup(target)
            init_db(temp_path)
            _validate_restored_schema(temp_path)
            with _connection(temp_path) as con:
                con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
                con.execute("PRAGMA journal_mode=DELETE").fetchone()
        except sqlite3.Error as exc:
            raise ValueError(f"backup is not a compatible CREMA database: {exc}") from exc

        os.replace(temp_path, DB_PATH)
        for suffix in ("-wal", "-shm"):
            try:
                os.remove(f"{DB_PATH}{suffix}")
            except FileNotFoundError:
                pass
        with _connection() as con:
            con.execute("PRAGMA journal_mode=WAL")
    finally:
        if temp_path is not None:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.remove(f"{temp_path}{suffix}")
                except FileNotFoundError:
                    pass


def get_or_create_user(token: str) -> dict:
    """Return user row for the given QR token, creating it if new."""
    token = validate_token(token)
    base_name = token.split("@")[0]
    with _connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            """
            SELECT id, token, name,
                   COALESCE(preferred_shot_type, 'double'),
                   COALESCE(preferred_decaf, 0)
            FROM users WHERE token=?
            """,
            (token,),
        ).fetchone()
        if row is None:
            name = base_name
            suffix = 2
            while con.execute("SELECT 1 FROM users WHERE name=?", (name,)).fetchone():
                name = f"{base_name}-{suffix}"
                suffix += 1
            cur = con.execute(
                """
                INSERT INTO users (
                    token, name, preferred_shot_type, preferred_decaf
                ) VALUES (?, ?, ?, ?)
                """,
                (token, name, _DEFAULT_SHOT_TYPE, int(_DEFAULT_DECAF)),
            )
            row = con.execute(
                """
                SELECT id, token, name,
                       COALESCE(preferred_shot_type, 'double'),
                       COALESCE(preferred_decaf, 0)
                FROM users WHERE id=?
                """,
                (cur.lastrowid,),
            ).fetchone()
    return {
        "id": row[0],
        "token": row[1],
        "name": row[2],
        "preferred_shot_type": row[3],
        "preferred_decaf": bool(row[4]),
    }


def update_user_preferences(user_id: int, shot_type: str, decaf: bool) -> bool:
    if shot_type not in {"single", "double"}:
        raise ValueError("shot_type must be 'single' or 'double'")
    with _connection() as con:
        cursor = con.execute(
            """
            UPDATE users
            SET preferred_shot_type=?, preferred_decaf=?
            WHERE id=?
            """,
            (shot_type, int(decaf), user_id),
        )
        return cursor.rowcount == 1


def start_session(user_id: int | None, started_at: float | None = None) -> int:
    """Open a new session, return its id."""
    with _connection() as con:
        cur = con.execute(
            "INSERT INTO sessions (user_id, started_at) VALUES (?, ?)",
            (user_id, time.time() if started_at is None else started_at),
        )
        return cur.lastrowid


def end_session(session_id: int):
    with _connection() as con:
        con.execute(
            "UPDATE sessions SET ended_at=? WHERE id=? AND ended_at IS NULL",
            (time.time(), session_id),
        )


def log_brew(session_id: int | None, started_at: float, ended_at: float, kind: str, shot_type: str | None = None, decaf: int | None = None) -> int:
    """Log a brew and return its id."""
    with _connection() as con:
        cur = con.execute(
            "INSERT INTO brews (session_id, started_at, ended_at, duration, kind, shot_type, decaf) VALUES (?,?,?,?,?,?,?)",
            (session_id, started_at, ended_at, ended_at - started_at, kind, shot_type, decaf),
        )
        return cur.lastrowid


def get_user_stats(user_id: int) -> dict:
    """Return total brews and total brew time (kind='brew' only) for a user."""
    with _connection() as con:
        row = con.execute("""
            SELECT COUNT(*), COALESCE(SUM(b.duration), 0)
            FROM brews b
            JOIN sessions s ON b.session_id = s.id
            WHERE s.user_id = ? AND b.kind = 'brew'
        """, (user_id,)).fetchone()
    return {"total_brews": row[0], "total_time": row[1]}


def rate_brew(brew_id: int, rating: int) -> bool:
    """Set rating (1–5) on a completed brew."""
    with _connection() as con:
        cursor = con.execute(
            "UPDATE brews SET rating=? WHERE id=? AND kind='brew'",
            (rating, brew_id),
        )
    return cursor.rowcount == 1


def get_session_avg_rating(session_id: int) -> float | None:
    """Average rating of rated brews in a session. None if none rated."""
    with _connection() as con:
        row = con.execute(
            "SELECT AVG(rating) FROM brews WHERE session_id=? AND kind='brew' AND rating IS NOT NULL",
            (session_id,)
        ).fetchone()
    return row[0]  # None if no rated brews
