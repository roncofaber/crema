from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.logging import JsonFormatter
from api.main import app
import core.db as db
from core.state import SessionState, State
from ops.monitoring import parse_metrics, probe_unit, unit_path


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = str(tmp_path / "operations.db")
    monkeypatch.delenv("CREMA_START_HARDWARE", raising=False)
    monkeypatch.setattr("core.db.DB_PATH", database)
    monkeypatch.setattr("api.deps.DB_PATH", database)
    db.init_db()

    def override_get_db():
        con = db.get_connection(database, check_same_thread=False)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_metrics_use_bounded_routes_and_exclude_identity(client):
    db.get_or_create_user("metric-user@example.com")
    assert client.get("/users/metric-user").status_code == 200
    assert client.get("/users/metric-user/made-up/path").status_code == 404

    response = client.get("/api/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert 'route="/users/{name}"' in response.text
    assert 'route="unmatched"' in response.text
    assert "metric-user" not in response.text
    assert "example.com" not in response.text
    assert "/users/metric-user" not in response.text
    assert 'crema_database_brews{kind="brew"} 0' in response.text


def test_metrics_honor_bearer_authentication(client):
    with patch("api.auth._TOKEN", "operations-secret"):
        assert client.get("/api/metrics").status_code == 401
        response = client.get(
            "/api/metrics", headers={"Authorization": "Bearer operations-secret"}
        )
    assert response.status_code == 200
    assert "crema_up 1" in response.text


def test_metrics_render_session_and_database_without_labels_for_users(client):
    user = db.get_or_create_user("private-name@example.com")
    session_id = db.start_session(user["id"])
    db.log_brew(session_id, 100, 125, "brew")
    state = SessionState()
    state.transition(State.ARMED)
    snapshot = {
        **state._snapshot(),
        "hardware": {"running": False},
    }

    with (
        patch("core.kiosk.get_snapshot", return_value=snapshot),
        patch("core.kiosk.get_health", return_value={
            "running": False,
            "scanner": {"connected": False},
            "sensor": {"connected": False, "stale_age": None},
        }),
    ):
        from core.monitoring import render_prometheus

        with closing(db.get_connection()) as con:
            rendered = render_prometheus(con)

    assert 'crema_kiosk_state{state="armed"} 1' in rendered
    assert 'crema_database_brews{kind="brew"} 1' in rendered
    assert "private-name" not in rendered


def test_json_formatter_preserves_structured_event_and_escapes_newlines():
    import logging

    record = logging.LogRecord(
        "core.state", logging.INFO, __file__, 1,
        "Kiosk state transition", (), None,
    )
    record.event = "kiosk_transition"
    record.from_state = "idle"
    record.to_state = "armed"

    rendered = JsonFormatter().format(record)
    payload = json.loads(rendered)

    assert rendered.count("\n") == 0
    assert payload["event"] == "kiosk_transition"
    assert payload["from_state"] == "idle"
    assert payload["to_state"] == "armed"
    assert payload["message"] == "Kiosk state transition"
    assert payload["timestamp"].endswith("Z")


def test_application_jsonl_file_records_actual_transition(tmp_path):
    output = tmp_path / "crema.jsonl"
    database = tmp_path / "json-log.db"
    environment = os.environ.copy()
    environment.update(
        CREMA_LOG_FORMAT="jsonl",
        CREMA_LOG_FILE=str(output),
        CREMA_DB_PATH=str(database),
        PYTHONPATH=str(Path(__file__).resolve().parents[1]),
    )
    code = """
from api.logging import configure_logging
configure_logging()
from core.state import SessionState, State
SessionState().transition(State.ARMED)
"""
    subprocess.run(
        [sys.executable, "-c", code], env=environment, check=True,
        capture_output=True, text=True,
    )

    lines = output.read_text().splitlines()
    record = json.loads(lines[-1])
    assert len(lines) == 1
    assert record["event"] == "kiosk_transition"
    assert record["from_state"] == "idle"
    assert record["to_state"] == "armed"


def test_uvicorn_child_configures_shared_jsonl_handlers(tmp_path):
    output = tmp_path / "uvicorn.jsonl"
    environment = os.environ.copy()
    environment.update(
        CREMA_LOG_FORMAT="jsonl",
        CREMA_LOG_FILE=str(output),
        PYTHONPATH=str(Path(__file__).resolve().parents[1]),
    )
    code = """
import logging
import uvicorn
from api.logging import uvicorn_log_config
config = uvicorn.Config(
    "api.main:app", log_level="info", log_config=uvicorn_log_config(),
    use_colors=False,
)
config.configure_logging()
assert logging.getLogger().handlers, "reload child has no root handlers"
logging.getLogger("uvicorn.error").info("server ready")
logging.getLogger("uvicorn.access").info(
    '%s - "%s" %s', "127.0.0.1:1234", "GET /health HTTP/1.1", 200,
)
logging.getLogger("core.test").info("application ready")
"""
    subprocess.run(
        [sys.executable, "-c", code], env=environment, check=True,
        capture_output=True, text=True,
    )

    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert [record["logger"] for record in records] == [
        "uvicorn.error", "uvicorn.access", "core.test",
    ]
    assert records[0]["message"] == "server ready"
    assert "GET /health HTTP/1.1" in records[1]["message"]
    assert records[2]["message"] == "application ready"
    assert all(record["timestamp"].endswith("Z") for record in records)


def test_backup_cycles_verify_and_prune_only_generated_files(test_db, tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    monkeypatch.setattr(db, "BACKUP_DIR", str(backups))
    user = db.get_or_create_user("backup@example.com")
    session_id = db.start_session(user["id"])
    db.log_brew(session_id, 100, 125, "brew", shot_type="single", decaf=1)

    created = [db.backup_database() for _ in range(4)]
    assert len(set(created)) == 4
    assert all(db.integrity_check(path) == ["ok"] for path in created)
    with closing(db.get_connection(created[-1])) as con:
        assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert con.execute("SELECT duration FROM brews").fetchone()[0] == 25

    unrelated = backups / "espresso-manual.db"
    notes = backups / "notes.txt"
    unrelated.write_text("keep me")
    notes.write_text("keep me too")
    removed = db.prune_backups(keep=2)

    assert sorted(removed) == sorted(created[:2])
    assert sorted(path.name for path in backups.glob("espresso-*.db")) == sorted(
        [Path(created[-1]).name, Path(created[-2]).name, unrelated.name]
    )
    assert unrelated.read_text() == "keep me"
    assert notes.read_text() == "keep me too"
    with closing(db.get_connection()) as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_backup_age_retention_applies_to_newest_expired_file(test_db, tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    monkeypatch.setattr(db, "BACKUP_DIR", str(backups))
    old = db.backup_database()
    new = db.backup_database()
    timestamp = (datetime.now(timezone.utc) - timedelta(days=31)).timestamp()
    os.utime(old, (timestamp, timestamp))
    os.utime(new, (timestamp, timestamp))

    removed = db.prune_backups(keep=2, max_age_days=30)

    assert sorted(removed) == sorted([old, new])
    assert db.prune_backups(keep=2, max_age_days=30) == []


def test_failed_verification_preserves_existing_destination_and_removes_temporary_files(test_db, tmp_path):
    destination = tmp_path / "destination.db"
    destination.write_bytes(b"previous destination")

    with patch("core.db.integrity_check", return_value=["corrupt"]):
        with pytest.raises(RuntimeError, match="integrity check"):
            db.backup_database(str(destination))

    assert destination.read_bytes() == b"previous destination"
    assert list(tmp_path.glob(".destination.db.backup-*")) == []


def test_backup_refuses_to_replace_live_database(test_db):
    with pytest.raises(ValueError, match="must differ"):
        db.backup_database(test_db)


def test_passive_monitor_parses_only_bounded_gauges():
    text = """
# HELP ignored help text
crema_up 1
crema_kiosk_running 0
crema_kiosk_sensor_stale_seconds 0.125
crema_http_requests_total{route=\"/users/{name}\"} 12
crema_up NaN
"""

    assert parse_metrics(text) == {
        "api_up": 1,
        "kiosk_running": 0,
        "sensor_stale_seconds": 0.125,
    }


def test_passive_monitor_reads_dbus_state_without_controlling_service():
    assert unit_path("crema-kiosk.service") == "/org/freedesktop/systemd1/unit/crema_2dkiosk_2eservice"
    completed = subprocess.CompletedProcess(
        ["busctl"], returncode=0, stdout='s "active"\ns "running"\n', stderr="",
    )
    with patch("ops.monitoring.subprocess.run", return_value=completed) as run:
        result = probe_unit("crema-kiosk.service")

    assert result == {"active_state": "active", "sub_state": "running"}
    assert run.call_args.args[0][:4] == ["busctl", "--system", "get-property", "org.freedesktop.systemd1"]
    assert "start" not in run.call_args.args[0]
    assert "restart" not in run.call_args.args[0]
