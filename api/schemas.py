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


class OverallStats(BaseModel):
    total_brews: int
    total_users: int
    total_brew_time: float
    today_brews: int
    top_brewer: str | None


class DailyStats(BaseModel):
    date: str
    brews: int
    total_duration: float


class Status(BaseModel):
    state: str          # 'idle' or 'active'
    user: str | None
    session_started_at: float | None
