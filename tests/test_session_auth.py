from contextlib import contextmanager

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from api import auth
from api.routers import auth as auth_router


@contextmanager
def session_client(monkeypatch, *, token="api-secret"):
    monkeypatch.setenv("CREMA_AUTH_MODE", "session")
    monkeypatch.setenv("CREMA_ADMIN_PASSWORD", "correct horse battery")
    monkeypatch.setenv("CREMA_SESSION_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("CREMA_COOKIE_SECURE", "0")
    monkeypatch.setenv("CREMA_SESSION_TTL", "3600")
    monkeypatch.setattr(auth, "_TOKEN", token)
    auth._LOGIN_FAILURES.clear()
    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key=auth.session_secret(),
        session_cookie="crema_session",
        max_age=auth.session_ttl(),
        same_site="strict",
        https_only=False,
    )
    app.include_router(auth_router.router)

    @app.get("/protected", dependencies=[Depends(auth.verify_token)])
    def protected_get():
        return {"ok": True}

    @app.post("/protected", dependencies=[Depends(auth.verify_token)])
    def protected_post():
        return {"ok": True}

    with TestClient(app, base_url="https://crema.test") as client:
        yield client
    auth._LOGIN_FAILURES.clear()


def login(client, password="correct horse battery"):
    return client.post("/auth/login", json={"password": password})


def test_session_login_cookie_and_logout(monkeypatch):
    with session_client(monkeypatch) as client:
        assert client.get("/protected").status_code == 401
        status = client.get("/auth/session")
        assert status.status_code == 200
        assert status.json() == {"mode": "session", "authenticated": False}

        response = login(client)
        assert response.status_code == 200
        assert response.json()["authenticated"] is True
        cookie_directives = response.headers["set-cookie"].lower()
        assert "httponly" in cookie_directives
        assert "samesite=strict" in cookie_directives
        assert "secure" not in cookie_directives
        assert client.get("/protected").status_code == 200
        assert client.get("/auth/session").json()["authenticated"] is True

        assert client.post("/auth/logout").status_code == 200
        assert client.get("/protected").status_code == 401


def test_bearer_remains_available_for_api_clients_in_session_mode(monkeypatch):
    with session_client(monkeypatch) as client:
        response = client.get("/protected", headers={"Authorization": "Bearer api-secret"})
        assert response.status_code == 200


def test_cookie_mutations_require_an_allowed_origin(monkeypatch):
    with session_client(monkeypatch) as client:
        assert login(client).status_code == 200
        response = client.post("/protected", headers={"Origin": "https://attacker.test"})
        assert response.status_code == 403
        response = client.post("/protected", headers={"Origin": "https://crema.test"})
        assert response.status_code == 200


def test_expired_or_tampered_session_is_rejected(monkeypatch):
    request = Request({
        "type": "http",
        "method": "GET",
        "headers": [],
        "session": {"authenticated": True, "expires_at": 1},
    })
    assert not auth._session_authorized(request)
    request.scope["session"]["expires_at"] = auth.time.time() + 60
    assert auth._session_authorized(request)

    with session_client(monkeypatch) as client:
        assert login(client).status_code == 200
        client.cookies.set("crema_session", "tampered", domain="crema.test", path="/")
        assert client.get("/protected").status_code == 401


def test_login_throttling_blocks_repeated_failures(monkeypatch):
    with session_client(monkeypatch) as client:
        for _ in range(5):
            assert login(client, "wrong").status_code == 401
        response = login(client)
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) > 0
        assert client.get("/protected").status_code == 401


def test_successful_login_clears_previous_failures(monkeypatch):
    with session_client(monkeypatch) as client:
        for _ in range(4):
            assert login(client, "wrong").status_code == 401
        assert login(client).status_code == 200
        assert client.post("/auth/logout").status_code == 200
        assert login(client).status_code == 200


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("CREMA_SESSION_SECRET", "short", "CREMA_SESSION_SECRET"),
        ("CREMA_ADMIN_PASSWORD", "short", "CREMA_ADMIN_PASSWORD"),
        ("CREMA_SESSION_TTL", "60", "CREMA_SESSION_TTL"),
        ("CREMA_AUTH_MODE", "unknown", "CREMA_AUTH_MODE"),
    ],
)
def test_invalid_session_configuration_fails_closed(monkeypatch, variable, value, message):
    monkeypatch.setenv("CREMA_AUTH_MODE", "session")
    monkeypatch.setenv("CREMA_ADMIN_PASSWORD", "correct horse battery")
    monkeypatch.setenv("CREMA_SESSION_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("CREMA_SESSION_TTL", "3600")
    monkeypatch.setenv(variable, value)
    with pytest.raises(RuntimeError, match=message):
        auth.validate_auth_configuration()


def test_session_configuration_allows_non_loopback_binding(monkeypatch):
    monkeypatch.setenv("CREMA_AUTH_MODE", "session")
    monkeypatch.setenv("CREMA_ADMIN_PASSWORD", "correct horse battery")
    monkeypatch.setenv("CREMA_SESSION_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.delenv("CREMA_API_TOKEN", raising=False)
    monkeypatch.delenv("CREMA_ALLOW_INSECURE", raising=False)
    auth.require_safe_binding("0.0.0.0")
