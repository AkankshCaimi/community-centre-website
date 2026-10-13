"""Commands for the people who run the application."""

import click
from flask.cli import with_appcontext

from app import db
from app.repositories import admin_repository
from app.services import passwords
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
