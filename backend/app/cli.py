"""Commands for the people who run the application."""

import logging

import click
from flask.cli import with_appcontext

from app import db
from app.repositories import admin_repository
from app.services import auto_decline, passwords
from app.services.booking_validation import check_email
from app.services.passwords import PASSWORD_MAX, PASSWORD_MIN


@click.command("create-admin")
@click.option("--email", required=True, help="Email address the admin logs in with.")
@with_appcontext
def create_admin_command(email: str):
    """Create the one admin account (docs/specs/F02.md, CL1 to CL4).

    The password is asked for at a hidden prompt, so it never appears on the
    command line or in the shell history.
    """
    password = click.prompt("Password", hide_input=True)
    repeat = click.prompt("Repeat password", hide_input=True)

    email, code = check_email(email)
    if code is not None:
        raise click.ClickException("That is not a valid email address.")
    if passwords.new_password_problem(password) is not None:
        raise click.ClickException(
            f"The password must be {PASSWORD_MIN} to {PASSWORD_MAX} characters"
            " with no control characters."
        )
    if password != repeat:
        raise click.ClickException("The two passwords do not match.")

    with db.connect() as connection:
        if admin_repository.count_admins(connection) > 0:
            raise click.ClickException("An admin account already exists.")
        admin_repository.insert_admin(connection, email, passwords.hash_password(password))

    click.echo("Admin account created.")


jobs_logger = logging.getLogger("app.jobs")


@click.command("auto-decline")
@with_appcontext
def auto_decline_command():
    """Decline every booking left in 'submitted' for 48 hours (docs/specs/F03.md).

    Meant to be run once an hour by a scheduler. Exits with code 1 if the run fails.
    """
    try:
        declined = auto_decline.run()
    except Exception as error:
        # Only the type: a database error's message can quote client details (F01 P1).
        line = f"Auto-decline run failed: {type(error).__name__}."
        jobs_logger.error(line)
        click.echo(line)
        raise SystemExit(1) from None

    line = f"Auto-decline run: {declined} declined."
    jobs_logger.info(line)
    click.echo(line)
