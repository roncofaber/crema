import subprocess
import click

_SERVICES = ["crema-kiosk", "crema-browser"]


def _systemctl(action: str, services: list[str]):
    subprocess.run(["sudo", "systemctl", action] + services)


@click.group()
def service():
    """Control CREMA systemd services."""


@service.command()
def restart():
    """Restart kiosk and browser services."""
    _systemctl("restart", _SERVICES)


@service.command()
def stop():
    """Stop kiosk and browser services."""
    _systemctl("stop", _SERVICES)


@service.command()
def start():
    """Start kiosk and browser services."""
    _systemctl("start", _SERVICES)


@service.command()
def status():
    """Show status of kiosk and browser services."""
    subprocess.run(["sudo", "systemctl", "status", "--no-pager"] + _SERVICES)
