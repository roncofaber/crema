import time
import sqlite3
from contextlib import closing

import pytest
import core.db as db


def test_init_db_creates_tables(test_db):
    with closing(db.get_connection()) as con, con:
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"users", "sessions", "brews", "schema_migrations"}.issubset(tables)


def test_connection_enables_sqlite_safety_settings(test_db):
    with closing(db.get_connection()) as con, con:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_get_or_create_user_new(test_db):
    user = db.get_or_create_user("alice@example.com")
    assert user["token"] == "alice@example.com"
    assert user["name"] == "alice"
    assert isinstance(user["id"], int)
    assert user["preferred_shot_type"] == "double"
    assert user["preferred_decaf"] is False


def test_get_or_create_user_existing(test_db):
    u1 = db.get_or_create_user("bob@example.com")
    u2 = db.get_or_create_user("bob@example.com")
    assert u1["id"] == u2["id"]


def test_get_or_create_user_extracts_local_part(test_db):
    user = db.get_or_create_user("john.doe@company.org")
    assert user["name"] == "john.doe"


def test_get_or_create_user_disambiguates_duplicate_local_parts(test_db):
    first = db.get_or_create_user("alice@example.com")
    second = db.get_or_create_user("alice@company.com")
    assert first["name"] == "alice"
    assert second["name"] == "alice-2"


def test_init_db_migrates_duplicate_names(tmp_path, monkeypatch):
    db_path = str(tmp_path / "legacy.db")
    monkeypatch.setattr("core.db.DB_PATH", db_path)
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, token TEXT UNIQUE, name TEXT NOT NULL)")
        con.execute("INSERT INTO users VALUES (1, 'alice@example.com', 'alice')")
        con.execute("INSERT INTO users VALUES (2, 'alice@company.com', 'alice')")

    db.init_db()

    with closing(db.get_connection()) as con, con:
        names = [row[0] for row in con.execute("SELECT name FROM users ORDER BY id")]
        indexes = {row[1] for row in con.execute("PRAGMA index_list(users)")}
    assert names == ["alice", "alice-2"]
    assert "idx_users_name" in indexes


def test_user_preferences_persist_and_validate(test_db):
    user = db.get_or_create_user("preferences@example.com")
    assert db.update_user_preferences(user["id"], "single", True)
    assert db.get_or_create_user(user["token"])["preferred_shot_type"] == "single"
    assert db.get_or_create_user(user["token"])["preferred_decaf"] is True
    with pytest.raises(ValueError, match="shot_type"):
        db.update_user_preferences(user["id"], "triple", False)


def test_legacy_users_receive_default_preferences_on_migration(test_db):
    with closing(db.get_connection()) as con, con:
        con.execute("ALTER TABLE users DROP COLUMN preferred_shot_type")
        con.execute("ALTER TABLE users DROP COLUMN preferred_decaf")
        con.execute("INSERT INTO users (token, name) VALUES ('legacy-pref@example.com', 'legacy-pref')")
        con.execute("PRAGMA user_version=1")

    db.init_db()

    user = db.get_or_create_user("legacy-pref@example.com")
    assert user["preferred_shot_type"] == "double"
    assert user["preferred_decaf"] is False
    assert db.SCHEMA_VERSION == 2


def test_backup_and_restore_database(test_db, tmp_path):
    user = db.get_or_create_user("backup@example.com")
    backup_path = str(tmp_path / "backup.db")
    assert db.backup_database(backup_path) == backup_path
    assert db.integrity_check(backup_path) == ["ok"]

    with closing(db.get_connection()) as con, con:
        con.execute("DELETE FROM users WHERE id=?", (user["id"],))
    db.restore_database(backup_path)

    with closing(db.get_connection()) as con, con:
        restored = con.execute("SELECT token FROM users WHERE id=?", (user["id"],)).fetchone()
    assert restored[0] == "backup@example.com"


def test_start_session_authenticated(test_db):
    user = db.get_or_create_user("carol@example.com")
    session_id = db.start_session(user["id"])
    assert isinstance(session_id, int)
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT user_id, ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] == user["id"]
    assert row[1] is None


def test_start_session_anonymous(test_db):
    session_id = db.start_session(None)
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT user_id FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] is None


def test_end_session_stamps_ended_at(test_db):
    user = db.get_or_create_user("dave@example.com")
    session_id = db.start_session(user["id"])
    db.end_session(session_id)
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] is not None


def test_log_brew_creates_row(test_db):
    user = db.get_or_create_user("eve@example.com")
    session_id = db.start_session(user["id"])
    t = time.time()
    brew_id = db.log_brew(session_id, t, t + 25.0, "brew")
    assert isinstance(brew_id, int)
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT duration, kind FROM brews WHERE session_id=?", (session_id,)
        ).fetchone()
    assert row[0] == pytest.approx(25.0)
    assert row[1] == "brew"


def test_log_brew_anonymous(test_db):
    t = time.time()
    brew_id = db.log_brew(None, t, t + 5.0, "noise")
    assert isinstance(brew_id, int)
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT session_id, kind FROM brews WHERE session_id IS NULL"
        ).fetchone()
    assert row[1] == "noise"


def test_get_user_stats_counts_brews_only(test_db):
    user = db.get_or_create_user("frank@example.com")
    s1 = db.start_session(user["id"])
    t = time.time()
    db.log_brew(s1, t, t + 25.0, "brew")
    db.log_brew(s1, t + 30.0, t + 33.0, "noise")
    s2 = db.start_session(user["id"])
    db.log_brew(s2, t + 60.0, t + 85.0, "brew")

    stats = db.get_user_stats(user["id"])
    assert stats["total_brews"] == 2
    assert stats["total_time"] == pytest.approx(50.0)


def test_log_brew_with_shot_type_and_decaf(test_db):
    user = db.get_or_create_user("grace@example.com")
    session_id = db.start_session(user["id"])
    t = time.time()
    brew_id = db.log_brew(session_id, t, t + 25.0, "brew", shot_type="double", decaf=1)
    assert isinstance(brew_id, int)
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT shot_type, decaf FROM brews WHERE id=?", (brew_id,)
        ).fetchone()
    assert row[0] == "double"
    assert row[1] == 1


def test_rate_brew(test_db):
    user = db.get_or_create_user("henry@example.com")
    session_id = db.start_session(user["id"])
    t = time.time()
    brew_id = db.log_brew(session_id, t, t + 25.0, "brew")
    assert db.rate_brew(brew_id, 4) is True
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT rating FROM brews WHERE id=?", (brew_id,)
        ).fetchone()
    assert row[0] == 4


def test_rate_brew_rejects_missing_and_noise(test_db):
    now = time.time()
    noise_id = db.log_brew(None, now, now + 3, "noise")
    assert db.rate_brew(noise_id, 4) is False
    assert db.rate_brew(9999, 4) is False


def test_get_session_avg_rating_no_ratings(test_db):
    user = db.get_or_create_user("iris@example.com")
    session_id = db.start_session(user["id"])
    t = time.time()
    db.log_brew(session_id, t, t + 25.0, "brew")
    db.log_brew(session_id, t + 30.0, t + 55.0, "brew")
    avg = db.get_session_avg_rating(session_id)
    assert avg is None


def test_get_session_avg_rating(test_db):
    user = db.get_or_create_user("jack@example.com")
    session_id = db.start_session(user["id"])
    t = time.time()
    brew_id_1 = db.log_brew(session_id, t, t + 25.0, "brew")
    brew_id_2 = db.log_brew(session_id, t + 30.0, t + 55.0, "brew")
    db.rate_brew(brew_id_1, 3)
    db.rate_brew(brew_id_2, 5)
    avg = db.get_session_avg_rating(session_id)
    assert avg == pytest.approx(4.0)


def test_get_session_avg_rating_ignores_noise(test_db):
    session_id = db.start_session(None)
    now = time.time()
    brew_id = db.log_brew(session_id, now, now + 25, "brew")
    noise_id = db.log_brew(session_id, now + 30, now + 33, "noise")
    db.rate_brew(brew_id, 5)
    with closing(db.get_connection()) as con, con:
        con.execute("UPDATE brews SET rating=1 WHERE id=?", (noise_id,))

    assert db.get_session_avg_rating(session_id) == 5


def test_get_or_create_user_normalizes_token(test_db):
    first = db.get_or_create_user("  Mixed.Case@Example.COM  ")
    second = db.get_or_create_user("mixed.case@example.com")

    assert first["id"] == second["id"]
    assert first["token"] == "mixed.case@example.com"
    with pytest.raises(ValueError, match="valid email"):
        db.get_or_create_user("not-an-email")


def test_repeated_init_preserves_open_sessions_and_recovery_is_explicit(test_db):
    session_id = db.start_session(None)

    db.init_db()
    db.init_db()

    with closing(db.get_connection()) as con, con:
        ended_at = con.execute(
            "SELECT ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()[0]
    assert ended_at is None

    assert db.recover_open_sessions(ended_at=123.0) == 1
    assert db.recover_open_sessions(ended_at=456.0) == 0
    with closing(db.get_connection()) as con, con:
        ended_at = con.execute(
            "SELECT ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()[0]
    assert ended_at == 123.0


def test_maintenance_lock_is_exclusive_nonblocking_and_released(test_db):
    with db.maintenance_lock() as lock_file:
        started = time.monotonic()
        with pytest.raises(db.MaintenanceLockError, match="in use"):
            with db.maintenance_lock():
                pass
        assert time.monotonic() - started < 1
    assert lock_file.closed

    with db.maintenance_lock():
        pass


def test_restore_rejects_unrelated_database(test_db, tmp_path):
    user = db.get_or_create_user("target@example.com")
    source = tmp_path / "unrelated.db"
    with closing(sqlite3.connect(source)) as con, con:
        con.execute("CREATE TABLE inventory (id INTEGER PRIMARY KEY, label TEXT)")

    with pytest.raises(ValueError, match="not a CREMA database"):
        db.restore_database(str(source))

    with closing(db.get_connection()) as con, con:
        token = con.execute(
            "SELECT token FROM users WHERE id=?", (user["id"],)
        ).fetchone()[0]
    assert token == "target@example.com"


def test_restore_rejects_wrong_schema_without_replacing_target(test_db, tmp_path):
    user = db.get_or_create_user("target@example.com")
    source = tmp_path / "wrong-schema.db"
    with closing(sqlite3.connect(source)) as con, con:
        con.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, token TEXT UNIQUE NOT NULL);
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                started_at REAL NOT NULL,
                ended_at REAL
            );
            CREATE TABLE brews (id INTEGER PRIMARY KEY, session_id INTEGER);
        """)

    with pytest.raises(ValueError, match="compatible CREMA database"):
        db.restore_database(str(source))

    with closing(db.get_connection()) as con, con:
        token = con.execute(
            "SELECT token FROM users WHERE id=?", (user["id"],)
        ).fetchone()[0]
    assert token == "target@example.com"
    assert list(tmp_path.glob(".test.db.restore-*")) == []


def test_restore_rejects_future_schema_version(test_db, tmp_path):
    user = db.get_or_create_user("target@example.com")
    source = str(tmp_path / "future.db")
    db.backup_database(source)
    with closing(sqlite3.connect(source)) as con, con:
        con.execute(f"PRAGMA user_version={db.SCHEMA_VERSION + 1}")

    with pytest.raises(ValueError, match="newer than"):
        db.restore_database(source)

    with closing(db.get_connection()) as con, con:
        token = con.execute(
            "SELECT token FROM users WHERE id=?", (user["id"],)
        ).fetchone()[0]
    assert token == "target@example.com"


def test_restore_migrates_legacy_schema_before_replacing_target(test_db, tmp_path):
    source = tmp_path / "legacy-restore.db"
    with closing(sqlite3.connect(source)) as con, con:
        con.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            );
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                started_at REAL NOT NULL,
                ended_at REAL
            );
            CREATE TABLE brews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES sessions(id),
                started_at REAL NOT NULL,
                ended_at REAL NOT NULL,
                duration REAL NOT NULL,
                kind TEXT NOT NULL
            );
            INSERT INTO users (token, name) VALUES ('legacy@example.com', 'legacy');
        """)

    db.restore_database(str(source))

    with closing(db.get_connection()) as con, con:
        token = con.execute("SELECT token FROM users").fetchone()[0]
        columns = {row[1] for row in con.execute("PRAGMA table_info(brews)")}
        version = con.execute("PRAGMA user_version").fetchone()[0]
    assert token == "legacy@example.com"
    assert {"shot_type", "decaf", "rating"}.issubset(columns)
    assert version == db.SCHEMA_VERSION


def test_database_operations_close_every_connection(test_db, tmp_path, monkeypatch):
    connections = []
    real_connect = sqlite3.connect

    def tracked_connect(*args, **kwargs):
        con = real_connect(*args, **kwargs)
        connections.append(con)
        return con

    monkeypatch.setattr(db.sqlite3, "connect", tracked_connect)
    db.get_or_create_user("resources@example.com")
    db.init_db()
    backup_path = str(tmp_path / "resource-backup.db")
    db.backup_database(backup_path)
    assert db.integrity_check() == ["ok"]
    assert db.integrity_check(backup_path) == ["ok"]
    db.restore_database(backup_path)

    assert connections
    for con in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            con.execute("SELECT 1")
