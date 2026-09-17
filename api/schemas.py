from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    token: str
    total_brews: int
    total_time: float
    last_brew: float | None


class UserUpdate(BaseModel):
    name: str | None = None
    token: str | None = None


class Brew(BaseModel):
    id: int
    user: str
    started_at: float
    ended_at: float
    duration: float
    kind: str
    shot_type: str | None = None
    decaf: bool | None = None
    rating: int | None = None


class OverallStats(BaseModel):
    total_brews: int
    total_users: int
    total_brew_time: float
    today_brews: int
    top_brewer: str | None
    average_duration: float
    average_rating: float | None
    decaf_brews: int


class DailyStats(BaseModel):
    date: str
    brews: int
    total_duration: float


class Status(BaseModel):
    state: str
    user: str | None
    session_started_at: float | None
    brew_started_at: float | None = None


class DeviceHealth(BaseModel):
    connected: bool
    error: str | None = None
    last_scan_at: float | None = None
    last_read_at: float | None = None


class KioskHealth(BaseModel):
    running: bool
    scanner: DeviceHealth
    sensor: DeviceHealth


class Health(BaseModel):
    status: str
    mode: str
    database: dict[str, bool]
    kiosk: KioskHealth
