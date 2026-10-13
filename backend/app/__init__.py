import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.api.admin import bp as admin_bp
from app.api.bookings import bp as bookings_bp
from app.api.health import bp as health_bp
from app.cli import auto_decline_command, create_admin_command, purge_command
from app.config import Config
from app.db import init_db_command


def json_error(error: HTTPException):
    """Answer HTTP errors in JSON, never HTML (spec F01, S4, A9 and A10)."""
    name = error.name.lower().replace(" ", "_")
    return jsonify(error=name), error.code


class Application(Flask):
    def log_exception(self, *args) -> None:
        """Log an unexpected failure as its type and booking ID only (spec F01, P1).

        The error's message and traceback are left out: database errors quote
        the row they failed on, client details included.
        """
        error = args[-1][1]
        booking_id = getattr(error, "booking_id", None)
        if booking_id is None:
            self.logger.error("Unexpected failure: %s", type(error).__name__)
        else:
            self.logger.error(
                "Unexpected failure: %s (booking %s)", type(error).__name__, booking_id
            )


def create_app() -> Flask:
    app = Application(__name__)
    app.config.from_object(Config)
    # Send INFO lines, including the logged emails, to the log output (spec F01, E4).
    app.logger.setLevel(logging.INFO)
    app.register_blueprint(health_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(admin_bp)
    app.register_error_handler(HTTPException, json_error)
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(auto_decline_command)
    app.cli.add_command(purge_command)
    return app
