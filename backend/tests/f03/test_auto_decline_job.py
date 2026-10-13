"""F03 rules J1 to J7, J11 to J13, R1, R3 and the mark M1 to M3.

Every expected value comes from docs/specs/F03.md; each test names the rule it checks.
"""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from f03_helpers import (
    HOURS_48,
    NOW,
    admin_call,
    booking_payload,
    declined_count,
    move,
    run_job,
    states,
)

# --- J1: what is overdue


@pytest.mark.parametrize(
    "age, declined",
    [
        pytest.param(timedelta(hours=47, minutes=59, seconds=59), False, id="one-second-short"),
        pytest.param(HOURS_48, True, id="exactly-48-hours"),
        pytest.param(HOURS_48 + timedelta(seconds=1), True, id="one-second-over"),
        pytest.param(timedelta(0), False, id="just-submitted"),
        pytest.param(timedelta(days=30), True, id="a-month-old"),
    ],
)
def test_j1_booking_is_declined_from_48_hours_on(app, make_booking, clock, db, age, declined):
    booking_id = make_booking(1, 1)
    clock.now = NOW + age

    result = run_job(app)

    assert result.exit_code == 0
    assert declined_count(result.output) == (1 if declined else 0)
    assert states(db)[booking_id] == (("declined", True) if declined else ("submitted", False))


def test_j1_booking_returned_at_47_hours_has_one_hour_left(app, admin, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    clock.now = NOW + timedelta(hours=10)
    move(app, booking_id, "contacted")
    clock.now = NOW + timedelta(hours=47)
    move(app, booking_id, "submitted")

    clock.now = NOW + timedelta(hours=47, minutes=59, seconds=59)
    assert declined_count(run_job(app).output) == 0
    assert states(db)[booking_id] == ("submitted", False)

    clock.now = NOW + HOURS_48
    assert declined_count(run_job(app).output) == 1
    assert states(db)[booking_id] == ("declined", True)


def test_j1_booking_returned_after_48_hours_is_overdue_at_once(app, admin, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    clock.now = NOW + timedelta(hours=10)
    move(app, booking_id, "accepted")
    clock.now = NOW + timedelta(hours=50)
    move(app, booking_id, "submitted")

    assert declined_count(run_job(app).output) == 1
    assert states(db)[booking_id] == ("declined", True)


def test_j1_only_overdue_bookings_among_several_are_declined(app, make_booking, clock, db):
    old = make_booking(1, 1)
    clock.now = NOW + timedelta(hours=1)
    newer = make_booking(2, 2)
    clock.now = NOW + HOURS_48  # the first is exactly 48 hours old, the second 47

    result = run_job(app)

    assert declined_count(result.output) == 1
    assert states(db) == {old: ("declined", True), newer: ("submitted", False)}


# --- J2 and J11: what a run changes, and what it leaves alone

EVERY_COLUMN_BUT_THE_THREE = """
    SELECT id, starts_at, ends_at, client_name, client_phone, client_email, host(client_ip),
           guest_count, event_details, terms_accepted_at, privacy_notice_accepted_at,
           submitted_at, erased_at
    FROM bookings ORDER BY id
"""


def test_j2_declined_booking_gets_state_mark_and_time(app, make_booking, clock, db):
    make_booking(1, 1)
    clock.now = NOW + timedelta(hours=49, minutes=7)

    run_job(app)

    row = db.execute(
        "SELECT state, auto_declined, state_changed_at AT TIME ZONE 'Europe/London' FROM bookings"
    ).fetchone()
    assert row == ("declined", True, NOW + timedelta(hours=49, minutes=7))


def test_j11_nothing_else_about_a_declined_booking_changes(app, make_booking, clock, db):
    make_booking(1, 1, details="Birthday party")
    before = db.execute(EVERY_COLUMN_BUT_THE_THREE).fetchall()
    clock.now = NOW + HOURS_48

    assert declined_count(run_job(app).output) == 1

    assert db.execute(EVERY_COLUMN_BUT_THE_THREE).fetchall() == before


def test_j11_booking_that_is_not_overdue_is_not_touched_at_all(app, make_booking, clock, db):
    make_booking(1, 1)
    clock.now = NOW + timedelta(hours=1)
    make_booking(2, 2)
    everything = "SELECT * FROM bookings WHERE client_name = 'Person 2'"
    before = db.execute(everything).fetchall()
    clock.now = NOW + HOURS_48

    assert declined_count(run_job(app).output) == 1

    assert db.execute(everything).fetchall() == before


def test_j11_requests_are_answered_as_usual_after_a_run(app, admin, make_booking, clock):
    make_booking(1, 1)
    clock.now = NOW + HOURS_48
    assert declined_count(run_job(app).output) == 1

    public = app.test_client().post("/api/v1/bookings", json=booking_payload(5, 2))
    listing = admin_call(app, "GET", "/bookings")

    assert public.status_code == 201
    assert listing.status_code == 200
    assert listing.get_json()["total"] == 2


# --- J3: only submitted bookings


def test_j3_other_states_are_never_touched_however_old(app, admin, make_booking, clock, db):
    contacted = make_booking(1, 1)
    accepted = make_booking(2, 2)
    declined = make_booking(3, 3)
    move(app, contacted, "contacted")
    move(app, accepted, "accepted")
    move(app, declined, "declined")
    before = db.execute("SELECT * FROM bookings ORDER BY id").fetchall()
    clock.now = NOW + timedelta(days=60)

    result = run_job(app)

    assert declined_count(result.output) == 0
    assert db.execute("SELECT * FROM bookings ORDER BY id").fetchall() == before
    assert states(db) == {
        contacted: ("contacted", False),
        accepted: ("accepted", False),
        declined: ("declined", False),
    }


# --- J4: the day is freed


def test_j4_auto_declined_day_can_be_requested_again(app, make_booking, clock):
    make_booking(1, 1)
    assert app.test_client().post("/api/v1/bookings", json=booking_payload(1, 2)).status_code == 409
    clock.now = NOW + HOURS_48

    run_job(app)

    assert app.test_client().post("/api/v1/bookings", json=booking_payload(1, 2)).status_code == 201


def test_j4_both_days_of_a_booking_past_midnight_are_freed(app, make_booking, clock):
    make_booking(1, 1, starts_at="2026-04-01T20:00", ends_at="2026-04-02T02:00")
    clock.now = NOW + HOURS_48

    run_job(app)

    client = app.test_client()
    assert client.post("/api/v1/bookings", json=booking_payload(1, 2)).status_code == 201
    assert client.post("/api/v1/bookings", json=booking_payload(2, 3)).status_code == 201


def test_j4_day_stays_taken_until_the_booking_is_overdue(app, make_booking, clock):
    make_booking(1, 1)
    clock.now = NOW + timedelta(hours=47)

    assert declined_count(run_job(app).output) == 0

    assert app.test_client().post("/api/v1/bookings", json=booking_payload(1, 2)).status_code == 409


# --- J5: nobody is told


def test_j5_a_run_writes_no_email(app, make_booking, clock, caplog):
    make_booking(1, 1)
    make_booking(2, 2)
    clock.now = NOW + HOURS_48
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        assert declined_count(run_job(app).output) == 2

    assert [record for record in caplog.records if record.name == "app.email"] == []


# --- J6: an auto-declined booking is final


@pytest.mark.parametrize("target", ["submitted", "contacted", "accepted", "declined"])
def test_j6_auto_declined_booking_cannot_be_moved(app, admin, make_booking, clock, db, target):
    booking_id = make_booking(1, 1)
    clock.now = NOW + HOURS_48
    run_job(app)

    body = {"state": target, "confirm": True}
    response = admin_call(app, "PATCH", f"/bookings/{booking_id}/state", body)

    assert response.status_code == 409
    assert response.get_json() == {"error": "declined_is_final"}
    assert states(db)[booking_id] == ("declined", True)


# --- J7: running again changes nothing


def test_j7_second_run_declines_nothing_and_changes_nothing(app, make_booking, clock, db):
    make_booking(1, 1)
    clock.now = NOW + HOURS_48
    assert declined_count(run_job(app).output) == 1
    after_first = db.execute("SELECT * FROM bookings").fetchall()

    clock.now = NOW + HOURS_48 + timedelta(hours=1)
    second = run_job(app)

    assert second.exit_code == 0
    assert declined_count(second.output) == 0
    assert db.execute("SELECT * FROM bookings").fetchall() == after_first


# --- J12: missed runs


def test_j12_first_run_after_a_gap_declines_everything_overdue(app, make_booking, clock, db):
    made = []
    for hour in range(6):  # six bookings submitted an hour apart
        clock.now = NOW + timedelta(hours=hour)
        made.append(make_booking(hour + 1, hour + 1))
    still_fresh_at = NOW + timedelta(hours=30)
    clock.now = still_fresh_at
    fresh = make_booking(10, 10)

    # No run for six hours after the last of the six became overdue.
    clock.now = NOW + timedelta(hours=5) + HOURS_48 + timedelta(hours=6)
    result = run_job(app)

    assert declined_count(result.output) == 6
    expected = {booking_id: ("declined", True) for booking_id in made}
    expected[fresh] = ("submitted", False)
    assert states(db) == expected
    # The time of the change is the time of this run, not each 48-hour mark.
    times = db.execute(
        "SELECT DISTINCT state_changed_at AT TIME ZONE 'Europe/London' FROM bookings"
        " WHERE state = 'declined'"
    ).fetchall()
    assert times == [(clock.now,)]


# --- J13: elapsed time


def test_j13_48_hours_is_elapsed_time_when_the_clocks_go_forward(app, make_booking, clock, db):
    # Submitted at 09:00 on Saturday 28 March 2026. The clocks go forward that
    # night, so 48 hours later the clock shows 10:00 on Monday, not 09:00.
    clock.now = datetime(2026, 3, 28, 9, 0)
    booking_id = make_booking(20, 1)

    clock.now = datetime(2026, 3, 30, 9, 59, 59)
    assert declined_count(run_job(app).output) == 0

    clock.now = datetime(2026, 3, 30, 10, 0)
    assert declined_count(run_job(app).output) == 1
    assert states(db)[booking_id] == ("declined", True)


def test_j13_48_hours_is_elapsed_time_when_the_clocks_go_back(app, make_booking, clock, db):
    # Submitted at 09:00 on Saturday 24 October 2026. The clocks go back that
    # night, so 48 hours later the clock shows 08:00 on Monday.
    clock.now = datetime(2026, 10, 24, 9, 0)
    body = {"starts_at": "2026-11-10T10:00", "ends_at": "2026-11-10T14:00"}
    booking_id = make_booking(1, 1, **body)

    clock.now = datetime(2026, 10, 26, 7, 59, 59)
    assert declined_count(run_job(app).output) == 0

    clock.now = datetime(2026, 10, 26, 8, 0)
    assert declined_count(run_job(app).output) == 1
    assert states(db)[booking_id] == ("declined", True)


def test_j13_exact_instants_from_the_clock_are_used_as_they_are(app, make_booking, clock, db):
    """F02 CK2: a clock that gives an exact instant is taken at its word."""
    clock.now = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
    booking_id = make_booking(1, 1)

    clock.now = datetime(2026, 3, 12, 8, 59, 59, tzinfo=UTC)
    assert declined_count(run_job(app).output) == 0

    clock.now = datetime(2026, 3, 12, 9, 0, tzinfo=UTC)
    assert declined_count(run_job(app).output) == 1
    assert states(db)[booking_id] == ("declined", True)


# --- R1 and R3: the command and its heartbeat


@pytest.mark.parametrize("overdue", [0, 1, 3])
def test_r3_successful_run_prints_and_logs_the_heartbeat(app, make_booking, clock, caplog, overdue):
    for number in range(1, overdue + 1):
        make_booking(number, number)
    clock.now = NOW + HOURS_48
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        result = run_job(app)

    line = f"Auto-decline run: {overdue} declined."
    assert result.exit_code == 0
    assert result.stdout.strip() == line
    records = [record for record in caplog.records if record.name == "app.jobs"]
    assert [record.getMessage() for record in records] == [line]
    assert [record.levelno for record in records] == [logging.INFO]


def test_r3_heartbeat_holds_no_client_details(app, make_booking, clock, caplog):
    make_booking(1, 1, details="Birthday party")
    clock.now = NOW + HOURS_48
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        result = run_job(app)

    assert result.exit_code == 0
    logged = result.output + "\n".join(record.getMessage() for record in caplog.records)
    for private in ("Person 1", "person1@example.com", "07700 900001", "Birthday party"):
        assert private not in logged


def test_r1_command_takes_no_arguments(app, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    clock.now = NOW + HOURS_48

    result = app.test_cli_runner().invoke(args=["auto-decline", "--all"])

    assert result.exit_code == 2
    assert states(db)[booking_id] == ("submitted", False)


# --- M1 to M3: the mark


def test_m1_booking_declined_by_an_admin_is_not_marked(app, admin, make_booking, db):
    booking_id = make_booking(1, 1)

    response = move(app, booking_id, "declined")

    assert states(db)[booking_id] == ("declined", False)
    assert response.get_json()["auto_declined"] is False


def test_m1_a_run_does_not_mark_a_booking_an_admin_already_declined(
    app, admin, make_booking, clock, db
):
    booking_id = make_booking(1, 1)
    move(app, booking_id, "declined")
    clock.now = NOW + timedelta(days=5)

    run_job(app)

    assert states(db)[booking_id] == ("declined", False)


def test_m2_every_list_item_says_whether_it_was_auto_declined(app, admin, make_booking, clock):
    auto = make_booking(1, 1)
    clock.now = NOW + HOURS_48
    run_job(app)
    by_admin = make_booking(2, 2)
    move(app, by_admin, "declined")
    for day, state in ((3, "submitted"), (4, "contacted"), (5, "accepted")):
        booking_id = make_booking(day, day)
        if state != "submitted":
            move(app, booking_id, state)

    items = admin_call(app, "GET", "/bookings").get_json()["items"]

    assert len(items) == 5
    assert all(isinstance(item["auto_declined"], bool) for item in items)
    assert {item["id"] for item in items if item["auto_declined"]} == {auto}
    assert {item["state"] for item in items if not item["auto_declined"]} == {
        "submitted",
        "contacted",
        "accepted",
        "declined",
    }


def test_m2_list_item_has_the_ten_fields_of_f02_and_the_mark(app, admin, make_booking):
    make_booking(1, 1)

    item = admin_call(app, "GET", "/bookings").get_json()["items"][0]

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
    assert item["auto_declined"] is False


def test_m2_state_change_response_carries_the_mark(app, admin, make_booking):
    booking_id = make_booking(1, 1)

    response = move(app, booking_id, "contacted")

    assert response.get_json()["auto_declined"] is False


def test_m3_declined_filter_lists_both_kinds(app, admin, make_booking, clock):
    auto = make_booking(1, 1)
    clock.now = NOW + HOURS_48
    run_job(app)
    by_admin = make_booking(2, 2)
    move(app, by_admin, "declined")
    make_booking(3, 3)

    body = admin_call(app, "GET", "/bookings?state=declined").get_json()

    assert {item["id"] for item in body["items"]} == {auto, by_admin}
    assert body["total"] == 2
