import hmac
import os
import threading
import time
from urllib.parse import urlsplit

from fastapi import Header, HTTPException, Request


_TOKEN = os.getenv("CREMA_API_TOKEN", "")
_DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
_LOGIN_FAILURES: dict[str, list[float]] = {}
_LOGIN_LOCK = threading.Lock()
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_BLOCK_SECONDS = 300
_LOGIN_MAX_FAILURES = 5


def auth_mode() -> str:
    return os.getenv("CREMA_AUTH_MODE", "token").strip().lower()


def session_ttl() -> int:
    raw = os.getenv("CREMA_SESSION_TTL", "43200")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("CREMA_SESSION_TTL must be an integer between 300 and 604800") from exc
    if not 300 <= value <= 604800:
        raise RuntimeError("CREMA_SESSION_TTL must be an integer between 300 and 604800")
    return value


def session_secret() -> str:
    secret = os.getenv("CREMA_SESSION_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("CREMA_SESSION_SECRET must contain at least 32 UTF-8 bytes")
    return secret


def session_cookie_secure() -> bool:
    return os.getenv("CREMA_COOKIE_SECURE", "1") == "1"


def validate_auth_configuration() -> None:
    mode = auth_mode()
    if mode not in {"token", "session"}:
        raise RuntimeError("CREMA_AUTH_MODE must be 'token' or 'session'")
    session_ttl()
    if mode == "session":
        session_secret()
        if len(os.getenv("CREMA_ADMIN_PASSWORD", "").encode("utf-8")) < 12:
            raise RuntimeError("CREMA_ADMIN_PASSWORD must contain at least 12 UTF-8 bytes in session mode")


def _session_configuration_available() -> bool:
    if auth_mode() != "session":
        return False
    try:
        validate_auth_configuration()
    except RuntimeError:
        return False
    return True


def _bearer_authorized(authorization: str | None) -> bool:
    if not _TOKEN:
        return False
    supplied = authorization.encode("utf-8") if authorization else b""
    expected = f"Bearer {_TOKEN}".encode("utf-8")
    return hmac.compare_digest(supplied, expected)


def _session_authorized(request: Request) -> bool:
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return False
    if session.get("authenticated") is not True:
        return False
    expires_at = session.get("expires_at")
    if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
        return False
    return time.time() < expires_at


def require_safe_origin(request: Request) -> None:
    if not origin_allowed(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(status_code=403, detail="Origin not allowed")


async def verify_token(request: Request, authorization: str | None = Header(None)):
    mode = auth_mode()
    if mode == "session":
        if _bearer_authorized(authorization):
            return
        if _session_authorized(request):
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                require_safe_origin(request)
            return
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not _TOKEN:
        return
    if not _bearer_authorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_safe_binding(host: str):
    if host.strip("[]").lower() in {"127.0.0.1", "localhost", "::1"}:
        return
    if _session_configuration_available() or os.getenv("CREMA_API_TOKEN") or os.getenv("CREMA_ALLOW_INSECURE") == "1":
        return
    raise RuntimeError(
        "Non-loopback binding requires CREMA_API_TOKEN, a complete session-auth "
        "configuration, or explicit CREMA_ALLOW_INSECURE=1"
    )


def cors_origins() -> list[str]:
    configured = os.getenv("CREMA_CORS_ORIGINS")
    if configured is None:
        return list(_DEFAULT_CORS_ORIGINS)
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]


def origin_allowed(origin: str | None, host: str | None) -> bool:
    if origin is None:
        return True
    origin = origin.rstrip("/")
    allowed = cors_origins()
    if "*" in allowed or origin in allowed:
        return True
    if host is None:
        return False
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host.lower()


def password_matches(supplied: str) -> bool:
    expected = os.getenv("CREMA_ADMIN_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def login_retry_after(client: str, now: float | None = None) -> int:
    current = time.monotonic() if now is None else now
    with _LOGIN_LOCK:
        failures = [stamp for stamp in _LOGIN_FAILURES.get(client, []) if current - stamp < _LOGIN_BLOCK_SECONDS]
        if failures:
            _LOGIN_FAILURES[client] = failures
        else:
            _LOGIN_FAILURES.pop(client, None)
        if len(failures) < _LOGIN_MAX_FAILURES:
            return 0
        return max(1, int(_LOGIN_BLOCK_SECONDS - (current - failures[-_LOGIN_MAX_FAILURES]) + 0.999))


def record_login_failure(client: str, now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    with _LOGIN_LOCK:
        failures = [stamp for stamp in _LOGIN_FAILURES.get(client, []) if current - stamp < _LOGIN_BLOCK_SECONDS]
        failures.append(current)
        _LOGIN_FAILURES[client] = failures
        if len(_LOGIN_FAILURES) > 1024:
            oldest = min(_LOGIN_FAILURES, key=lambda key: _LOGIN_FAILURES[key][-1])
            del _LOGIN_FAILURES[oldest]


def clear_login_failures(client: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.pop(client, None)
