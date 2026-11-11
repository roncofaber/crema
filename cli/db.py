import csv
import os
import sys
import time
from contextlib import closing

import click

from config import (
    BACKUP_RETENTION_COUNT,
    BACKUP_RETENTION_DAYS,
    DB_PATH,
    MIN_BREW_DURATION,
)
import core.db as core_db


def get_con():
    try:
        return core_db.get_connection()
    except Exception as e:
        raise click.ClickException(f"Cannot open database: {e}")


@click.group()
def db():
    """Database utilities."""


@db.command()
def reclassify():
    """Reapply the current MIN_BREW_DURATION threshold to all existing entries."""
    try:
        with core_db.maintenance_lock(DB_PATH), closing(get_con()) as con:
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
                return

            click.echo(f"Will reclassify {to_brew} noise -> brew, {to_noise} brew -> noise.")
            click.confirm("Proceed?", abort=True)

            with con:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    "UPDATE brews SET kind = 'brew' WHERE duration >= ? AND kind = 'noise'",
                    (MIN_BREW_DURATION,),
                )
                con.execute(
                    """
                    UPDATE brews
                    SET kind = 'noise', shot_type = NULL, decaf = NULL, rating = NULL
                    WHERE duration < ? AND kind = 'brew'
                    """,
                    (MIN_BREW_DURATION,),
                )
            click.echo("Done.")
    except core_db.MaintenanceLockError as exc:
        raise click.ClickException(
            "Database is in use. Stop CREMA services before reclassifying."
        ) from exc


@db.command()
@click.argument("output", required=False, type=click.Path(dir_okay=False))
@click.option("--keep", type=click.IntRange(min=1), default=BACKUP_RETENTION_COUNT, show_default=True)
def backup(output, keep):
    """Create a verified SQLite backup and prune older generated backups."""
    path = core_db.backup_database(output)
    click.echo(f"Backup created and verified: {path}")
    if output is None:
        removed = core_db.prune_backups(keep=keep, max_age_days=BACKUP_RETENTION_DAYS)
        if removed:
            click.echo(f"Removed {len(removed)} expired backups.")


@db.command()
@click.argument("directory", required=False, type=click.Path(file_okay=False))
@click.option("--keep", type=click.IntRange(min=1), default=BACKUP_RETENTION_COUNT, show_default=True)
@click.option("--max-age-days", type=click.IntRange(min=0), default=BACKUP_RETENTION_DAYS, show_default=True)
def cleanup(directory, keep, max_age_days):
    """Prune only CREMA timestamped backups by count and optional age."""
    removed = core_db.prune_backups(directory, keep=keep, max_age_days=max_age_days)
    for path in removed:
        click.echo(f"Removed: {path}")
    click.echo(f"Removed {len(removed)} backups.")


@db.command(name="check")
@click.argument("database", required=False, type=click.Path(exists=True, dir_okay=False))
def check_database(database):
    """Run SQLite integrity checks."""
    results = core_db.integrity_check(database)
    if results != ["ok"]:
        raise click.ClickException("; ".join(results))
    click.echo("Database integrity check: ok")


@db.command()
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
def restore(source):
    """Replace the live database from a verified backup."""
    click.echo(f"Will replace {DB_PATH} with {source}.")
    click.confirm("Proceed?", abort=True)
    try:
        with core_db.maintenance_lock(DB_PATH):
            safety_backup = core_db.backup_database() if os.path.isfile(DB_PATH) else None
            core_db.restore_database(source)
    except core_db.MaintenanceLockError as exc:
        raise click.ClickException(
            "Database is in use. Stop CREMA services before restoring."
        ) from exc
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Database restored successfully.")
    if safety_backup:
        click.echo(f"Previous database saved as: {safety_backup}")


@db.command()
@click.argument("output", default="-", type=click.Path())
def export(output):
    """Export all brews to CSV. Use - for stdout."""
    with closing(get_con()) as con:
        rows = con.execute("""
            SELECT
                b.id,
                COALESCE(u.name, 'anonymous') AS user,
                b.started_at,
                b.ended_at,
                b.duration,
                b.kind,
                b.shot_type,
                b.decaf,
                b.rating
            FROM brews b
            LEFT JOIN sessions s ON b.session_id = s.id
            LEFT JOIN users u    ON s.user_id    = u.id
            ORDER BY b.started_at
        """).fetchall()

    def fmt_ts(ts):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else ""

    out = sys.stdout if output == "-" else open(output, "w", newline="")
    writer = csv.writer(out)
    writer.writerow([
        "id", "user", "started_at", "ended_at", "duration_s", "kind",
        "shot_type", "decaf", "rating",
    ])
    for r in rows:
        writer.writerow([
            r[0], r[1], fmt_ts(r[2]), fmt_ts(r[3]), round(r[4], 1), r[5],
            r[6] or "", "" if r[7] is None else bool(r[7]), r[8] or "",
        ])
    if output != "-":
        out.close()
        click.echo(f"Exported {len(rows)} rows to {output}.")
