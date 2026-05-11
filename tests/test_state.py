import time
import pytest
from unittest.mock import patch, MagicMock
import core.db as db
from core.state import SessionState, State
from core.events import QRScanned, BrewStart, BrewEnd
from config import ARMED_TIMEOUT, SESSION_TIMEOUT, MIN_BREW_DURATION


@pytest.fixture
def state(test_db, mock_display):
    return SessionState(mock_display)


def brew_end(duration=25.0):
    now = time.time()
    return BrewEnd(started_at=now - duration, ended_at=now)


def short_brew_end(duration=3.0):
    now = time.time()
    return BrewEnd(started_at=now - duration, ended_at=now)


# -- IDLE transitions --

def test_idle_valid_qr_transitions_to_armed(state, mock_display):
    state.handle(QRScanned(token="alice@example.com"))
    assert state.state == State.ARMED
    mock_display.show_armed.assert_called_once_with("alice", 0)


def test_idle_brew_start_transitions_to_anon(state, mock_display):
    state.handle(BrewStart())
    assert state.state == State.ANON_BREW
    mock_display.show_anon_brewing.assert_called_once_with(0)


def test_idle_brew_end_ignored(state):
    state.handle(brew_end())
    assert state.state == State.IDLE


# -- ARMED transitions --

def test_armed_brew_start_transitions_to_brewing(state, mock_display):
    state.handle(QRScanned(token="bob@example.com"))
    state.handle(BrewStart())
    assert state.state == State.BREWING
    mock_display.show_brewing.assert_called_with("bob", 0, pytest.approx(0, abs=1))


def test_armed_same_user_scan_cancels_session(state, mock_display):
    state.handle(QRScanned(token="carol@example.com"))
    state.handle(QRScanned(token="carol@example.com"))
    assert state.state == State.IDLE
    mock_display.show_idle.assert_called()


def test_armed_different_user_scan_swaps_session(state, mock_display):
    state.handle(QRScanned(token="dave@example.com"))
    state.handle(QRScanned(token="eve@example.com"))
    assert state.state == State.ARMED
    assert state._user["name"] == "eve"
    mock_display.show_armed.assert_called_with("eve", 0)


def test_armed_timeout_no_brew_returns_to_idle(state, mock_display):
    state.handle(QRScanned(token="frank@example.com"))
    state._state_since = time.time() - (ARMED_TIMEOUT + 1)
    state.on_tick()
    assert state.state == State.IDLE
    mock_display.show_idle.assert_called()


def test_armed_inactivity_timeout_after_brew_shows_summary(state, mock_display):
    state.handle(QRScanned(token="grace@example.com"))
    state.handle(BrewStart())
    state.handle(brew_end(25.0))
    assert state.state == State.ARMED
    # Backdate last brew to trigger inactivity timeout
    state._last_brew_at = time.time() - (SESSION_TIMEOUT + 1)
    with patch("core.state.time") as mock_time:
        mock_time.time.return_value = time.time()
        mock_time.sleep = MagicMock()
        state.on_tick()
    assert state.state == State.IDLE
    mock_display.show_summary.assert_called_once()
    mock_display.show_idle.assert_called()


# -- BREWING transitions --

def test_brewing_brew_end_above_threshold_logs_brew(state, test_db):
    state.handle(QRScanned(token="hank@example.com"))
    state.handle(BrewStart())
    state.handle(brew_end(25.0))
    assert state.state == State.ARMED
    assert state._brew_count == 1
    stats = db.get_user_stats(state._user["id"])
    assert stats["total_brews"] == 1


def test_brewing_brew_end_below_threshold_logs_noise(state, test_db):
    state.handle(QRScanned(token="iris@example.com"))
    state.handle(BrewStart())
    state.handle(short_brew_end(3.0))
    assert state.state == State.ARMED
    assert state._brew_count == 0
    with db.get_connection() as con:
        row = con.execute("SELECT kind FROM brews").fetchone()
    assert row[0] == "noise"


def test_brewing_qr_scan_pending_applied_after_brew(state, mock_display):
    state.handle(QRScanned(token="jack@example.com"))
    state.handle(BrewStart())
    state.handle(QRScanned(token="kate@example.com"))
    assert state.state == State.BREWING  # still brewing
    state.handle(brew_end(25.0))
    assert state.state == State.ARMED
    assert state._user["name"] == "kate"
    mock_display.show_armed.assert_called_with("kate", 0)


def test_multiple_brews_same_session(state):
    state.handle(QRScanned(token="leo@example.com"))
    for _ in range(3):
        state.handle(BrewStart())
        state.handle(brew_end(25.0))
    assert state._brew_count == 3
    assert state.state == State.ARMED


# -- ANON_BREW transitions --

def test_anon_brew_end_above_threshold_logs_anonymous(state, test_db):
    state.handle(BrewStart())
    state.handle(brew_end(25.0))
    assert state.state == State.IDLE
    with db.get_connection() as con:
        row = con.execute(
            "SELECT session_id, kind FROM brews"
        ).fetchone()
    assert row[0] is None
    assert row[1] == "brew"


def test_anon_brew_end_below_threshold_logs_noise(state, test_db):
    state.handle(BrewStart())
    state.handle(short_brew_end(3.0))
    assert state.state == State.IDLE
    with db.get_connection() as con:
        row = con.execute("SELECT kind FROM brews").fetchone()
    assert row[0] == "noise"
