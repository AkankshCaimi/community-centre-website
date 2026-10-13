"""Fixtures for the F01 tests. Spec: docs/specs/F01.md."""

import os

import psycopg
import pytest
from f01_helpers import TEAM_EMAIL, Clock, FakeCaptcha

from app import create_app


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def captcha():
    return FakeCaptcha()


@pytest.fixture
def db():
    """Autocommit connection to the test database, for checking what was stored."""
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True) as connection:
        yield connection


@pytest.fixture
def app(db, clock, captcha):
    app = create_app()
    app.config.update(
        TESTING=True,
        DATABASE_URL=os.environ["TEST_DATABASE_URL"],
        CLOCK=clock,
        CAPTCHA_VERIFIER=captcha,
        TEAM_EMAIL=TEAM_EMAIL,
    )
    # Start every test from an empty bookings table (spec: Database).
    db.execute("DROP TABLE IF EXISTS bookings CASCADE")
    app.test_cli_runner().invoke(args=["init-db"])
    return app


@pytest.fixture
def booking_count(db):
    def count():
        return db.execute("SELECT count(*) FROM bookings").fetchone()[0]

    return count
