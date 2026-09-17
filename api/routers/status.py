import sqlite3
from fastapi import APIRouter, Depends
from api.deps import get_db
from api.schemas import Status
import core.kiosk as kiosk

router = APIRouter()


@router.get("/status", response_model=Status)
def get_status(db: sqlite3.Connection = Depends(get_db)):
    live_state = kiosk.get_state()
    if live_state is not None:
        snapshot = live_state._snapshot()
        state = "ready" if snapshot["state"] == "armed" else snapshot["state"]
        return {
            "state": state,
            "user": snapshot["user"],
            "session_started_at": snapshot["session_started_at"],
            "brew_started_at": snapshot["brew_started_at"],
        }

    row = db.execute("""
        SELECT s.started_at, u.name
        FROM sessions s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.ended_at IS NULL
        ORDER BY s.started_at DESC
        LIMIT 1
    """).fetchone()

    if not row:
        return {
            "state": "idle",
            "user": None,
            "session_started_at": None,
            "brew_started_at": None,
        }

    return {
        "state": "ready",
        "user": row["name"],
        "session_started_at": row["started_at"],
        "brew_started_at": None,
    }
