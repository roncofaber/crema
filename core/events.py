from dataclasses import dataclass


@dataclass(frozen=True)
class QRScanned:
    token: str


@dataclass(frozen=True)
class BrewStart:
    pass


@dataclass(frozen=True)
class BrewEnd:
    started_at: float
    ended_at:   float

    @property
    def duration(self) -> float:
        return self.ended_at - self.started_at
