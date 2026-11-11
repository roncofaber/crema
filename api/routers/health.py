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
    scanner_ready = (
        hardware["scanner"]["connected"]
        and hardware["scanner"].get("thread_alive", True)
    )
    sensor_stale_age = hardware["sensor"].get("stale_age")
    sensor_ready = (
        hardware["sensor"]["connected"]
        and hardware["sensor"].get("thread_alive", True)
        and sensor_stale_age is not None
        and sensor_stale_age <= 5
    )
    healthy = not hardware_expected or (
        hardware["running"] and scanner_ready and sensor_ready
    )
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "degraded",
        "mode": "hardware" if hardware_expected else "api-only",
        "database": {"connected": True},
        "kiosk": hardware,
    }
