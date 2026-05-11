import click

from cli.stats import stats
from cli.db import db
from cli.sensor import sensor


@click.group()
def cli():
    """CREMA - Coffee Realtime Event Monitoring Application."""


cli.add_command(stats)
cli.add_command(db)
cli.add_command(sensor)
