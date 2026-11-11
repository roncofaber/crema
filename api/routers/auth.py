import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api import auth
from api.schemas import OkResponse


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class AuthStatus(BaseModel):
    mode: str
    authenticated: bool


class LoginResponse(BaseModel):
    authenticated: bool
    expires_at: float


@router.get("/session", response_model=AuthStatus)
def session_status(request: Request):
    mode = auth.auth_mode()
    return {
        "mode": mode,
        "authenticated": mode == "session" and auth._session_authorized(request),
    }


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(auth.require_safe_origin)])
def login(body: LoginRequest, request: Request):
    if auth.auth_mode() != "session":
        raise HTTPException(status_code=404, detail="Session authentication is disabled")
    auth.validate_auth_configuration()
    client = request.client.host if request.client else "unknown"
    retry_after = auth.login_retry_after(client)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts",
            headers={"Retry-After": str(retry_after)},
        )
    if not auth.password_matches(body.password):
        auth.record_login_failure(client)
        raise HTTPException(status_code=401, detail="Invalid password")
    auth.clear_login_failures(client)
    expires_at = time.time() + auth.session_ttl()
    request.session.clear()
    request.session.update({"authenticated": True, "expires_at": expires_at})
    return {"authenticated": True, "expires_at": expires_at}


@router.post("/logout", response_model=OkResponse, dependencies=[Depends(auth.require_safe_origin)])
def logout(request: Request):
    if auth.auth_mode() == "session":
        request.session.clear()
    return {"ok": True}
