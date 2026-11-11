import click

from cli.db import db
from cli.logs import logs
from cli.sensor import sensor
from cli.service import service
from cli.stats import stats
from cli.users import users


@click.group()
def cli():
    """CREMA - Coffee Realtime Event Monitoring Application."""


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind address.")
@click.option("--port", default=8000, show_default=True, help="Port to listen on.")
@click.option("--reload", is_flag=True, default=False, help="Auto-reload on code changes (dev only).")
def serve(host, port, reload):
    """Start the CREMA API server."""
    import os
    import uvicorn
    from api.auth import require_safe_binding
    from api.logging import configure_logging, uvicorn_log_config

    configure_logging()
    require_safe_binding(host)
    os.environ["CREMA_START_HARDWARE"] = "1"
    uvicorn.run(
        "api.main:app", host=host, port=port, reload=reload,
        log_config=uvicorn_log_config(),
    )


cli.add_command(stats)
cli.add_command(db)
cli.add_command(users)
cli.add_command(sensor)
cli.add_command(service)
cli.add_command(logs)
