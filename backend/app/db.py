from pathlib import Path

import click
import psycopg
from flask import current_app
from flask.cli import with_appcontext

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def connect(give_up_after: int | None = None) -> psycopg.Connection:
    """Open a connection to the application's database.

    Used as a context manager it commits on success and rolls back on an error.
    `give_up_after` is how many seconds to wait for the database to answer;
    without it the driver's own, much longer, limit applies.
    """
    url = current_app.config.get("DATABASE_URL")
    if not url:
        # Without this the driver would fall back to its own defaults and
        # quietly connect to whatever database they happen to name.
        raise psycopg.OperationalError("DATABASE_URL is not set")
    if give_up_after is None:
        return psycopg.connect(url)
    return psycopg.connect(url, connect_timeout=give_up_after)


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create the tables in the database named by DATABASE_URL."""
    with connect() as connection:
        connection.execute(SCHEMA_FILE.read_text())
    click.echo("Database schema applied.")
