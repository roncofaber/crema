import time
import pytest
import core.db as db


def test_init_db_creates_tables(test_db):
    with db.get_connection() as con:
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"users", "sessions", "brews"}.issubset(tables)


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
    db.log_brew(session_id, t, t + 25.0, "brew")
    with db.get_connection() as con:
        row = con.execute(
            "SELECT duration, kind FROM brews WHERE session_id=?", (session_id,)
        ).fetchone()
    assert row[0] == pytest.approx(25.0)
    assert row[1] == "brew"


def test_log_brew_anonymous(test_db):
    t = time.time()
    db.log_brew(None, t, t + 5.0, "noise")
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
