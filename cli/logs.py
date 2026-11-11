import subprocess
import click


@click.group()
def logs():
    """View live service logs."""


def _follow(units: list[str], lines: int):
    args = ["journalctl", "-n", str(lines), "-f"]
    for u in units:
        args += ["-u", u]
    try:
        result = subprocess.run(args)
    except OSError as exc:
        raise click.ClickException(f"Cannot run journalctl: {exc}") from exc
    if result.returncode:
        raise click.ClickException(f"journalctl exited with status {result.returncode}.")


@logs.command(name="all")
@click.option("-n", default=50, show_default=True, help="Lines of history before following.")
def logs_all(n):
    """Follow logs from kiosk and browser services."""
    _follow(["crema-kiosk", "crema-browser"], n)


@logs.command()
@click.option("-n", default=50, show_default=True, help="Lines of history before following.")
def kiosk(n):
    """Follow kiosk logs (sensor, scanner, state machine, API)."""
    _follow(["crema-kiosk"], n)


@logs.command()
@click.option("-n", default=50, show_default=True, help="Lines of history before following.")
def browser(n):
    """Follow browser (Chromium kiosk display) logs."""
    _follow(["crema-browser"], n)
