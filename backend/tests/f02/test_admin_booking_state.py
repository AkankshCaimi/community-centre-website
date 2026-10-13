"""F02 state-change rules ST1 to ST11.

Every expected value comes from docs/specs/F02.md; each test names the rule it checks.
"""

import logging
import threading
from datetime import timedelta

import pytest
from f02_helpers import NOW, TEAM_EMAIL, booking_payload, call, iso, login

STATES = ["submitted", "contacted", "accepted", "declined"]
OPEN_STATES = ["submitted", "contacted", "accepted"]
DECLINED_IS_FINAL = {"error": "declined_is_final"}


def change(client, booking_id, state, **extra):
    body = {"state": state, **extra}
    if state == "declined" and "confirm" not in extra:
        body["confirm"] = True
    return call(client, "PATCH", f"/bookings/{booking_id}/state", body)


def state_of(db, booking_id):
    return db.execute("SELECT state FROM bookings WHERE id = %s", (booking_id,)).fetchone()[0]


def put_in_state(db, booking_id, state):
    """Set up a starting state directly, without going through the API under test."""
    db.execute("UPDATE bookings SET state = %s WHERE id = %s", (state, booking_id))


def email_log(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.email"]


def fields(response):
    assert response.status_code == 400
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body["error"] == "validation_failed"
    return body["fields"]


# --- ST3: every move except out of declined


@pytest.mark.parametrize("start", OPEN_STATES)
@pytest.mark.parametrize("target", STATES)
def test_st3_any_move_from_an_open_state_is_allowed(admin_client, make_booking, db, start, target):
    booking_id = make_booking(1, 1)
    put_in_state(db, booking_id, start)

    response = change(admin_client, booking_id, target)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json()["state"] == target
    assert state_of(db, booking_id) == target


def test_r7_response_is_the_booking_in_list_form(admin_client, make_booking):
    booking_id = make_booking(1, 1, details="Birthday party")

    response = change(admin_client, booking_id, "contacted")

    assert response.get_json() == {
        "id": booking_id,
        "state": "contacted",
        "name": "Person 1",
        "email": "person1@example.com",
        "phone": "07700 900001",
        "guest_count": 40,
        "starts_at": "2026-04-01T10:00",
        "ends_at": "2026-04-01T14:00",
        "details": "Birthday party",
        "submitted_at": iso(NOW),
    }


def test_st3_only_the_named_booking_changes(admin_client, make_booking, db):
    first = make_booking(1, 1)
    second = make_booking(2, 2)

    change(admin_client, first, "accepted")

    assert state_of(db, first) == "accepted"
    assert state_of(db, second) == "submitted"


# --- ST2: declined is final


@pytest.mark.parametrize("target", STATES)
def test_st2_nothing_moves_a_declined_booking(admin_client, make_booking, db, target):
    booking_id = make_booking(1, 1)
    assert change(admin_client, booking_id, "declined").status_code == 200

    response = change(admin_client, booking_id, target)

    assert response.status_code == 409
    assert response.content_type == "application/json"
    assert response.get_json() == DECLINED_IS_FINAL
    assert state_of(db, booking_id) == "declined"


def test_st2_refused_move_out_of_declined_has_no_side_effects(
    admin_client, make_booking, db, clock, caplog
):
    booking_id = make_booking(1, 1)
    change(admin_client, booking_id, "declined")
    changed_at = db.execute("SELECT state_changed_at FROM bookings").fetchone()[0]
    clock.now = NOW + timedelta(minutes=5)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        response = change(admin_client, booking_id, "accepted")

    assert response.status_code == 409
    assert email_log(caplog) == []
    assert db.execute("SELECT state_changed_at FROM bookings").fetchone()[0] == changed_at


# --- ST4: a move to the current state


@pytest.mark.parametrize("state", OPEN_STATES)
def test_st4_move_to_the_current_state_changes_nothing(
    admin_client, make_booking, db, clock, caplog, state
):
    booking_id = make_booking(1, 1)
    if state != "submitted":
        change(admin_client, booking_id, state)
    changed_at = db.execute("SELECT state_changed_at FROM bookings").fetchone()[0]
    clock.now = NOW + timedelta(minutes=5)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        response = change(admin_client, booking_id, state)

    assert response.status_code == 200
    assert response.get_json()["state"] == state
    assert email_log(caplog) == []
    assert db.execute("SELECT state_changed_at FROM bookings").fetchone()[0] == changed_at


# --- ST5: a decline must be confirmed


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"state": "declined"}, id="missing"),
        pytest.param({"state": "declined", "confirm": False}, id="false"),
        pytest.param({"state": "declined", "confirm": "true"}, id="string"),
        pytest.param({"state": "declined", "confirm": 1}, id="number"),
        pytest.param({"state": "declined", "confirm": None}, id="null"),
    ],
)
def test_st5_decline_without_confirmation_is_refused(admin_client, make_booking, db, body):
    booking_id = make_booking(1, 1)

    response = call(admin_client, "PATCH", f"/bookings/{booking_id}/state", body)

    assert fields(response) == {"confirm": "required"}
    assert state_of(db, booking_id) == "submitted"


def test_st5_confirmed_decline_is_accepted(admin_client, make_booking, db):
    booking_id = make_booking(1, 1)

    response = call(
        admin_client,
        "PATCH",
        f"/bookings/{booking_id}/state",
        {"state": "declined", "confirm": True},
    )

    assert response.status_code == 200
    assert state_of(db, booking_id) == "declined"


@pytest.mark.parametrize("confirm", [False, "no", None])
def test_st5_confirm_is_ignored_for_other_states(admin_client, make_booking, db, confirm):
    booking_id = make_booking(1, 1)

    response = change(admin_client, booking_id, "accepted", confirm=confirm)

    assert response.status_code == 200
    assert state_of(db, booking_id) == "accepted"


# --- ST6: the time of the change


def test_st6_change_records_its_time(admin_client, make_booking, db, clock):
    booking_id = make_booking(1, 1)
    clock.now = NOW + timedelta(minutes=17)

    change(admin_client, booking_id, "contacted")

    stored = db.execute(
        "SELECT state_changed_at AT TIME ZONE 'Europe/London', submitted_at AT TIME ZONE"
        " 'Europe/London' FROM bookings"
    ).fetchone()
    assert stored == (NOW + timedelta(minutes=17), NOW)


# --- ST7: accepting writes an email to the client


@pytest.mark.parametrize("start", ["submitted", "contacted"])
def test_st7_accepting_logs_one_email_to_the_client(admin_client, make_booking, db, caplog, start):
    booking_id = make_booking(1, 1)
    put_in_state(db, booking_id, start)

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="app.email"):
        change(admin_client, booking_id, "accepted")

    records = [record for record in caplog.records if record.name == "app.email"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    text = records[0].getMessage()
    assert "person1@example.com" in text
    assert "Person 1" in text
    assert "2026-04-01T10:00" in text
    assert "2026-04-01T14:00" in text
    assert TEAM_EMAIL not in text


def test_st7_a_booking_accepted_twice_gets_two_emails(admin_client, make_booking, caplog):
    booking_id = make_booking(1, 1)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        change(admin_client, booking_id, "accepted")
        change(admin_client, booking_id, "contacted")
        change(admin_client, booking_id, "accepted")

    assert len(email_log(caplog)) == 2


def test_st7_line_breaks_in_the_name_are_collapsed(admin_client, make_booking, caplog):
    booking_id = make_booking(1, 1, name="Alice To: attacker@evil.example")

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        change(admin_client, booking_id, "accepted")

    text = email_log(caplog)[0]
    assert "Alice To: attacker@evil.example" in text
    assert " " not in text


# --- ST8: declining frees the day, and writes no email


def test_st8_declining_frees_the_day_for_a_new_request(app, admin_client, make_booking):
    booking_id = make_booking(1, 1)
    taken = app.test_client().post("/api/v1/bookings", json=booking_payload(1, 2))
    assert taken.status_code == 409

    change(admin_client, booking_id, "declined")

    assert app.test_client().post("/api/v1/bookings", json=booking_payload(1, 2)).status_code == 201


def test_st8_declining_frees_both_days_of_a_booking_past_midnight(app, admin_client, make_booking):
    booking_id = make_booking(1, 1, starts_at="2026-04-01T20:00", ends_at="2026-04-02T02:00")

    change(admin_client, booking_id, "declined")

    assert app.test_client().post("/api/v1/bookings", json=booking_payload(1, 2)).status_code == 201
    assert app.test_client().post("/api/v1/bookings", json=booking_payload(2, 3)).status_code == 201


@pytest.mark.parametrize("start", OPEN_STATES)
def test_st8_declining_writes_no_email(admin_client, make_booking, db, caplog, start):
    booking_id = make_booking(1, 1)
    put_in_state(db, booking_id, start)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        response = change(admin_client, booking_id, "declined")

    assert response.status_code == 200
    assert email_log(caplog) == []


def test_st8_other_states_keep_the_day_locked(app, admin_client, make_booking):
    booking_id = make_booking(1, 1)

    for state in ("contacted", "accepted", "submitted"):
        assert change(admin_client, booking_id, state).status_code == 200
        assert (
            app.test_client().post("/api/v1/bookings", json=booking_payload(1, 2)).status_code
            == 409
        )


# --- ST9: other moves write no email


@pytest.mark.parametrize(
    "start, target",
    [
        ("submitted", "contacted"),
        ("contacted", "submitted"),
        ("accepted", "contacted"),
        ("accepted", "submitted"),
    ],
)
def test_st9_moves_into_submitted_or_contacted_write_no_email(
    admin_client, make_booking, db, caplog, start, target
):
    booking_id = make_booking(1, 1)
    put_in_state(db, booking_id, start)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        response = change(admin_client, booking_id, target)

    assert response.status_code == 200
    assert email_log(caplog) == []


# --- ST1: the state field


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param({}, "required", id="missing"),
        pytest.param({"state": None}, "required", id="null"),
        pytest.param({"state": 2}, "required", id="number"),
        pytest.param({"state": ["accepted"]}, "required", id="list"),
        pytest.param({"state": ""}, "invalid", id="empty"),
        pytest.param({"state": "cancelled"}, "invalid", id="unknown"),
        pytest.param({"state": "Accepted"}, "invalid", id="capitalised"),
        pytest.param({"state": " accepted "}, "invalid", id="padded"),
    ],
)
def test_st1_bad_state_is_refused(admin_client, make_booking, db, body, code):
    booking_id = make_booking(1, 1)

    response = call(admin_client, "PATCH", f"/bookings/{booking_id}/state", body)

    assert fields(response) == {"state": code}
    assert state_of(db, booking_id) == "submitted"


# --- ST10 and O1: which booking


@pytest.mark.parametrize("booking_id", ["999999", "0", "-1", "abc", "1.5", "9" * 30])
def test_st10_unknown_booking_is_not_found(admin_client, make_booking, booking_id):
    real_id = make_booking(1, 1)
    # The address itself works for a booking that exists.
    assert change(admin_client, real_id, "contacted").status_code == 200

    response = call(admin_client, "PATCH", f"/bookings/{booking_id}/state", {"state": "contacted"})

    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert response.get_json() == {"error": "not_found"}


def test_o1_fields_are_checked_before_the_booking_is_looked_up(admin_client):
    response = call(admin_client, "PATCH", "/bookings/999999/state", {"state": "nonsense"})

    assert fields(response) == {"state": "invalid"}


def test_o1_fields_are_checked_before_declined_is_reported(admin_client, make_booking):
    booking_id = make_booking(1, 1)
    change(admin_client, booking_id, "declined")

    response = call(admin_client, "PATCH", f"/bookings/{booking_id}/state", {"state": "nonsense"})

    assert fields(response) == {"state": "invalid"}


def test_b1_state_change_accepts_only_json(admin_client, make_booking, db):
    booking_id = make_booking(1, 1)

    response = admin_client.patch(
        f"/api/v1/admin/bookings/{booking_id}/state",
        data="state=accepted",
        content_type="application/x-www-form-urlencoded",
        base_url="https://localhost",
    )

    assert response.status_code == 415
    assert state_of(db, booking_id) == "submitted"


def test_b1_state_change_refuses_an_unreadable_body(admin_client, make_booking, db):
    booking_id = make_booking(1, 1)

    response = admin_client.patch(
        f"/api/v1/admin/bookings/{booking_id}/state",
        data='{"state": "accepted", "state": "declined"}',
        content_type="application/json",
        base_url="https://localhost",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_request"}
    assert state_of(db, booking_id) == "submitted"


# --- ST11: simultaneous requests


def test_st11_simultaneous_decline_and_accept_always_end_declined(app, admin, make_booking, db):
    decliner, accepter = app.test_client(), app.test_client()
    login(decliner)
    login(accepter)

    for day in range(1, 9):
        booking_id = make_booking(day, day)
        barrier = threading.Barrier(2)
        statuses = {}

        def send(name, client, state, booking_id=booking_id, barrier=barrier, statuses=statuses):
            barrier.wait()
            statuses[name] = change(client, booking_id, state).status_code

        threads = [
            threading.Thread(target=send, args=("decline", decliner, "declined")),
            threading.Thread(target=send, args=("accept", accepter, "accepted")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            assert not thread.is_alive()

        assert statuses["decline"] == 200
        assert statuses["accept"] in (200, 409)
        assert state_of(db, booking_id) == "declined"
