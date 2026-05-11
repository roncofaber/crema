import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Query
from api.deps import get_db
from api.schemas import User, UserUpdate, Brew

router = APIRouter()

_USER_STATS_SQL = """
    SELECT
        u.id, u.name, u.token,
        COUNT(CASE WHEN b.kind = 'brew' THEN 1 END)              AS total_brews,
        COALESCE(SUM(CASE WHEN b.kind = 'brew' THEN b.duration END), 0) AS total_time,
        MAX(CASE WHEN b.kind = 'brew' THEN b.ended_at END)       AS last_brew
    FROM users u
    LEFT JOIN sessions s ON s.user_id = u.id
    LEFT JOIN brews b    ON b.session_id = s.id
"""


@router.get("/", response_model=list[User])
def list_users(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(_USER_STATS_SQL + " GROUP BY u.id ORDER BY total_brews DESC").fetchall()
    return [dict(r) for r in rows]


@router.get("/{name}", response_model=User)
def get_user(name: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        _USER_STATS_SQL + " WHERE u.name = ? GROUP BY u.id", (name,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


@router.patch("/{name}", response_model=User)
def update_user(name: str, body: UserUpdate, db: sqlite3.Connection = Depends(get_db)):
    user = db.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.name is not None:
        taken = db.execute(
            "SELECT id FROM users WHERE name = ? AND id != ?", (body.name, user["id"])
        ).fetchone()
        if taken:
            raise HTTPException(status_code=409, detail="Name already taken")
        db.execute("UPDATE users SET name = ? WHERE id = ?", (body.name, user["id"]))

    if body.token is not None:
        taken = db.execute(
            "SELECT id FROM users WHERE token = ? AND id != ?", (body.token, user["id"])
        ).fetchone()
        if taken:
            raise HTTPException(status_code=409, detail="Token already in use")
        db.execute("UPDATE users SET token = ? WHERE id = ?", (body.token, user["id"]))

    db.commit()
    return get_user(body.name or name, db)


@router.get("/{name}/brews", response_model=list[Brew])
def get_user_brews(
    name: str,
    kind: str | None = Query(None),
    limit: int = Query(50, le=500),
    db: sqlite3.Connection = Depends(get_db),
):
    user = db.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    clauses = ["s.user_id = ?"]
    params: list = [user["id"]]
    if kind:
        clauses.append("b.kind = ?")
        params.append(kind)
    params.append(limit)

    rows = db.execute(f"""
        SELECT b.id, u.name AS user, b.started_at, b.ended_at, b.duration, b.kind
        FROM brews b
        JOIN sessions s ON b.session_id = s.id
        JOIN users u    ON s.user_id    = u.id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.started_at DESC
        LIMIT ?
    """, params).fetchall()
    return [dict(r) for r in rows]


@router.delete("/{name}", status_code=204)
def delete_user(name: str, db: sqlite3.Connection = Depends(get_db)):
    user = db.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.execute("""
        DELETE FROM brews WHERE session_id IN (
            SELECT id FROM sessions WHERE user_id = ?
        )
    """, (user["id"],))
    db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    db.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    db.commit()
