import logging
import threading
from enum import Enum, auto
import time
import core.db as db
from core.events import QRScanned, BrewStart, BrewEnd
from config import (
    ARMED_TIMEOUT, SESSION_TIMEOUT, SUMMARY_DURATION, MIN_BREW_DURATION
)

log = logging.getLogger(__name__)


class State(Enum):
    IDLE      = auto()
    ARMED     = auto()
    BREWING   = auto()
    ANON_BREW = auto()
    SUMMARY   = auto()


class SessionState:
    def __init__(self, on_broadcast=None):
        self._lock = threading.RLock()  # RLock: transition→broadcast→snapshot re-enters
        self._on_broadcast = on_broadcast or (lambda s: None)
        self.state       = State.IDLE
        self._state_since = time.time()

        self._user          = None   # {id, token, name}
        self._session_id    = None
        self._brew_count    = 0
        self._last_brew_at  = None
        self._brew_start    = None
        self._pending_token = None
        self._summary_shown_at = None
        self._last_display_tick = None
        self._shot_type     = "double"
        self._decaf         = False
        self._last_brew_id  = None
        self._avg_rating    = None

    def _snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> dict:
        now = time.time()
        if self.state == State.ARMED:
            if self._last_brew_at is None:
                time_remaining = max(0.0, ARMED_TIMEOUT - self.time_in_state())
                timeout = float(ARMED_TIMEOUT)
            else:
                time_remaining = max(0.0, SESSION_TIMEOUT - (now - self._last_brew_at))
                timeout = float(SESSION_TIMEOUT)
        else:
            time_remaining = None
            timeout = None
        elapsed = (now - self._brew_start) if self._brew_start else None
        return {
            "state": self.state.name.lower(),
            "user": self._user["name"] if self._user else None,
            "brew_count": self._brew_count,
            "time_remaining": time_remaining,
            "timeout": timeout,
            "elapsed": elapsed,
            "shot_type": self._shot_type,
            "decaf": self._decaf,
            "last_brew_id": self._last_brew_id,
            "avg_rating": self._avg_rating,
        }

    def _broadcast(self):
        self._on_broadcast(self._snapshot_unlocked())

    def transition(self, new_state: State):
        log.info("state %s -> %s", self.state.name, new_state.name)
        self.state        = new_state
        self._state_since = time.time()
        self._broadcast()

    def time_in_state(self) -> float:
        return time.time() - self._state_since

    def set_brew_options(self, shot_type: str, decaf: bool):
        with self._lock:
            self._shot_type = shot_type
            self._decaf = decaf
            self._broadcast()

    def force_logout(self):
        with self._lock:
            if self.state == State.ARMED:
                db.end_session(self._session_id)
                self._reset()
                self.transition(State.IDLE)

    def handle(self, event):
        with self._lock:
            log.debug("event: %s", event)
            if isinstance(event, QRScanned):
                self._on_qr_scan(event.token)
            elif isinstance(event, BrewStart):
                self._on_brew_start()
            elif isinstance(event, BrewEnd):
                self._on_brew_end(event)

    def on_tick(self):
        with self._lock:
            self._on_tick()

    def _on_tick(self):
        now = time.time()
        now_sec = int(now)

        if self.state == State.ARMED:
            if self._last_brew_at is None:
                time_in = self.time_in_state()
                if time_in > ARMED_TIMEOUT:
                    db.end_session(self._session_id)
                    self._reset()
                    self.transition(State.IDLE)
                elif self._last_display_tick != now_sec:
                    self._last_display_tick = now_sec
                    self._broadcast()
            else:
                idle_for = now - self._last_brew_at
                if idle_for > SESSION_TIMEOUT:
                    if self._summary_shown_at is None:
                        self._avg_rating = db.get_session_avg_rating(self._session_id)
                        self._summary_shown_at = now
                        self.transition(State.SUMMARY)
                elif self._last_display_tick != now_sec:
                    self._last_display_tick = now_sec
                    self._broadcast()

        elif self.state == State.SUMMARY:
            if self._summary_shown_at and now - self._summary_shown_at >= SUMMARY_DURATION:
                db.end_session(self._session_id)
                self._reset()
                self.transition(State.IDLE)

        elif self.state == State.BREWING:
            if self._last_display_tick != now_sec:
                self._last_display_tick = now_sec
                self._broadcast()

        elif self.state == State.ANON_BREW:
            if self._last_display_tick != now_sec:
                self._last_display_tick = now_sec
                self._broadcast()

    def _on_qr_scan(self, token: str):
        if self.state == State.IDLE:
            user = db.get_or_create_user(token)
            log.info("user %r logged in (id=%s)", user["name"], user["id"])
            self._user       = user
            self._session_id = db.start_session(user["id"])
            self._brew_count = 0
            self._last_brew_at = None
            self._shot_type = "double"
            self._decaf = False
            self._last_brew_id = None
            self.transition(State.ARMED)

        elif self.state == State.ARMED:
            if token == self._user["token"]:
                log.debug("re-scan ignored for current user")
                return
            else:
                log.info("handoff: %r -> new scan", self._user["name"])
                db.end_session(self._session_id)
                user = db.get_or_create_user(token)
                log.info("user %r logged in (id=%s)", user["name"], user["id"])
                self._user       = user
                self._session_id = db.start_session(user["id"])
                self._brew_count = 0
                self._last_brew_at = None
                self._shot_type = "double"
                self._decaf = False
                self._last_brew_id = None
                self.transition(State.ARMED)

        elif self.state == State.BREWING:
            log.info("QR scan queued during brew: %s", token)
            self._pending_token = token

    def _on_brew_start(self):
        now = time.time()
        if self.state == State.IDLE:
            self._brew_start = now
            self.transition(State.ANON_BREW)

        elif self.state == State.ARMED:
            self._brew_start = now
            self.transition(State.BREWING)

    def _on_brew_end(self, event: BrewEnd):
        kind = "brew" if event.duration >= MIN_BREW_DURATION else "noise"
        log.info("brew ended: duration=%.1fs kind=%s", event.duration, kind)

        if self.state == State.BREWING:
            brew_id = db.log_brew(
                self._session_id, event.started_at, event.ended_at, kind,
                shot_type=self._shot_type if kind == "brew" else None,
                decaf=int(self._decaf) if kind == "brew" else None
            )
            if kind == "brew":
                self._brew_count += 1
                self._last_brew_at = time.time()
                self._last_brew_id = brew_id
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
                self._shot_type = "double"
                self._decaf = False
                self._last_brew_id = None
                self.transition(State.ARMED)
            else:
                self.transition(State.ARMED)

        elif self.state == State.ANON_BREW:
            db.log_brew(None, event.started_at, event.ended_at, kind)
            self._brew_start = None
            self.transition(State.IDLE)

    def _reset(self):
        self._user          = None
        self._session_id    = None
        self._brew_count    = 0
        self._last_brew_at  = None
        self._brew_start    = None
        self._pending_token = None
        self._summary_shown_at = None
        self._last_display_tick = None
        self._shot_type     = "double"
        self._decaf         = False
        self._last_brew_id  = None
        self._avg_rating    = None
