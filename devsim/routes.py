from pathlib import Path
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from api.auth import verify_token
from core.events import BrewEnd, BrewStart, QRScanned
from core.identity import validate_token
import core.kiosk as kiosk


router = APIRouter(
    prefix="/dev/simulator",
    tags=["simulator"],
    dependencies=[Depends(verify_token)],
)

panel_router = APIRouter(prefix="/dev/simulator", include_in_schema=False)
_PANEL = Path(__file__).with_name("panel.html")


@panel_router.get("/panel")
def panel():
    return FileResponse(_PANEL, media_type="text/html")


class ScanRequest(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def valid_token(cls, value):
        return validate_token(value)


class BrewEndRequest(BaseModel):
    duration: float = Field(default=25, gt=0, le=3600)


def _state():
    state = kiosk.get_state()
    if state is None:
        raise HTTPException(status_code=503, detail="Simulator not running")
    return state


def _devices():
    scanner = kiosk._scanner
    sensor = kiosk._sensor
    if scanner is None or sensor is None:
        raise HTTPException(status_code=503, detail="Simulator devices not running")
    return scanner, sensor


def _identified(token="alice@example.com"):
    state = _state()
    state.shutdown()
    state.handle(QRScanned(token=token))


def _brewing():
    _identified()
    _state().handle(BrewStart())


def _finish_brew(duration=25):
    ended_at = time.time()
    _state().handle(BrewEnd(started_at=ended_at - duration, ended_at=ended_at))


@router.get("/snapshot")
def snapshot():
    result = kiosk.get_snapshot()
    if result is None:
        raise HTTPException(status_code=503, detail="Simulator not running")
    return result


@router.post("/state/{name}")
def set_state(name: str):
    state = _state()
    if name == "idle":
        state.shutdown()
    elif name == "armed":
        _identified()
    elif name == "brewing":
        _brewing()
    elif name == "anon_brew":
        state.shutdown()
        state.handle(BrewStart())
    elif name == "summary":
        _brewing()
        _finish_brew()
        state.force_logout()
    elif name == "rating":
        if state.state.name != "BREWING":
            _brewing()
        _finish_brew()
    elif name == "handoff":
        _identified("bob@example.com")
    else:
        raise HTTPException(status_code=404, detail="Unknown simulator state")
    kiosk.broadcast_now()
    return kiosk.get_snapshot()


@router.post("/scan")
def scan(body: ScanRequest):
    scanner, _ = _devices()
    scanner.scanned()
    _state().handle(QRScanned(token=body.token))
    kiosk.broadcast_now()
    return kiosk.get_snapshot()


@router.post("/brew/start")
def start_brew():
    _state().handle(BrewStart())
    kiosk.broadcast_now()
    return kiosk.get_snapshot()


@router.post("/brew/end")
def end_brew(body: BrewEndRequest):
    _finish_brew(body.duration)
    kiosk.broadcast_now()
    return kiosk.get_snapshot()


@router.post("/disconnect")
async def disconnect():
    kiosk.set_simulator_available(False)
    await kiosk.disconnect_clients()
    return {"available": False}


@router.post("/restore")
def restore():
    kiosk.set_simulator_available(True)
    kiosk.broadcast_now()
    return {"available": True}


@router.post("/hardware")
def set_hardware(degraded: bool = True, missing_samples: bool = False):
    scanner, sensor = _devices()
    scanner.degrade(degraded)
    sensor.configure(degraded=degraded, missing_samples=missing_samples)
    if degraded:
        sensor.last_read_at = time.time() - 12
    elif not missing_samples:
        sensor.last_read_at = time.time()
    kiosk.broadcast_now()
    return kiosk.get_health()
