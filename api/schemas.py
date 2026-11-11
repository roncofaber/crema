from typing import Literal

from pydantic import BaseModel, field_validator

from core.identity import normalize_name, validate_token


class User(BaseModel):
    id: int
    name: str
    token: str
    total_brews: int
    total_time: float
    last_brew: float | None
    preferred_shot_type: Literal["single", "double"] | None = None
    preferred_decaf: bool | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    token: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return normalize_name(value) if value is not None else None

    @field_validator("token")
    @classmethod
    def validate_user_token(cls, value):
        return validate_token(value) if value is not None else None


class Brew(BaseModel):
    id: int
    user: str
    started_at: float
    ended_at: float
    duration: float
    kind: Literal["brew", "noise"]
    shot_type: Literal["single", "double"] | None = None
    decaf: bool | None = None
    rating: int | None = None


class OkResponse(BaseModel):
    ok: bool


class RootResponse(BaseModel):
    status: Literal["ok"]


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
    thread_alive: bool = False
    stale_age: float | None = None


class KioskHealth(BaseModel):
    running: bool
    scanner: DeviceHealth
    sensor: DeviceHealth


class Health(BaseModel):
    status: str
    mode: str
    database: dict[str, bool]
    kiosk: KioskHealth
