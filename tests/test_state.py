import time
from contextlib import closing
from unittest.mock import patch

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
    with closing(db.get_connection()) as con, con:
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
    with closing(db.get_connection()) as con, con:
        row = con.execute(
            "SELECT session_id, kind FROM brews"
        ).fetchone()
    assert row[0] is None
    assert row[1] == "brew"


def test_anon_brew_end_below_threshold_logs_noise(state, test_db):
    state.handle(BrewStart())
    state.handle(short_brew_end(3.0))
    assert state.state == State.IDLE
    with closing(db.get_connection()) as con, con:
        row = con.execute("SELECT kind FROM brews").fetchone()
    assert row[0] == "noise"


def test_scan_during_anonymous_brew_claims_it(state, test_db):
    state.handle(BrewStart())
    state.handle(QRScanned(token="claim@example.com"))
    state.handle(brew_end(25.0))
    assert state.state == State.ARMED
    assert state._user["name"] == "claim"
    assert state._brew_count == 1
    with closing(db.get_connection()) as con, con:
        row = con.execute("""
            SELECT u.name FROM brews b
            JOIN sessions s ON s.id = b.session_id
            JOIN users u ON u.id = s.user_id
        """).fetchone()
    assert row[0] == "claim"


def test_session_brew_time_accumulates(state):
    state.handle(QRScanned(token="timer@example.com"))
    state.handle(BrewStart())
    state.handle(brew_end(25.0))
    state.handle(BrewStart())
    state.handle(brew_end(30.0))
    assert state._snapshot()["session_brew_time"] == pytest.approx(55.0)


def test_force_logout_after_brew_shows_summary(state):
    state.handle(QRScanned(token="summary@example.com"))
    state.handle(BrewStart())
    state.handle(brew_end(25.0))
    state.force_logout()
    assert state.state == State.SUMMARY


# -- New tests for brew options, force_logout, and broadcasts --

def test_brew_options_default_double_non_decaf(state):
    assert state._shot_type == "double"
    assert state._decaf == False


def test_set_brew_options(state):
    state.handle(QRScanned(token="options@example.com"))
    assert state.set_brew_options("single", True, state._session_started_at) is True
    assert state._shot_type == "single"
    assert state._decaf == True


def test_brew_preferences_survive_logout_and_new_session(state):
    state.handle(QRScanned(token="remember@example.com"))
    state.set_brew_options("single", True, state._session_started_at)
    state.force_logout()


    state.handle(QRScanned(token="remember@example.com"))

    assert state._shot_type == "single"
    assert state._decaf is True
    assert db.get_or_create_user("remember@example.com")["preferred_decaf"] is True


def test_direct_handoff_loads_each_users_preferences(state):
    state.handle(QRScanned(token="preference-a@example.com"))
    state.set_brew_options("single", True, state._session_started_at)
    state.handle(QRScanned(token="preference-b@example.com"))
    assert (state._shot_type, state._decaf) == ("double", False)
    state.set_brew_options("double", True, state._session_started_at)

    state.handle(QRScanned(token="preference-a@example.com"))

    assert (state._shot_type, state._decaf) == ("single", True)


def test_pending_handoff_loads_new_user_preferences_before_summary(state):
    bob = db.get_or_create_user("pending-pref@example.com")
    db.update_user_preferences(bob["id"], "single", True)
    state.handle(QRScanned(token="pending-owner@example.com"))
    state.handle(BrewStart())
    state.handle(QRScanned(token="pending-pref@example.com"))

    state.handle(brew_end(25))

    assert state.state == State.ARMED
    assert state._user["id"] == bob["id"]
    assert (state._shot_type, state._decaf) == ("single", True)


def test_anonymous_claim_uses_preferences_for_recorded_brew(state):
    user = db.get_or_create_user("claim-pref@example.com")
    db.update_user_preferences(user["id"], "single", True)
    state.handle(BrewStart())
    state.handle(QRScanned(token="claim-pref@example.com"))

    state.handle(brew_end(25))

    with closing(db.get_connection()) as con:
        row = con.execute(
            "SELECT shot_type, decaf FROM brews WHERE id=?", (state._last_brew_id,)
        ).fetchone()
    assert row == ("single", 1)


def test_later_preferences_do_not_rewrite_recorded_brew(state):
    state.handle(QRScanned(token="immutable-pref@example.com"))
    state.set_brew_options("single", True, state._session_started_at)
    state.handle(BrewStart())
    state.handle(brew_end(25))
    state.set_brew_options("double", False, state._session_started_at)

    with closing(db.get_connection()) as con:
        row = con.execute(
            "SELECT shot_type, decaf FROM brews WHERE id=?", (state._last_brew_id,)
        ).fetchone()
    assert row == ("single", 1)


def test_preference_save_failure_does_not_change_visible_options(state):
    state.handle(QRScanned(token="save-failure@example.com"))
    with patch("core.state.db.update_user_preferences", return_value=False):
        with pytest.raises(RuntimeError, match="current user"):
            state.set_brew_options("single", True, state._session_started_at)
    assert (state._shot_type, state._decaf) == ("double", False)


def test_stale_brew_options_request_cannot_overwrite_new_session(state):
    state.handle(QRScanned(token="first@example.com"))
    previous_started_at = state._session_started_at
    state.handle(QRScanned(token="second@example.com"))

    assert state.set_brew_options("single", True, previous_started_at) is False
    assert state._shot_type == "double"
    assert state._decaf is False


def test_stale_logout_request_cannot_end_new_session(state):
    state.handle(QRScanned(token="first-logout@example.com"))
    previous_started_at = state._session_started_at
    state.handle(QRScanned(token="second-logout@example.com"))
    current_session_id = state._session_id

    assert state.force_logout(previous_started_at) is False
    assert state.state == State.ARMED
    assert state._user["token"] == "second-logout@example.com"
    assert state._session_id == current_session_id
    assert session_ended_at(current_session_id) is None
    assert state.force_logout(state._session_started_at) is True
    assert state.state == State.IDLE


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
    state.set_brew_options("single", True, state._session_started_at)
    snap = state._snapshot()
    assert snap["shot_type"] == "single"
    assert snap["decaf"] == True


def session_ended_at(session_id):
    with closing(db.get_connection()) as con, con:
        return con.execute(
            "SELECT ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()[0]


@pytest.mark.parametrize("use_timeout", [False, True])
def test_entering_summary_closes_session(state, use_timeout):
    state.handle(QRScanned(token="summary-close@example.com"))
    state.handle(BrewStart())
    state.handle(brew_end())
    session_id = state._session_id
    assert session_ended_at(session_id) is None

    if use_timeout:
        state._last_brew_at = time.time() - (SESSION_TIMEOUT + 1)
        state.on_tick()
    else:
        state.force_logout()

    assert state.state == State.SUMMARY
    ended_at = session_ended_at(session_id)
    assert ended_at is not None

    state._summary_shown_at = time.time() - (SUMMARY_DURATION + 1)
    state.on_tick()
    assert state.state == State.IDLE
    assert session_ended_at(session_id) == ended_at


@pytest.mark.parametrize("brewing", [False, True])
def test_shutdown_closes_session_and_is_idempotent(state, brewing):
    state.handle(QRScanned(token="shutdown@example.com"))
    if brewing:
        state.handle(BrewStart())
    session_id = state._session_id

    state.shutdown()

    assert state.state == State.IDLE
    assert state._session_id is None
    assert state._user is None
    ended_at = session_ended_at(session_id)
    assert ended_at is not None

    state.shutdown()
    assert state.state == State.IDLE
    assert session_ended_at(session_id) == ended_at


def test_repeated_shutdown_does_not_broadcast_again(state_with_broadcast, captured_broadcasts):
    state_with_broadcast.handle(QRScanned(token="broadcast-shutdown@example.com"))
    state_with_broadcast.shutdown()
    count = len(captured_broadcasts)
    assert captured_broadcasts[-1]["state"] == "idle"

    state_with_broadcast.shutdown()
    assert len(captured_broadcasts) == count
