import pytest
from click.testing import CliRunner

import api.auth as auth
import cli.main as cli_main
import main


def test_loopback_binding_does_not_require_token(monkeypatch):
    monkeypatch.delenv("CREMA_API_TOKEN", raising=False)
    monkeypatch.delenv("CREMA_ALLOW_INSECURE", raising=False)
    auth.require_safe_binding("127.0.0.1")


def test_non_loopback_binding_requires_token_or_explicit_override(monkeypatch):
    monkeypatch.delenv("CREMA_API_TOKEN", raising=False)
    monkeypatch.delenv("CREMA_ALLOW_INSECURE", raising=False)
    with pytest.raises(RuntimeError, match="CREMA_API_TOKEN"):
        auth.require_safe_binding("0.0.0.0")

    monkeypatch.setenv("CREMA_ALLOW_INSECURE", "1")
    auth.require_safe_binding("0.0.0.0")


def test_non_loopback_binding_accepts_token(monkeypatch):
    monkeypatch.setenv("CREMA_API_TOKEN", "secret")
    auth.require_safe_binding("0.0.0.0")


def test_non_ascii_authorization_is_compared_without_server_errors(monkeypatch):
    monkeypatch.setattr(auth, "_TOKEN", "sëcret")
    assert auth._bearer_authorized("Bearer sëcret")
    assert not auth._bearer_authorized("Bearer other")


def test_serve_defaults_to_loopback(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    result = CliRunner().invoke(cli_main.cli, ["serve"])
    assert result.exit_code == 0, result.output
    assert calls[0]["host"] == "127.0.0.1"


def test_main_defaults_to_loopback(monkeypatch):
    calls = []
    monkeypatch.delenv("CREMA_HOST", raising=False)
    monkeypatch.delenv("CREMA_API_TOKEN", raising=False)
    monkeypatch.delenv("CREMA_ALLOW_INSECURE", raising=False)
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: calls.append(kwargs))

    main.main()

    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["log_config"]["loggers"]["uvicorn.access"]["propagate"] is True


def test_main_rejects_unsafe_public_binding(monkeypatch):
    monkeypatch.setenv("CREMA_HOST", "0.0.0.0")
    monkeypatch.delenv("CREMA_API_TOKEN", raising=False)
    monkeypatch.delenv("CREMA_ALLOW_INSECURE", raising=False)

    with pytest.raises(RuntimeError, match="CREMA_API_TOKEN"):
        main.main()


def test_cors_defaults_and_explicit_empty_configuration(monkeypatch):
    monkeypatch.delenv("CREMA_CORS_ORIGINS", raising=False)
    assert auth.cors_origins() == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert auth.origin_allowed("http://example.test", "example.test")
    assert not auth.origin_allowed("http://attacker.test", "example.test")

    monkeypatch.setenv("CREMA_CORS_ORIGINS", "")
    assert auth.cors_origins() == []
    assert not auth.origin_allowed("http://localhost:5173", "example.test")


def test_cors_explicit_allowlist_and_wildcard(monkeypatch):
    monkeypatch.setenv("CREMA_CORS_ORIGINS", "https://dashboard.example/")
    assert auth.origin_allowed("https://dashboard.example", "api.example")
    assert not auth.origin_allowed("https://other.example", "api.example")

    monkeypatch.setenv("CREMA_CORS_ORIGINS", "*")
    assert auth.origin_allowed("https://other.example", "api.example")
