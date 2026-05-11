import sqlite3
import time
from fastapi import APIRouter, Depends, Query
from api.deps import get_db
from api.schemas import OverallStats, DailyStats

router = APIRouter()


def _today_start() -> float:
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


@router.get("/", response_model=OverallStats)
def overall_stats(db: sqlite3.Connection = Depends(get_db)):
    today = _today_start()

    row = db.execute("""
        SELECT
            COUNT(CASE WHEN b.kind = 'brew' THEN 1 END)                          AS total_brews,
            COUNT(DISTINCT CASE WHEN b.kind = 'brew' THEN s.user_id END)          AS total_users,
            COALESCE(SUM(CASE WHEN b.kind = 'brew' THEN b.duration END), 0)       AS total_brew_time,
            COUNT(CASE WHEN b.kind = 'brew' AND b.started_at >= ? THEN 1 END)     AS today_brews
        FROM brews b
        LEFT JOIN sessions s ON b.session_id = s.id
    """, (today,)).fetchone()

    top = db.execute("""
        SELECT u.name
        FROM brews b
        JOIN sessions s ON b.session_id = s.id
        JOIN users u    ON s.user_id    = u.id
        WHERE b.kind = 'brew'
        GROUP BY u.id
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """).fetchone()

    return {
        "total_brews":     row["total_brews"],
        "total_users":     row["total_users"],
        "total_brew_time": row["total_brew_time"],
        "today_brews":     row["today_brews"],
        "top_brewer":      top["name"] if top else None,
    }


@router.get("/daily", response_model=list[DailyStats])
def daily_stats(days: int = Query(30, le=365), db: sqlite3.Connection = Depends(get_db)):
    since = time.time() - days * 86400
    rows = db.execute("""
        SELECT
            DATE(b.started_at, 'unixepoch', 'localtime') AS date,
            COUNT(*)                                      AS brews,
            COALESCE(SUM(b.duration), 0)                 AS total_duration
        FROM brews b
        WHERE b.kind = 'brew' AND b.started_at >= ?
        GROUP BY date
        ORDER BY date
    """, (since,)).fetchall()
    return [dict(r) for r in rows]
