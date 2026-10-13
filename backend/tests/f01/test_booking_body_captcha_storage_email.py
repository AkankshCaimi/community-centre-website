"""F01 body rules B1 to B3, CAPTCHA rules C1 and C2, storage rules S1 to S4,
email rules E1 to E3, and the error responses A9 to A11.

Every expected value comes from docs/specs/F01.md; each test names the rule it checks.
"""

import json
import logging
from datetime import datetime

import pytest
from f01_helpers import NOW, TEAM_EMAIL, payload, post, post_raw


def raw(**overrides):
    """The valid request as JSON text."""
    return json.dumps(payload(**overrides))


def refused(response, status, error):
    return (
        response.status_code == status
        and response.content_type == "application/json"
        and response.get_json() == {"error": error}
    )


# --- B1: only application/json


@pytest.mark.parametrize(
    "content_type",
    [
        pytest.param("text/plain", id="text-plain"),
        pytest.param("application/x-www-form-urlencoded", id="form-encoded"),
        pytest.param("multipart/form-data; boundary=x", id="multipart"),
        pytest.param("application/xml", id="xml"),
        pytest.param("application/jsonx", id="almost-json"),
        pytest.param("text/json", id="text-json"),
        pytest.param(None, id="no-content-type"),
    ],
)
def test_b1_other_content_types_are_refused(client, booking_count, content_type):
    """The body is a perfectly valid request; only the content type is wrong."""
    response = post_raw(client, raw(), content_type=content_type)

    assert refused(response, 415, "unsupported_media_type")
    assert booking_count() == 0


@pytest.mark.parametrize(
    "content_type",
    ["application/json", "application/json; charset=utf-8", "APPLICATION/JSON;charset=UTF-8"],
)
def test_b1_application_json_is_accepted(client, content_type):
    assert post_raw(client, raw(), content_type=content_type).status_code == 201


# --- B2: at most 64 KB


def body_of_exactly(size):
    """A valid request padded with an ignored field to exactly `size` bytes."""
    empty = json.dumps(payload(padding=""))
    body = json.dumps(payload(padding="x" * (size - len(empty.encode()))))
    assert len(body.encode()) == size
    return body


def test_b2_body_of_exactly_64_kb_is_accepted(client):
    assert post_raw(client, body_of_exactly(65536)).status_code == 201


def test_b2_body_one_byte_over_64_kb_is_refused(client, booking_count):
    response = post_raw(client, body_of_exactly(65537))

    assert refused(response, 413, "request_entity_too_large")
    assert booking_count() == 0


# --- B3: the body is one readable JSON object


def nested(levels):
    """A JSON value nested `levels` deep: nested(1) is [], nested(2) is [[]]."""
    return "[" * levels + "]" * levels


@pytest.mark.parametrize(
    "data",
    [
        pytest.param("this is not json", id="not-json"),
        pytest.param("", id="empty-body"),
        pytest.param("[1, 2, 3]", id="array"),
        pytest.param('"a string"', id="string"),
        pytest.param("42", id="number"),
        pytest.param("null", id="null"),
        pytest.param(raw() + raw(), id="two-objects"),
        pytest.param(raw()[:-1], id="truncated"),
        pytest.param(raw().replace('"guest_count": 40', '"guest_count": NaN'), id="nan"),
        pytest.param(raw().replace('"guest_count": 40', '"guest_count": Infinity'), id="infinity"),
        pytest.param(
            raw().replace('"guest_count": 40', '"guest_count": -Infinity'), id="minus-infinity"
        ),
        pytest.param(raw().replace('"guest_count": 40', '"guest_count": 1e2'), id="exponent"),
        pytest.param(
            raw().replace('"guest_count": 40', '"guest_count": 1E2'), id="exponent-capital"
        ),
        pytest.param(
            raw().replace('"guest_count": 40', '"guest_count": 4.0e1'), id="exponent-with-fraction"
        ),
        pytest.param(raw()[:-1] + ', "extra": 1e2}', id="exponent-in-an-ignored-field"),
        pytest.param(raw()[:-1] + ', "name": "Second Name"}', id="duplicate-key"),
        pytest.param(raw()[:-1] + ', "x": {"a": 1, "a": 2}}', id="duplicate-key-nested"),
        pytest.param(raw()[:-1] + ', "x": ' + nested(10) + "}", id="11-levels-deep"),
        pytest.param(raw()[:-1] + ', "x": ' + nested(5000) + "}", id="5000-levels-deep"),
        pytest.param(raw().encode("utf-16"), id="utf-16"),
        pytest.param(b'{"name": "\xff\xfe"}', id="invalid-utf-8"),
    ],
)
def test_b3_unreadable_body_is_refused(client, booking_count, data):
    response = post_raw(client, data)

    assert refused(response, 400, "invalid_request")
    assert booking_count() == 0


def test_b3_ten_levels_deep_is_accepted(client):
    # The outer object is level 1, so nine nested lists inside it reach level 10.
    body = raw()[:-1] + ', "x": ' + nested(9) + "}"

    assert post_raw(client, body).status_code == 201


def test_b3_same_key_in_different_objects_is_not_a_duplicate(client):
    body = raw()[:-1] + ', "x": {"name": 1}, "y": {"name": 2}}'

    assert post_raw(client, body).status_code == 201


def test_b3_decimal_without_exponent_is_a_field_error_not_an_unreadable_body(client):
    """B3 refuses exponents; V4 refuses other decimals as a field error."""
    response = post_raw(client, raw().replace('"guest_count": 40', '"guest_count": 40.0'))

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "validation_failed",
        "fields": {"guest_count": "invalid"},
    }


# --- C1: the token is verified


def test_c1_token_and_address_are_passed_to_the_verifier(client, captcha):
    post(client, payload(captcha_token="abc-123"), ip="198.51.100.7")

    assert captcha.calls == [("abc-123", "198.51.100.7")]


def test_c1_failed_check_is_refused(client, captcha, booking_count):
    captcha.passes = False

    response = post(client, payload())

    assert refused(response, 403, "captcha_failed")
    assert booking_count() == 0


# --- C2: the stand-in verifier


def test_c2_stand_in_passes_every_token_and_logs_one_line(app, booking_count, caplog):
    del app.config["CAPTCHA_VERIFIER"]  # use the application's own verifier

    with caplog.at_level(logging.DEBUG, logger="app.captcha"):
        response = post(app.test_client(), payload(captcha_token="anything at all"))

    assert response.status_code == 201
    assert booking_count() == 1
    records = [record for record in caplog.records if record.name == "app.captcha"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO


# --- S1: what a created booking holds


def test_s1_created_booking_is_submitted_with_times_and_address(client, db):
    post(client, payload(), ip="198.51.100.7")

    row = db.execute(
        """
        SELECT state, guest_count, host(client_ip),
               submitted_at AT TIME ZONE 'Europe/London',
               terms_accepted_at AT TIME ZONE 'Europe/London',
               privacy_notice_accepted_at AT TIME ZONE 'Europe/London',
               erased_at
        FROM bookings
        """
    ).fetchone()

    assert row == ("submitted", 40, "198.51.100.7", NOW, NOW, NOW, None)


def test_s1_start_and_end_are_stored_in_utc(client, db):
    # 1 April is in summer time: 10:00 to 14:00 in London is 09:00 to 13:00 UTC.
    post(client, payload())

    row = db.execute(
        "SELECT starts_at AT TIME ZONE 'UTC', ends_at AT TIME ZONE 'UTC' FROM bookings"
    ).fetchone()

    assert row == (datetime(2026, 4, 1, 9, 0), datetime(2026, 4, 1, 13, 0))


def test_s1_winter_times_are_stored_in_utc_unchanged(client, db):
    # 20 March is in winter time: London time and UTC are the same.
    post(client, payload(starts_at="2026-03-20T10:00", ends_at="2026-03-20T14:00"))

    row = db.execute(
        "SELECT starts_at AT TIME ZONE 'UTC', ends_at AT TIME ZONE 'UTC' FROM bookings"
    ).fetchone()

    assert row == (datetime(2026, 3, 20, 10, 0), datetime(2026, 3, 20, 14, 0))


def test_s1_ipv6_address_is_stored(client, db):
    post(client, payload(), ip="2001:db8:1:2::7")

    assert db.execute("SELECT host(client_ip) FROM bookings").fetchone()[0] == "2001:db8:1:2::7"


def test_s1_response_id_is_the_stored_booking(client, db):
    booking_id = post(client, payload()).get_json()["id"]

    assert db.execute("SELECT id FROM bookings").fetchone()[0] == booking_id


# --- S2: text is stored exactly as sent


def test_s2_text_is_stored_exactly_as_sent(client, db):
    name = "<script>alert('x')</script> O'Brien & Sons"
    details = 'Tom & Jerry <b>party</b> "quoted" é中\U0001f389\nsecond line  '

    assert post(client, payload(name=name, details=details)).status_code == 201

    stored = db.execute("SELECT client_name, event_details FROM bookings").fetchone()
    assert stored == (name, details)


def test_s2_name_email_and_phone_are_trimmed(client, db):
    body = payload(name="  Alice Example ", email=" alice@example.com\n", phone="\t07700 900123 ")

    assert post(client, body).status_code == 201

    stored = db.execute("SELECT client_name, client_email, client_phone FROM bookings").fetchone()
    assert stored == ("Alice Example", "alice@example.com", "07700 900123")


def test_s2_sql_in_text_is_stored_as_text(client, db, booking_count):
    name = "Robert'); DROP TABLE bookings;--"

    assert post(client, payload(name=name)).status_code == 201

    assert booking_count() == 1
    assert db.execute("SELECT client_name FROM bookings").fetchone()[0] == name


# --- S4 and A9 to A11: the API answers in JSON only


def test_s4_refusal_is_json_and_does_not_echo_markup(client):
    response = post(client, payload(name="<b>x</b>" * 20))

    assert response.status_code == 400
    assert response.content_type == "application/json"
    assert "<b>" not in response.get_data(as_text=True)


def test_a9_unknown_address_is_a_json_404(client):
    assert refused(client.get("/api/v1/no-such-thing"), 404, "not_found")


def test_a9_trailing_slash_is_an_unknown_address(client, booking_count):
    response = client.post("/api/v1/bookings/", json=payload())

    assert refused(response, 404, "not_found")
    assert booking_count() == 0


@pytest.mark.parametrize("method", ["get", "put", "delete", "patch"])
def test_a10_other_methods_are_a_json_405(client, method):
    assert refused(getattr(client, method)("/api/v1/bookings"), 405, "method_not_allowed")


def test_a11_unexpected_failure_is_a_json_500(app, caplog):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    # Nothing is listening on port 1, so the database cannot be reached.
    app.config["DATABASE_URL"] = "postgresql://nobody:nothing@127.0.0.1:1/nowhere"

    with caplog.at_level(logging.CRITICAL):
        response = post(app.test_client(), payload())

    assert refused(response, 500, "internal_server_error")


# --- E1 to E3: emails are logged


def email_log(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.email"]


def test_e1_client_confirmation_is_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.email"):
        post(client, payload())

    to_client = [text for text in email_log(caplog) if TEAM_EMAIL not in text]
    assert len(to_client) == 1
    assert "alice@example.com" in to_client[0]
    assert "Alice Example" in to_client[0]
    assert "2026-04-01T10:00" in to_client[0]
    assert "2026-04-01T14:00" in to_client[0]


def test_e1_e2_emails_are_logged_at_info_level(client, caplog):
    with caplog.at_level(logging.DEBUG, logger="app.email"):
        post(client, payload())

    records = [record for record in caplog.records if record.name == "app.email"]
    assert len(records) == 2
    assert {record.levelno for record in records} == {logging.INFO}


def test_e2_team_notification_is_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.email"):
        post(client, payload(guest_count=137))

    to_team = [text for text in email_log(caplog) if TEAM_EMAIL in text]
    assert len(to_team) == 1
    for expected in (
        "Alice Example",
        "alice@example.com",
        "07700 900123",
        "137",
        "2026-04-01T10:00",
        "2026-04-01T14:00",
        "Birthday party",
    ):
        assert expected in to_team[0]


def test_e1_e2_times_are_logged_as_local_times_in_winter_too(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.email"):
        post(client, payload(starts_at="2026-03-20T10:00", ends_at="2026-03-20T14:00"))

    for text in email_log(caplog):
        assert "2026-03-20T10:00" in text
        assert "2026-03-20T14:00" in text


@pytest.mark.parametrize(
    "refused_body, status",
    [
        pytest.param(payload(name=""), 400, id="validation"),
        pytest.param(
            payload(starts_at="2026-04-02T10:00", ends_at="2026-04-02T12:00"), 409, id="day-taken"
        ),
    ],
)
def test_e3_nothing_is_logged_when_a_request_is_refused(client, caplog, refused_body, status):
    post(client, payload(starts_at="2026-04-02T10:00", ends_at="2026-04-02T14:00"))
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="app.email"):
        response = post(client, refused_body)

    assert response.status_code == status
    assert email_log(caplog) == []


def test_e3_nothing_is_logged_when_captcha_fails(client, captcha, caplog):
    captcha.passes = False

    with caplog.at_level(logging.INFO, logger="app.email"):
        response = post(client, payload())

    assert response.status_code == 403
    assert email_log(caplog) == []
