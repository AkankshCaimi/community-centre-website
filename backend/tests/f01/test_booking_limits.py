"""F01 limits L1 to L6, the generic refusal G1 and the order of checks O1.

Every expected value comes from docs/specs/F01.md; each test names the rule it checks.
"""

import threading
from datetime import datetime, timedelta

import pytest
from f01_helpers import NOW, iso, payload, person, post, post_raw

RATE_LIMIT_BODY = {
    "error": "rate_limited",
    "message": "Too many responses submitted. Try again later.",
}
NOT_ACCEPTED = {"error": "not_accepted"}


def on_day(day, number, **overrides):
    """A valid request by person(number) for 10:00 to 14:00 on April <day> 2026."""
    body = payload(
        starts_at=f"2026-04-{day:02d}T10:00", ends_at=f"2026-04-{day:02d}T14:00", **person(number)
    )
    body.update(overrides)
    return body


def create(client, body, ip="203.0.113.10"):
    response = post(client, body, ip=ip)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def decline(db, booking_id):
    db.execute("UPDATE bookings SET state = 'declined' WHERE id = %s", (booking_id,))


def refused_as_not_accepted(response):
    return (
        response.status_code == 409
        and response.content_type == "application/json"
        and response.get_json() == NOT_ACCEPTED
    )


# --- L1: rate limit of 5 per network address in 24 hours


def test_l1_fifth_request_from_an_address_is_accepted(client):
    for number in range(1, 6):
        create(client, on_day(number, number))


def test_l1_sixth_request_from_an_address_is_refused(client, booking_count):
    for number in range(1, 6):
        create(client, on_day(number, number))

    response = post(client, on_day(6, 6))

    assert response.status_code == 429
    assert response.content_type == "application/json"
    assert response.get_json() == RATE_LIMIT_BODY
    assert booking_count() == 5


def test_l1_other_ipv4_addresses_are_not_affected(client):
    """L1: an IPv4 address counts by itself, even next to a limited one."""
    for number in range(1, 6):
        create(client, on_day(number, number), ip="203.0.113.10")

    assert post(client, on_day(6, 6), ip="203.0.113.11").status_code == 201


def test_l1_request_is_refused_just_inside_24_hours(client, clock):
    for number in range(1, 6):
        create(client, on_day(number, number))

    clock.now = NOW + timedelta(hours=23, minutes=59)

    assert post(client, on_day(6, 6)).status_code == 429


def test_l1_request_is_accepted_exactly_24_hours_later(client, clock):
    """L1: a booking created exactly 24 hours ago no longer counts."""
    for number in range(1, 6):
        create(client, on_day(number, number))

    clock.now = NOW + timedelta(hours=24)

    assert post(client, on_day(6, 6)).status_code == 201


def test_l1_only_the_last_24_hours_count(client, clock):
    """Four old bookings and four recent ones: the old ones must not count."""
    for number in range(1, 5):
        create(client, on_day(number, number))

    clock.now = NOW + timedelta(hours=25)
    for number in range(5, 9):
        create(client, on_day(number, number))

    assert post(client, on_day(9, 9)).status_code == 201
    assert post(client, on_day(10, 10)).status_code == 429


def test_l1_declined_bookings_still_count(client, db):
    """L1: bookings in every state count."""
    for number in range(1, 6):
        decline(db, create(client, on_day(number, number)))

    assert post(client, on_day(6, 6)).status_code == 429


def test_l1_ipv6_addresses_in_one_64_block_share_the_limit(client):
    for number in range(1, 6):
        create(client, on_day(number, number), ip=f"2001:db8:1:2::{number}")

    response = post(client, on_day(6, 6), ip="2001:db8:1:2:ffff:ffff:ffff:9")

    assert response.status_code == 429


def test_l1_ipv6_address_in_another_64_block_is_not_affected(client):
    for number in range(1, 6):
        create(client, on_day(number, number), ip=f"2001:db8:1:2::{number}")

    assert post(client, on_day(6, 6), ip="2001:db8:1:3::1").status_code == 201


# --- L2: at most 2 active slots per person


def test_l2_second_slot_for_the_same_person_is_accepted(client):
    create(client, on_day(1, 1))

    assert post(client, on_day(2, 1)).status_code == 201


def test_l2_third_slot_with_the_same_email_is_refused(client, booking_count):
    create(client, on_day(1, 1))
    create(client, on_day(2, 1))

    response = post(client, on_day(3, 1, phone="07700 955555"))

    assert refused_as_not_accepted(response)
    assert booking_count() == 2


def test_l2_email_match_ignores_letter_case(client):
    create(client, on_day(1, 1))
    create(client, on_day(2, 1))

    response = post(client, on_day(3, 1, email="PERSON1@Example.COM", phone="07700 955555"))

    assert refused_as_not_accepted(response)


def test_l2_third_slot_with_the_same_phone_is_refused(client):
    create(client, on_day(1, 1))
    create(client, on_day(2, 1))

    response = post(client, on_day(3, 1, email="someone.else@example.com"))

    assert refused_as_not_accepted(response)


@pytest.mark.parametrize(
    "same_number",
    [
        pytest.param("07700900222", id="no-spaces"),
        pytest.param("07700-900-222", id="dashes"),
        pytest.param("0 7700 - 900 222", id="spaces-and-dashes"),
        pytest.param("+447700900222", id="plus-44"),
        pytest.param("+44 7700 900-222", id="plus-44-with-spaces-and-dashes"),
    ],
)
def test_l2_phone_match_normalises_spaces_dashes_and_plus_44(client, same_number):
    create(client, on_day(1, 2, phone="07700 900 222"))
    create(client, on_day(2, 2, phone="07700 900 222"))

    response = post(client, on_day(3, 2, email="someone.else@example.com", phone=same_number))

    assert refused_as_not_accepted(response)


@pytest.mark.parametrize(
    "other_number",
    [
        pytest.param("07700 900 223", id="different-last-digit"),
        pytest.param("447700900222", id="44-without-plus"),
        pytest.param("+33 7700 900 222", id="another-country-code"),
        pytest.param("0+447700900222", id="plus-44-not-leading"),
    ],
)
def test_l2_different_phone_is_a_different_person(client, other_number):
    create(client, on_day(1, 2, phone="07700 900 222"))
    create(client, on_day(2, 2, phone="07700 900 222"))

    response = post(client, on_day(3, 2, email="someone.else@example.com", phone=other_number))

    assert response.status_code == 201


def test_l2_one_slot_by_email_and_one_by_phone_reach_the_limit(client):
    """L2: a booking belongs to the person if email OR phone matches."""
    create(client, on_day(1, 1, phone="07700 911111"))
    create(client, on_day(2, 1, email="other.address@example.com"))

    assert refused_as_not_accepted(post(client, on_day(3, 1)))


def test_l2_another_person_is_not_affected(client):
    create(client, on_day(1, 1))
    create(client, on_day(2, 1))

    assert post(client, on_day(3, 2)).status_code == 201


def test_l2_declined_booking_is_not_an_active_slot(client, db):
    decline(db, create(client, on_day(1, 1)))
    create(client, on_day(2, 1))

    assert post(client, on_day(3, 1)).status_code == 201


def test_l2_booking_whose_end_has_passed_is_not_an_active_slot(client, clock):
    create(client, on_day(1, 1))  # ends 2026-04-01 14:00
    create(client, on_day(2, 1))

    clock.now = datetime(2026, 4, 1, 14, 0)  # the end is no longer later than now

    assert post(client, on_day(3, 1)).status_code == 201


def test_l2_booking_that_has_not_ended_is_still_an_active_slot(client, clock):
    create(client, on_day(1, 1))  # ends 2026-04-01 14:00
    create(client, on_day(2, 1))

    clock.now = datetime(2026, 4, 1, 13, 59)

    assert refused_as_not_accepted(post(client, on_day(3, 1)))


# --- L3: one non-declined booking per calendar day


def test_l3_second_booking_on_a_taken_day_is_refused(client, booking_count):
    create(client, on_day(1, 1))

    response = post(client, on_day(1, 2, starts_at="2026-04-01T18:00", ends_at="2026-04-01T20:00"))

    assert refused_as_not_accepted(response)
    assert booking_count() == 1


def test_l3_next_day_is_free(client):
    create(client, on_day(1, 1))

    assert post(client, on_day(2, 2)).status_code == 201


def test_l3_booking_past_midnight_locks_both_days(client, booking_count):
    create(client, on_day(1, 1, starts_at="2026-04-01T20:00", ends_at="2026-04-02T02:00"))

    first_day = post(client, on_day(1, 2, starts_at="2026-04-01T08:00", ends_at="2026-04-01T10:00"))
    second_day = post(client, on_day(2, 3))

    assert refused_as_not_accepted(first_day)
    assert refused_as_not_accepted(second_day)
    assert booking_count() == 1


def test_l3_request_past_midnight_is_refused_when_its_second_day_is_taken(client):
    create(client, on_day(2, 1))

    response = post(client, on_day(1, 2, starts_at="2026-04-01T20:00", ends_at="2026-04-02T02:00"))

    assert refused_as_not_accepted(response)


def test_l3_booking_ending_at_midnight_does_not_lock_the_next_day(client):
    create(client, on_day(1, 1, starts_at="2026-04-01T18:00", ends_at="2026-04-02T00:00"))

    assert post(client, on_day(2, 2)).status_code == 201


def test_l3_days_are_london_days_not_utc_days(client):
    """L3: calendar days in Europe/London time.

    In summer time 00:30 on 1 April in London is 23:30 on 31 March in UTC. The
    booking must lock 1 April and leave 31 March free.
    """
    create(client, on_day(1, 1, starts_at="2026-04-01T00:30", ends_at="2026-04-01T02:00"))

    march_31 = post(
        client, payload(starts_at="2026-03-31T10:00", ends_at="2026-03-31T14:00", **person(2))
    )
    april_1 = post(client, on_day(1, 3, starts_at="2026-04-01T12:00", ends_at="2026-04-01T14:00"))

    assert march_31.status_code == 201
    assert refused_as_not_accepted(april_1)


def test_l3_declined_booking_locks_nothing(client, db):
    decline(db, create(client, on_day(1, 1)))

    assert post(client, on_day(1, 2)).status_code == 201


# --- L4: double submit


def test_l4_repeated_submission_is_refused_by_the_day_lock(client, booking_count):
    body = payload()
    create(client, body)

    response = post(client, body)

    assert refused_as_not_accepted(response)
    assert booking_count() == 1


# --- G1: refusals are generic


def test_g1_day_taken_and_slot_limit_are_the_same_response(client):
    create(client, on_day(1, 1))
    create(client, on_day(2, 1))

    slot_limit = post(client, on_day(3, 1))  # person 1 holds 2 slots, day 3 is free
    day_taken = post(client, on_day(1, 2))  # person 2 holds none, day 1 is taken

    assert slot_limit.status_code == day_taken.status_code == 409
    assert slot_limit.get_data() == day_taken.get_data()
    assert slot_limit.get_json() == NOT_ACCEPTED


def test_g1_refusal_carries_no_date_and_no_message(client):
    create(client, on_day(1, 1))

    text = post(client, on_day(1, 2)).get_data(as_text=True)

    assert "2026" not in text
    assert "message" not in text
    assert "day" not in text.lower()
    assert "taken" not in text.lower()


# --- L5: limits hold for simultaneous requests


def post_simultaneously(app, bodies, addresses):
    """Send every body at the same instant, each from its own client. Returns the statuses."""
    barrier = threading.Barrier(len(bodies))
    statuses = [None] * len(bodies)

    def send(index):
        client = app.test_client()
        barrier.wait()
        statuses[index] = post(client, bodies[index], ip=addresses[index]).status_code

    threads = [threading.Thread(target=send, args=(index,)) for index in range(len(bodies))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return statuses


def one_address(count):
    return ["203.0.113.10"] * count


def different_addresses(count):
    return [f"198.51.100.{index + 1}" for index in range(count)]


def test_l5_two_simultaneous_requests_for_one_day_create_exactly_one(app, booking_count):
    statuses = post_simultaneously(app, [on_day(1, 1), on_day(1, 2)], different_addresses(2))

    assert sorted(statuses) == [201, 409]
    assert booking_count() == 1


def test_l5_many_simultaneous_requests_for_one_day_create_exactly_one(app, booking_count):
    # Eight people, each from a different address, so only the day lock applies.
    bodies = [on_day(1, number) for number in range(1, 9)]

    statuses = post_simultaneously(app, bodies, different_addresses(8))

    assert sorted(statuses) == [201] + [409] * 7
    assert booking_count() == 1


def test_l5_simultaneous_requests_cannot_take_an_address_past_five(app, booking_count):
    # Eight different people asking for eight different days from one address.
    bodies = [on_day(number, number) for number in range(1, 9)]

    statuses = post_simultaneously(app, bodies, one_address(8))

    assert sorted(statuses) == [201] * 5 + [429] * 3
    assert booking_count() == 5


def test_l5_simultaneous_requests_cannot_take_a_person_past_two(app, booking_count):
    # One person asking for five different days, each from a different address.
    bodies = [on_day(day, 1) for day in range(1, 6)]

    statuses = post_simultaneously(app, bodies, different_addresses(5))

    assert sorted(statuses) == [201] * 2 + [409] * 3
    assert booking_count() == 2


# --- L6: which network address is used


def stored_addresses(db):
    return [row[0] for row in db.execute("SELECT host(client_ip) FROM bookings ORDER BY id")]


def test_l6_forwarded_header_from_the_client_is_ignored(client, db):
    post(client, on_day(1, 1), ip="203.0.113.10", headers={"X-Forwarded-For": "198.51.100.77"})

    assert stored_addresses(db) == ["203.0.113.10"]


def test_l6_forged_forwarded_header_does_not_escape_the_rate_limit(client):
    for number in range(1, 6):
        create(client, on_day(number, number))

    response = post(client, on_day(6, 6), headers={"X-Forwarded-For": "198.51.100.77"})

    assert response.status_code == 429


@pytest.mark.parametrize(
    "hops, header, expected",
    [
        pytest.param(1, "198.51.100.7", "198.51.100.7", id="one-hop-one-entry"),
        pytest.param(1, "192.0.2.1, 198.51.100.7", "198.51.100.7", id="one-hop-takes-rightmost"),
        pytest.param(2, "192.0.2.1, 198.51.100.7, 10.0.0.1", "198.51.100.7", id="two-hops"),
        pytest.param(1, "192.0.2.1,2001:db8::5", "2001:db8::5", id="ipv6-entry"),
        pytest.param(1, "192.0.2.1,   198.51.100.7  ", "198.51.100.7", id="spaces-around-entry"),
        pytest.param(2, "198.51.100.7", "203.0.113.10", id="fewer-entries-than-hops"),
        pytest.param(1, "not-an-address", "203.0.113.10", id="entry-is-not-an-address"),
        pytest.param(1, "198.51.100.7, ", "203.0.113.10", id="empty-rightmost-entry"),
        pytest.param(0, "198.51.100.7", "203.0.113.10", id="zero-hops-ignores-header"),
    ],
)
def test_l6_trusted_proxy_hops_select_the_forwarded_entry(app, db, hops, header, expected):
    app.config["TRUSTED_PROXY_HOPS"] = hops

    response = post(
        app.test_client(), on_day(1, 1), ip="203.0.113.10", headers={"X-Forwarded-For": header}
    )

    assert response.status_code == 201
    assert stored_addresses(db) == [expected]


def test_l6_missing_header_with_trusted_proxy_uses_the_connection(app, db):
    app.config["TRUSTED_PROXY_HOPS"] = 1

    post(app.test_client(), on_day(1, 1), ip="203.0.113.10")

    assert stored_addresses(db) == ["203.0.113.10"]


def test_l6_rate_limit_follows_the_forwarded_address_behind_a_trusted_proxy(app):
    app.config["TRUSTED_PROXY_HOPS"] = 1
    client = app.test_client()
    for number in range(1, 6):
        create_response = post(
            client, on_day(number, number), headers={"X-Forwarded-For": "198.51.100.7"}
        )
        assert create_response.status_code == 201

    same_visitor = post(client, on_day(6, 6), headers={"X-Forwarded-For": "198.51.100.7"})
    other_visitor = post(client, on_day(6, 6), headers={"X-Forwarded-For": "198.51.100.8"})

    assert same_visitor.status_code == 429
    assert other_visitor.status_code == 201


# --- O1: order of checks


def test_o1_wrong_method_comes_before_content_type(client):
    response = client.put("/api/v1/bookings", data="x", content_type="text/plain")

    assert response.status_code == 405


def test_o1_content_type_comes_before_body_size(client):
    response = post_raw(client, b"x" * 70000, content_type="text/plain")

    assert response.status_code == 415


def test_o1_body_size_comes_before_reading_the_json(client):
    response = post_raw(client, b"x" * 70000)

    assert response.status_code == 413


def test_o1_unreadable_body_comes_before_validation(client):
    response = post_raw(client, '{"name": "", "name": ""}')

    assert response.get_json() == {"error": "invalid_request"}


def test_o1_validation_comes_before_captcha(client, captcha):
    captcha.passes = False

    response = post(client, payload(name=""))

    assert response.status_code == 400
    assert captcha.calls == []


def test_o1_captcha_comes_before_the_rate_limit(client, captcha):
    for number in range(1, 6):
        create(client, on_day(number, number))
    captcha.passes = False

    assert post(client, on_day(6, 6)).status_code == 403


def test_o1_rate_limit_comes_before_the_slot_limit_and_day_lock(client):
    create(client, on_day(1, 1))
    create(client, on_day(2, 1))
    for number in range(3, 6):
        create(client, on_day(number, number))

    # Person 1 holds 2 slots and day 1 is taken, but the address has made 5 requests.
    assert post(client, on_day(1, 1)).status_code == 429


@pytest.mark.parametrize("day", [1, 3])
def test_o1_nothing_is_stored_when_a_check_fails(client, booking_count, day):
    create(client, on_day(1, 1))
    create(client, on_day(2, 1))

    post(client, on_day(day, 1))

    assert booking_count() == 2


def test_times_in_iso_helper_match_the_spec_format():
    """Guards the helper used above against drifting from V5."""
    assert iso(datetime(2026, 4, 1, 9, 5)) == "2026-04-01T09:05"
