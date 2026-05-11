import subprocess
import click


@click.group()
def logs():
    """View live service logs."""


def _follow(units: list[str], lines: int):
    args = ["journalctl", "-n", str(lines), "-f"]
    for u in units:
        args += ["-u", u]
    subprocess.run(args)


@logs.command()
@click.option("-n", default=50, show_default=True, help="Lines of history before following.")
def all(n):
    """Follow logs from both kiosk and API."""
    _follow(["crema-kiosk", "crema-api"], n)


@logs.command()
@click.option("-n", default=50, show_default=True, help="Lines of history before following.")
def kiosk(n):
    """Follow kiosk logs (sensor, scanner, state machine)."""
    _follow(["crema-kiosk"], n)


@logs.command()
@click.option("-n", default=50, show_default=True, help="Lines of history before following.")
def api(n):
    """Follow API server logs."""
    _follow(["crema-api"], n)
