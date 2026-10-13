import os

import psycopg
import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def db_connection():
    """Connection to the test database in the Docker Compose PostgreSQL.

    A test that uses this fixture fails if the database cannot be reached.
    """
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
        yield connection
