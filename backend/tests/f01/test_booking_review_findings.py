"""F01 rules found untested by the branch review: A10, C2, L1 and V4.

Every expected value comes from docs/specs/F01.md; each test names the rule it checks.
"""

import logging

import pytest
from f01_helpers import payload, person, post, post_raw


def on_day(day, number):
    return payload(
        starts_at=f"2026-04-{day:02d}T10:00", ends_at=f"2026-04-{day:02d}T14:00", **person(number)
    )


# --- A10: OPTIONS and HEAD are refused like any other method


def test_a10_options_is_a_json_405(client):
    response = client.options("/api/v1/bookings")

    assert response.status_code == 405
    assert response.content_type == "application/json"
    assert response.get_json() == {"error": "method_not_allowed"}


def test_a10_head_is_a_405_with_json_content_type_and_no_body(client):
    response = client.head("/api/v1/bookings")

    assert response.status_code == 405
    assert response.content_type == "application/json"
    assert response.get_data() == b""


# --- C2: what the stand-in writes to the log


def test_c2_stand_in_line_holds_neither_token_nor_address(app, caplog):
    del app.config["CAPTCHA_VERIFIER"]  # use the application's own verifier

    with caplog.at_level(logging.INFO, logger="app.captcha"):
        post(app.test_client(), payload(captcha_token="secret-token-123"), ip="198.51.100.7")

    lines = [record.getMessage() for record in caplog.records if record.name == "app.captcha"]
    assert lines == ["CAPTCHA stand-in passed a token."]


# --- L1: an IPv4 address written in IPv6 form is that IPv4 address


def test_l1_ipv4_in_ipv6_form_is_stored_as_ipv4(client, db):
    post(client, payload(), ip="::ffff:203.0.113.10")

    assert db.execute("SELECT host(client_ip) FROM bookings").fetchone()[0] == "203.0.113.10"


def test_l1_ipv4_in_ipv6_form_counts_by_itself(client):
    for number in range(1, 6):
        assert post(client, on_day(number, number), ip="::ffff:203.0.113.10").status_code == 201

    same = post(client, on_day(6, 6), ip="::ffff:203.0.113.10")
    neighbour = post(client, on_day(6, 6), ip="::ffff:203.0.113.11")

    assert same.status_code == 429
    assert neighbour.status_code == 201


def test_l1_both_forms_of_one_ipv4_address_share_the_limit(client):
    for number in range(1, 6):
        assert post(client, on_day(number, number), ip="::ffff:203.0.113.10").status_code == 201

    assert post(client, on_day(6, 6), ip="203.0.113.10").status_code == 429


# --- V4: an integer of any length is a field error, not an unreadable body


@pytest.mark.parametrize("digits", ["9" * 4301, "9" * 20000, "-" + "9" * 5000])
def test_v4_very_long_integer_is_out_of_range(client, booking_count, digits):
    import json

    body = json.dumps(payload()).replace('"guest_count": 40', f'"guest_count": {digits}')

    response = post_raw(client, body)

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "validation_failed",
        "fields": {"guest_count": "out_of_range"},
    }
    assert booking_count() == 0
