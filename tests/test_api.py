import sqlite3
import time as time_mod
from contextlib import closing
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
import core.db as db_module
from api.main import app
from api.deps import get_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("CREMA_START_HARDWARE", raising=False)
    monkeypatch.setattr("core.db.DB_PATH", db_path)
    monkeypatch.setattr("api.deps.DB_PATH", db_path)
    db_module.init_db()

    def override_get_db():
        con = db_module.get_connection(db_path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_list_users_empty(client):
    resp = client.get("/users/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_production_connection_pragmas(client):
    dependency = get_db()
    con = next(dependency)
    try:
        assert con.row_factory is sqlite3.Row
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        dependency.close()


def test_list_users(client):
    db_module.get_or_create_user("alice@example.com")
    resp = client.get("/users/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "alice"
    assert data[0]["token"] == "alice@example.com"
    assert data[0]["total_brews"] == 0


def test_get_user(client):
    db_module.get_or_create_user("alice@example.com")
    resp = client.get("/users/alice")
    assert resp.status_code == 200
    assert resp.json()["name"] == "alice"


def test_get_user_not_found(client):
    resp = client.get("/users/nobody")
    assert resp.status_code == 404


def test_patch_user_name(client):
    db_module.get_or_create_user("alice@example.com")
    resp = client.patch("/users/alice", json={"name": "Alice"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice"


def test_patch_user_name_conflict(client):
    db_module.get_or_create_user("alice@example.com")
    db_module.get_or_create_user("bob@example.com")
    resp = client.patch("/users/alice", json={"name": "bob"})
    assert resp.status_code == 409


def test_patch_user_rejects_empty_name_without_mutation(client):
    db_module.get_or_create_user("alice@example.com")
    resp = client.patch("/users/alice", json={"name": "   "})
    assert resp.status_code == 422
    current = client.get("/users/alice")
    assert current.status_code == 200
    assert current.json()["name"] == "alice"
    assert current.json()["token"] == "alice@example.com"


def test_patch_user_rejects_unbounded_name(client):
    db_module.get_or_create_user("alice@example.com")
    resp = client.patch("/users/alice", json={"name": "x" * 81})
    assert resp.status_code == 422
    assert client.get("/users/alice").status_code == 200


def test_patch_user_normalizes_name_and_token(client):
    db_module.get_or_create_user("alice@example.com")
    resp = client.patch(
        "/users/alice",
        json={"name": "  Alice  ", "token": "  ALICE@EXAMPLE.COM  "},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice"
    assert resp.json()["token"] == "alice@example.com"
    assert client.get("/users/Alice").status_code == 200


def test_patch_user_rejects_invalid_token_without_mutation(client):
    db_module.get_or_create_user("alice@example.com")
    resp = client.patch("/users/alice", json={"token": "not-an-email"})
    assert resp.status_code == 422
    assert client.get("/users/alice").json()["token"] == "alice@example.com"


def test_patch_user_token_conflict_rolls_back_name(client):
    db_module.get_or_create_user("alice@example.com")
    db_module.get_or_create_user("bob@example.com")
    resp = client.patch(
        "/users/alice",
        json={"name": "charlie", "token": " BOB@EXAMPLE.COM "},
    )
    assert resp.status_code == 409
    assert client.get("/users/alice").status_code == 200
    assert client.get("/users/charlie").status_code == 404


def test_list_brews_empty(client):
    resp = client.get("/brews/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_brews(client):
    user = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(user["id"])
    now = time_mod.time()
    brew_id = db_module.log_brew(
        sid, now - 30, now, "brew", shot_type="single", decaf=1
    )
    db_module.rate_brew(brew_id, 5)
    resp = client.get("/brews/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["user"] == "alice"
    assert data[0]["kind"] == "brew"


def test_list_brews_filter_user(client):
    alice = db_module.get_or_create_user("alice@example.com")
    bob   = db_module.get_or_create_user("bob@example.com")
    now = time_mod.time()
    db_module.log_brew(db_module.start_session(alice["id"]), now - 30, now, "brew")
    db_module.log_brew(db_module.start_session(bob["id"]),   now - 30, now, "brew")
    resp = client.get("/brews/?user=alice")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_brews_filter_anonymous_includes_unowned_sessions(client):
    anonymous_session = db_module.start_session(None)
    db_module.log_brew(anonymous_session, 100, 125, "brew")
    user = db_module.get_or_create_user("alice@example.com")
    named_session = db_module.start_session(user["id"])
    db_module.log_brew(named_session, 200, 225, "brew")

    response = client.get("/brews/?user=anonymous")

    assert response.status_code == 200
    assert [(row["started_at"], row["user"]) for row in response.json()] == [
        (100, "anonymous")
    ]


def test_list_brews_combines_shot_decaf_and_date_filters(client):
    user = db_module.get_or_create_user("filters@example.com")
    session_id = db_module.start_session(user["id"])
    db_module.log_brew(session_id, 100, 125, "brew", shot_type="single", decaf=1)
    db_module.log_brew(session_id, 200, 225, "brew", shot_type="single", decaf=0)
    db_module.log_brew(session_id, 300, 325, "brew", shot_type="double", decaf=1)
    db_module.log_brew(session_id, 400, 402, "noise", shot_type="single", decaf=1)

    response = client.get(
        "/brews/?shot_type=single&decaf=true&from_ts=50&to_ts=150"
    )
    assert response.status_code == 200
    assert [row["started_at"] for row in response.json()] == [100]

    response = client.get("/brews/?shot_type=single&decaf=false")
    assert [row["started_at"] for row in response.json()] == [200]
    assert client.get("/brews/?kind=invalid").status_code == 422


def test_list_brews_filter_kind(client):
    user = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(user["id"])
    now = time_mod.time()
    db_module.log_brew(sid, now - 30, now, "brew")
    db_module.log_brew(sid, now - 5,  now, "noise")
    resp = client.get("/brews/?kind=noise")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["kind"] == "noise"


def test_overall_stats_empty(client):
    resp = client.get("/stats/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_brews"] == 0
    assert data["total_users"] == 0
    assert data["top_brewer"] is None
    assert data["average_duration"] == 0
    assert data["average_rating"] is None
    assert data["decaf_brews"] == 0


def test_overall_stats(client):
    alice = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(alice["id"])
    now = time_mod.time()
    db_module.log_brew(sid, now - 30, now, "brew")
    db_module.log_brew(sid, now - 5,  now, "noise")
    resp = client.get("/stats/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_brews"] == 1
    assert data["total_users"] == 1
    assert data["top_brewer"] == "alice"


def test_overall_stats_counts_users_without_brews(client):
    db_module.get_or_create_user("alice@example.com")
    db_module.get_or_create_user("bob@example.com")
    resp = client.get("/stats/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] == 2
    assert data["total_brews"] == 0
    assert data["top_brewer"] is None


def test_daily_stats(client):
    alice = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(alice["id"])
    now = time_mod.time()
    db_module.log_brew(sid, now - 30, now, "brew")
    resp = client.get("/stats/daily")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["brews"] == 1


def test_status_idle(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "idle"
    assert data["user"] is None


def test_status_active(client):
    alice = db_module.get_or_create_user("alice@example.com")
    db_module.start_session(alice["id"])
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "ready"
    assert data["user"] == "alice"
    assert data["session_started_at"] is not None


def test_status_live_brewing(client):
    state = MagicMock()
    state._snapshot.return_value = {
        "state": "brewing",
        "user": "alice",
        "session_started_at": 1000.0,
        "brew_started_at": 1010.0,
    }
    with patch("api.routers.status.kiosk.get_state", return_value=state):
        resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.json() == {
        "state": "brewing",
        "user": "alice",
        "session_started_at": 1000.0,
        "brew_started_at": 1010.0,
    }


def test_health_api_only(client, monkeypatch):
    monkeypatch.delenv("CREMA_START_HARDWARE", raising=False)
    with patch("api.routers.health.kiosk.get_health", return_value={
        "running": False,
        "scanner": {"connected": False, "last_scan_at": None, "error": "not started"},
        "sensor": {"connected": False, "last_read_at": None, "error": "not started"},
    }):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["mode"] == "api-only"


def test_health_degraded_when_hardware_missing(client, monkeypatch):
    monkeypatch.setenv("CREMA_START_HARDWARE", "1")
    with patch("api.routers.health.kiosk.get_health", return_value={
        "running": True,
        "scanner": {"connected": False, "last_scan_at": None, "error": "not found"},
        "sensor": {"connected": True, "last_read_at": 1000.0, "error": None},
    }):
        resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_get_user_brews(client):
    alice = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(alice["id"])
    now = time_mod.time()
    brew_id = db_module.log_brew(
        sid, now - 30, now, "brew", shot_type="single", decaf=1
    )
    db_module.rate_brew(brew_id, 5)
    db_module.log_brew(sid, now - 5,  now, "noise")
    resp = client.get("/users/alice/brews")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    brew = next(item for item in data if item["kind"] == "brew")
    assert brew["shot_type"] == "single"
    assert brew["decaf"] is True
    assert brew["rating"] == 5


def test_get_user_brews_filter_kind(client):
    alice = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(alice["id"])
    now = time_mod.time()
    db_module.log_brew(sid, now - 30, now, "brew")
    db_module.log_brew(sid, now - 5,  now, "noise")
    resp = client.get("/users/alice/brews?kind=brew")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["kind"] == "brew"


def test_list_brews_rejects_nonpositive_limit(client):
    assert client.get("/brews/?limit=0").status_code == 422


def test_daily_stats_rejects_nonpositive_days(client):
    assert client.get("/stats/daily?days=0").status_code == 422


def test_delete_user(client):
    alice = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(alice["id"])
    db_module.log_brew(sid, time_mod.time() - 30, time_mod.time(), "brew")
    db_module.end_session(sid)
    resp = client.delete("/users/alice")
    assert resp.status_code == 204
    assert client.get("/users/alice").status_code == 404


def test_delete_user_with_open_session_preserves_kiosk_state(client):
    alice = db_module.get_or_create_user("alice@example.com")
    db_module.start_session(alice["id"])
    with patch("core.kiosk.get_state", side_effect=AssertionError("hardware accessed")) as state:
        resp = client.delete("/users/alice")
    assert resp.status_code == 409
    state.assert_not_called()
    assert client.get("/users/alice").status_code == 200
    status = client.get("/status")
    assert status.status_code == 200
    assert status.json()["state"] == "ready"
    assert status.json()["user"] == "alice"


def test_delete_user_not_found(client):
    resp = client.delete("/users/nobody")
    assert resp.status_code == 404


def test_auth_disabled_by_default(client):
    resp = client.get("/users/")
    assert resp.status_code == 200


def test_auth_required_when_token_set(client, monkeypatch):
    monkeypatch.setattr("api.auth._TOKEN", "secret")
    resp = client.get("/users/")
    assert resp.status_code == 401


def test_auth_valid_token(client, monkeypatch):
    monkeypatch.setattr("api.auth._TOKEN", "secret")
    resp = client.get("/users/", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200


def test_auth_invalid_token(client, monkeypatch):
    monkeypatch.setattr("api.auth._TOKEN", "secret")
    resp = client.get("/users/", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


# ── Kiosk endpoints ───────────────────────────────────────────────────────────


def test_kiosk_logout_no_state(client):
    """Returns 503 when kiosk hardware is not running."""
    with patch("api.routers.kiosk.kiosk.get_state", return_value=None):
        resp = client.post("/kiosk/logout", json={"session_started_at": 1000.0})
    assert resp.status_code == 503


def test_kiosk_logout_calls_force_logout(client):
    mock_state = MagicMock()
    mock_state.force_logout.return_value = True
    with patch("api.routers.kiosk.kiosk.get_state", return_value=mock_state):
        resp = client.post("/kiosk/logout", json={"session_started_at": 1000.0})
    assert resp.status_code == 200
    mock_state.force_logout.assert_called_once_with(1000.0)


def test_kiosk_logout_rejects_stale_session(client):
    mock_state = MagicMock()
    mock_state.force_logout.return_value = False
    with patch("api.routers.kiosk.kiosk.get_state", return_value=mock_state):
        resp = client.post("/kiosk/logout", json={"session_started_at": 999.0})
    assert resp.status_code == 409


def test_kiosk_brew_options(client):
    mock_state = MagicMock()
    mock_state.set_brew_options.return_value = True
    with patch("api.routers.kiosk.kiosk.get_state", return_value=mock_state):
        resp = client.post(
            "/kiosk/brew-options",
            json={"shot_type": "single", "decaf": True, "session_started_at": 1000.0},
        )
    assert resp.status_code == 200
    mock_state.set_brew_options.assert_called_once_with("single", True, 1000.0)


def test_kiosk_brew_options_rejects_stale_session(client):
    mock_state = MagicMock()
    mock_state.set_brew_options.return_value = False
    with patch("api.routers.kiosk.kiosk.get_state", return_value=mock_state):
        resp = client.post(
            "/kiosk/brew-options",
            json={"shot_type": "single", "decaf": True, "session_started_at": 999.0},
        )
    assert resp.status_code == 409


def test_kiosk_rate_valid(client):
    user = db_module.get_or_create_user("rater@example.com")
    sid = db_module.start_session(user["id"])
    now = time_mod.time()
    brew_id = db_module.log_brew(sid, now - 30, now, "brew")
    resp = client.post("/kiosk/rate", json={"brew_id": brew_id, "rating": 4})
    assert resp.status_code == 200
    with closing(db_module.get_connection()) as con:
        row = con.execute("SELECT rating FROM brews WHERE id=?", (brew_id,)).fetchone()
    assert row[0] == 4


def test_kiosk_rate_invalid_range(client):
    resp = client.post("/kiosk/rate", json={"brew_id": 1, "rating": 6})
    assert resp.status_code == 422


def test_kiosk_rate_invalid_range_zero(client):
    resp = client.post("/kiosk/rate", json={"brew_id": 1, "rating": 0})
    assert resp.status_code == 422


def test_kiosk_rate_missing_brew(client):
    resp = client.post("/kiosk/rate", json={"brew_id": 9999, "rating": 4})
    assert resp.status_code == 404
