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
