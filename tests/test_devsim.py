import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devsim.devices import SimulatedScanner, SimulatedSensor
from devsim.routes import router
import core.kiosk as kiosk


@pytest.fixture
def simulator(test_db):
    app = FastAPI()
    app.include_router(router)
    kiosk.start_simulator(SimulatedScanner(), SimulatedSensor())
    with TestClient(app) as client:
        yield client
    assert kiosk.stop()


def test_simulator_drives_real_session_transitions_without_hardware_recovery(simulator):
    response = simulator.get("/dev/simulator/snapshot")
    assert response.status_code == 200
    assert response.json()["state"] == "idle"
    assert response.json()["hardware"]["running"] is True

    response = simulator.post("/dev/simulator/state/armed")
    assert response.json()["user"] == "alice"
    response = simulator.post("/dev/simulator/scan", json={"token": "bob@example.com"})
    assert response.json()["user"] == "bob"

    assert simulator.post("/dev/simulator/brew/start").json()["state"] == "brewing"
    response = simulator.post("/dev/simulator/brew/end", json={"duration": 25})
    assert response.json()["state"] == "armed"
    assert response.json()["last_brew_id"] is not None

    assert simulator.post("/dev/simulator/state/summary").json()["state"] == "summary"
    assert simulator.post("/dev/simulator/state/rating").json()["state"] == "armed"
    assert simulator.post("/dev/simulator/state/anon_brew").json()["state"] == "anon_brew"
    assert simulator.post("/dev/simulator/state/idle").json()["state"] == "idle"


def test_simulator_fault_injection_and_input_validation(simulator):
    response = simulator.post("/dev/simulator/hardware?degraded=true")
    assert response.status_code == 200
    health = response.json()
    assert health["scanner"]["connected"] is False
    assert health["sensor"]["stale_age"] >= 10

    response = simulator.post("/dev/simulator/hardware?degraded=false&missing_samples=true")
    assert response.json()["sensor"]["last_read_at"] is None
    assert simulator.post("/dev/simulator/disconnect").status_code == 200
    assert simulator.get("/dev/simulator/snapshot").status_code == 503
    assert simulator.post("/dev/simulator/restore").status_code == 200
    assert simulator.get("/dev/simulator/snapshot").status_code == 200
    assert simulator.post("/dev/simulator/state/handoff").json()["user"] == "bob"
    assert simulator.post("/dev/simulator/state/unknown").status_code == 404
    assert simulator.post("/dev/simulator/scan", json={"token": "invalid"}).status_code == 422
    assert simulator.post("/dev/simulator/brew/end", json={"duration": 0}).status_code == 422


def test_simulator_panel_is_served_without_auth(test_db):
    import devsim

    app = FastAPI()
    app.include_router(devsim.router())
    with patch("api.auth._TOKEN", "secret"), TestClient(app) as client:
        response = client.get("/dev/simulator/panel")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "/dev/simulator" in response.text
        assert client.get("/dev/simulator/snapshot").status_code == 401


def test_simulated_sensor_produces_continuous_samples():
    sensor = SimulatedSensor()
    sensor.start()
    initial_read = sensor.last_read_at
    deadline = time.monotonic() + 2
    try:
        while sensor.last_read_at == initial_read and time.monotonic() < deadline:
            time.sleep(0.01)
        assert sensor.last_read_at > initial_read
        assert sensor.status()["stale_age"] < 1
    finally:
        sensor.stop()
    assert sensor.status()["thread_alive"] is False


def test_simulator_lifecycle_does_not_acquire_maintenance_lock_or_recover(test_db):
    with patch("core.db.maintenance_lock") as lock, patch("core.db.recover_open_sessions") as recover:
        kiosk.start_simulator(SimulatedScanner(), SimulatedSensor())
        assert kiosk.stop()
    lock.assert_not_called()
    recover.assert_not_called()
