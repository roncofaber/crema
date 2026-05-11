from enum import Enum, auto
import time


class State(Enum):
    IDLE      = auto()   # no active user, vibration ignored
    ARMED     = auto()   # user scanned, waiting for machine to start
    BREWING   = auto()   # machine running, attributed to current user
    ANON_BREW = auto()   # machine running, no user scanned


class SessionState:
    def __init__(self):
        self.state         = State.IDLE
        self.user          = None       # dict from db.get_or_create_user
        self.session_id    = None
        self.state_since   = time.time()
        self.brew_start    = None

    def transition(self, new_state: State):
        self.state       = new_state
        self.state_since = time.time()

    def time_in_state(self) -> float:
        return time.time() - self.state_since

    # -- event handlers (to be called from main loop) --

    def on_qr_scan(self, token: str):
        """Called when the QR scanner reads a code."""
        raise NotImplementedError

    def on_vibration_start(self):
        """Called when sustained vibration is first detected."""
        raise NotImplementedError

    def on_vibration_end(self, duration: float):
        """Called when vibration stops; duration is the brew duration in seconds."""
        raise NotImplementedError

    def on_tick(self):
        """Called periodically to handle timeouts."""
        raise NotImplementedError
