"""F02 rules added after the hostile-input review: CK1, CK2, HD1, SE8, SE9,
PR6, PR7, and the additions to LI3, LI5, LI6, CL2 and PR5.

Every expected value comes from docs/specs/F02.md; each test names the rule it checks.
"""

import logging
import re
import threading
from datetime import UTC, datetime, timedelta

import pytest
from f02_helpers import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    BASE_URL,
    NOT_AUTHENTICATED,
    NOW,
    booking_payload,
    call,
    create_admin,
    login,
    session_cookie,
)


def fields(response):
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    return body["fields"]


def reset_token(app, caplog):
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        call(app.test_client(), "POST", "/password-reset", {"email": ADMIN_EMAIL})
    messages = [r.getMessage() for r in caplog.records if r.name == "app.email"]
    return re.search(r"^Token: (\S+)$", messages[-1], flags=re.MULTILINE).group(1)


def confirm(app, token, password):
    return call(
        app.test_client(), "POST", "/password-reset/confirm", {"token": token, "password": password}
    )


# --- LI3: control characters in the search


@pytest.mark.parametrize(
    "search",
    [
        pytest.param("%00", id="nul"),
        pytest.param("smith%00", id="nul-at-the-end"),
        pytest.param("a%09b", id="tab-inside"),
        pytest.param("a%0Ab", id="newline-inside"),
        pytest.param("a%1Bb", id="escape"),
        pytest.param("a%7Fb", id="delete"),
    ],
)
def test_li3_control_character_in_search_is_refused(app, admin_client, search):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    response = call(admin_client, "GET", f"/bookings?search={search}")

    assert fields(response) == {"search": "invalid"}


def test_li3_search_over_100_characters_wins_over_a_control_character(admin_client):
    response = call(admin_client, "GET", "/bookings?search=" + "a" * 101 + "%00")

    assert fields(response) == {"search": "too_long"}


# --- LI5: very long page numbers


def test_li5_page_of_100_digits_is_an_empty_page(admin_client, make_booking):
    make_booking(1, 1)

    response = call(admin_client, "GET", "/bookings?page=" + "9" * 100)

    assert response.status_code == 200
    body = response.get_json()
    assert body["items"] == []
    assert body["total"] == 1
    assert body["page"] == int("9" * 100)


@pytest.mark.parametrize("digits", [101, 4301, 20000])
@pytest.mark.parametrize("name", ["page", "page_size"])
def test_li5_number_of_more_than_100_digits_is_out_of_range(app, admin_client, name, digits):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    response = call(admin_client, "GET", f"/bookings?{name}=" + "9" * digits)

    assert fields(response) == {name: "out_of_range"}


def test_li5_leading_zeros_count_as_digits(admin_client):
    response = call(admin_client, "GET", "/bookings?page=" + "0" * 100 + "1")

    assert fields(response) == {"page": "out_of_range"}


# --- LI6: a parameter given more than once


def test_li6_first_value_of_a_repeated_parameter_is_used(admin_client, make_booking, db):
    accepted = make_booking(1, 1)
    make_booking(2, 2)
    db.execute("UPDATE bookings SET state = 'accepted' WHERE id = %s", (accepted,))

    by_state = call(admin_client, "GET", "/bookings?state=accepted&state=submitted").get_json()
    by_size = call(admin_client, "GET", "/bookings?page_size=1&page_size=100").get_json()

    assert [item["id"] for item in by_state["items"]] == [accepted]
    assert (len(by_size["items"]), by_size["page_size"]) == (1, 1)


def test_li6_bad_first_value_is_refused_even_if_a_later_one_is_good(admin_client):
    response = call(admin_client, "GET", "/bookings?state=nonsense&state=accepted")

    assert fields(response) == {"state": "invalid"}


# --- PR5 and CL2: control characters in a new password


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("long enough\x00password", id="nul"),
        pytest.param("long enough\tpassword", id="tab"),
        pytest.param("long enough\npassword", id="newline"),
        pytest.param("long enough\x7fpassword", id="delete"),
        pytest.param("long enough\ud800password", id="unpaired-surrogate"),
    ],
)
def test_pr5_control_character_in_new_password_is_refused(app, admin, caplog, password):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    token = reset_token(app, caplog)

    response = confirm(app, token, password)

    assert fields(response) == {"password": "invalid"}
    # The token was not used up, and the old password still works.
    assert login(app.test_client()).status_code == 200
    assert confirm(app, token, "a brand new password").status_code == 200


def test_pr5_length_is_reported_before_control_characters(app, admin, caplog):
    token = reset_token(app, caplog)

    assert fields(confirm(app, token, "short\x00")) == {"password": "too_short"}
    assert fields(confirm(app, token, "\x00" + "p" * 1025)) == {"password": "too_long"}


def test_pr5_spaces_and_other_scripts_are_not_control_characters(app, admin, caplog):
    token = reset_token(app, caplog)
    password = "  pässwörd 密码 \U0001f511 with spaces  "

    assert confirm(app, token, password).status_code == 200
    assert login(app.test_client(), password=password).status_code == 200
    assert login(app.test_client(), password=password.strip()).status_code == 401


def test_cl2_control_character_in_password_creates_nothing(app, db):
    result = create_admin(app, password="long enough\tpassword")

    assert result.exit_code == 1
    assert db.execute("SELECT count(*) FROM admin_users").fetchone()[0] == 0


# --- PR6 and PR7


def test_pr6_two_simultaneous_uses_of_a_token_change_the_password_once(app, admin, caplog):
    token = reset_token(app, caplog)
    passwords = ["first new password", "second new password"]
    barrier = threading.Barrier(2)
    statuses = [None, None]

    def send(index):
        barrier.wait()
        statuses[index] = confirm(app, token, passwords[index]).status_code

    threads = [threading.Thread(target=send, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()

    assert sorted(statuses) == [200, 400]
    winner = passwords[statuses.index(200)]
    loser = passwords[statuses.index(400)]
    assert login(app.test_client(), password=winner).status_code == 200
    assert login(app.test_client(), password=loser).status_code == 401


def test_pr7_new_password_may_equal_the_old_one(app, admin, caplog):
    token = reset_token(app, caplog)

    assert confirm(app, token, ADMIN_PASSWORD).status_code == 200
    assert login(app.test_client()).status_code == 200


# --- B1 on the reset endpoints


@pytest.mark.parametrize("path", ["/password-reset", "/password-reset/confirm"])
def test_b1_reset_endpoints_accept_only_json(app, admin, path):
    response = app.test_client().post(
        "/api/v1/admin" + path,
        data=f"email={ADMIN_EMAIL}",
        content_type="application/x-www-form-urlencoded",
        base_url=BASE_URL,
    )

    assert response.status_code == 415
    assert response.get_json() == {"error": "unsupported_media_type"}


# --- SE5, SE6: logging out twice, and a cookie value chosen by someone else


def test_se5_second_logout_is_refused(admin_client):
    assert call(admin_client, "POST", "/logout", {}).status_code == 200

    again = call(admin_client, "POST", "/logout", {})

    assert again.status_code == 401
    assert again.get_json() == NOT_AUTHENTICATED


def test_se6_cookie_value_planted_before_login_never_becomes_valid(app, admin):
    planted = "value-chosen-by-an-attacker-0123456789-0123456789"
    victim = app.test_client()
    victim.set_cookie("admin_session", planted, domain="localhost", secure=True)

    value, _ = session_cookie(login(victim))

    assert value != planted
    attacker = app.test_client()
    attacker.set_cookie("admin_session", planted, domain="localhost", secure=True)
    assert call(attacker, "GET", "/session").status_code == 401


# --- SE8: more than one session cookie


def test_se8_first_of_two_session_cookies_is_used(app, admin):
    value, _ = session_cookie(login(app.test_client()))

    # use_cookies=False: the client sends exactly the Cookie header written here.
    valid_first = app.test_client(use_cookies=False).get(
        "/api/v1/admin/session",
        base_url=BASE_URL,
        headers={"Cookie": f"admin_session={value}; admin_session=made-up"},
    )
    valid_second = app.test_client(use_cookies=False).get(
        "/api/v1/admin/session",
        base_url=BASE_URL,
        headers={"Cookie": f"admin_session=made-up; admin_session={value}"},
    )

    assert valid_first.status_code == 200
    assert valid_second.status_code == 401


# --- SE9: HEAD on the GET endpoints


@pytest.mark.parametrize("path", ["/session", "/bookings"])
def test_se9_head_needs_a_session(app, admin, path):
    response = call(app.test_client(), "HEAD", path)

    assert response.status_code == 401
    assert response.get_data() == b""


@pytest.mark.parametrize("path", ["/session", "/bookings"])
def test_se9_head_with_a_session_is_the_get_without_a_body(admin_client, path):
    response = call(admin_client, "HEAD", path)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_data() == b""


def test_se9_head_counts_as_a_use_of_the_session(admin_client, clock):
    clock.now = NOW + timedelta(minutes=20)
    assert call(admin_client, "HEAD", "/session").status_code == 200

    clock.now = NOW + timedelta(minutes=45)
    assert call(admin_client, "GET", "/session").status_code == 200


# --- HD1: no copies are kept


def test_hd1_login_responses_are_not_stored(app, admin):
    assert login(app.test_client()).headers.get("Cache-Control") == "no-store"
    assert login(app.test_client(), password="wrong").headers.get("Cache-Control") == "no-store"


@pytest.mark.parametrize(
    "method, path, body",
    [
        pytest.param("GET", "/session", None, id="session"),
        pytest.param("GET", "/bookings", None, id="bookings"),
        pytest.param("GET", "/bookings?page=0", None, id="bookings-refused"),
        pytest.param("PATCH", "/bookings/1/state", {"state": "contacted"}, id="state-change"),
        pytest.param("PATCH", "/bookings/999/state", {"state": "contacted"}, id="state-not-found"),
        pytest.param("POST", "/logout", {}, id="logout"),
    ],
)
def test_hd1_responses_with_a_session_are_not_stored(
    admin_client, make_booking, method, path, body
):
    make_booking(1, 1)

    assert call(admin_client, method, path, body).headers.get("Cache-Control") == "no-store"


@pytest.mark.parametrize(
    "method, path, body",
    [
        pytest.param("GET", "/session", None, id="session"),
        pytest.param("GET", "/bookings", None, id="bookings"),
        pytest.param("POST", "/password-reset", {"email": "x@example.com"}, id="reset"),
        pytest.param(
            "POST", "/password-reset/confirm", {"token": "t", "password": "p" * 12}, id="confirm"
        ),
    ],
)
def test_hd1_responses_without_a_session_are_not_stored(app, admin, method, path, body):
    response = call(app.test_client(), method, path, body)

    assert response.headers.get("Cache-Control") == "no-store"


# --- CK1 and CK2: elapsed time, also in the hour repeated when the clocks go back
#
# On 25 October 2026 the clocks go back at 01:00 UTC: 01:00 to 02:00 London
# time happens twice. These tests give the clock exact instants (CK2).


def instant(hour, minute, second=0):
    return datetime(2026, 10, 25, hour, minute, second, tzinfo=UTC)


def test_ck1_session_lasts_30_minutes_across_the_repeated_hour(app, admin, clock):
    clock.now = instant(0, 40)  # 01:40 on the clock, first time round
    client = app.test_client()
    assert login(client).status_code == 200

    clock.now = instant(1, 9, 59)  # 01:09:59 on the clock, second time round
    assert call(client, "GET", "/session").status_code == 200

    clock.now = instant(1, 39, 59)  # 30 minutes after that use
    assert call(client, "GET", "/session").status_code == 401


def test_ck1_session_is_refused_30_minutes_later_though_the_clock_face_went_back(app, admin, clock):
    clock.now = instant(0, 40)  # 01:40 on the clock
    client = app.test_client()
    login(client)

    clock.now = instant(1, 10)  # 01:10 on the clock, but 30 minutes later

    assert call(client, "GET", "/session").status_code == 401


def test_ck1_reset_token_lasts_30_minutes_across_the_repeated_hour(app, admin, clock, caplog):
    clock.now = instant(0, 40)
    token = reset_token(app, caplog)

    clock.now = instant(1, 10)

    refused = confirm(app, token, "a brand new password")
    assert refused.status_code == 400
    assert refused.get_json() == {"error": "invalid_token"}


def test_ck1_reset_token_is_valid_just_inside_30_minutes_in_the_repeated_hour(
    app, admin, clock, caplog
):
    clock.now = instant(0, 40)
    token = reset_token(app, caplog)

    clock.now = instant(1, 9, 59)

    assert confirm(app, token, "a brand new password").status_code == 200


def test_ck1_submission_time_in_the_second_pass_of_the_repeated_hour_is_stored_exactly(
    app, clock, db
):
    """F01 S1, as CK1 extends it: the stored submission time is the exact instant."""
    clock.now = instant(1, 30)  # 01:30 on the clock, second time round
    body = booking_payload(1, 1, starts_at="2026-11-01T10:00", ends_at="2026-11-01T14:00")

    response = app.test_client().post("/api/v1/bookings", json=body)

    assert response.status_code == 201
    stored = db.execute("SELECT submitted_at AT TIME ZONE 'UTC' FROM bookings").fetchone()[0]
    assert stored == datetime(2026, 10, 25, 1, 30)


def test_ck2_clock_with_a_time_zone_is_that_exact_instant(app, admin, clock, db):
    # 09:00 in New York on 10 March 2026 is 13:00 UTC.
    from zoneinfo import ZoneInfo

    clock.now = datetime(2026, 3, 10, 9, 0, tzinfo=ZoneInfo("America/New_York"))

    login(app.test_client())

    stored = db.execute("SELECT created_at AT TIME ZONE 'UTC' FROM admin_sessions").fetchone()[0]
    assert stored == datetime(2026, 3, 10, 13, 0)


def test_ck2_public_form_checks_a_start_against_the_exact_instant(app, clock):
    """F01 V6 with an exact clock: a start that is already past is refused.

    At 01:30 UTC on 25 October the London clock shows 01:30 for the second
    time. A booking starting at 02:00 London time (02:00 UTC) is 30 minutes
    ahead; one starting at 01:45, first time round (00:45 UTC), is in the past.
    """
    clock.now = instant(1, 30)

    past = app.test_client().post(
        "/api/v1/bookings",
        json=booking_payload(1, 1, starts_at="2026-10-25T01:45", ends_at="2026-10-25T04:00"),
    )
    ahead = app.test_client().post(
        "/api/v1/bookings",
        json=booking_payload(1, 2, starts_at="2026-10-25T02:00", ends_at="2026-10-25T04:00"),
    )

    assert past.get_json() == {"error": "validation_failed", "fields": {"starts_at": "in_past"}}
    assert ahead.status_code == 201


# --- ST7 with simultaneous requests


def test_st7_two_simultaneous_accepts_write_one_email(app, admin, make_booking, caplog):
    booking_id = make_booking(1, 1)
    clients = [app.test_client(), app.test_client()]
    for client in clients:
        login(client)
    barrier = threading.Barrier(2)
    statuses = [None, None]

    def send(index):
        barrier.wait()
        statuses[index] = call(
            clients[index], "PATCH", f"/bookings/{booking_id}/state", {"state": "accepted"}
        ).status_code

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        threads = [threading.Thread(target=send, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            assert not thread.is_alive()

    assert statuses == [200, 200]
    assert len([r for r in caplog.records if r.name == "app.email"]) == 1
