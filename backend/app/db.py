from pathlib import Path

import click
import psycopg
from flask import current_app
from flask.cli import with_appcontext

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def connect() -> psycopg.Connection:
    """Open a connection to the application's database.

    Used as a context manager it commits on success and rolls back on an error.
    """
    return psycopg.connect(current_app.config["DATABASE_URL"])


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create the tables in the database named by DATABASE_URL."""
    with connect() as connection:
        connection.execute(SCHEMA_FILE.read_text())
    click.echo("Database schema applied.")
