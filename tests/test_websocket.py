import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.main import app
import core.kiosk as kiosk


@pytest.fixture
def client():
    return TestClient(app)


def test_websocket_accepts_same_host_origin(client, monkeypatch):
    snapshot = {"state": "idle"}
    monkeypatch.setattr(kiosk, "get_snapshot", lambda: snapshot)
    monkeypatch.setattr(kiosk, "register_ws", lambda ws: None)
    monkeypatch.setattr(kiosk, "unregister_ws", lambda ws: None)

    with client.websocket_connect(
        "/ws/kiosk", headers={"origin": "http://testserver"}
    ) as websocket:
        assert websocket.receive_json() == snapshot


def test_websocket_accepts_explicitly_allowed_origin(client, monkeypatch):
    monkeypatch.setenv("CREMA_CORS_ORIGINS", "https://dashboard.example")
    monkeypatch.setattr(kiosk, "get_snapshot", lambda: {"state": "idle"})
    monkeypatch.setattr(kiosk, "register_ws", lambda ws: None)
    monkeypatch.setattr(kiosk, "unregister_ws", lambda ws: None)

    with client.websocket_connect(
        "/ws/kiosk", headers={"origin": "https://dashboard.example"}
    ) as websocket:
        assert websocket.receive_json() == {"state": "idle"}


def test_websocket_rejects_unlisted_cross_origin(client, monkeypatch):
    monkeypatch.setenv("CREMA_CORS_ORIGINS", "")
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect(
            "/ws/kiosk", headers={"origin": "https://attacker.example"}
        ):
            pass
    assert caught.value.code == 1008


def test_websocket_closes_retryably_when_kiosk_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(kiosk, "get_snapshot", lambda: None)
    register = []
    monkeypatch.setattr(kiosk, "register_ws", lambda ws: register.append(ws))

    with client.websocket_connect("/ws/kiosk") as websocket:
        with pytest.raises(WebSocketDisconnect) as caught:
            websocket.receive_json()
    assert caught.value.code == 1013
    assert register == []


def test_cors_preflight_uses_default_development_allowlist(client):
    allowed = client.options(
        "/users/",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "GET",
        },
    )
    denied = client.options(
        "/users/",
        headers={
            "origin": "https://attacker.example",
            "access-control-request-method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert denied.status_code == 400
