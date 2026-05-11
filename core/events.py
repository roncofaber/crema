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
