# Espresso Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Raspberry Pi kiosk that identifies coffee makers via QR scan, tracks each brew cycle with a vibration sensor, logs stats to SQLite, and gives real-time feedback on an LCD.

**Architecture:** Thread-per-device + shared event queue. Hardware threads (sensor, scanner) push typed events onto a `queue.Queue`; the main loop drains the queue and drives a state machine (`IDLE → ARMED → BREWING → ARMED`, plus `ANON_BREW`). The state machine owns all DB writes and display updates — no logic in hardware drivers.

**Tech Stack:** Python 3.11+, RPi.GPIO, evdev, adafruit-rgb-display, Pillow, sqlite3, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `config.py` | Modify | Add `MIN_VIBRATION_PULSE`, `BREW_CONFIRM_WINDOW`, `SENSOR_POLL_INTERVAL`, `SUMMARY_DURATION` |
| `core/events.py` | Create | Typed event dataclasses: `QRScanned`, `BrewStart`, `BrewEnd` |
| `core/db.py` | Modify | Implement all stub functions |
| `core/state.py` | Modify | Implement full state machine |
| `hardware/sensor.py` | Modify | Implement debounce polling loop |
| `hardware/scanner.py` | Modify | Implement evdev read + stdin fallback |
| `hardware/display.py` | Modify | Implement all `show_*` screens |
| `main.py` | Modify | Wire queue, state, hardware together |
| `tests/__init__.py` | Create | Empty |
| `tests/conftest.py` | Create | Shared pytest fixtures |
| `tests/test_db.py` | Create | DB function tests |
| `tests/test_state.py` | Create | State machine transition tests |
| `tests/test_scanner.py` | Create | Email validation + event posting tests |

---

## Task 1: Update config.py with missing constants

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add the four missing constants**

Open `config.py` and replace the entire file with:

```python
# GPIO pins
VIBRATION_PIN = 17          # SW-420 signal pin

# Vibration thresholds
MIN_BREW_DURATION    = 20   # seconds — below this → kind='noise'
BREW_END_SILENCE     = 10   # seconds of silence before BrewEnd fires
MIN_VIBRATION_PULSE  = 0.5  # seconds — minimum HIGH pulse to reset silence timer
BREW_CONFIRM_WINDOW  = 2    # seconds of sustained vibration before BrewStart fires
SENSOR_POLL_INTERVAL = 0.01 # seconds between GPIO reads (10 ms)

# Session timeouts
ARMED_TIMEOUT   = 120   # seconds waiting for machine after scan (no brew yet)
SESSION_TIMEOUT = 300   # seconds of inactivity after last brew before auto-logout
SUMMARY_DURATION = 5    # seconds to display summary screen before returning to idle

# Display
DISPLAY_WIDTH    = 320
DISPLAY_HEIGHT   = 240
FONT_PATH        = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE_SMALL  = 20
FONT_SIZE_LARGE  = 40

# Database
DB_PATH = "data/espresso.db"
```

- [ ] **Step 2: Commit**

```bash
git add config.py
git commit -m "config: add vibration and session timing constants"
```

---

## Task 2: Create event types

**Files:**
- Create: `core/events.py`
- Create: `tests/__init__.py`
- Create: `tests/test_events.py`

- [ ] **Step 1: Create `core/events.py`**

```python
from dataclasses import dataclass


@dataclass
class QRScanned:
    token: str


@dataclass
class BrewStart:
    pass


@dataclass
class BrewEnd:
    started_at: float   # Unix timestamp — first confirmed vibration
    ended_at:   float   # Unix timestamp — last valid HIGH pulse
    duration:   float   # seconds (ended_at - started_at)
```

- [ ] **Step 2: Create `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 3: Write the failing test**

Create `tests/test_events.py`:

```python
from core.events import QRScanned, BrewStart, BrewEnd


def test_qr_scanned_holds_token():
    e = QRScanned(token="user@example.com")
    assert e.token == "user@example.com"


def test_brew_end_holds_timing():
    e = BrewEnd(started_at=1000.0, ended_at=1030.0, duration=30.0)
    assert e.duration == 30.0
    assert e.ended_at - e.started_at == 30.0


def test_brew_start_is_instantiable():
    e = BrewStart()
    assert isinstance(e, BrewStart)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd /home/roncofaber/software/espresso
python -m pytest tests/test_events.py -v
```

Expected:
```
tests/test_events.py::test_qr_scanned_holds_token PASSED
tests/test_events.py::test_brew_end_holds_timing PASSED
tests/test_events.py::test_brew_start_is_instantiable PASSED
```

- [ ] **Step 5: Commit**

```bash
git add core/events.py tests/__init__.py tests/test_events.py
git commit -m "feat: add typed event dataclasses"
```

---

## Task 3: Implement core/db.py

**Files:**
- Modify: `core/db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest
from unittest.mock import MagicMock
import core.db as db


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("core.db.DB_PATH", db_path)
    db.init_db()
    return db_path


@pytest.fixture
def mock_display():
    return MagicMock()
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_db.py`:

```python
import time
import pytest
import core.db as db


def test_init_db_creates_tables(test_db):
    with db.get_connection() as con:
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"users", "sessions", "brews"}.issubset(tables)


def test_get_or_create_user_new(test_db):
    user = db.get_or_create_user("alice@example.com")
    assert user["token"] == "alice@example.com"
    assert user["name"] == "alice"
    assert isinstance(user["id"], int)


def test_get_or_create_user_existing(test_db):
    u1 = db.get_or_create_user("bob@example.com")
    u2 = db.get_or_create_user("bob@example.com")
    assert u1["id"] == u2["id"]


def test_get_or_create_user_extracts_local_part(test_db):
    user = db.get_or_create_user("john.doe@company.org")
    assert user["name"] == "john.doe"


def test_start_session_authenticated(test_db):
    user = db.get_or_create_user("carol@example.com")
    session_id = db.start_session(user["id"])
    assert isinstance(session_id, int)
    with db.get_connection() as con:
        row = con.execute(
            "SELECT user_id, ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] == user["id"]
    assert row[1] is None


def test_start_session_anonymous(test_db):
    session_id = db.start_session(None)
    with db.get_connection() as con:
        row = con.execute(
            "SELECT user_id FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] is None


def test_end_session_stamps_ended_at(test_db):
    user = db.get_or_create_user("dave@example.com")
    session_id = db.start_session(user["id"])
    db.end_session(session_id)
    with db.get_connection() as con:
        row = con.execute(
            "SELECT ended_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert row[0] is not None


def test_log_brew_creates_row(test_db):
    user = db.get_or_create_user("eve@example.com")
    session_id = db.start_session(user["id"])
    t = time.time()
    db.log_brew(session_id, t, t + 25.0, "brew")
    with db.get_connection() as con:
        row = con.execute(
            "SELECT duration, kind FROM brews WHERE session_id=?", (session_id,)
        ).fetchone()
    assert row[0] == pytest.approx(25.0)
    assert row[1] == "brew"


def test_log_brew_anonymous(test_db):
    t = time.time()
    db.log_brew(None, t, t + 5.0, "noise")
    with db.get_connection() as con:
        row = con.execute(
            "SELECT session_id, kind FROM brews WHERE session_id IS NULL"
        ).fetchone()
    assert row[1] == "noise"


def test_get_user_stats_counts_brews_only(test_db):
    user = db.get_or_create_user("frank@example.com")
    s1 = db.start_session(user["id"])
    t = time.time()
    db.log_brew(s1, t, t + 25.0, "brew")
    db.log_brew(s1, t + 30.0, t + 33.0, "noise")
    s2 = db.start_session(user["id"])
    db.log_brew(s2, t + 60.0, t + 85.0, "brew")

    stats = db.get_user_stats(user["id"])
    assert stats["total_brews"] == 2
    assert stats["total_time"] == pytest.approx(50.0)
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
python -m pytest tests/test_db.py -v
```

Expected: all fail with `NotImplementedError`.

- [ ] **Step 4: Implement `core/db.py`**

Replace the file content:

```python
import sqlite3
import os
import time
from config import DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                token   TEXT UNIQUE NOT NULL,
                name    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER REFERENCES users(id),
                started_at  REAL NOT NULL,
                ended_at    REAL
            );

            CREATE TABLE IF NOT EXISTS brews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER REFERENCES sessions(id),
                started_at  REAL NOT NULL,
                ended_at    REAL NOT NULL,
                duration    REAL NOT NULL,
                kind        TEXT NOT NULL
            );
        """)


def get_or_create_user(token: str) -> dict:
    local_part = token.split("@")[0]
    with get_connection() as con:
        con.execute(
            "INSERT OR IGNORE INTO users (token, name) VALUES (?, ?)",
            (token, local_part),
        )
        row = con.execute(
            "SELECT id, token, name FROM users WHERE token=?", (token,)
        ).fetchone()
    return {"id": row[0], "token": row[1], "name": row[2]}


def start_session(user_id: int | None) -> int:
    with get_connection() as con:
        cur = con.execute(
            "INSERT INTO sessions (user_id, started_at) VALUES (?, ?)",
            (user_id, time.time()),
        )
        return cur.lastrowid


def end_session(session_id: int):
    with get_connection() as con:
        con.execute(
            "UPDATE sessions SET ended_at=? WHERE id=?",
            (time.time(), session_id),
        )


def log_brew(session_id: int | None, started_at: float, ended_at: float, kind: str):
    with get_connection() as con:
        con.execute(
            "INSERT INTO brews (session_id, started_at, ended_at, duration, kind) VALUES (?,?,?,?,?)",
            (session_id, started_at, ended_at, ended_at - started_at, kind),
        )


def get_user_stats(user_id: int) -> dict:
    with get_connection() as con:
        row = con.execute("""
            SELECT COUNT(*), COALESCE(SUM(b.duration), 0)
            FROM brews b
            JOIN sessions s ON b.session_id = s.id
            WHERE s.user_id = ? AND b.kind = 'brew'
        """, (user_id,)).fetchone()
    return {"total_brews": row[0], "total_time": row[1]}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
python -m pytest tests/test_db.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/db.py tests/conftest.py tests/test_db.py
git commit -m "feat: implement db layer with full test coverage"
```

---

## Task 4: Implement core/state.py

**Files:**
- Modify: `core/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_state.py`:

```python
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
    return BrewEnd(started_at=now - duration, ended_at=now, duration=duration)


def short_brew_end(duration=3.0):
    now = time.time()
    return BrewEnd(started_at=now - duration, ended_at=now, duration=duration)


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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/test_state.py -v
```

Expected: all fail with `NotImplementedError`.

- [ ] **Step 3: Implement `core/state.py`**

```python
from enum import Enum, auto
import time
import core.db as db
from core.events import QRScanned, BrewStart, BrewEnd
from config import (
    ARMED_TIMEOUT, SESSION_TIMEOUT, SUMMARY_DURATION, MIN_BREW_DURATION
)


class State(Enum):
    IDLE      = auto()
    ARMED     = auto()
    BREWING   = auto()
    ANON_BREW = auto()


class SessionState:
    def __init__(self, display):
        self._display    = display
        self.state       = State.IDLE
        self._state_since = time.time()

        self._user          = None   # {id, token, name}
        self._session_id    = None
        self._brew_count    = 0
        self._last_brew_at  = None
        self._brew_start    = None
        self._pending_token = None

    def transition(self, new_state: State):
        self.state        = new_state
        self._state_since = time.time()

    def time_in_state(self) -> float:
        return time.time() - self._state_since

    def handle(self, event):
        if isinstance(event, QRScanned):
            self._on_qr_scan(event.token)
        elif isinstance(event, BrewStart):
            self._on_brew_start()
        elif isinstance(event, BrewEnd):
            self._on_brew_end(event)

    def on_tick(self):
        now = time.time()

        if self.state == State.ARMED:
            if self._last_brew_at is None:
                if self.time_in_state() > ARMED_TIMEOUT:
                    db.end_session(self._session_id)
                    self._reset()
                    self.transition(State.IDLE)
                    self._display.show_idle()
            else:
                if now - self._last_brew_at > SESSION_TIMEOUT:
                    stats = db.get_user_stats(self._user["id"])
                    self._display.show_summary(
                        self._user["name"],
                        self._brew_count,
                        stats["total_time"],
                    )
                    time.sleep(SUMMARY_DURATION)
                    db.end_session(self._session_id)
                    self._reset()
                    self.transition(State.IDLE)
                    self._display.show_idle()

        elif self.state == State.BREWING:
            elapsed = now - self._brew_start
            self._display.show_brewing(self._user["name"], self._brew_count, elapsed)

        elif self.state == State.ANON_BREW:
            elapsed = now - self._brew_start
            self._display.show_anon_brewing(elapsed)

    def _on_qr_scan(self, token: str):
        if self.state == State.IDLE:
            user = db.get_or_create_user(token)
            self._user       = user
            self._session_id = db.start_session(user["id"])
            self._brew_count = 0
            self._last_brew_at = None
            self.transition(State.ARMED)
            self._display.show_armed(user["name"], 0)

        elif self.state == State.ARMED:
            if token == self._user["token"]:
                db.end_session(self._session_id)
                self._reset()
                self.transition(State.IDLE)
                self._display.show_idle()
            else:
                db.end_session(self._session_id)
                user = db.get_or_create_user(token)
                self._user       = user
                self._session_id = db.start_session(user["id"])
                self._brew_count = 0
                self._last_brew_at = None
                self.transition(State.ARMED)
                self._display.show_armed(user["name"], 0)

        elif self.state == State.BREWING:
            self._pending_token = token

    def _on_brew_start(self):
        now = time.time()
        if self.state == State.IDLE:
            self._brew_start = now
            self.transition(State.ANON_BREW)
            self._display.show_anon_brewing(0)

        elif self.state == State.ARMED:
            self._brew_start = now
            self.transition(State.BREWING)
            self._display.show_brewing(self._user["name"], self._brew_count, 0)

    def _on_brew_end(self, event: BrewEnd):
        kind = "brew" if event.duration >= MIN_BREW_DURATION else "noise"

        if self.state == State.BREWING:
            db.log_brew(self._session_id, event.started_at, event.ended_at, kind)
            if kind == "brew":
                self._brew_count += 1
                self._last_brew_at = time.time()
            self._brew_start = None

            if self._pending_token:
                pending = self._pending_token
                self._pending_token = None
                db.end_session(self._session_id)
                user = db.get_or_create_user(pending)
                self._user       = user
                self._session_id = db.start_session(user["id"])
                self._brew_count = 0
                self._last_brew_at = None
                self.transition(State.ARMED)
                self._display.show_armed(user["name"], 0)
            else:
                self.transition(State.ARMED)
                self._display.show_armed(self._user["name"], self._brew_count)

        elif self.state == State.ANON_BREW:
            db.log_brew(None, event.started_at, event.ended_at, kind)
            self._brew_start = None
            self.transition(State.IDLE)
            self._display.show_idle()

    def _reset(self):
        self._user          = None
        self._session_id    = None
        self._brew_count    = 0
        self._last_brew_at  = None
        self._brew_start    = None
        self._pending_token = None
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_state.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add core/state.py tests/test_state.py
git commit -m "feat: implement state machine with full transition coverage"
```

---

## Task 5: Implement hardware/sensor.py

**Files:**
- Modify: `hardware/sensor.py`
- Create: `tests/test_sensor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sensor.py`:

```python
import sys
import time
import queue
from unittest.mock import patch, MagicMock

# Mock RPi.GPIO before hardware.sensor is imported (not available on non-Pi)
_gpio_mock = MagicMock()
_gpio_mock.HIGH = 1
_gpio_mock.LOW  = 0
sys.modules.setdefault("RPi",     MagicMock())
sys.modules.setdefault("RPi.GPIO", _gpio_mock)

from core.events import BrewStart, BrewEnd  # noqa: E402


def run_sensor_loop(gpio_sequence, poll_interval=0.01):
    """
    Runs the sensor _step loop against a fake GPIO sequence.
    gpio_sequence: list of (value, duration_seconds) tuples.
    Returns the list of events posted to the queue.
    """
    q = queue.Queue()
    readings = []
    for value, duration in gpio_sequence:
        count = max(1, int(duration / poll_interval))
        readings.extend([value] * count)

    call_count = [0]

    def fake_input(pin):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(readings):
            return readings[idx]
        return 0  # LOW after sequence ends

    with patch("hardware.sensor.GPIO") as mock_gpio, \
         patch("hardware.sensor.time") as mock_time:

        mock_gpio.HIGH = 1
        mock_gpio.LOW  = 0
        mock_gpio.BCM  = 11
        mock_gpio.PUD_DOWN = 21
        mock_gpio.IN   = 1
        mock_gpio.input.side_effect = fake_input
        mock_time.sleep = MagicMock()

        # Replace time.time with a counter advancing by poll_interval per call
        t = [0.0]
        def fake_time():
            val = t[0]
            t[0] += poll_interval
            return val
        mock_time.time.side_effect = fake_time

        from hardware.sensor import VibrationSensor
        s = VibrationSensor(q)

        # Run enough iterations to process the whole sequence
        for _ in range(len(readings) + 1500):  # extra for silence window
            s._step()

    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events


def test_long_vibration_posts_brew_start_then_end():
    # 30 seconds HIGH (> BREW_CONFIRM_WINDOW=2s), then 15s LOW (> BREW_END_SILENCE=10s)
    events = run_sensor_loop([(1, 30), (0, 15)])
    types = [type(e).__name__ for e in events]
    assert "BrewStart" in types
    assert "BrewEnd" in types
    brew_end = next(e for e in events if isinstance(e, BrewEnd))
    assert brew_end.duration >= 28  # approximately 30s


def test_short_spike_does_not_post_brew_start():
    # 0.2s HIGH (< MIN_VIBRATION_PULSE=0.5s), then 15s LOW
    events = run_sensor_loop([(1, 0.2), (0, 15)])
    assert not any(isinstance(e, BrewStart) for e in events)


def test_cleanup_vibration_below_confirm_window():
    # 1s HIGH (> MIN_VIBRATION_PULSE but < BREW_CONFIRM_WINDOW=2s), then 15s LOW
    events = run_sensor_loop([(1, 1.0), (0, 15)])
    assert not any(isinstance(e, BrewStart) for e in events)
    # BrewEnd still fires (cleanup logged as noise by state machine)
    assert any(isinstance(e, BrewEnd) for e in events)


def test_brief_silence_does_not_end_brew():
    # 5s HIGH, 2s LOW (< BREW_END_SILENCE=10s), 5s HIGH, 15s LOW
    events = run_sensor_loop([(1, 5), (0, 2), (1, 5), (0, 15)])
    brew_ends = [e for e in events if isinstance(e, BrewEnd)]
    assert len(brew_ends) == 1  # only one brew end


def test_post_brew_spike_does_not_reset_timer():
    # 30s HIGH, 0.3s LOW, 0.3s HIGH spike, 15s LOW
    # The 0.3s spike is < MIN_VIBRATION_PULSE, so silence timer shouldn't reset
    events = run_sensor_loop([(1, 30), (0, 0.3), (1, 0.3), (0, 15)])
    brew_ends = [e for e in events if isinstance(e, BrewEnd)]
    assert len(brew_ends) == 1
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/test_sensor.py -v
```

Expected: fail because `VibrationSensor` has no `_step` method and `_run` is `NotImplementedError`.

- [ ] **Step 3: Implement `hardware/sensor.py`**

```python
import threading
import time
import RPi.GPIO as GPIO
from queue import Queue
from core.events import BrewStart, BrewEnd
from config import (
    VIBRATION_PIN, BREW_END_SILENCE, MIN_VIBRATION_PULSE,
    BREW_CONFIRM_WINDOW, SENSOR_POLL_INTERVAL,
)


class VibrationSensor:
    def __init__(self, queue: Queue):
        self._queue          = queue
        self._thread         = threading.Thread(target=self._run, daemon=True)

        self._vibration_start  = None   # timestamp of first HIGH in current cycle
        self._last_valid_high  = None   # timestamp of last HIGH pulse >= MIN_VIBRATION_PULSE
        self._pulse_start      = None   # timestamp when current HIGH pulse began
        self._brew_start_fired = False  # whether BrewStart has been posted this cycle

    def start(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(VIBRATION_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self._thread.start()

    def stop(self):
        GPIO.cleanup()

    def _run(self):
        while True:
            self._step()
            time.sleep(SENSOR_POLL_INTERVAL)

    def _step(self):
        now      = time.time()
        is_high  = GPIO.input(VIBRATION_PIN) == GPIO.HIGH

        if is_high:
            if self._pulse_start is None:
                self._pulse_start = now

            pulse_duration = now - self._pulse_start

            if pulse_duration >= MIN_VIBRATION_PULSE:
                self._last_valid_high = now
                if self._vibration_start is None:
                    self._vibration_start = self._pulse_start

                if not self._brew_start_fired:
                    if now - self._vibration_start >= BREW_CONFIRM_WINDOW:
                        self._queue.put(BrewStart())
                        self._brew_start_fired = True
        else:
            self._pulse_start = None

            if self._last_valid_high is not None:
                silence = now - self._last_valid_high
                if silence >= BREW_END_SILENCE:
                    self._queue.put(BrewEnd(
                        started_at=self._vibration_start,
                        ended_at=self._last_valid_high,
                        duration=self._last_valid_high - self._vibration_start,
                    ))
                    self._vibration_start  = None
                    self._last_valid_high  = None
                    self._brew_start_fired = False
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_sensor.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add hardware/sensor.py tests/test_sensor.py
git commit -m "feat: implement vibration sensor with debounce and MIN_VIBRATION_PULSE guard"
```

---

## Task 6: Implement hardware/scanner.py

**Files:**
- Modify: `hardware/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scanner.py`:

```python
import queue
import threading
import time
from hardware.scanner import QRScanner, _is_email
from core.events import QRScanned


def test_is_email_valid():
    assert _is_email("alice@example.com")
    assert _is_email("john.doe+tag@company.org")


def test_is_email_rejects_badge_number():
    assert not _is_email("123456")


def test_is_email_rejects_garbage():
    assert not _is_email("notanemail")
    assert not _is_email("")
    assert not _is_email("@nodomain")


def test_scanner_posts_valid_email(monkeypatch):
    q = queue.Queue()
    lines = iter(["alice@example.com", ""])

    scanner = QRScanner(q, device_path=None)

    def fake_input():
        return next(lines)

    monkeypatch.setattr("hardware.scanner._readline", fake_input)

    scanner._handle_raw("alice@example.com")
    event = q.get_nowait()
    assert isinstance(event, QRScanned)
    assert event.token == "alice@example.com"


def test_scanner_ignores_badge_number():
    q = queue.Queue()
    scanner = QRScanner(q, device_path=None)
    scanner._handle_raw("987654")
    assert q.empty()


def test_scanner_ignores_empty_input():
    q = queue.Queue()
    scanner = QRScanner(q, device_path=None)
    scanner._handle_raw("")
    assert q.empty()


def test_scanner_lowercases_email():
    q = queue.Queue()
    scanner = QRScanner(q, device_path=None)
    scanner._handle_raw("Alice@Example.COM")
    event = q.get_nowait()
    assert event.token == "alice@example.com"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/test_scanner.py -v
```

Expected: fail — `QRScanner` has no `_handle_raw`, `_is_email` doesn't exist.

- [ ] **Step 3: Implement `hardware/scanner.py`**

```python
import re
import threading
import sys
from queue import Queue
from core.events import QRScanned

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _is_email(token: str) -> bool:
    return bool(_EMAIL_RE.match(token.strip()))


def _readline() -> str:
    return sys.stdin.readline().strip()


class QRScanner:
    """
    Reads QR codes from a USB HID scanner.
    device_path=None → reads from stdin (useful for testing / dev without hardware).
    device_path='/dev/input/eventX' → reads exclusively via evdev.
    """

    def __init__(self, queue: Queue, device_path: str = None):
        self._queue       = queue
        self._device_path = device_path
        self._thread      = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        if self._device_path:
            self._run_evdev()
        else:
            self._run_stdin()

    def _run_stdin(self):
        while True:
            try:
                raw = _readline()
                self._handle_raw(raw)
            except EOFError:
                break

    def _run_evdev(self):
        from evdev import InputDevice, categorize, ecodes, KeyEvent

        _KEYMAP = {
            **{f"KEY_{c}": (c.lower(), c.upper()) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
            "KEY_1": ("1", "!"), "KEY_2": ("2", "@"), "KEY_3": ("3", "#"),
            "KEY_4": ("4", "$"), "KEY_5": ("5", "%"), "KEY_6": ("6", "^"),
            "KEY_7": ("7", "&"), "KEY_8": ("8", "*"), "KEY_9": ("9", "("),
            "KEY_0": ("0", ")"),
            "KEY_MINUS":  ("-", "_"),
            "KEY_EQUAL":  ("=", "+"),
            "KEY_DOT":    (".", ">"),
            "KEY_AT":     ("@", "@"),
        }
        _SHIFT_KEYS = {"KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"}

        device  = InputDevice(self._device_path)
        device.grab()
        buffer  = []
        shifted = False

        for event in device.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key = categorize(event)
            if key.keystate == KeyEvent.key_down:
                code = key.keycode if isinstance(key.keycode, str) else key.keycode[0]
                if code in _SHIFT_KEYS:
                    shifted = True
                elif code == "KEY_ENTER":
                    self._handle_raw("".join(buffer))
                    buffer.clear()
                elif code in _KEYMAP:
                    buffer.append(_KEYMAP[code][1 if shifted else 0])
            elif key.keystate == KeyEvent.key_up:
                code = key.keycode if isinstance(key.keycode, str) else key.keycode[0]
                if code in _SHIFT_KEYS:
                    shifted = False

    def _handle_raw(self, raw: str):
        token = raw.strip().lower()
        if _is_email(token):
            self._queue.put(QRScanned(token=token))
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_scanner.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add hardware/scanner.py tests/test_scanner.py
git commit -m "feat: implement QR scanner with email validation and evdev support"
```

---

## Task 7: Implement hardware/display.py

**Files:**
- Modify: `hardware/display.py`

No automated tests — screen output must be verified on hardware.

- [ ] **Step 1: Implement all screens**

Replace `hardware/display.py`:

```python
import board
import busio
import digitalio
from adafruit_rgb_display import st7789
from PIL import Image, ImageDraw, ImageFont
from config import DISPLAY_WIDTH, DISPLAY_HEIGHT, FONT_PATH, FONT_SIZE_SMALL, FONT_SIZE_LARGE

_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_GREY  = (160, 160, 160)


class Display:
    def __init__(self):
        cs  = digitalio.DigitalInOut(board.CE0)
        dc  = digitalio.DigitalInOut(board.D25)
        rst = digitalio.DigitalInOut(board.D27)
        bl  = digitalio.DigitalInOut(board.D18)

        bl.direction = digitalio.Direction.OUTPUT
        bl.value = True

        spi = busio.SPI(clock=board.SCLK, MOSI=board.MOSI)
        self.disp = st7789.ST7789(
            spi, cs=cs, dc=dc, rst=rst,
            width=240, height=320,
            baudrate=24000000,
        )

        self._font_s = ImageFont.truetype(FONT_PATH, FONT_SIZE_SMALL)
        self._font_l = ImageFont.truetype(FONT_PATH, FONT_SIZE_LARGE)
        self._logo   = self._load_logo()

    def _load_logo(self):
        try:
            img = Image.open("assets/pxArt.png").convert("RGBA")
            return img.resize((80, 80))
        except FileNotFoundError:
            return None

    def _new_canvas(self, bg=_BLACK):
        img  = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=bg)
        draw = ImageDraw.Draw(img)
        return img, draw

    def _send(self, img: Image.Image):
        self.disp.image(img.rotate(90, expand=True))

    def _center_text(self, draw, y, text, font, color=_WHITE):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((DISPLAY_WIDTH - w) // 2, y), text, fill=color, font=font)

    def _fmt_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s" if m else f"{s}s"

    def show_idle(self):
        img, draw = self._new_canvas()
        if self._logo:
            x = (DISPLAY_WIDTH - self._logo.width) // 2
            img.paste(self._logo, (x, 60), mask=self._logo)
        self._center_text(draw, 170, "Scan to start", self._font_s, _GREY)
        self._send(img)

    def show_armed(self, user_name: str, brew_count: int = 0):
        img, draw = self._new_canvas()
        self._center_text(draw, 70, f"Hi, {user_name}!", self._font_l)
        self._center_text(draw, 130, "Start the machine", self._font_s, _GREY)
        if brew_count > 0:
            self._center_text(draw, 170, f"{brew_count} coffee{'s' if brew_count != 1 else ''} so far", self._font_s, _GREY)
        self._send(img)

    def show_brewing(self, user_name: str, brew_count: int, elapsed: float):
        img, draw = self._new_canvas()
        draw.text((10, 10), user_name, fill=_GREY, font=self._font_s)
        count_str = f"x{brew_count + 1}"
        self._center_text(draw, 80, count_str, self._font_l)
        self._center_text(draw, 190, self._fmt_time(elapsed), self._font_s, _GREY)
        self._send(img)

    def show_anon_brewing(self, elapsed: float):
        img, draw = self._new_canvas()
        draw.text((10, 10), "Anonymous", fill=_GREY, font=self._font_s)
        self._center_text(draw, 80, "x1", self._font_l)
        self._center_text(draw, 190, self._fmt_time(elapsed), self._font_s, _GREY)
        self._send(img)

    def show_summary(self, user_name: str, brew_count: int, total_time: float):
        img, draw = self._new_canvas()
        self._center_text(draw, 60, f"See ya, {user_name}!", self._font_l)
        label = f"{brew_count} coffee{'s' if brew_count != 1 else ''}"
        self._center_text(draw, 140, label, self._font_s)
        self._center_text(draw, 175, self._fmt_time(total_time) + " total", self._font_s, _GREY)
        self._send(img)
```

- [ ] **Step 2: Test on hardware**

Run this on the Pi to verify each screen renders correctly:

```bash
python - <<'EOF'
import time
from hardware.display import Display

d = Display()

d.show_idle()
time.sleep(3)

d.show_armed("alice", 0)
time.sleep(3)

d.show_armed("alice", 2)
time.sleep(3)

d.show_brewing("alice", 2, 17.5)
time.sleep(3)

d.show_anon_brewing(8.0)
time.sleep(3)

d.show_summary("alice", 3, 85.0)
time.sleep(5)

d.show_idle()
EOF
```

Expected: each screen displays for 3–5s, text is readable, no exceptions.

- [ ] **Step 3: Commit**

```bash
git add hardware/display.py
git commit -m "feat: implement all display screens"
```

---

## Task 8: Wire up main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Implement `main.py`**

```python
import time
from queue import Queue

import core.db as db
from core.state import SessionState
from hardware.display import Display
from hardware.scanner import QRScanner
from hardware.sensor import VibrationSensor


def main():
    db.init_db()

    q       = Queue()
    display = Display()
    state   = SessionState(display)
    scanner = QRScanner(q, device_path=None)  # set device_path for production evdev
    sensor  = VibrationSensor(q)

    scanner.start()
    sensor.start()

    display.show_idle()

    try:
        while True:
            state.on_tick()
            while not q.empty():
                state.handle(q.get_nowait())
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.stop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest tests/ -v --ignore=tests/test_sensor.py
```

Note: `test_sensor.py` requires mocked GPIO — run it separately if it fails due to import issues on non-Pi hardware.

Expected: all tests pass.

- [ ] **Step 3: End-to-end test on hardware**

Start the system:
```bash
python main.py
```

Walk through the golden path:
1. Display shows idle screen
2. Scan a valid email QR → armed screen appears with your name
3. Start the coffee machine → brewing screen appears with counter and timer
4. Stop the machine → after 10s silence, armed screen returns with count
5. Make a second coffee → count increments
6. Wait 5 minutes idle → summary screen appears, then idle

Also verify:
- Badge barcode scan → nothing happens (stays idle/armed)
- Short vibration (cleanup) → no brew counted, logs as noise in DB
- New user scan while ARMED → screen switches to new user

- [ ] **Step 4: Set evdev device path**

Find the scanner device:
```bash
python -c "import evdev; [print(d.path, d.name) for d in evdev.list_devices()]"
```

Update `main.py` line:
```python
scanner = QRScanner(q, device_path="/dev/input/event<N>")
```
where `<N>` is the event number for the QR scanner.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: wire main loop with queue-driven state machine"
```

---

## Task 9: Run full test suite and verify

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Commit if any fixups were needed**

```bash
git add -p
git commit -m "fix: final integration adjustments"
```
