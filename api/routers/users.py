import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Query
from api.deps import get_db
from api.schemas import User, UserUpdate, Brew

router = APIRouter()

_USER_STATS_SQL = """
    SELECT
        u.id, u.name, u.token, u.preferred_shot_type, u.preferred_decaf,
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
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            user = db.execute(
                "SELECT id, name, token FROM users WHERE name = ?", (name,)
            ).fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            new_name = body.name if body.name is not None else user["name"]
            new_token = body.token if body.token is not None else user["token"]

            if new_name != user["name"]:
                taken = db.execute(
                    "SELECT id FROM users WHERE name = ? AND id != ?",
                    (new_name, user["id"]),
                ).fetchone()
                if taken:
                    raise HTTPException(status_code=409, detail="Name already taken")

            if new_token != user["token"]:
                taken = db.execute(
                    "SELECT id FROM users WHERE token = ? AND id != ?",
                    (new_token, user["id"]),
                ).fetchone()
                if taken:
                    raise HTTPException(status_code=409, detail="Token already in use")

            db.execute(
                "UPDATE users SET name = ?, token = ? WHERE id = ?",
                (new_name, new_token, user["id"]),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Name or token already in use") from exc

    return get_user(new_name, db)


@router.get("/{name}/brews", response_model=list[Brew])
def get_user_brews(
    name: str,
    kind: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
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
        SELECT b.id, u.name AS user, b.started_at, b.ended_at, b.duration, b.kind,
               b.shot_type, CAST(b.decaf AS INTEGER) AS decaf, b.rating
        FROM brews b
        JOIN sessions s ON b.session_id = s.id
        JOIN users u    ON s.user_id    = u.id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.started_at DESC
        LIMIT ?
    """, params).fetchall()
    result = [dict(r) for r in rows]
    for brew in result:
        if brew["decaf"] is not None:
            brew["decaf"] = bool(brew["decaf"])
    return result


@router.delete("/{name}", status_code=204)
def delete_user(name: str, db: sqlite3.Connection = Depends(get_db)):
    with db:
        db.execute("BEGIN IMMEDIATE")
        user = db.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        active = db.execute(
            "SELECT 1 FROM sessions WHERE user_id = ? AND ended_at IS NULL LIMIT 1",
            (user["id"],),
        ).fetchone()
        if active:
            raise HTTPException(status_code=409, detail="User has an open session")
        db.execute("""
            DELETE FROM brews WHERE session_id IN (
                SELECT id FROM sessions WHERE user_id = ?
            )
        """, (user["id"],))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        db.execute("DELETE FROM users WHERE id = ?", (user["id"],))
