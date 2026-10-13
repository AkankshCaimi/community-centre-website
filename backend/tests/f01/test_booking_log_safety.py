"""F01 rule P1: log safety.

Every expected value comes from docs/specs/F01.md.
"""

import logging

import pytest
from f01_helpers import TEAM_EMAIL, payload, post

CLIENT_DETAILS = ("Alice Example", "alice@example.com", "07700 900123", "Birthday party")


def all_log_text(caplog):
    """Everything any logger wrote, including any attached exception text."""
    return "\n".join(
        record.getMessage() + "\n" + (record.exc_text or "") + "\n" + str(record.exc_info or "")
        for record in caplog.records
    )


# --- P1 (a): an unexpected failure logs the error type, never its message


def test_p1a_database_error_text_does_not_reach_the_log(app, db, caplog, booking_count):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    # Make the insert fail with a database error that quotes the whole row,
    # client details included ("Failing row contains (...)").
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT always_fails CHECK (client_name <> 'Alice Example')"
    )

    with caplog.at_level(logging.DEBUG):
        response = post(app.test_client(), payload())

    assert response.status_code == 500
    assert response.get_json() == {"error": "internal_server_error"}
    assert booking_count() == 0
    logged = all_log_text(caplog)
    assert "CheckViolation" in logged
    for private in CLIENT_DETAILS + ("Failing row", "always_fails"):
        assert private not in logged


def test_p1a_failure_is_one_log_line(app, db, caplog):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT always_fails CHECK (client_name <> 'Alice Example')"
    )

    with caplog.at_level(logging.WARNING):
        post(app.test_client(), payload())

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].exc_info is None
    assert "\n" not in caplog.records[0].getMessage()


class Explode(logging.Filter):
    """Makes writing an email to the log fail, after the booking is stored."""

    def filter(self, record):
        raise RuntimeError("secret detail alice@example.com")


@pytest.fixture
def exploding_email_log():
    logger = logging.getLogger("app.email")
    explode = Explode()
    logger.addFilter(explode)
    yield
    logger.removeFilter(explode)


def test_p1a_failure_after_storing_logs_the_booking_id(
    app, db, caplog, exploding_email_log, booking_count
):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    with caplog.at_level(logging.WARNING):
        response = post(app.test_client(), payload())

    assert response.status_code == 500
    assert booking_count() == 1
    booking_id = db.execute("SELECT id FROM bookings").fetchone()[0]
    assert len(caplog.records) == 1
    line = caplog.records[0].getMessage()
    assert "RuntimeError" in line
    assert f"booking {booking_id}" in line
    assert "secret detail" not in all_log_text(caplog)
    assert "alice@example.com" not in all_log_text(caplog)


def test_p1a_failure_before_storing_logs_no_booking_id(app, db, caplog):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT always_fails CHECK (client_name <> 'Alice Example')"
    )

    with caplog.at_level(logging.WARNING):
        post(app.test_client(), payload())

    assert "booking" not in caplog.records[0].getMessage()


# --- P1 (b): line breaks in client text are collapsed in the logs


def email_log(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.email"]


def test_p1b_line_breaks_in_details_are_collapsed_in_the_logged_email(client, db, caplog):
    details = "First line\n\n\nTo: attacker@evil.example\nSubject: You have won"

    with caplog.at_level(logging.INFO, logger="app.email"):
        assert post(client, payload(details=details)).status_code == 201

    to_team = [text for text in email_log(caplog) if TEAM_EMAIL in text]
    assert len(to_team) == 1
    assert "First line To: attacker@evil.example Subject: You have won" in to_team[0]
    assert not any(line.startswith("To: attacker") for line in to_team[0].splitlines())
    assert not any(line.startswith("Subject: You have won") for line in to_team[0].splitlines())
    # S2: what is stored is unchanged.
    assert db.execute("SELECT event_details FROM bookings").fetchone()[0] == details


@pytest.mark.parametrize(
    "separator",
    [
        pytest.param(" ", id="line-separator"),
        pytest.param(" ", id="paragraph-separator"),
        pytest.param("   ", id="a-run-of-separators"),
    ],
)
def test_p1b_unicode_line_breaks_in_the_name_are_collapsed(client, db, caplog, separator):
    # These are not control characters (V1), so the name is accepted.
    name = f"Alice{separator}To: attacker@evil.example"

    with caplog.at_level(logging.INFO, logger="app.email"):
        assert post(client, payload(name=name)).status_code == 201

    messages = email_log(caplog)
    assert len(messages) == 2
    for text in messages:
        assert "Alice To: attacker@evil.example" in text
        assert separator[0] not in text
        assert " " not in text
    assert db.execute("SELECT client_name FROM bookings").fetchone()[0] == name


def test_p1b_details_without_line_breaks_are_logged_unchanged(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.email"):
        post(client, payload(details="Tom & Jerry  <b>party</b>"))

    to_team = [text for text in email_log(caplog) if TEAM_EMAIL in text]
    assert "Tom & Jerry  <b>party</b>" in to_team[0]
