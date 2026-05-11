import sqlite3
import time

import click

from config import DB_PATH, MIN_BREW_DURATION


def fmt_duration(seconds):
    if seconds is None:
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


def section(title):
    click.echo(f"\n{title}")
    click.echo("=" * len(title))


@click.command()
def stats():
    """Show the stats dashboard."""
    try:
        con = sqlite3.connect(DB_PATH)
    except Exception as e:
        raise click.ClickException(f"Cannot open database: {e}")

    section("All-time leaderboard")
    rows = con.execute("""
        SELECT
            u.name,
            COUNT(b.id)                          AS brews,
            ROUND(SUM(b.duration) / 60.0, 1)     AS minutes,
            MAX(b.ended_at)                       AS last_brew
        FROM brews b
        JOIN sessions s ON b.session_id = s.id
        JOIN users u    ON s.user_id    = u.id
        WHERE b.kind = 'brew'
        GROUP BY u.id
        ORDER BY brews DESC
    """).fetchall()
    if rows:
        print_table(
            ["Name", "Brews", "Total time", "Last brew"],
            [(r[0], r[1], fmt_duration(r[2] * 60), fmt_ts(r[3])) for r in rows],
        )
    else:
        click.echo("No brews logged yet.")

    section("Recent brews (last 20)")
    rows = con.execute("""
        SELECT
            COALESCE(u.name, 'anonymous'),
            b.started_at,
            b.duration,
            b.kind
        FROM brews b
        LEFT JOIN sessions s ON b.session_id = s.id
        LEFT JOIN users u    ON s.user_id    = u.id
        ORDER BY b.started_at DESC
        LIMIT 20
    """).fetchall()
    if rows:
        print_table(
            ["User", "Time", "Duration", "Kind"],
            [(r[0], fmt_ts(r[1]), fmt_duration(r[2]), r[3]) for r in rows],
        )
    else:
        click.echo("No brews logged yet.")

    section("Noise events")
    row = con.execute("""
        SELECT COUNT(*), ROUND(AVG(duration), 1), ROUND(MAX(duration), 1)
        FROM brews WHERE kind = 'noise'
    """).fetchone()
    if row[0]:
        click.echo(f"Count: {row[0]}  avg duration: {fmt_duration(row[1])}  max: {fmt_duration(row[2])}")
        click.echo(f"(threshold for 'brew' is {MIN_BREW_DURATION}s)")
    else:
        click.echo("No noise events logged.")

    con.close()
