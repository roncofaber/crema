import sqlite3
import time

import click

from config import DB_PATH


def get_con():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        raise click.ClickException(f"Cannot open database: {e}")


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


@click.group()
def users():
    """User management."""


@users.command("list")
def list_users():
    """List all users with their brew stats."""
    con = get_con()
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
    con.close()

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
    con = get_con()
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
    """, (user[0],)).fetchall()
    if rows:
        print_table(
            ["Time", "Duration", "Kind"],
            [(fmt_ts(r[0]), fmt_duration(r[1]), r[2]) for r in rows],
        )
    else:
        click.echo("  No brews yet.")

    con.close()


@users.command()
@click.argument("name")
@click.argument("new_name")
def rename(name, new_name):
    """Rename a user."""
    con = get_con()
    user = find_user(con, name)

    existing = con.execute(
        "SELECT id FROM users WHERE name = ?", (new_name,)
    ).fetchone()
    if existing:
        raise click.ClickException(f"Name '{new_name}' is already taken.")

    con.execute("UPDATE users SET name = ? WHERE id = ?", (new_name, user[0]))
    con.commit()
    click.echo(f"Renamed '{user[1]}' to '{new_name}'.")
    con.close()


@users.command()
@click.argument("name")
def delete(name):
    """Delete a user and all their sessions and brews."""
    con = get_con()
    user = find_user(con, name)

    brews = con.execute("""
        SELECT COUNT(*) FROM brews b
        JOIN sessions s ON b.session_id = s.id
        WHERE s.user_id = ?
    """, (user[0],)).fetchone()[0]

    click.echo(f"Will delete user '{user[1]}' ({user[2]}) and {brews} brew(s).")
    click.confirm("Proceed?", abort=True)

    con.execute("""
        DELETE FROM brews WHERE session_id IN (
            SELECT id FROM sessions WHERE user_id = ?
        )
    """, (user[0],))
    con.execute("DELETE FROM sessions WHERE user_id = ?", (user[0],))
    con.execute("DELETE FROM users WHERE id = ?", (user[0],))
    con.commit()
    click.echo("Done.")
    con.close()
