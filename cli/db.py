import csv
import sqlite3
import sys
import time

import click

from config import DB_PATH, MIN_BREW_DURATION


def get_con():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        raise click.ClickException(f"Cannot open database: {e}")


@click.group()
def db():
    """Database utilities."""


@db.command()
def reclassify():
    """Reapply the current MIN_BREW_DURATION threshold to all existing entries."""
    con = get_con()
    to_brew = con.execute(
        "SELECT COUNT(*) FROM brews WHERE duration >= ? AND kind = 'noise'",
        (MIN_BREW_DURATION,),
    ).fetchone()[0]
    to_noise = con.execute(
        "SELECT COUNT(*) FROM brews WHERE duration < ? AND kind = 'brew'",
        (MIN_BREW_DURATION,),
    ).fetchone()[0]

    if not to_brew and not to_noise:
        click.echo("Nothing to reclassify.")
        con.close()
        return

    click.echo(f"Will reclassify {to_brew} noise -> brew, {to_noise} brew -> noise.")
    click.confirm("Proceed?", abort=True)

    con.execute(
        "UPDATE brews SET kind = 'brew' WHERE duration >= ? AND kind = 'noise'",
        (MIN_BREW_DURATION,),
    )
    con.execute(
        "UPDATE brews SET kind = 'noise' WHERE duration < ? AND kind = 'brew'",
        (MIN_BREW_DURATION,),
    )
    con.commit()
    click.echo("Done.")
    con.close()


@db.command()
@click.argument("output", default="-", type=click.Path())
def export(output):
    """Export all brews to CSV. Use - for stdout."""
    con = get_con()
    rows = con.execute("""
        SELECT
            COALESCE(u.name, 'anonymous') AS user,
            b.started_at,
            b.ended_at,
            b.duration,
            b.kind
        FROM brews b
        LEFT JOIN sessions s ON b.session_id = s.id
        LEFT JOIN users u    ON s.user_id    = u.id
        ORDER BY b.started_at
    """).fetchall()
    con.close()

    def fmt_ts(ts):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else ""

    out = sys.stdout if output == "-" else open(output, "w", newline="")
    writer = csv.writer(out)
    writer.writerow(["user", "started_at", "ended_at", "duration_s", "kind"])
    for r in rows:
        writer.writerow([r[0], fmt_ts(r[1]), fmt_ts(r[2]), round(r[3], 1), r[4]])
    if output != "-":
        out.close()
        click.echo(f"Exported {len(rows)} rows to {output}.")


