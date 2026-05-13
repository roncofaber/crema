import sqlite3
import pytest
from fastapi.testclient import TestClient
import core.db as db_module
from api.main import app
from api.deps import get_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("core.db.DB_PATH", db_path)
    monkeypatch.setattr("api.deps.DB_PATH", db_path)
    db_module.init_db()

    def override_get_db():
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_users_empty(client):
    resp = client.get("/users/")
    assert resp.status_code == 200
    assert resp.json() == []


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


import time as time_mod


def test_list_brews_empty(client):
    resp = client.get("/brews/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_brews(client):
    user = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(user["id"])
    now = time_mod.time()
    db_module.log_brew(sid, now - 30, now, "brew")
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


def test_get_user_brews(client):
    alice = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(alice["id"])
    now = time_mod.time()
    db_module.log_brew(sid, now - 30, now, "brew")
    db_module.log_brew(sid, now - 5,  now, "noise")
    resp = client.get("/users/alice/brews")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


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


def test_delete_user(client):
    alice = db_module.get_or_create_user("alice@example.com")
    sid = db_module.start_session(alice["id"])
    db_module.log_brew(sid, time_mod.time() - 30, time_mod.time(), "brew")
    resp = client.delete("/users/alice")
    assert resp.status_code == 204
    assert client.get("/users/alice").status_code == 404


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

from unittest.mock import MagicMock, patch


def test_kiosk_logout_no_state(client):
    """Returns 503 when kiosk hardware is not running."""
    with patch("api.routers.kiosk.kiosk.get_state", return_value=None):
        resp = client.post("/kiosk/logout")
    assert resp.status_code == 503


def test_kiosk_logout_calls_force_logout(client):
    mock_state = MagicMock()
    with patch("api.routers.kiosk.kiosk.get_state", return_value=mock_state):
        resp = client.post("/kiosk/logout")
    assert resp.status_code == 200
    mock_state.force_logout.assert_called_once()


def test_kiosk_brew_options(client):
    mock_state = MagicMock()
    with patch("api.routers.kiosk.kiosk.get_state", return_value=mock_state):
        resp = client.post("/kiosk/brew-options", json={"shot_type": "single", "decaf": True})
    assert resp.status_code == 200
    mock_state.set_brew_options.assert_called_once_with("single", True)


def test_kiosk_rate_valid(client):
    user = db_module.get_or_create_user("rater@example.com")
    sid = db_module.start_session(user["id"])
    now = time_mod.time()
    brew_id = db_module.log_brew(sid, now - 30, now, "brew")
    resp = client.post("/kiosk/rate", json={"brew_id": brew_id, "rating": 4})
    assert resp.status_code == 200
    with db_module.get_connection() as con:
        row = con.execute("SELECT rating FROM brews WHERE id=?", (brew_id,)).fetchone()
    assert row[0] == 4


def test_kiosk_rate_invalid_range(client):
    resp = client.post("/kiosk/rate", json={"brew_id": 1, "rating": 6})
    assert resp.status_code == 422


def test_kiosk_rate_invalid_range_zero(client):
    resp = client.post("/kiosk/rate", json={"brew_id": 1, "rating": 0})
    assert resp.status_code == 422
