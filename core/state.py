import logging
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
        self._summary_shown_at = None

    def transition(self, new_state: State):
        log.info("state %s -> %s", self.state.name, new_state.name)
        self.state        = new_state
        self._state_since = time.time()

    def time_in_state(self) -> float:
        return time.time() - self._state_since

    def handle(self, event):
        log.debug("event: %s", event)
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
                    if self._summary_shown_at is None:
                        stats = db.get_user_stats(self._user["id"])
                        self._display.show_summary(
                            self._user["name"],
                            self._brew_count,
                            stats["total_time"],
                        )
                        self._summary_shown_at = now
                    elif now - self._summary_shown_at >= SUMMARY_DURATION:
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
            log.info("user %r logged in (id=%s)", user["name"], user["id"])
            self._user       = user
            self._session_id = db.start_session(user["id"])
            self._brew_count = 0
            self._last_brew_at = None
            self.transition(State.ARMED)
            self._display.show_armed(user["name"], 0)

        elif self.state == State.ARMED:
            if token == self._user["token"]:
                log.info("user %r logged out", self._user["name"])
                db.end_session(self._session_id)
                self._reset()
                self.transition(State.IDLE)
                self._display.show_idle()
            else:
                log.info("handoff: %r -> new scan", self._user["name"])
                db.end_session(self._session_id)
                user = db.get_or_create_user(token)
                log.info("user %r logged in (id=%s)", user["name"], user["id"])
                self._user       = user
                self._session_id = db.start_session(user["id"])
                self._brew_count = 0
                self._last_brew_at = None
                self.transition(State.ARMED)
                self._display.show_armed(user["name"], 0)

        elif self.state == State.BREWING:
            log.info("QR scan queued during brew: %s", token)
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
        log.info("brew ended: duration=%.1fs kind=%s", event.duration, kind)

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
        self._summary_shown_at = None
