"""F04 rules E1 to E5 (what erasing means), D1 to D9 (deleting by an admin)
and A1 to A4 (erased bookings in the admin API).

Every expected value comes from docs/specs/F04.md; each test names the rule it checks.
"""

import logging
import threading
from datetime import datetime, timedelta

import pytest
from f04_helpers import (
    BASE_URL,
    NOTHING,
    NOW,
    admin_call,
    booking_payload,
    emptied,
    erase,
    is_erased,
    kept,
    logged_in_client,
    move,
    run_command,
)

LIVE = {"error": "booking_is_live"}


@pytest.fixture
def declined(admin, make_booking, app):
    """A declined booking: it can be erased (D4)."""
    booking_id = make_booking(1, 1)
    move(app, booking_id, "declined")
    return booking_id


# --- D5 and E1: erasing


def test_d5_erase_answers_with_the_booking_and_its_details_empty(app, declined):
    response = erase(app, declined)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {
        "id": declined,
        "state": "declined",
        "name": None,
        "email": None,
        "phone": None,
        "guest_count": None,
        "starts_at": "2026-04-01T10:00",
        "ends_at": "2026-04-01T14:00",
        "details": None,
        "submitted_at": "2026-03-10T09:00",
        "auto_declined": False,
    }


def test_e1_client_details_are_emptied_and_the_rest_is_kept(app, declined, db, clock):
    before_emptied = emptied(db, declined)
    before_kept = kept(db, declined)
    assert None not in before_emptied  # every detail was there to begin with
    clock.now = NOW + timedelta(hours=3)

    erase(app, declined)

    assert emptied(db, declined) == NOTHING
    assert kept(db, declined) == before_kept
    erased_at = db.execute(
        "SELECT erased_at AT TIME ZONE 'Europe/London' FROM bookings WHERE id = %s", (declined,)
    ).fetchone()[0]
    assert erased_at == NOW + timedelta(hours=3)


def test_e1_only_the_named_booking_is_erased(app, declined, make_booking, db):
    other = make_booking(2, 2)
    before = db.execute("SELECT * FROM bookings WHERE id = %s", (other,)).fetchone()

    assert erase(app, declined).status_code == 200

    assert db.execute("SELECT * FROM bookings WHERE id = %s", (other,)).fetchone() == before
    assert is_erased(db, other) is False


def test_d1_erase_response_is_not_stored(app, declined):
    assert erase(app, declined).headers.get("Cache-Control") == "no-store"


# --- D2: confirmation


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="missing"),
        pytest.param({"confirm": False}, id="false"),
        pytest.param({"confirm": "true"}, id="string"),
        pytest.param({"confirm": 1}, id="number"),
        pytest.param({"confirm": None}, id="null"),
    ],
)
def test_d2_erase_without_confirmation_is_refused(app, declined, db, body):
    response = erase(app, declined, body=body)

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "validation_failed",
        "fields": {"confirm": "required"},
    }
    assert is_erased(db, declined) is False


# --- D3: which booking


@pytest.mark.parametrize("booking_id", ["999999", "0", "-1", "abc", "1.5", "9" * 30, "9" * 5000])
def test_d3_unknown_booking_is_not_found(app, declined, booking_id):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    response = erase(app, booking_id)

    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert response.get_json() == {"error": "not_found"}
    # The address itself works for a booking that exists.
    assert erase(app, declined).status_code == 200


# --- D4: only when the booking is no longer live


@pytest.mark.parametrize("state", ["submitted", "contacted", "accepted"])
def test_d4_upcoming_booking_that_is_not_declined_cannot_be_erased(
    app, admin, make_booking, db, state
):
    booking_id = make_booking(1, 1)
    if state != "submitted":
        move(app, booking_id, state)
    before = db.execute("SELECT * FROM bookings").fetchall()

    response = erase(app, booking_id)

    assert response.status_code == 409
    assert response.content_type == "application/json"
    assert response.get_json() == LIVE
    assert db.execute("SELECT * FROM bookings").fetchall() == before


@pytest.mark.parametrize("state", ["contacted", "accepted"])
def test_d4_booking_can_be_erased_from_the_moment_it_ends(
    app, admin, make_booking, db, clock, state
):
    booking_id = make_booking(1, 1)  # ends 2026-04-01 14:00
    move(app, booking_id, state)

    clock.now = datetime(2026, 4, 1, 13, 59, 59)
    assert erase(app, booking_id).get_json() == LIVE

    clock.now = datetime(2026, 4, 1, 14, 0)  # its end is no longer later than now
    assert erase(app, booking_id).status_code == 200
    assert is_erased(db, booking_id) is True
    assert kept(db, booking_id)[1] == state


def test_d4_declined_upcoming_booking_can_be_erased(app, declined, db):
    assert erase(app, declined).status_code == 200
    assert is_erased(db, declined) is True


def test_d4_auto_declined_booking_can_be_erased(app, admin, make_booking, db, clock):
    booking_id = make_booking(1, 1)
    clock.now = NOW + timedelta(hours=48)
    assert run_command(app, "auto-decline").exit_code == 0

    response = erase(app, booking_id)

    assert response.status_code == 200
    assert response.get_json()["auto_declined"] is True
    assert is_erased(db, booking_id) is True


# --- D6 and E5: deleting twice


def test_d6_erasing_twice_answers_the_same_and_changes_nothing(app, declined, db, clock):
    first = erase(app, declined)
    after_first = db.execute("SELECT * FROM bookings").fetchall()
    clock.now = NOW + timedelta(hours=5)

    second = erase(app, declined)

    assert second.status_code == 200
    assert second.get_json() == first.get_json()
    assert db.execute("SELECT * FROM bookings").fetchall() == after_first


def test_d6_booking_the_purge_erased_is_answered_as_erased_even_while_live(
    app, admin, make_booking, db, clock
):
    # Requested six months ahead and accepted: when the purge is due, the
    # event has not ended, so the booking is erased and still live.
    booking_id = make_booking(1, 1, starts_at="2026-09-10T09:00", ends_at="2026-09-10T13:00")
    move(app, booking_id, "accepted")
    clock.now = datetime(2026, 9, 10, 9, 0)
    assert run_command(app, "purge").exit_code == 0
    assert is_erased(db, booking_id) is True
    after_purge = db.execute("SELECT * FROM bookings").fetchall()

    response = erase(app, booking_id)

    assert response.status_code == 200
    assert response.get_json()["name"] is None
    assert response.get_json()["state"] == "accepted"
    assert db.execute("SELECT * FROM bookings").fetchall() == after_purge


# --- D7: two admins at once


def test_d7_two_simultaneous_erasures_erase_once(app, declined, db, caplog):
    clients = [logged_in_client(app), logged_in_client(app)]
    barrier = threading.Barrier(2)
    responses = [None, None]

    def send(index):
        barrier.wait()
        responses[index] = erase(app, declined, client=clients[index])

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.auth"):
        threads = [threading.Thread(target=send, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            assert not thread.is_alive()

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].get_json() == responses[1].get_json()
    assert is_erased(db, declined) is True
    lines = [
        r.getMessage()
        for r in caplog.records
        if r.name == "app.auth" and "erased" in r.getMessage()
    ]
    assert lines == [f"Booking {declined} erased by an admin."]


# --- D8: the log line


def auth_lines(caplog):
    return [record for record in caplog.records if record.name == "app.auth"]


def test_d8_erasure_writes_one_line_with_the_booking_id_only(app, declined, caplog):
    client = logged_in_client(app)
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        erase(app, declined, client=client)

    records = auth_lines(caplog)
    assert [record.getMessage() for record in records] == [
        f"Booking {declined} erased by an admin."
    ]
    assert [record.levelno for record in records] == [logging.INFO]
    everything = "\n".join(record.getMessage() for record in caplog.records)
    for private in ("Person 1", "person1@example.com", "07700 900001", "Party 1"):
        assert private not in everything


def test_d8_repeated_request_writes_nothing(app, declined, caplog):
    client = logged_in_client(app)
    erase(app, declined, client=client)
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.auth"):
        assert erase(app, declined, client=client).status_code == 200

    assert auth_lines(caplog) == []


def test_d8_refused_requests_write_nothing(app, admin, make_booking, caplog):
    live = make_booking(1, 1)
    client = logged_in_client(app)
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.auth"):
        assert erase(app, live, client=client).status_code == 409
        assert erase(app, live, client=client, body={}).status_code == 400
        assert erase(app, 999999, client=client).status_code == 404

    assert auth_lines(caplog) == []


# --- D1 and D9: session, body and the order of checks


def test_d1_erase_needs_a_session(app, declined, db):
    response = app.test_client().post(
        f"/api/v1/admin/bookings/{declined}/erase", json={"confirm": True}, base_url=BASE_URL
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "not_authenticated"}
    assert is_erased(db, declined) is False


def test_d9_session_comes_first(app, declined):
    response = app.test_client().post(
        "/api/v1/admin/bookings/999999/erase",
        data="x",
        content_type="text/plain",
        base_url=BASE_URL,
    )

    assert response.status_code == 401


def test_d1_erase_accepts_only_json(app, declined, db):
    client = logged_in_client(app)

    response = client.post(
        f"/api/v1/admin/bookings/{declined}/erase",
        data="confirm=true",
        content_type="application/x-www-form-urlencoded",
        base_url=BASE_URL,
    )

    assert response.status_code == 415
    assert is_erased(db, declined) is False


def test_d9_confirmation_is_checked_before_the_booking_is_looked_up(app, admin):
    response = erase(app, 999999, body={})

    assert response.status_code == 400
    assert response.get_json()["fields"] == {"confirm": "required"}


def test_d9_existence_is_checked_before_liveness(app, admin, make_booking):
    live = make_booking(1, 1)

    assert erase(app, live).status_code == 409
    assert erase(app, 999999).status_code == 404


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
def test_d1_only_post_is_allowed(app, declined, db, method):
    response = admin_call(app, method, f"/bookings/{declined}/erase", {"confirm": True})

    assert response.status_code == 405
    assert response.get_json() == {"error": "method_not_allowed"}
    assert is_erased(db, declined) is False


# --- E4: an erased booking no longer counts towards the limits


def test_e4_erased_booking_does_not_count_towards_the_rate_limit(app, admin, make_booking):
    ids = [make_booking(number, number, ip="203.0.113.50") for number in range(1, 6)]
    sixth = booking_payload(6, 6)
    refused = app.test_client().post(
        "/api/v1/bookings", json=sixth, environ_base={"REMOTE_ADDR": "203.0.113.50"}
    )
    assert refused.status_code == 429

    move(app, ids[0], "declined")
    assert erase(app, ids[0]).status_code == 200

    allowed = app.test_client().post(
        "/api/v1/bookings", json=sixth, environ_base={"REMOTE_ADDR": "203.0.113.50"}
    )
    assert allowed.status_code == 201


# --- A1 and A2: erased bookings in the list


@pytest.fixture
def three_with_one_erased(admin, make_booking, app):
    """Bookings named Alice, Bob and Carol; Bob's is declined and erased."""
    alice = make_booking(1, 1, name="Alice Adams")
    bob = make_booking(2, 2, name="Bob Brown")
    carol = make_booking(3, 3, name="Carol Clark")
    move(app, bob, "declined")
    assert erase(app, bob).status_code == 200
    return {"alice": alice, "bob": bob, "carol": carol}


def listing(app, query=""):
    response = admin_call(app, "GET", "/bookings" + query)
    assert response.status_code == 200
    return response.get_json()


def test_a1_erased_booking_stays_in_the_list_with_empty_details(app, three_with_one_erased):
    body = listing(app)

    assert body["total"] == 3
    item = next(item for item in body["items"] if item["id"] == three_with_one_erased["bob"])
    assert item == {
        "id": three_with_one_erased["bob"],
        "state": "declined",
        "name": None,
        "email": None,
        "phone": None,
        "guest_count": None,
        "starts_at": "2026-04-02T10:00",
        "ends_at": "2026-04-02T14:00",
        "details": None,
        "submitted_at": "2026-03-10T09:00",
        "auto_declined": False,
    }


def test_a1_no_field_is_added_to_any_item(app, three_with_one_erased):
    for item in listing(app)["items"]:
        assert set(item) == {
            "id",
            "state",
            "name",
            "email",
            "phone",
            "guest_count",
            "starts_at",
            "ends_at",
            "details",
            "submitted_at",
            "auto_declined",
        }


@pytest.mark.parametrize("search", ["Bob", "brown", "person2@example.com", "900002"])
def test_a2_search_never_matches_an_erased_booking(app, three_with_one_erased, search):
    assert listing(app, f"?search={search}")["total"] == 0


def test_a2_state_and_date_filters_still_find_an_erased_booking(app, three_with_one_erased):
    bob = three_with_one_erased["bob"]

    assert [item["id"] for item in listing(app, "?state=declined")["items"]] == [bob]
    by_date = listing(app, "?from=2026-04-02&to=2026-04-02")
    assert [item["id"] for item in by_date["items"]] == [bob]


def test_a2_erased_bookings_sort_after_names_ascending_and_before_them_descending(
    app, three_with_one_erased
):
    made = three_with_one_erased

    ascending = [item["id"] for item in listing(app, "?sort=name&order=asc")["items"]]
    descending = [item["id"] for item in listing(app, "?sort=name&order=desc")["items"]]

    assert ascending == [made["alice"], made["carol"], made["bob"]]
    assert descending == [made["bob"], made["carol"], made["alice"]]


# --- A3: the state of an erased booking can still be changed


def test_a3_accepting_an_erased_booking_writes_no_email(
    app, admin, make_booking, db, clock, caplog
):
    booking_id = make_booking(1, 1)
    move(app, booking_id, "contacted")
    clock.now = datetime(2026, 4, 2, 9, 0)  # the event is over
    assert erase(app, booking_id).status_code == 200
    app.config["PROPAGATE_EXCEPTIONS"] = False
    client = logged_in_client(app)
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="app.email"):
        response = admin_call(
            app, "PATCH", f"/bookings/{booking_id}/state", {"state": "accepted"}, client=client
        )

    assert response.status_code == 200
    assert response.get_json()["state"] == "accepted"
    assert response.get_json()["name"] is None
    assert [record for record in caplog.records if record.name == "app.email"] == []
    assert is_erased(db, booking_id) is True


def test_a3_erased_booking_can_be_declined_to_free_its_day(app, admin, make_booking, db, clock):
    booking_id = make_booking(1, 1, starts_at="2026-09-10T09:00", ends_at="2026-09-10T13:00")
    move(app, booking_id, "accepted")
    clock.now = datetime(2026, 9, 10, 9, 0)
    run_command(app, "purge")
    assert is_erased(db, booking_id) is True

    response = move(app, booking_id, "declined")

    assert response.get_json()["state"] == "declined"
    assert emptied(db, booking_id) == NOTHING


# --- A4: the auto-decline job and erased bookings


def test_a4_auto_decline_treats_an_erased_booking_like_any_other(
    app, admin, make_booking, db, clock
):
    booking_id = make_booking(1, 1)  # stays submitted; its event ends 2026-04-01 14:00
    clock.now = datetime(2026, 4, 1, 14, 0)
    assert erase(app, booking_id).status_code == 200

    result = run_command(app, "auto-decline")

    assert result.exit_code == 0
    assert kept(db, booking_id)[1:3] == ("declined", True)
    assert emptied(db, booking_id) == NOTHING
