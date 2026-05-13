import time
import pytest
import core.db as db
from core.state import SessionState, State
from core.events import QRScanned, BrewStart, BrewEnd
from config import ARMED_TIMEOUT, SESSION_TIMEOUT, SUMMARY_DURATION, MIN_BREW_DURATION


@pytest.fixture
def state(test_db):
    return SessionState()


@pytest.fixture
def captured_broadcasts():
    snapshots = []
    return snapshots


@pytest.fixture
def state_with_broadcast(test_db, captured_broadcasts):
    return SessionState(on_broadcast=lambda s: captured_broadcasts.append(s))


def brew_end(duration=25.0):
    now = time.time()
    return BrewEnd(started_at=now - duration, ended_at=now)


def short_brew_end(duration=3.0):
    now = time.time()
    return BrewEnd(started_at=now - duration, ended_at=now)


# -- IDLE transitions --

def test_idle_valid_qr_transitions_to_armed(state):
    state.handle(QRScanned(token="alice@example.com"))
    assert state.state == State.ARMED


def test_idle_brew_start_transitions_to_anon(state):
    state.handle(BrewStart())
    assert state.state == State.ANON_BREW


def test_idle_brew_end_ignored(state):
    state.handle(brew_end())
    assert state.state == State.IDLE


# -- ARMED transitions --

def test_armed_brew_start_transitions_to_brewing(state):
    state.handle(QRScanned(token="bob@example.com"))
    state.handle(BrewStart())
    assert state.state == State.BREWING


def test_armed_same_user_scan_is_ignored(state):
    state.handle(QRScanned(token="carol@example.com"))
    state.handle(QRScanned(token="carol@example.com"))
    assert state.state == State.ARMED
    assert state._user["name"] == "carol"


def test_armed_different_user_scan_swaps_session(state):
    state.handle(QRScanned(token="dave@example.com"))
    state.handle(QRScanned(token="eve@example.com"))
    assert state.state == State.ARMED
    assert state._user["name"] == "eve"


def test_armed_timeout_no_brew_returns_to_idle(state):
    state.handle(QRScanned(token="frank@example.com"))
    state._state_since = time.time() - (ARMED_TIMEOUT + 1)
    state.on_tick()
    assert state.state == State.IDLE


def test_inactivity_timeout_transitions_to_summary(state):
    state.handle(QRScanned(token="grace@example.com"))
    state.handle(BrewStart())
    state.handle(brew_end(25.0))
    assert state.state == State.ARMED

    state._last_brew_at = time.time() - (SESSION_TIMEOUT + 1)
    state.on_tick()
    assert state.state == State.SUMMARY

    state._summary_shown_at = time.time() - (SUMMARY_DURATION + 1)
    state.on_tick()
    assert state.state == State.IDLE


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


def test_brewing_qr_scan_pending_applied_after_brew(state):
    state.handle(QRScanned(token="jack@example.com"))
    state.handle(BrewStart())
    state.handle(QRScanned(token="kate@example.com"))
    assert state.state == State.BREWING  # still brewing
    state.handle(brew_end(25.0))
    assert state.state == State.ARMED
    assert state._user["name"] == "kate"


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


# -- New tests for brew options, force_logout, and broadcasts --

def test_brew_options_default_double_non_decaf(state):
    assert state._shot_type == "double"
    assert state._decaf == False


def test_set_brew_options(state):
    state.set_brew_options("single", True)
    assert state._shot_type == "single"
    assert state._decaf == True


def test_force_logout_in_armed_state(state, test_db):
    state.handle(QRScanned(token="test@example.com"))
    assert state.state == State.ARMED
    state.force_logout()
    assert state.state == State.IDLE
    assert state._user is None


def test_force_logout_ignored_during_brewing(state):
    state.handle(QRScanned(token="test@example.com"))
    state.handle(BrewStart())
    assert state.state == State.BREWING
    state.force_logout()
    assert state.state == State.BREWING  # unchanged


def test_last_brew_id_set_after_brew(state, test_db):
    state.handle(QRScanned(token="test@example.com"))
    state.handle(BrewStart())
    state.handle(brew_end(25.0))
    assert state._last_brew_id is not None
    assert isinstance(state._last_brew_id, int)


def test_last_brew_id_not_set_for_noise(state, test_db):
    state.handle(QRScanned(token="test@example.com"))
    state.handle(BrewStart())
    state.handle(short_brew_end(3.0))
    assert state._last_brew_id is None


def test_broadcast_called_on_transition(test_db):
    snapshots = []
    state = SessionState(on_broadcast=lambda s: snapshots.append(s))
    state.handle(QRScanned(token="test@example.com"))
    assert len(snapshots) >= 1
    assert snapshots[-1]["state"] == "armed"
    assert snapshots[-1]["user"] == "test"


def test_snapshot_includes_brew_options(state):
    state.handle(QRScanned(token="test@example.com"))
    state.set_brew_options("single", True)
    snap = state._snapshot()
    assert snap["shot_type"] == "single"
    assert snap["decaf"] == True
