import asyncio
from contextlib import closing
import os
from queue import Queue
import subprocess
import sys
from unittest.mock import MagicMock, patch

from fastapi import Response
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

import core.db as db
import core.kiosk as kiosk
from api.main import app
from api.routers.health import get_health
from api.routers.kiosk import kiosk_ws


class FakeDevice:
    def __init__(self, sensor=False):
        self.sensor = sensor
        self.alive = False
        self.stopped = False

    def start(self):
        self.alive = True

    def stop(self):
        self.stopped = True
        self.alive = False
        return True

    def status(self):
        status = {
            "connected": True,
            "error": None,
            "thread_alive": self.alive,
        }
        if self.sensor:
            status.update(last_read_at=1000.0, stale_age=0.02)
        else:
            status["last_scan_at"] = None
        return status


@pytest.fixture(autouse=True)
def prevent_test_process_termination(monkeypatch):
    monkeypatch.setattr(kiosk, "_request_process_restart", MagicMock())


def fake_state():
    state = MagicMock()
    state._snapshot.return_value = {"state": "idle"}
    return state


def test_hardware_start_recovers_and_holds_exclusive_lock(tmp_path, monkeypatch):
    database = str(tmp_path / "lifecycle.db")
    monkeypatch.setattr(db, "DB_PATH", database)
    db.init_db()
    session_id = db.start_session(None)
    state = fake_state()
    scanner = FakeDevice()
    sensor = FakeDevice(sensor=True)

    with (
        patch("core.state.SessionState", return_value=state),
        patch("hardware.scanner.QRScanner", return_value=scanner),
        patch("hardware.sensor.VibrationSensor", return_value=sensor),
    ):
        kiosk.start()
        try:
            with closing(db.get_connection()) as con:
                ended_at = con.execute(
                    "SELECT ended_at FROM sessions WHERE id=?", (session_id,)
                ).fetchone()[0]
            assert ended_at is not None
            with pytest.raises(db.MaintenanceLockError):
                with db.maintenance_lock():
                    pass
        finally:
            assert kiosk.stop() is True

    state.shutdown.assert_called_once_with()
    assert scanner.stopped and sensor.stopped
    with db.maintenance_lock():
        pass


def test_contended_hardware_lock_prevents_recovery(tmp_path, monkeypatch):
    database = str(tmp_path / "contended.db")
    monkeypatch.setattr(db, "DB_PATH", database)
    db.init_db()

    with db.maintenance_lock():
        with patch.object(db, "recover_open_sessions", wraps=db.recover_open_sessions) as recover:
            with pytest.raises(db.MaintenanceLockError, match="database is in use"):
                kiosk.start()
    recover.assert_not_called()
    assert kiosk.get_state() is None


def test_api_only_startup_does_not_start_or_recover_hardware(tmp_path, monkeypatch):
    database = str(tmp_path / "api-only.db")
    monkeypatch.setattr(db, "DB_PATH", database)
    monkeypatch.setattr("api.deps.DB_PATH", database)
    monkeypatch.delenv("CREMA_START_HARDWARE", raising=False)
    db.init_db()

    with (
        patch("api.main.kiosk.start") as start,
        patch("api.main.db.recover_open_sessions") as recover,
    ):
        with TestClient(app) as client:
            assert client.get("/").status_code == 200
    start.assert_not_called()
    recover.assert_not_called()


def test_kiosk_loop_exception_requests_supervised_restart(caplog):
    state = fake_state()
    state.on_tick.side_effect = RuntimeError("loop failed")
    kiosk._stop.clear()

    kiosk._run_loop(state, Queue())

    kiosk._request_process_restart.assert_called_once_with()
    assert kiosk._stop.is_set()
    assert "Kiosk hardware loop failed" in caplog.text


def test_stop_retains_owners_and_lock_after_timed_out_join(monkeypatch):
    state = fake_state()
    thread = MagicMock()
    thread.is_alive.return_value = True
    scanner = FakeDevice()
    sensor = FakeDevice(sensor=True)
    lock = MagicMock()
    monkeypatch.setattr(kiosk, "_state", state)
    monkeypatch.setattr(kiosk, "_hw_thread", thread)
    monkeypatch.setattr(kiosk, "_scanner", scanner)
    monkeypatch.setattr(kiosk, "_sensor", sensor)
    monkeypatch.setattr(kiosk, "_maintenance_lock", lock)

    assert kiosk.stop() is False

    thread.join.assert_called_once_with(timeout=3)
    state.shutdown.assert_not_called()
    lock.__exit__.assert_not_called()
    assert kiosk.get_state() is state


def test_health_degrades_when_connected_device_thread_is_dead(monkeypatch):
    monkeypatch.setenv("CREMA_START_HARDWARE", "1")
    response = Response()
    database = MagicMock()
    hardware = {
        "running": True,
        "scanner": {"connected": True, "thread_alive": False},
        "sensor": {"connected": True, "thread_alive": True, "stale_age": 0.02},
    }
    with patch("api.routers.health.kiosk.get_health", return_value=hardware):
        result = get_health(response, database)

    assert response.status_code == 503
    assert result["kiosk"]["sensor"]["stale_age"] == 0.02


@pytest.mark.parametrize("stale_age", [None, 5.01])
def test_health_degrades_when_sensor_samples_are_stale(monkeypatch, stale_age):
    monkeypatch.setenv("CREMA_START_HARDWARE", "1")
    response = Response()
    hardware = {
        "running": True,
        "scanner": {"connected": True, "thread_alive": True},
        "sensor": {
            "connected": True,
            "thread_alive": True,
            "stale_age": stale_age,
        },
    }
    with patch("api.routers.health.kiosk.get_health", return_value=hardware):
        result = get_health(response, MagicMock())

    assert response.status_code == 503
    assert result["status"] == "degraded"


class FakeWebSocket:
    def __init__(self, origin=None):
        self.headers = {} if origin is None else {"origin": origin}
        self.accepted = False
        self.sent = []
        self.close_code = None

    async def accept(self):
        self.accepted = True

    async def send_json(self, value):
        self.sent.append(value)

    async def receive_text(self):
        raise WebSocketDisconnect()

    async def close(self, code, reason):
        self.close_code = code


def test_websocket_closes_retryably_when_snapshot_is_unavailable():
    websocket = FakeWebSocket()
    with patch("api.routers.kiosk.kiosk.get_snapshot", return_value=None):
        asyncio.run(kiosk_ws(websocket))

    assert websocket.accepted is True
    assert websocket.sent == []
    assert websocket.close_code == 1013
    assert websocket not in kiosk._ws_clients


def test_websocket_rejects_origin_outside_configured_allowlist(monkeypatch):
    monkeypatch.setenv("CREMA_CORS_ORIGINS", "http://localhost:8000")
    websocket = FakeWebSocket(origin="https://untrusted.example")

    asyncio.run(kiosk_ws(websocket))

    assert websocket.accepted is False
    assert websocket.close_code == 1008


def test_all_numeric_environment_settings_reject_invalid_values():
    numeric_variables = [
        "CREMA_ADXL_BREW_THRESHOLD",
        "CREMA_ADXL_SAMPLE_RATE",
        "CREMA_MIN_BREW_DURATION",
        "CREMA_BREW_END_SILENCE",
        "CREMA_MIN_VIBRATION_PULSE",
        "CREMA_BREW_CONFIRM_WINDOW",
        "CREMA_ARMED_TIMEOUT",
        "CREMA_SESSION_TIMEOUT",
        "CREMA_SUMMARY_DURATION",
    ]
    environment = os.environ.copy()
    for variable in numeric_variables:
        for other in numeric_variables:
            environment.pop(other, None)
        environment[variable] = "nan"
        result = subprocess.run(
            [sys.executable, "-c", "import config"],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert variable in result.stderr
        assert "finite" in result.stderr or "integer" in result.stderr


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CREMA_ADXL_SAMPLE_RATE", "0"),
        ("CREMA_ADXL_SAMPLE_RATE", "-2"),
        ("CREMA_ADXL_BREW_THRESHOLD", "0"),
        ("CREMA_BREW_END_SILENCE", "0"),
        ("CREMA_MIN_VIBRATION_PULSE", "0"),
        ("CREMA_BREW_CONFIRM_WINDOW", "0"),
        ("CREMA_ARMED_TIMEOUT", "0"),
        ("CREMA_SESSION_TIMEOUT", "0"),
        ("CREMA_MIN_BREW_DURATION", "-1"),
        ("CREMA_SUMMARY_DURATION", "-1"),
    ],
)
def test_numeric_environment_ranges_include_clear_variable_names(variable, value):
    environment = os.environ.copy()
    environment[variable] = value
    result = subprocess.run(
        [sys.executable, "-c", "import config"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert variable in result.stderr
