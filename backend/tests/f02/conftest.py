"""Fixtures for the F02 tests. Spec: docs/specs/F02.md."""

import os

import psycopg
import pytest
from f02_helpers import TEAM_EMAIL, Clock, FakeCaptcha, booking_payload, create_admin, login

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
        CAPTCHA_VERIFIER=FakeCaptcha(),
        TEAM_EMAIL=TEAM_EMAIL,
    )
    # Start every test from empty tables (F01 Database, F02 CL5).
    db.execute("DROP TABLE IF EXISTS admin_sessions, admin_users, bookings CASCADE")
    app.test_cli_runner().invoke(args=["init-db"])
    return app


@pytest.fixture
def admin(app):
    """The one admin account, created by the command of CL1."""
    create_admin(app)


@pytest.fixture
def admin_client(app, admin):
    """A client that has logged in as the admin."""
    client = app.test_client()
    login(client)
    return client


@pytest.fixture
def make_booking(app):
    """Create a booking through the public API of F01. Returns its ID."""
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
