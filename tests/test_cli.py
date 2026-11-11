import subprocess
from contextlib import closing
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import core.db as db_module
from cli.db import db as db_commands
from cli.logs import logs
from cli.service import service
from cli.stats import stats
from cli.users import users


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cli.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    monkeypatch.setattr("cli.users.DB_PATH", db_path)
    monkeypatch.setattr("cli.db.DB_PATH", db_path)
    db_module.init_db()
    return db_path


def test_cli_rename_normalizes_name(cli_db):
    db_module.get_or_create_user("alice@example.com")
    result = CliRunner().invoke(users, ["rename", "alice", "  Alice Smith  "])
    assert result.exit_code == 0, result.output
    with closing(db_module.get_connection()) as con:
        row = con.execute("SELECT name FROM users").fetchone()
    assert row[0] == "Alice Smith"


@pytest.mark.parametrize("new_name", ["", "   ", "x" * 81])
def test_cli_rename_rejects_invalid_name_without_mutation(cli_db, new_name):
    db_module.get_or_create_user("alice@example.com")
    result = CliRunner().invoke(users, ["rename", "alice", new_name])
    assert result.exit_code != 0
    with closing(db_module.get_connection()) as con:
        row = con.execute("SELECT name, token FROM users").fetchone()
    assert row == ("alice", "alice@example.com")


def test_cli_edit_normalizes_name_and_token(cli_db, monkeypatch):
    db_module.get_or_create_user("alice@example.com")
    monkeypatch.setattr(
        "cli.users.click.edit",
        lambda original: "name:  Alice Smith  \ntoken:  PERSON@EXAMPLE.COM  \n",
    )
    result = CliRunner().invoke(users, ["edit", "alice"])
    assert result.exit_code == 0, result.output
    with closing(db_module.get_connection()) as con:
        row = con.execute("SELECT name, token FROM users").fetchone()
    assert row == ("Alice Smith", "person@example.com")


def test_cli_edit_rejects_empty_name_without_mutation(cli_db, monkeypatch):
    db_module.get_or_create_user("alice@example.com")
    monkeypatch.setattr(
        "cli.users.click.edit",
        lambda original: "name:   \ntoken: new@example.com\n",
    )
    result = CliRunner().invoke(users, ["edit", "alice"])
    assert result.exit_code != 0
    with closing(db_module.get_connection()) as con:
        row = con.execute("SELECT name, token FROM users").fetchone()
    assert row == ("alice", "alice@example.com")


def test_cli_delete_rejects_open_session(cli_db):
    alice = db_module.get_or_create_user("alice@example.com")
    db_module.start_session(alice["id"])
    result = CliRunner().invoke(users, ["delete", "alice"], input="y\n")
    assert result.exit_code != 0
    assert "open session" in result.output
    with closing(db_module.get_connection()) as con:
        user = con.execute("SELECT id FROM users").fetchone()
        session = con.execute("SELECT ended_at FROM sessions").fetchone()
    assert user is not None
    assert session[0] is None


def test_cli_delete_allows_closed_session(cli_db):
    alice = db_module.get_or_create_user("alice@example.com")
    session_id = db_module.start_session(alice["id"])
    db_module.end_session(session_id)
    result = CliRunner().invoke(users, ["delete", "alice"], input="y\n")
    assert result.exit_code == 0, result.output
    with closing(db_module.get_connection()) as con:
        assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_reclassify_clears_noise_fields_and_preserves_brew_fields(cli_db, monkeypatch):
    monkeypatch.setattr("cli.db.MIN_BREW_DURATION", 10)
    alice = db_module.get_or_create_user("alice@example.com")
    session_id = db_module.start_session(alice["id"])
    short_id = db_module.log_brew(
        session_id, 100, 105, "brew", shot_type="single", decaf=1
    )
    long_id = db_module.log_brew(session_id, 200, 212, "noise")
    db_module.end_session(session_id)
    db_module.rate_brew(short_id, 5)
    with closing(db_module.get_connection()) as con:
        with con:
            con.execute(
                "UPDATE brews SET shot_type = 'double', decaf = 0, rating = 4 WHERE id = ?",
                (long_id,),
            )

    result = CliRunner().invoke(db_commands, ["reclassify"], input="y\n")
    assert result.exit_code == 0, result.output

    with closing(db_module.get_connection()) as con:
        short = con.execute(
            "SELECT kind, shot_type, decaf, rating FROM brews WHERE id = ?",
            (short_id,),
        ).fetchone()
        upgraded = con.execute(
            "SELECT kind, shot_type, decaf, rating FROM brews WHERE id = ?",
            (long_id,),
        ).fetchone()
    assert short == ("noise", None, None, None)
    assert upgraded == ("brew", "double", 0, 4)


def test_reclassify_abort_does_not_mutate(cli_db, monkeypatch):
    monkeypatch.setattr("cli.db.MIN_BREW_DURATION", 10)
    brew_id = db_module.log_brew(None, 100, 105, "brew", shot_type="double", decaf=0)
    result = CliRunner().invoke(db_commands, ["reclassify"], input="n\n")
    assert result.exit_code != 0
    with closing(db_module.get_connection()) as con:
        row = con.execute(
            "SELECT kind, shot_type, decaf FROM brews WHERE id = ?", (brew_id,)
        ).fetchone()
    assert row == ("brew", "double", 0)


def test_reclassify_requires_exclusive_maintenance_lock(cli_db):
    brew_id = db_module.log_brew(None, 100, 105, "brew")
    with db_module.maintenance_lock(cli_db):
        result = CliRunner().invoke(db_commands, ["reclassify"], input="y\n")

    assert result.exit_code != 0
    assert "Stop CREMA services" in result.output
    with closing(db_module.get_connection()) as con:
        kind = con.execute("SELECT kind FROM brews WHERE id = ?", (brew_id,)).fetchone()[0]
    assert kind == "brew"


def test_restore_uses_and_releases_maintenance_lock(cli_db, tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "BACKUP_DIR", str(tmp_path / "backups"))
    user = db_module.get_or_create_user("alice@example.com")
    source = str(tmp_path / "backup.db")
    db_module.backup_database(source)
    with closing(db_module.get_connection()) as con:
        with con:
            con.execute("DELETE FROM users WHERE id = ?", (user["id"],))

    result = CliRunner().invoke(db_commands, ["restore", source], input="y\n")
    assert result.exit_code == 0, result.output
    assert "Previous database saved as:" in result.output
    with closing(db_module.get_connection()) as con:
        restored = con.execute(
            "SELECT token FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
    assert restored[0] == "alice@example.com"
    with db_module.maintenance_lock(cli_db):
        pass


def test_restore_requires_exclusive_maintenance_lock(cli_db, tmp_path):
    source = tmp_path / "backup.db"
    source.write_bytes(b"not reached while the live database is locked")
    with db_module.maintenance_lock(cli_db):
        with patch("cli.db.core_db.restore_database") as restore:
            result = CliRunner().invoke(
                db_commands, ["restore", str(source)], input="y\n"
            )
    assert result.exit_code != 0
    assert "Database is in use" in result.output
    restore.assert_not_called()


def test_service_failure_is_click_error():
    completed = subprocess.CompletedProcess(["systemctl"], returncode=1)
    with patch("cli.service.subprocess.run", return_value=completed):
        result = CliRunner().invoke(service, ["restart"])
    assert result.exit_code != 0
    assert "status 1" in result.output


def test_logs_failure_is_click_error():
    completed = subprocess.CompletedProcess(["journalctl"], returncode=2)
    with patch("cli.logs.subprocess.run", return_value=completed):
        result = CliRunner().invoke(logs, ["kiosk"])
    assert result.exit_code != 0
    assert "status 2" in result.output


def test_stats_uses_configured_database_and_closes_connection(cli_db):
    alice = db_module.get_or_create_user("alice@example.com")
    session_id = db_module.start_session(alice["id"], started_at=100)
    db_module.log_brew(session_id, 100, 130, "brew")
    db_module.log_brew(session_id, 200, 205, "noise")

    result = CliRunner().invoke(stats)

    assert result.exit_code == 0, result.output
    assert "alice" in result.output
    assert "Count: 1" in result.output
