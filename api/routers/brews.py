import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, Query
from api.deps import get_db
from api.schemas import Brew

router = APIRouter()


@router.get("/", response_model=list[Brew])
def list_brews(
    user: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    from_ts: Optional[float] = Query(None),
    to_ts: Optional[float] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    clauses = []
    params: list = []

    if user:
        clauses.append("u.name = ?")
        params.append(user)
    if kind:
        clauses.append("b.kind = ?")
        params.append(kind)
    if from_ts:
        clauses.append("b.started_at >= ?")
        params.append(from_ts)
    if to_ts:
        clauses.append("b.started_at <= ?")
        params.append(to_ts)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = db.execute(f"""
        SELECT
            b.id,
            COALESCE(u.name, 'anonymous') AS user,
            b.started_at, b.ended_at, b.duration, b.kind,
            b.shot_type, CAST(b.decaf AS INTEGER) AS decaf, b.rating
        FROM brews b
        LEFT JOIN sessions s ON b.session_id = s.id
        LEFT JOIN users u    ON s.user_id    = u.id
        {where}
        ORDER BY b.started_at DESC
        LIMIT ?
    """, params).fetchall()

    rows = [dict(r) for r in rows]
    for r in rows:
        if r["decaf"] is not None:
            r["decaf"] = bool(r["decaf"])
    return rows
