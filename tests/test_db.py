import time
import sqlite3
import pytest
import core.db as db


def test_init_db_creates_tables(test_db):
    with db.get_connection() as con:
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"users", "sessions", "brews", "schema_migrations"}.issubset(tables)


def test_connection_enables_sqlite_safety_settings(test_db):
    with db.get_connection() as con:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_get_or_create_user_new(test_db):
    user = db.get_or_create_user("alice@example.com")
    assert user["token"] == "alice@example.com"
    assert user["name"] == "alice"
    assert isinstance(user["id"], int)


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
    with sqlite3.connect(db_path) as con:
        con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, token TEXT UNIQUE, name TEXT NOT NULL)")
        con.execute("INSERT INTO users VALUES (1, 'alice@example.com', 'alice')")
        con.execute("INSERT INTO users VALUES (2, 'alice@company.com', 'alice')")

    db.init_db()

    with db.get_connection() as con:
        names = [row[0] for row in con.execute("SELECT name FROM users ORDER BY id")]
        indexes = {row[1] for row in con.execute("PRAGMA index_list(users)")}
    assert names == ["alice", "alice-2"]
    assert "idx_users_name" in indexes


def test_backup_and_restore_database(test_db, tmp_path):
    user = db.get_or_create_user("backup@example.com")
    backup_path = str(tmp_path / "backup.db")
    assert db.backup_database(backup_path) == backup_path
    assert db.integrity_check(backup_path) == ["ok"]

    with db.get_connection() as con:
        con.execute("DELETE FROM users WHERE id=?", (user["id"],))
    db.restore_database(backup_path)

    with db.get_connection() as con:
        restored = con.execute("SELECT token FROM users WHERE id=?", (user["id"],)).fetchone()
    assert restored[0] == "backup@example.com"


def test_start_session_authenticated(test_db):
    user = db.get_or_create_user("carol@example.com")
    session_id = db.start_session(user["id"])
    assert isinstance(session_id, int)
    with db.get_connection() as con:
        row = con.execute(
            "SELECT user_id, ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] == user["id"]
    assert row[1] is None


def test_start_session_anonymous(test_db):
    session_id = db.start_session(None)
    with db.get_connection() as con:
        row = con.execute(
            "SELECT user_id FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] is None


def test_end_session_stamps_ended_at(test_db):
    user = db.get_or_create_user("dave@example.com")
    session_id = db.start_session(user["id"])
    db.end_session(session_id)
    with db.get_connection() as con:
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
    with db.get_connection() as con:
        row = con.execute(
            "SELECT duration, kind FROM brews WHERE session_id=?", (session_id,)
        ).fetchone()
    assert row[0] == pytest.approx(25.0)
    assert row[1] == "brew"


def test_log_brew_anonymous(test_db):
    t = time.time()
    brew_id = db.log_brew(None, t, t + 5.0, "noise")
    assert isinstance(brew_id, int)
    with db.get_connection() as con:
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
    with db.get_connection() as con:
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
    with db.get_connection() as con:
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
