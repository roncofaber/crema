import click

from cli.db import db
from cli.logs import logs
from cli.sensor import sensor
from cli.stats import stats
from cli.users import users


@click.group()
def cli():
    """CREMA - Coffee Realtime Event Monitoring Application."""


@cli.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind address.")
@click.option("--port", default=8000, show_default=True, help="Port to listen on.")
@click.option("--reload", is_flag=True, default=False, help="Auto-reload on code changes (dev only).")
def serve(host, port, reload):
    """Start the CREMA API server."""
    import uvicorn
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


cli.add_command(stats)
cli.add_command(db)
cli.add_command(users)
cli.add_command(sensor)
cli.add_command(logs)
