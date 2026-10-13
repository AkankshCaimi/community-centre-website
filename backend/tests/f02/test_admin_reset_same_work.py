"""F02 rule PR8: a reset request does the same work for a known and an unknown email.

Every expected value comes from docs/specs/F02.md.
"""

import logging
import statistics
import time

from f02_helpers import ADMIN_EMAIL, call

UNKNOWN_EMAIL = "someone.else@centre.example"
NOT_THE_ADMIN = "Password reset requested for an address that is not the admin's."


def request_reset(app, email):
    return call(app.test_client(), "POST", "/password-reset", {"email": email})


def row_version(db):
    """PostgreSQL's marker of which transaction last wrote the admin's row."""
    return db.execute("SELECT xmin::text FROM admin_users").fetchone()[0]


def logged(caplog, logger):
    return [record for record in caplog.records if record.name == logger]


def test_pr8_unknown_email_writes_one_line_without_an_address(app, admin, caplog):
    with caplog.at_level(logging.DEBUG):
        request_reset(app, UNKNOWN_EMAIL)

    auth = logged(caplog, "app.auth")
    assert [record.getMessage() for record in auth] == [NOT_THE_ADMIN]
    assert [record.levelno for record in auth] == [logging.INFO]
    assert logged(caplog, "app.email") == []
    everything = "\n".join(record.getMessage() for record in caplog.records)
    assert UNKNOWN_EMAIL not in everything
    assert ADMIN_EMAIL not in everything


def test_pr8_known_email_writes_one_line_the_email(app, admin, caplog):
    with caplog.at_level(logging.DEBUG):
        request_reset(app, ADMIN_EMAIL)

    assert len(logged(caplog, "app.email")) == 1
    assert logged(caplog, "app.auth") == []


def test_pr8_unknown_email_rewrites_the_admin_row_without_storing_a_token(app, admin, db):
    before = row_version(db)

    request_reset(app, UNKNOWN_EMAIL)

    assert row_version(db) != before
    assert db.execute(
        "SELECT password_reset_token_hash, password_reset_created_at FROM admin_users"
    ).fetchone() == (None, None)


def test_pr8_known_email_rewrites_the_admin_row_once(app, admin, db):
    before = row_version(db)

    request_reset(app, ADMIN_EMAIL)

    after = row_version(db)
    assert after != before
    # One statement, one transaction: the row was written once, not twice.
    assert int(after) - int(before) <= 2


def test_pr8_unknown_email_does_not_disturb_a_token_already_issued(app, admin, db):
    request_reset(app, ADMIN_EMAIL)
    issued = db.execute(
        "SELECT password_reset_token_hash, password_reset_created_at FROM admin_users"
    ).fetchone()

    request_reset(app, UNKNOWN_EMAIL)

    assert (
        db.execute(
            "SELECT password_reset_token_hash, password_reset_created_at FROM admin_users"
        ).fetchone()
        == issued
    )


def test_pr8_known_and_unknown_emails_take_the_same_class_of_time(app, admin):
    """A coarse check: the typical time for one must be within twice the other.

    The two kinds of request are timed alternately so that anything else the
    machine is doing affects both alike, and the median ignores stray slow runs.
    """
    for email in (ADMIN_EMAIL, UNKNOWN_EMAIL):  # warm up connections and caches
        request_reset(app, email)

    times = {ADMIN_EMAIL: [], UNKNOWN_EMAIL: []}
    for _ in range(60):
        for email in (ADMIN_EMAIL, UNKNOWN_EMAIL):
            started = time.perf_counter()
            request_reset(app, email)
            times[email].append(time.perf_counter() - started)

    known = statistics.median(times[ADMIN_EMAIL])
    unknown = statistics.median(times[UNKNOWN_EMAIL])
    assert 0.5 < known / unknown < 2.0, (
        f"known {known * 1000:.2f} ms, unknown {unknown * 1000:.2f} ms"
    )
