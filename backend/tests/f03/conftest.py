"""Fixtures for the F03 tests. Spec: docs/specs/F03.md."""

import os

import psycopg
import pytest
from f03_helpers import ADMIN_EMAIL, ADMIN_PASSWORD, TEAM_EMAIL, Clock, booking_payload

from app import create_app


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def db():
    """Autocommit connection to the test database, for checking what was stored."""
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True) as connection:
        yield connection


@pytest.fixture
def app(db, clock):
    app = create_app()
    app.config.update(
        TESTING=True,
        DATABASE_URL=os.environ["TEST_DATABASE_URL"],
        CLOCK=clock,
        CAPTCHA_VERIFIER=lambda token, ip: True,
        TEAM_EMAIL=TEAM_EMAIL,
    )
    # Start every test from empty tables.
    db.execute("DROP TABLE IF EXISTS job_runs, admin_sessions, admin_users, bookings CASCADE")
    app.test_cli_runner().invoke(args=["init-db"])
    return app


@pytest.fixture
def admin(app):
    """The admin account (F02 CL1)."""
    result = app.test_cli_runner().invoke(
        args=["create-admin", "--email", ADMIN_EMAIL],
        input=f"{ADMIN_PASSWORD}\n{ADMIN_PASSWORD}\n",
    )
    assert result.exit_code == 0, result.output


@pytest.fixture
def make_booking(app):
    """Create a booking through the public API of F01, at the clock's current time."""
    count = 0

    def make(day, number, **overrides):
        nonlocal count
        count += 1
        response = app.test_client().post(
            "/api/v1/bookings",
            json=booking_payload(day, number, **overrides),
            # A different address each time, so the rate limit of F01 L1 never applies.
            environ_base={"REMOTE_ADDR": f"198.51.100.{count}"},
        )
        assert response.status_code == 201, response.get_json()
        return response.get_json()["id"]

    return make
