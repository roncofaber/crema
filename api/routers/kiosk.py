import logging
from typing import Literal
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import origin_allowed, verify_token
from api.schemas import OkResponse
import core.kiosk as kiosk
import core.db as db

log = logging.getLogger(__name__)
router = APIRouter()


# ── WebSocket ─────────────────────────────────────────────────────────────────


def _origin_allowed(websocket: WebSocket) -> bool:
    return origin_allowed(
        websocket.headers.get("origin"),
        websocket.headers.get("host"),
    )


@router.websocket("/ws/kiosk")
async def kiosk_ws(websocket: WebSocket):
    """Real-time kiosk state stream. No auth - local display only."""
    if not _origin_allowed(websocket):
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    await websocket.accept()
    snapshot = kiosk.get_snapshot()
    if snapshot is None:
        await websocket.close(code=1013, reason="Kiosk state unavailable")
        return
    kiosk.register_ws(websocket)
    try:
        await websocket.send_json(snapshot)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        kiosk.unregister_ws(websocket)


# ── REST endpoints ────────────────────────────────────────────────────────────

class SessionRequest(BaseModel):
    session_started_at: float


class BrewOptions(SessionRequest):
    shot_type: Literal["single", "double"]
    decaf: bool


class RateRequest(BaseModel):
    brew_id: int
    rating: int = Field(..., ge=1, le=5)


def _require_state():
    state = kiosk.get_state()
    if state is None:
        raise HTTPException(status_code=503, detail="Kiosk not running")
    return state


@router.post("/kiosk/logout", response_model=OkResponse, dependencies=[Depends(verify_token)])
def kiosk_logout(req: SessionRequest):
    """End the current user session (only works in ARMED state)."""
    state = _require_state()
    if not state.force_logout(req.session_started_at):
        raise HTTPException(status_code=409, detail="Session changed; refresh and retry")
    return {"ok": True}


@router.post("/kiosk/brew-options", response_model=OkResponse, dependencies=[Depends(verify_token)])
def kiosk_brew_options(opts: BrewOptions):
    """Set sticky shot type and decaf flag for the current session."""
    state = _require_state()
    if not state.set_brew_options(opts.shot_type, opts.decaf, opts.session_started_at):
        raise HTTPException(status_code=409, detail="Session changed; refresh and retry")
    return {"ok": True}


@router.post("/kiosk/rate", response_model=OkResponse, dependencies=[Depends(verify_token)])
def kiosk_rate(req: RateRequest):
    """Submit a 1–5 star rating for a completed brew."""
    if not db.rate_brew(req.brew_id, req.rating):
        raise HTTPException(status_code=404, detail="Brew not found")
    return {"ok": True}
