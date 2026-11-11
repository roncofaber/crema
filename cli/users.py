import sqlite3
import time
from contextlib import closing

import click

from config import DB_PATH
import core.db as core_db
from core.identity import normalize_name, validate_token


def get_con():
    try:
        return core_db.get_connection(DB_PATH)
    except Exception as e:
        raise click.ClickException(f"Cannot open database: {e}")


def _validated_name(value):
    try:
        return normalize_name(value)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _validated_token(value):
    try:
        return validate_token(value)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def fmt_duration(seconds):
    if not seconds:
        return "-"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fmt_ts(ts):
    if ts is None:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def print_table(headers, rows, col_sep="  "):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = col_sep.join(f"{{:<{w}}}" for w in widths)
    click.echo(fmt.format(*headers))
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo(fmt.format(*[str(c) for c in row]))


def find_user(con, name):
    user = con.execute(
        "SELECT id, name, token FROM users WHERE name = ?", (name,)
    ).fetchone()
    if not user:
        raise click.ClickException(f"User '{name}' not found.")
    return user


def _require_no_open_session(con, user_id):
    active = con.execute(
        "SELECT 1 FROM sessions WHERE user_id = ? AND ended_at IS NULL LIMIT 1",
        (user_id,),
    ).fetchone()
    if active:
        raise click.ClickException("Cannot delete a user with an open session.")


@click.group()
def users():
    """User management."""


@users.command("list")
def list_users():
    """List all users with their brew stats."""
    with closing(get_con()) as con:
        rows = con.execute("""
            SELECT
                u.name,
                u.token,
                COUNT(b.id)                        AS brews,
                ROUND(SUM(b.duration) / 60.0, 1)   AS minutes,
                MAX(b.ended_at)                    AS last_brew
            FROM users u
            LEFT JOIN sessions s ON s.user_id = u.id
            LEFT JOIN brews b    ON b.session_id = s.id AND b.kind = 'brew'
            GROUP BY u.id
            ORDER BY brews DESC
        """).fetchall()

    if not rows:
        click.echo("No users registered.")
        return

    print_table(
        ["Name", "Token", "Brews", "Total time", "Last brew"],
        [(r[0], r[1], r[2] or 0, fmt_duration((r[3] or 0) * 60), fmt_ts(r[4])) for r in rows],
    )


@users.command()
@click.argument("name")
def show(name):
    """Show detailed stats for a user."""
    with closing(get_con()) as con:
        user = find_user(con, name)

        click.echo(f"\n{user[1]}  ({user[2]})")
        click.echo("-" * 40)

        totals = con.execute("""
            SELECT COUNT(*), COALESCE(SUM(b.duration), 0)
            FROM brews b
            JOIN sessions s ON b.session_id = s.id
            WHERE s.user_id = ? AND b.kind = 'brew'
        """, (user[0],)).fetchone()
        click.echo(f"Total brews : {totals[0]}")
        click.echo(f"Total time  : {fmt_duration(totals[1])}")

        noise = con.execute("""
            SELECT COUNT(*) FROM brews b
            JOIN sessions s ON b.session_id = s.id
            WHERE s.user_id = ? AND b.kind = 'noise'
        """, (user[0],)).fetchone()[0]
        click.echo(f"Noise events: {noise}")

        click.echo("\nLast 10 brews:")
        rows = con.execute("""
            SELECT b.started_at, b.duration, b.kind
            FROM brews b
            JOIN sessions s ON b.session_id = s.id
            WHERE s.user_id = ?
            ORDER BY b.started_at DESC
            LIMIT 10
        """).fetchall()
        if rows:
            print_table(
                ["Time", "Duration", "Kind"],
                [(fmt_ts(r[0]), fmt_duration(r[1]), r[2]) for r in rows],
            )
        else:
            click.echo("  No brews yet.")


@users.command()
@click.argument("name")
def edit(name):
    """Open a user record in $EDITOR for editing."""
    with closing(get_con()) as con:
        user = find_user(con, name)

        original = f"name: {user[1]}\ntoken: {user[2]}\n"
        edited = click.edit(original)

        if edited is None or edited == original:
            click.echo("No changes.")
            return

        fields = {}
        for line in edited.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                fields[key.strip()] = val.strip()

        new_name = _validated_name(fields.get("name", user[1]))
        new_token = _validated_token(fields.get("token", user[2]))

        try:
            with con:
                con.execute("BEGIN IMMEDIATE")
                if new_name != user[1]:
                    taken = con.execute(
                        "SELECT id FROM users WHERE name = ? AND id != ?",
                        (new_name, user[0]),
                    ).fetchone()
                    if taken:
                        raise click.ClickException(f"Name '{new_name}' is already taken.")

                if new_token != user[2]:
                    taken = con.execute(
                        "SELECT id FROM users WHERE token = ? AND id != ?",
                        (new_token, user[0]),
                    ).fetchone()
                    if taken:
                        raise click.ClickException(f"Token '{new_token}' is already in use.")

                con.execute(
                    "UPDATE users SET name = ?, token = ? WHERE id = ?",
                    (new_name, new_token, user[0]),
                )
        except sqlite3.IntegrityError as exc:
            raise click.ClickException("Name or token is already in use.") from exc
        click.echo(f"Updated '{user[1]}'.")


@users.command()
@click.argument("name")
@click.argument("new_name")
def rename(name, new_name):
    """Rename a user."""
    new_name = _validated_name(new_name)
    with closing(get_con()) as con:
        user = find_user(con, name)

        try:
            with con:
                con.execute("BEGIN IMMEDIATE")
                existing = con.execute(
                    "SELECT id FROM users WHERE name = ? AND id != ?",
                    (new_name, user[0]),
                ).fetchone()
                if existing:
                    raise click.ClickException(f"Name '{new_name}' is already taken.")

                con.execute(
                    "UPDATE users SET name = ? WHERE id = ?", (new_name, user[0])
                )
        except sqlite3.IntegrityError as exc:
            raise click.ClickException(f"Name '{new_name}' is already taken.") from exc
        click.echo(f"Renamed '{user[1]}' to '{new_name}'.")


@users.command()
@click.argument("name")
def delete(name):
    """Delete a user and all their sessions and brews."""
    with closing(get_con()) as con:
        user = find_user(con, name)
        _require_no_open_session(con, user[0])

        brews = con.execute("""
            SELECT COUNT(*) FROM brews b
            JOIN sessions s ON b.session_id = s.id
            WHERE s.user_id = ?
        """, (user[0],)).fetchone()[0]

        click.echo(f"Will delete user '{user[1]}' ({user[2]}) and {brews} brew(s).")
        click.confirm("Proceed?", abort=True)

        with con:
            con.execute("BEGIN IMMEDIATE")
            _require_no_open_session(con, user[0])
            con.execute("""
                DELETE FROM brews WHERE session_id IN (
                    SELECT id FROM sessions WHERE user_id = ?
                )
            """, (user[0],))
            con.execute("DELETE FROM sessions WHERE user_id = ?", (user[0],))
            con.execute("DELETE FROM users WHERE id = ?", (user[0],))
        click.echo("Done.")
