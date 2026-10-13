"""F01 validation rules V1 to V14 and response A1.

Every expected value comes from docs/specs/F01.md; each test names the rule it checks.
"""

from datetime import datetime, timedelta

import pytest
from f01_helpers import NOW, iso, payload, post, without


def fields(response):
    """The failing fields of an A5 response."""
    assert response.status_code == 400
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert set(body) == {"error", "fields"}
    return body["fields"]


# --- A1: booking created


def test_a1_valid_request_is_created(client, booking_count):
    response = post(client, payload())

    assert response.status_code == 201
    assert response.content_type == "application/json"
    body = response.get_json()
    assert set(body) == {"id", "state", "starts_at", "ends_at"}
    assert isinstance(body["id"], int)
    assert body["state"] == "submitted"
    assert body["starts_at"] == "2026-04-01T10:00"
    assert body["ends_at"] == "2026-04-01T14:00"
    assert booking_count() == 1


def test_g1_created_response_holds_no_client_details(client):
    """G1: a response never contains name, email, phone or details."""
    response = post(client, payload())

    assert response.status_code == 201
    text = response.get_data(as_text=True)
    for private in ("Alice Example", "alice@example.com", "07700 900123", "Birthday party"):
        assert private not in text


# --- V1: name


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param(without(payload(), "name"), "required", id="missing"),
        pytest.param(payload(name=""), "required", id="empty"),
        pytest.param(payload(name="   "), "required", id="only-spaces"),
        pytest.param(payload(name="\t\n "), "required", id="only-tab-and-newline"),
        pytest.param(payload(name="  　"), "required", id="only-unicode-spaces"),
        pytest.param(payload(name=123), "required", id="not-a-string"),
        pytest.param(payload(name=None), "required", id="null"),
        pytest.param(payload(name=["Alice"]), "required", id="list"),
        pytest.param(payload(name="a" * 101), "too_long", id="101-chars"),
        pytest.param(payload(name="\U0001f389" * 101), "too_long", id="101-emoji"),
        pytest.param(payload(name="Ali\x00ce"), "invalid", id="nul"),
        pytest.param(payload(name="Ali\tce"), "invalid", id="tab-inside"),
        pytest.param(payload(name="Ali\nce"), "invalid", id="newline-inside"),
        pytest.param(payload(name="Ali\rce"), "invalid", id="carriage-return-inside"),
        pytest.param(payload(name="Ali\x1bce"), "invalid", id="escape"),
        pytest.param(payload(name="Ali\x7fce"), "invalid", id="delete"),
        pytest.param(payload(name="Ali\x9fce"), "invalid", id="c1-control"),
        pytest.param(payload(name="Ali\ud800ce"), "invalid", id="unpaired-surrogate"),
        pytest.param(payload(name="\x00" + "a" * 101), "too_long", id="too-long-wins-over-invalid"),
    ],
)
def test_v1_bad_name_is_refused(client, booking_count, body, code):
    assert fields(post(client, body)) == {"name": code}
    assert booking_count() == 0


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("a", id="1-char"),
        pytest.param("a" * 100, id="100-chars"),
        pytest.param("\U0001f389" * 100, id="100-emoji-code-points"),
        pytest.param("é" * 50, id="100-code-points-in-50-accented-letters"),
        pytest.param("  " + "a" * 100 + "\n", id="100-chars-after-trimming"),
        pytest.param("Zoë O'Brien-张 محمد", id="many-scripts"),
    ],
)
def test_v1_name_of_1_to_100_characters_is_accepted(client, name):
    assert post(client, payload(name=name)).status_code == 201


# --- V2: email

LONGEST_EMAIL = "a" * 242 + "@example.com"  # 254 characters


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param(without(payload(), "email"), "required", id="missing"),
        pytest.param(payload(email=""), "required", id="empty"),
        pytest.param(payload(email=" \n "), "required", id="only-whitespace"),
        pytest.param(payload(email=42), "required", id="not-a-string"),
        pytest.param(payload(email="a" + LONGEST_EMAIL), "too_long", id="255-chars"),
        pytest.param(payload(email="plainaddress"), "invalid", id="no-at"),
        pytest.param(payload(email="a@@example.com"), "invalid", id="two-ats"),
        pytest.param(payload(email="a@b@example.com"), "invalid", id="two-ats-apart"),
        pytest.param(payload(email="@example.com"), "invalid", id="nothing-before-at"),
        pytest.param(payload(email="alice@example"), "invalid", id="domain-without-dot"),
        pytest.param(payload(email="alice@.com"), "invalid", id="domain-starts-with-dot"),
        pytest.param(payload(email="alice@example."), "invalid", id="domain-ends-with-dot"),
        pytest.param(payload(email="ali ce@example.com"), "invalid", id="space-inside"),
        pytest.param(payload(email="alice@exam\tple.com"), "invalid", id="tab-inside"),
        pytest.param(payload(email="alice@exam\nple.com"), "invalid", id="newline-inside"),
        pytest.param(
            payload(email="alice@example.com\nBcc: x@evil.example"),
            "invalid",
            id="header-injection",
        ),
        pytest.param(payload(email="alice x@example.com"), "invalid", id="unicode-space"),
        pytest.param(payload(email="ali\x00ce@example.com"), "invalid", id="nul"),
        pytest.param(payload(email="ali\x7fce@example.com"), "invalid", id="delete"),
        pytest.param(payload(email="ali\ud800ce@example.com"), "invalid", id="unpaired-surrogate"),
    ],
)
def test_v2_bad_email_is_refused(client, booking_count, body, code):
    assert fields(post(client, body)) == {"email": code}
    assert booking_count() == 0


@pytest.mark.parametrize(
    "email",
    [
        "a@b.c",
        LONGEST_EMAIL,
        "  alice@example.com  ",
        "first.last+tag@sub.example.co.uk",
        "álice@exämple.com",
    ],
)
def test_v2_valid_email_is_accepted(client, email):
    assert post(client, payload(email=email)).status_code == 201


# --- V3: phone


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param(without(payload(), "phone"), "required", id="missing"),
        pytest.param(payload(phone=""), "required", id="empty"),
        pytest.param(payload(phone="  "), "required", id="only-spaces"),
        pytest.param(payload(phone=7700900123), "required", id="not-a-string"),
        pytest.param(payload(phone="0 7 7 0 0 9 0 0 1 2 3 0 0 0 0 0"), "too_long", id="31-chars"),
        pytest.param(payload(phone="07700 abc 123"), "invalid", id="letters"),
        pytest.param(payload(phone="07700/900123"), "invalid", id="slash"),
        pytest.param(payload(phone="(07700) 900123"), "invalid", id="brackets"),
        pytest.param(payload(phone="07700.900.123"), "invalid", id="dots"),
        pytest.param(payload(phone="07700\t900123"), "invalid", id="tab-inside"),
        pytest.param(payload(phone="07700\n900123"), "invalid", id="newline-inside"),
        pytest.param(payload(phone="07700 900123"), "invalid", id="unicode-space"),
        pytest.param(payload(phone="07700–900123"), "invalid", id="en-dash"),
        pytest.param(
            payload(phone="٠٧٧٠٠٩٠٠١٢٣"),
            "invalid",
            id="arabic-indic-digits",
        ),
        pytest.param(
            payload(phone="０７７００９００１２３"),
            "invalid",
            id="full-width-digits",
        ),
        pytest.param(payload(phone="123456"), "invalid", id="6-digits"),
        pytest.param(payload(phone="1234567890123456"), "invalid", id="16-digits"),
        pytest.param(payload(phone="+ - -"), "invalid", id="no-digits"),
    ],
)
def test_v3_bad_phone_is_refused(client, booking_count, body, code):
    assert fields(post(client, body)) == {"phone": code}
    assert booking_count() == 0


@pytest.mark.parametrize(
    "phone",
    [
        "1234567",
        "123456789012345",
        "+44 7700 900-123",
        "07700-900-123",
        "  07700 900123  ",
        "0 7 7 0 0 9 0 0 1 2 3 0 0 0 0",  # 29 characters, 15 digits
        "0 7 7 0 0 9 0 0 1 2 3 0 0 0 0-",  # 30 characters
    ],
)
def test_v3_valid_phone_is_accepted(client, phone):
    assert post(client, payload(phone=phone)).status_code == 201


# --- V4: guest count


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param(without(payload(), "guest_count"), "required", id="missing"),
        pytest.param(payload(guest_count="40"), "invalid", id="string"),
        pytest.param(payload(guest_count=2.5), "invalid", id="decimal"),
        pytest.param(payload(guest_count=2.0), "invalid", id="decimal-whole"),
        pytest.param(payload(guest_count=True), "invalid", id="boolean"),
        pytest.param(payload(guest_count=None), "invalid", id="null"),
        pytest.param(payload(guest_count=[40]), "invalid", id="list"),
        pytest.param(payload(guest_count=0), "out_of_range", id="zero"),
        pytest.param(payload(guest_count=-1), "out_of_range", id="negative"),
        pytest.param(payload(guest_count=251), "out_of_range", id="251"),
        pytest.param(payload(guest_count=10**400), "out_of_range", id="400-digits"),
    ],
)
def test_v4_bad_guest_count_is_refused(client, booking_count, body, code):
    assert fields(post(client, body)) == {"guest_count": code}
    assert booking_count() == 0


@pytest.mark.parametrize("guest_count", [1, 250])
def test_v4_guest_count_of_1_to_250_is_accepted(client, db, guest_count):
    assert post(client, payload(guest_count=guest_count)).status_code == 201
    assert db.execute("SELECT guest_count FROM bookings").fetchone()[0] == guest_count


# --- V5: the times are well-formed and exist


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param(20260401, id="number"),
        pytest.param("", id="empty"),
        pytest.param("2026-04-01 10:00", id="space-separator"),
        pytest.param("2026-04-01T10:00:00", id="with-seconds"),
        pytest.param("2026-04-01T10:00Z", id="with-zone"),
        pytest.param("2026-04-01T10:00\n", id="trailing-newline"),
        pytest.param(" 2026-04-01T10:00", id="leading-space"),
        pytest.param("01/04/2026 10:00", id="uk-format"),
        pytest.param("2026-4-1T10:00", id="unpadded"),
        pytest.param("２０２６-04-01T10:00", id="full-width-digits"),
        pytest.param("2026-02-30T10:00", id="30-february"),
        pytest.param("2027-02-29T10:00", id="29-february-not-leap"),
        pytest.param("2026-04-31T10:00", id="31-april"),
        pytest.param("2026-13-01T10:00", id="month-13"),
        pytest.param("2026-04-01T24:00", id="hour-24"),
        pytest.param("2026-04-01T10:60", id="minute-60"),
        pytest.param("0000-01-01T10:00", id="year-0000"),
        pytest.param("2026-03-29T01:00", id="skipped-hour-start"),
        pytest.param("2026-03-29T01:30", id="skipped-hour-middle"),
        pytest.param("2026-03-29T01:59", id="skipped-hour-end"),
    ],
)
@pytest.mark.parametrize("field", ["starts_at", "ends_at"])
def test_v5_malformed_or_impossible_time_is_refused(client, booking_count, field, value):
    assert fields(post(client, payload(**{field: value}))) == {field: "invalid"}
    assert booking_count() == 0


@pytest.mark.parametrize("field", ["starts_at", "ends_at"])
def test_v5_missing_time_is_refused(client, booking_count, field):
    assert fields(post(client, without(payload(), field))) == {field: "required"}
    assert booking_count() == 0


@pytest.mark.parametrize(
    "starts_at, ends_at",
    [
        pytest.param(
            "2026-03-28T23:00", "2026-03-29T00:59", id="ends-just-before-the-skipped-hour"
        ),
        pytest.param(
            "2026-03-29T02:00", "2026-03-29T04:00", id="starts-just-after-the-skipped-hour"
        ),
    ],
)
def test_v5_times_either_side_of_the_skipped_hour_exist(client, starts_at, ends_at):
    assert post(client, payload(starts_at=starts_at, ends_at=ends_at)).status_code == 201


def test_v5_time_in_the_repeated_hour_means_its_first_occurrence(client, clock, db):
    # On 25 October 2026 the hour 01:00 to 02:00 happens twice: first in
    # summer time (UTC+1), then in winter time (UTC+0).
    clock.now = datetime(2026, 6, 1, 9, 0)

    response = post(client, payload(starts_at="2026-10-25T01:30", ends_at="2026-10-25T03:30"))

    assert response.status_code == 201
    assert response.get_json()["starts_at"] == "2026-10-25T01:30"
    stored = db.execute("SELECT starts_at AT TIME ZONE 'UTC' FROM bookings").fetchone()[0]
    assert stored == datetime(2026, 10, 25, 0, 30)


# --- V6: no past start


def booking_at(start, hours=2):
    return payload(starts_at=iso(start), ends_at=iso(start + timedelta(hours=hours)))


@pytest.mark.parametrize(
    "start",
    [
        pytest.param(NOW, id="equal-to-now"),
        pytest.param(NOW - timedelta(minutes=1), id="one-minute-ago"),
        pytest.param(NOW - timedelta(days=1), id="yesterday"),
    ],
)
def test_v6_start_not_later_than_now_is_refused(client, booking_count, start):
    assert fields(post(client, booking_at(start))) == {"starts_at": "in_past"}
    assert booking_count() == 0


def test_v6_start_in_year_0001_is_in_the_past(client):
    body = payload(starts_at="0001-01-01T00:00", ends_at="0001-01-01T02:00")

    assert fields(post(client, body)) == {"starts_at": "in_past"}


def test_v6_start_one_minute_after_now_is_accepted(client):
    assert post(client, booking_at(NOW + timedelta(minutes=1))).status_code == 201


# --- V7: at most six calendar months ahead


def test_v7_start_exactly_six_months_ahead_is_accepted(client):
    # NOW is 2026-03-10 09:00, so the limit is 2026-09-10 09:00.
    assert post(client, booking_at(datetime(2026, 9, 10, 9, 0))).status_code == 201


def test_v7_start_one_minute_past_six_months_is_refused(client, booking_count):
    response = post(client, booking_at(datetime(2026, 9, 10, 9, 1)))

    assert fields(response) == {"starts_at": "too_far_ahead"}
    assert booking_count() == 0


def test_v7_limit_uses_last_day_of_a_shorter_month(client, clock):
    # Six months after 31 August 2026 is February 2027, which has 28 days.
    clock.now = datetime(2026, 8, 31, 9, 0)

    assert post(client, booking_at(datetime(2027, 2, 28, 9, 0))).status_code == 201


def test_v7_start_past_the_shorter_month_limit_is_refused(client, clock):
    clock.now = datetime(2026, 8, 31, 9, 0)

    response = post(client, booking_at(datetime(2027, 2, 28, 9, 1)))

    assert fields(response) == {"starts_at": "too_far_ahead"}


def test_v7_limit_crosses_the_year_end(client, clock):
    clock.now = datetime(2026, 10, 15, 12, 0)

    assert post(client, booking_at(datetime(2027, 4, 15, 12, 0))).status_code == 201
    assert fields(post(client, booking_at(datetime(2027, 4, 15, 12, 1)))) == {
        "starts_at": "too_far_ahead"
    }


def test_v7_limit_keeps_the_local_time_of_day_across_a_clock_change(client, clock):
    # Now is in winter time, six months later is in summer time: the limit is
    # still 09:00 on the clock.
    clock.now = datetime(2026, 1, 10, 9, 0)

    assert post(client, booking_at(datetime(2026, 7, 10, 9, 0))).status_code == 201
    assert fields(post(client, booking_at(datetime(2026, 7, 10, 9, 1)))) == {
        "starts_at": "too_far_ahead"
    }


def test_v7_far_future_year_is_refused(client):
    body = payload(starts_at="9999-12-31T10:00", ends_at="9999-12-31T12:00")

    assert fields(post(client, body)) == {"starts_at": "too_far_ahead"}


# --- V8 and V9: length of the booking, in elapsed time


def lasting(minutes):
    start = datetime(2026, 4, 1, 10, 0)
    return payload(starts_at=iso(start), ends_at=iso(start + timedelta(minutes=minutes)))


@pytest.mark.parametrize("minutes", [59, 1, 0, -60])
def test_v8_booking_shorter_than_one_hour_is_refused(client, booking_count, minutes):
    assert fields(post(client, lasting(minutes))) == {"ends_at": "duration_too_short"}
    assert booking_count() == 0


def test_v9_booking_longer_than_twelve_hours_is_refused(client, booking_count):
    assert fields(post(client, lasting(12 * 60 + 1))) == {"ends_at": "duration_too_long"}
    assert booking_count() == 0


@pytest.mark.parametrize("minutes", [60, 12 * 60])
def test_v8_v9_booking_of_one_to_twelve_hours_is_accepted(client, minutes):
    assert post(client, lasting(minutes)).status_code == 201


def test_v8_length_is_elapsed_time_when_the_clocks_go_forward(client, booking_count):
    # 29 March 2026: 01:00 to 02:00 is skipped, so 00:30 to 02:30 lasts 1 hour
    # and 00:30 to 02:00 lasts 30 minutes.
    too_short = post(client, payload(starts_at="2026-03-29T00:30", ends_at="2026-03-29T02:00"))
    assert fields(too_short) == {"ends_at": "duration_too_short"}
    assert booking_count() == 0

    one_hour = post(client, payload(starts_at="2026-03-29T00:30", ends_at="2026-03-29T02:30"))
    assert one_hour.status_code == 201


def test_v9_length_is_elapsed_time_when_the_clocks_go_forward(client):
    # 14:00 to 03:00 is 13 hours on the clock but 12 hours of elapsed time.
    body = payload(starts_at="2026-03-28T14:00", ends_at="2026-03-29T03:00")

    assert post(client, body).status_code == 201


def test_v9_length_is_elapsed_time_when_the_clocks_go_back(client, clock):
    # 25 October 2026: 14:00 to 02:00 is 12 hours on the clock but 13 elapsed.
    clock.now = datetime(2026, 6, 1, 9, 0)
    body = payload(starts_at="2026-10-24T14:00", ends_at="2026-10-25T02:00")

    assert fields(post(client, body)) == {"ends_at": "duration_too_long"}


def test_v8_both_times_in_the_repeated_hour_are_its_first_occurrence(client, clock):
    # 01:00 and 01:59 both mean the first pass through that hour: 59 minutes.
    clock.now = datetime(2026, 6, 1, 9, 0)
    body = payload(starts_at="2026-10-25T01:00", ends_at="2026-10-25T01:59")

    assert fields(post(client, body)) == {"ends_at": "duration_too_short"}


# --- V10: details


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param(payload(details=123), "invalid", id="number"),
        pytest.param(payload(details=["a"]), "invalid", id="list"),
        pytest.param(payload(details={"a": "b"}), "invalid", id="object"),
        pytest.param(payload(details="a\tb"), "invalid", id="tab"),
        pytest.param(payload(details="a\r\nb"), "invalid", id="carriage-return"),
        pytest.param(payload(details="a\x00b"), "invalid", id="nul"),
        pytest.param(payload(details="a\x1bb"), "invalid", id="escape"),
        pytest.param(payload(details="a\x85b"), "invalid", id="c1-control"),
        pytest.param(payload(details="a\ud800b"), "invalid", id="unpaired-surrogate"),
        pytest.param(payload(details="d" * 2001), "too_long", id="2001-chars"),
        pytest.param(payload(details="\U0001f389" * 2001), "too_long", id="2001-emoji"),
    ],
)
def test_v10_bad_details_are_refused(client, booking_count, body, code):
    assert fields(post(client, body)) == {"details": code}
    assert booking_count() == 0


@pytest.mark.parametrize(
    "body, stored",
    [
        pytest.param(without(payload(), "details"), None, id="omitted"),
        pytest.param(payload(details=None), None, id="null"),
        pytest.param(payload(details=""), None, id="empty-is-absent"),
        pytest.param(payload(details="d" * 2000), "d" * 2000, id="2000-chars"),
        pytest.param(
            payload(details="\U0001f389" * 2000), "\U0001f389" * 2000, id="2000-emoji-code-points"
        ),
        pytest.param(payload(details="line 1\nline 2\n"), "line 1\nline 2\n", id="newlines"),
        pytest.param(payload(details="   "), "   ", id="only-spaces-is-kept"),
    ],
)
def test_v10_optional_details_are_accepted(client, db, body, stored):
    assert post(client, body).status_code == 201
    assert db.execute("SELECT event_details FROM bookings").fetchone()[0] == stored


# --- V11: the two ticks


@pytest.mark.parametrize("field", ["terms_accepted", "privacy_notice_accepted"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(False, id="false"),
        pytest.param("true", id="string"),
        pytest.param(1, id="number"),
        pytest.param(None, id="null"),
    ],
)
def test_v11_tick_that_is_not_true_is_refused(client, booking_count, field, value):
    assert fields(post(client, payload(**{field: value}))) == {field: "required"}
    assert booking_count() == 0


@pytest.mark.parametrize("field", ["terms_accepted", "privacy_notice_accepted"])
def test_v11_missing_tick_is_refused(client, booking_count, field):
    assert fields(post(client, without(payload(), field))) == {field: "required"}
    assert booking_count() == 0


# --- V12: CAPTCHA token


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param(without(payload(), "captcha_token"), "required", id="missing"),
        pytest.param(payload(captcha_token=""), "required", id="empty"),
        pytest.param(payload(captcha_token=123), "required", id="not-a-string"),
        pytest.param(payload(captcha_token=None), "required", id="null"),
        pytest.param(payload(captcha_token="t" * 2049), "too_long", id="2049-chars"),
    ],
)
def test_v12_bad_captcha_token_is_refused(client, captcha, booking_count, body, code):
    assert fields(post(client, body)) == {"captcha_token": code}
    assert captcha.calls == []
    assert booking_count() == 0


def test_v12_token_of_2048_characters_is_accepted(client, captcha):
    assert post(client, payload(captcha_token="t" * 2048)).status_code == 201
    assert captcha.calls[0][0] == "t" * 2048


# --- V13: every failing field is reported together


def test_v13_all_failing_fields_are_reported_at_once(client, booking_count):
    body = payload(
        name="",
        email="not-an-email",
        phone="abc",
        guest_count=0,
        starts_at=iso(NOW - timedelta(hours=1)),
        ends_at=iso(NOW - timedelta(minutes=30)),
        details="d" * 2001,
        terms_accepted=False,
        privacy_notice_accepted=False,
        captcha_token="",
    )

    assert fields(post(client, body)) == {
        "name": "required",
        "email": "invalid",
        "phone": "invalid",
        "guest_count": "out_of_range",
        "starts_at": "in_past",
        "ends_at": "duration_too_short",
        "details": "too_long",
        "terms_accepted": "required",
        "privacy_notice_accepted": "required",
        "captcha_token": "required",
    }
    assert booking_count() == 0


def test_v13_empty_object_reports_every_required_field(client):
    assert fields(post(client, {})) == {
        "name": "required",
        "email": "required",
        "phone": "required",
        "guest_count": "required",
        "starts_at": "required",
        "ends_at": "required",
        "terms_accepted": "required",
        "privacy_notice_accepted": "required",
        "captcha_token": "required",
    }


def test_v13_length_is_not_checked_when_start_is_malformed(client):
    """V13: V8 and V9 are checked only when both times are well-formed."""
    body = payload(starts_at="nonsense", ends_at="2026-04-01T14:00")

    assert fields(post(client, body)) == {"starts_at": "invalid"}


def test_v13_past_start_is_still_checked_when_end_is_malformed(client):
    """V13: V6 needs only a well-formed start."""
    body = payload(starts_at=iso(NOW - timedelta(hours=1)), ends_at="nonsense")

    assert fields(post(client, body)) == {"starts_at": "in_past", "ends_at": "invalid"}


def test_v13_far_start_is_still_checked_when_end_is_malformed(client):
    body = payload(starts_at="2027-01-01T10:00", ends_at="nonsense")

    assert fields(post(client, body)) == {"starts_at": "too_far_ahead", "ends_at": "invalid"}


def test_unknown_fields_are_ignored(client, db):
    """Request fields: fields not in the table are ignored."""
    response = post(client, payload(state="accepted", id=999, colour="blue"))

    assert response.status_code == 201
    assert db.execute("SELECT state FROM bookings").fetchone()[0] == "submitted"
    assert response.get_json()["id"] != 999


# --- V14: open 24 hours


@pytest.mark.parametrize(
    "start_time, end_time",
    [
        pytest.param("2026-04-01T00:00", "2026-04-01T01:00", id="midnight-start"),
        pytest.param("2026-04-01T03:00", "2026-04-01T05:00", id="small-hours"),
        pytest.param("2026-04-01T22:59", "2026-04-01T23:59", id="late-evening"),
    ],
)
def test_v14_any_time_of_day_is_accepted(client, start_time, end_time):
    assert post(client, payload(starts_at=start_time, ends_at=end_time)).status_code == 201
