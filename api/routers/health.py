import os
import sqlite3

from fastapi import APIRouter, Depends, Response, status

from api.deps import get_db
from api.schemas import Health
import core.kiosk as kiosk

router = APIRouter()


@router.get("/health", response_model=Health)
def get_health(response: Response, db: sqlite3.Connection = Depends(get_db)):
    db.execute("SELECT 1").fetchone()
    hardware_expected = os.getenv("CREMA_START_HARDWARE") == "1"
    hardware = kiosk.get_health()
    devices_ready = hardware["scanner"]["connected"] and hardware["sensor"]["connected"]
    healthy = not hardware_expected or (hardware["running"] and devices_ready)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "degraded",
        "mode": "hardware" if hardware_expected else "api-only",
        "database": {"connected": True},
        "kiosk": hardware,
    }
