import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import BaseModel
from api.auth import verify_token
import core.kiosk as kiosk
import core.db as db

log = logging.getLogger(__name__)
router = APIRouter()


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/kiosk")
async def kiosk_ws(websocket: WebSocket):
    """Real-time kiosk state stream. No auth — local display only."""
    await websocket.accept()
    kiosk.register_ws(websocket)
    # Send current state immediately on connect
    state = kiosk.get_state()
    if state is not None:
        try:
            await websocket.send_json(state._snapshot())
        except Exception:
            pass
    try:
        while True:
            await websocket.receive_text()  # keep connection alive; client sends nothing
    except WebSocketDisconnect:
        kiosk.unregister_ws(websocket)


# ── REST endpoints ────────────────────────────────────────────────────────────

class BrewOptions(BaseModel):
    shot_type: str   # "single" | "double"
    decaf: bool


class RateRequest(BaseModel):
    brew_id: int
    rating: int      # 1–5


def _require_state():
    state = kiosk.get_state()
    if state is None:
        raise HTTPException(status_code=503, detail="Kiosk not running")
    return state


@router.post("/kiosk/logout", dependencies=[Depends(verify_token)])
def kiosk_logout():
    """End the current user session (only works in ARMED state)."""
    state = _require_state()
    state.force_logout()
    return {"ok": True}


@router.post("/kiosk/brew-options", dependencies=[Depends(verify_token)])
def kiosk_brew_options(opts: BrewOptions):
    """Set sticky shot type and decaf flag for the current session."""
    state = _require_state()
    state.set_brew_options(opts.shot_type, opts.decaf)
    return {"ok": True}


@router.post("/kiosk/rate", dependencies=[Depends(verify_token)])
def kiosk_rate(req: RateRequest):
    """Submit a 1–5 star rating for a completed brew."""
    if not 1 <= req.rating <= 5:
        raise HTTPException(status_code=422, detail="rating must be 1–5")
    db.rate_brew(req.brew_id, req.rating)
    return {"ok": True}
