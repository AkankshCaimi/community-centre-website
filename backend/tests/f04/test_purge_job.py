"""F04 rules P1 to P14 (the purge job), E3 and E4 for purged bookings, and the
database change.

Every expected value comes from docs/specs/F04.md; each test names the rule it checks.
"""

import logging
import os
import re
import time
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from f04_helpers import (
    NOTHING,
    NOW,
    SEVEN_DAYS,
    SIX_MONTHS_ON,
    booking_payload,
    emptied,
    finish,
    is_erased,
    kept,
    move,
    purge_counts,
    run_command,
    run_purge,
    start_process,
)


def address(db, booking_id):
    return db.execute(
        "SELECT host(client_ip) FROM bookings WHERE id = %s", (booking_id,)
    ).fetchone()[0]


def health(app):
    response = app.test_client().get("/health")
    assert response.status_code == 200
    return response.get_json()


# --- P2 and P3: retention


@pytest.mark.parametrize(
    "when, due",
    [
        pytest.param(SIX_MONTHS_ON - timedelta(seconds=1), False, id="one-second-short"),
        pytest.param(SIX_MONTHS_ON, True, id="exactly-six-months"),
        pytest.param(SIX_MONTHS_ON + timedelta(seconds=1), True, id="one-second-over"),
        pytest.param(NOW + timedelta(days=30), False, id="one-month"),
        pytest.param(NOW + timedelta(days=400), True, id="over-a-year"),
    ],
)
def test_p2_booking_is_erased_from_six_calendar_months_on(app, make_booking, clock, db, when, due):
    booking_id = make_booking(1, 1)
    clock.now = when

    result = run_purge(app)

    assert result.exit_code == 0
    assert purge_counts(result.output)[0] == (1 if due else 0)
    assert is_erased(db, booking_id) is due


def test_p2_six_months_ends_on_the_last_day_of_a_shorter_month(app, make_booking, clock, db):
    # Submitted on 31 August 2026: six months on is February 2027, which has 28 days.
    clock.now = datetime(2026, 8, 31, 9, 0)
    booking_id = make_booking(1, 1, starts_at="2026-09-20T10:00", ends_at="2026-09-20T14:00")

    clock.now = datetime(2027, 2, 28, 8, 59, 59)
    assert purge_counts(run_purge(app).output)[0] == 0

    clock.now = datetime(2027, 2, 28, 9, 0)
    assert purge_counts(run_purge(app).output)[0] == 1
    assert is_erased(db, booking_id) is True


def test_p2_six_months_keeps_the_local_time_of_day_across_a_clock_change(
    app, make_booking, clock, db
):
    # Submitted in winter time at 09:00; six months on is in summer time, and
    # the booking is due at 09:00 on the clock there, not 10:00.
    clock.now = datetime(2026, 1, 15, 9, 0)
    booking_id = make_booking(1, 1, starts_at="2026-02-10T10:00", ends_at="2026-02-10T14:00")

    clock.now = datetime(2026, 7, 15, 8, 59, 59)
    assert purge_counts(run_purge(app).output)[0] == 0

    clock.now = datetime(2026, 7, 15, 9, 0)
    assert purge_counts(run_purge(app).output)[0] == 1
    assert is_erased(db, booking_id) is True


def test_p3_due_booking_is_erased_with_the_time_of_the_run(app, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    before_kept = kept(db, booking_id)
    clock.now = SIX_MONTHS_ON + timedelta(hours=7)

    run_purge(app)

    assert emptied(db, booking_id) == NOTHING
    assert kept(db, booking_id) == before_kept
    erased_at = db.execute(
        "SELECT erased_at AT TIME ZONE 'Europe/London' FROM bookings"
    ).fetchone()[0]
    assert erased_at == SIX_MONTHS_ON + timedelta(hours=7)


def test_p2_bookings_in_every_state_are_due_alike(app, admin, make_booking, clock, db):
    made = {}
    for day, state in enumerate(["submitted", "contacted", "accepted", "declined"], start=1):
        made[state] = make_booking(day, day)
        if state != "submitted":
            move(app, made[state], state)
    clock.now = SIX_MONTHS_ON

    result = run_purge(app)

    assert purge_counts(result.output)[0] == 4
    for state, booking_id in made.items():
        assert is_erased(db, booking_id) is True
        assert kept(db, booking_id)[1] == state  # P5: the state is not changed


def test_p2_only_due_bookings_among_several_are_erased(app, make_booking, clock, db):
    old = make_booking(1, 1)
    clock.now = NOW + timedelta(days=1)
    newer = make_booking(2, 2)
    before = db.execute("SELECT * FROM bookings WHERE id = %s", (newer,)).fetchone()
    clock.now = SIX_MONTHS_ON  # the first is exactly due; the second is a day short

    result = run_purge(app)

    assert purge_counts(result.output)[0] == 1
    assert is_erased(db, old) is True
    # P5: nothing about the newer one changes except its address, long past 7 days (P4).
    after = db.execute("SELECT * FROM bookings WHERE id = %s", (newer,)).fetchone()
    assert is_erased(db, newer) is False
    assert emptied(db, newer)[:3] == ("Person 2", "07700 900002", "person2@example.com")
    assert len(after) == len(before)


# --- P4: the network address lives 7 days


@pytest.mark.parametrize(
    "age, removed",
    [
        pytest.param(SEVEN_DAYS - timedelta(seconds=1), False, id="one-second-short"),
        pytest.param(SEVEN_DAYS, True, id="exactly-7-days"),
        pytest.param(SEVEN_DAYS + timedelta(hours=1), True, id="an-hour-over"),
        pytest.param(timedelta(hours=25), False, id="a-day-old"),
    ],
)
def test_p4_network_address_is_removed_from_7_days_on(app, make_booking, clock, db, age, removed):
    booking_id = make_booking(1, 1, ip="203.0.113.77")
    clock.now = NOW + age

    result = run_purge(app)

    assert purge_counts(result.output) == (0, 1 if removed else 0)
    assert address(db, booking_id) == (None if removed else "203.0.113.77")


def test_p4_nothing_else_about_the_booking_changes(app, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    everything_else = (
        "SELECT id, state, auto_declined, starts_at, ends_at, submitted_at, state_changed_at,"
        " client_name, client_email, client_phone, guest_count, event_details,"
        " terms_accepted_at, privacy_notice_accepted_at, erased_at FROM bookings"
    )
    before = db.execute(everything_else).fetchall()
    clock.now = NOW + SEVEN_DAYS

    assert purge_counts(run_purge(app).output) == (0, 1)

    assert db.execute(everything_else).fetchall() == before
    assert is_erased(db, booking_id) is False


def test_p4_seven_days_is_elapsed_time_across_a_clock_change(app, make_booking, clock, db):
    # Submitted at 09:00 on 25 March 2026; the clocks go forward on the 29th,
    # so 168 hours later the clock shows 10:00 on 1 April.
    clock.now = datetime(2026, 3, 25, 9, 0)
    booking_id = make_booking(20, 1, ip="203.0.113.77")

    clock.now = datetime(2026, 4, 1, 9, 59, 59)
    assert purge_counts(run_purge(app).output) == (0, 0)

    clock.now = datetime(2026, 4, 1, 10, 0)
    assert purge_counts(run_purge(app).output) == (0, 1)
    assert address(db, booking_id) is None


def test_p4_booking_without_an_address_can_still_be_used(app, admin, make_booking, clock, db):
    """Database: a booking that is not erased no longer needs a network address."""
    booking_id = make_booking(1, 1)
    clock.now = NOW + SEVEN_DAYS
    run_purge(app)

    response = move(app, booking_id, "accepted")

    assert response.get_json()["name"] == "Person 1"
    assert address(db, booking_id) is None


def test_p4_removed_addresses_are_counted_once(app, make_booking, clock):
    for number in range(1, 4):
        make_booking(number, number)
    clock.now = NOW + SEVEN_DAYS

    assert purge_counts(run_purge(app).output) == (0, 3)
    assert purge_counts(run_purge(app).output) == (0, 0)


def test_p4_erased_booking_is_not_counted_as_an_address_removed(app, make_booking, clock):
    make_booking(1, 1)
    clock.now = SIX_MONTHS_ON  # never purged before: due for erasure, address still there

    assert purge_counts(run_purge(app).output) == (1, 0)


# --- P6 and P1: heartbeat and the command


def test_p6_successful_run_prints_and_logs_the_heartbeat(app, make_booking, clock, caplog):
    make_booking(1, 1)
    make_booking(2, 2)
    clock.now = NOW + SEVEN_DAYS
    make_booking(3, 3)
    clock.now = SIX_MONTHS_ON  # two are due; the third is past 7 days but not due
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        result = run_purge(app)

    line = "Purge run: 2 erased, 1 addresses removed."
    assert result.exit_code == 0
    assert result.stdout.strip() == line
    records = [record for record in caplog.records if record.name == "app.jobs"]
    assert [record.getMessage() for record in records] == [line]
    assert [record.levelno for record in records] == [logging.INFO]


def test_p6_run_with_nothing_to_do_reports_zeros(app, clock):
    result = run_purge(app)

    assert result.exit_code == 0
    assert result.stdout.strip() == "Purge run: 0 erased, 0 addresses removed."


def test_p6_p14_heartbeat_holds_no_client_details_and_no_email_is_written(
    app, make_booking, clock, caplog
):
    make_booking(1, 1)
    clock.now = SIX_MONTHS_ON
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        result = run_purge(app)

    assert result.exit_code == 0
    assert purge_counts(result.output)[0] == 1
    assert [record for record in caplog.records if record.name == "app.email"] == []
    logged = result.output + "\n".join(record.getMessage() for record in caplog.records)
    for private in ("Person 1", "person1@example.com", "07700 900001", "Party 1", "198.51.100."):
        assert private not in logged


def test_p1_command_takes_no_arguments(app, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    clock.now = SIX_MONTHS_ON

    result = app.test_cli_runner().invoke(args=["purge", "--all"])

    assert result.exit_code == 2
    assert is_erased(db, booking_id) is False
    # Without the argument the same command runs.
    assert run_purge(app).exit_code == 0
    assert is_erased(db, booking_id) is True


# --- P7 and P9: failure


BREAK_ONE_BOOKING = """
    CREATE FUNCTION refuse_person_2() RETURNS trigger AS $$
    BEGIN
        IF OLD.client_name = 'Person 2' AND NEW.erased_at IS NOT NULL THEN
            RAISE EXCEPTION 'cannot erase %', OLD.client_email;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER refuse_person_2 BEFORE UPDATE ON bookings
        FOR EACH ROW EXECUTE FUNCTION refuse_person_2();
"""
MEND = "DROP TRIGGER refuse_person_2 ON bookings; DROP FUNCTION refuse_person_2();"


@pytest.fixture
def broken(app, make_booking, clock, db):
    made = [make_booking(number, number) for number in range(1, 4)]
    clock.now = SIX_MONTHS_ON
    db.execute(BREAK_ONE_BOOKING)
    yield made
    db.execute("DROP TRIGGER IF EXISTS refuse_person_2 ON bookings")
    db.execute("DROP FUNCTION IF EXISTS refuse_person_2()")


def test_p7_p9_run_that_stops_part_way_changes_nothing(app, broken, db):
    before = db.execute("SELECT * FROM bookings ORDER BY id").fetchall()

    result = run_purge(app)

    assert result.exit_code == 1
    assert db.execute("SELECT * FROM bookings ORDER BY id").fetchall() == before


def test_p9_next_run_does_the_work_once_the_fault_is_gone(app, broken, db):
    assert run_purge(app).exit_code == 1
    db.execute(MEND)

    result = run_purge(app)

    assert purge_counts(result.output) == (3, 0)
    assert all(is_erased(db, booking_id) for booking_id in broken)


def test_p7_failed_run_reports_only_the_type_of_the_error(app, broken, caplog):
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        result = run_purge(app)

    assert result.exit_code == 1
    records = [record for record in caplog.records if record.name == "app.jobs"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    line = records[0].getMessage()
    assert re.fullmatch(r"Purge run failed: \w+\.", line), line
    assert line in result.stdout
    assert "Purge run:" not in result.stdout
    everything = result.output + "\n".join(
        record.getMessage() + str(record.exc_info or "") for record in caplog.records
    )
    for private in ("Person 2", "person2@example.com", "cannot erase"):
        assert private not in everything


def test_p9_running_again_changes_nothing(app, make_booking, clock, db):
    make_booking(1, 1)
    clock.now = SIX_MONTHS_ON
    assert purge_counts(run_purge(app).output) == (1, 0)
    after_first = db.execute("SELECT * FROM bookings").fetchall()

    clock.now = SIX_MONTHS_ON + timedelta(hours=1)
    second = run_purge(app)

    assert purge_counts(second.output) == (0, 0)
    assert db.execute("SELECT * FROM bookings").fetchall() == after_first


# --- P8: last run and /health


def test_p8_health_shows_null_before_any_purge(app):
    body = health(app)

    assert body["purge_last_run"] is None
    assert set(body) == {"status", "auto_decline_last_run", "purge_last_run"}
    assert body["status"] == "ok"


def test_p8_health_shows_the_instant_of_the_last_successful_purge(app, clock):
    clock.now = NOW.replace(month=6, hour=14, minute=30, second=5)  # 14:30:05 BST is 13:30:05 UTC

    assert run_purge(app).exit_code == 0

    assert health(app)["purge_last_run"] == "2026-06-10T13:30:05Z"


def test_p8_the_two_jobs_have_their_own_last_run(app, clock):
    run_command(app, "auto-decline")
    clock.now = NOW + timedelta(hours=2)
    run_purge(app)

    assert health(app) == {
        "status": "ok",
        "auto_decline_last_run": "2026-03-10T09:00:00Z",
        "purge_last_run": "2026-03-10T11:00:00Z",
    }


def test_p8_failed_run_does_not_move_the_last_run_on(app, broken, clock, db):
    db.execute(MEND)
    clock.now = NOW + timedelta(hours=1)
    assert run_purge(app).exit_code == 0  # nothing is due yet
    db.execute(BREAK_ONE_BOOKING)

    clock.now = SIX_MONTHS_ON
    assert run_purge(app).exit_code == 1

    assert health(app)["purge_last_run"] == "2026-03-10T10:00:00Z"


def test_p8_last_run_does_not_move_backwards(app, clock):
    clock.now = NOW + timedelta(hours=5)
    run_purge(app)
    clock.now = NOW + timedelta(hours=2)
    assert run_purge(app).exit_code == 0

    assert health(app)["purge_last_run"] == "2026-03-10T14:00:00Z"


def test_p8_nothing_is_erased_if_the_run_cannot_be_recorded(app, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    clock.now = SIX_MONTHS_ON
    db.execute("DROP TABLE job_runs")

    result = run_purge(app)

    assert result.exit_code == 1
    assert is_erased(db, booking_id) is False


# --- P10: missed runs


def test_p10_first_run_after_a_gap_erases_everything_due(app, make_booking, clock, db):
    made = []
    for day in range(5):  # five bookings submitted a day apart
        clock.now = NOW + timedelta(days=day)
        made.append(make_booking(day + 1, day + 1))
    clock.now = SIX_MONTHS_ON + timedelta(days=10)  # no run until all five are overdue

    result = run_purge(app)

    assert purge_counts(result.output)[0] == 5
    times = db.execute(
        "SELECT DISTINCT erased_at AT TIME ZONE 'Europe/London' FROM bookings"
    ).fetchall()
    assert times == [(clock.now,)]


# --- E3 and E4 for a booking the purge erased while it is still to come


def test_e3_erased_booking_that_is_not_declined_still_locks_its_day(
    app, admin, make_booking, clock, db
):
    # Requested for exactly six months ahead, so the purge erases it on the
    # morning of the event, before the event has happened.
    booking_id = make_booking(1, 1, starts_at="2026-09-10T09:00", ends_at="2026-09-10T13:00")
    move(app, booking_id, "accepted")
    clock.now = SIX_MONTHS_ON
    run_purge(app)
    assert is_erased(db, booking_id) is True

    same_day = booking_payload(1, 2, starts_at="2026-09-10T19:00", ends_at="2026-09-10T21:00")
    response = app.test_client().post("/api/v1/bookings", json=same_day)

    assert response.status_code == 409


def test_e4_erased_booking_does_not_count_towards_the_slot_limit(
    app, admin, make_booking, clock, db
):
    # Person 1 holds two slots: one requested for exactly six months ahead,
    # and one requested much later for a later day.
    make_booking(1, 1, starts_at="2026-09-10T09:00", ends_at="2026-09-10T13:00")
    clock.now = datetime(2026, 9, 1, 9, 0)
    make_booking(1, 1, starts_at="2026-09-20T10:00", ends_at="2026-09-20T14:00")
    third = booking_payload(1, 1, starts_at="2026-09-25T10:00", ends_at="2026-09-25T14:00")
    clock.now = SIX_MONTHS_ON - timedelta(hours=1)
    assert app.test_client().post("/api/v1/bookings", json=third).status_code == 409

    clock.now = SIX_MONTHS_ON
    # The first is erased while its event is still to come; the second is not due.
    assert purge_counts(run_purge(app).output) == (1, 1)

    assert app.test_client().post("/api/v1/bookings", json=third).status_code == 201


# --- P11 to P13: overlapping runs, the auto-decline job, and an admin
#
# These start the commands as real processes with the real clock. Bookings
# made here were submitted in March 2026, so both jobs have work to do on them.

SLOW_AND_COUNTED = """
    CREATE TABLE change_log (booking_id bigint NOT NULL, what text NOT NULL);
    CREATE FUNCTION slow_change() RETURNS trigger AS $$
    BEGIN
        IF NEW.erased_at IS NOT NULL AND OLD.erased_at IS NULL THEN
            INSERT INTO change_log VALUES (NEW.id, 'erased');
            PERFORM pg_sleep(0.1);
        END IF;
        IF NEW.state = 'declined' AND OLD.state <> 'declined' THEN
            INSERT INTO change_log VALUES (NEW.id, 'declined');
            PERFORM pg_sleep(0.1);
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER slow_change BEFORE UPDATE ON bookings
        FOR EACH ROW EXECUTE FUNCTION slow_change();
"""


@pytest.fixture
def slow_changes(app, db):
    db.execute(SLOW_AND_COUNTED)
    yield
    db.execute("DROP TRIGGER IF EXISTS slow_change ON bookings")
    db.execute("DROP FUNCTION IF EXISTS slow_change()")
    db.execute("DROP TABLE IF EXISTS change_log")


def wait_until_a_run_is_changing_bookings(db, timeout=20):
    """The slow_changes trigger sleeps inside each change; a session in that sleep is a run."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if db.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE wait_event = 'PgSleep'"
        ).fetchone()[0]:
            return
        time.sleep(0.02)
    raise AssertionError("no run started changing bookings")


def changes(db, what):
    return sorted(
        row[0] for row in db.execute("SELECT booking_id FROM change_log WHERE what = %s", (what,))
    )


def test_p11_overlapping_purge_runs_erase_each_booking_exactly_once(
    app, make_booking, db, slow_changes
):
    made = [make_booking(number, number) for number in range(1, 16)]

    first = start_process("purge")
    wait_until_a_run_is_changing_bookings(db)
    second = start_process("purge")
    results = [finish(first), finish(second)]

    assert [code for code, _, _ in results] == [0, 0]
    assert sum(purge_counts(stdout)[0] for _, stdout, _ in results) == 15
    assert changes(db, "erased") == sorted(made)
    assert all(is_erased(db, booking_id) for booking_id in made)


def test_p12_purge_and_auto_decline_at_once_neither_waits_nor_blocks(
    app, make_booking, db, slow_changes
):
    # Fifteen bookings that are overdue for the auto-decline job and due for the purge.
    made = [make_booking(number, number) for number in range(1, 16)]

    started = time.monotonic()
    declining, purging = start_process("auto-decline"), start_process("purge")
    results = [finish(declining, timeout=60), finish(purging, timeout=60)]
    together = time.monotonic() - started

    assert [code for code, _, _ in results] == [0, 0]  # no deadlock, no failure
    # One more run of each picks up whatever the other was holding.
    assert finish(start_process("auto-decline"))[0] == 0
    assert finish(start_process("purge"))[0] == 0

    states = db.execute(
        "SELECT state, auto_declined, erased_at IS NOT NULL FROM bookings"
    ).fetchall()
    assert states == [("declined", True, True)] * 15
    # Each booking was declined once and erased once, across all four runs.
    assert changes(db, "declined") == sorted(made)
    assert changes(db, "erased") == sorted(made)
    assert together < 45


def test_p12_overlapping_purge_and_auto_decline_do_not_fail_when_forced_to_meet(
    app, make_booking, db, slow_changes
):
    for number in range(1, 16):
        make_booking(number, number)

    purging = start_process("purge")
    wait_until_a_run_is_changing_bookings(db)  # the purge now holds bookings
    code, stdout, _ = finish(start_process("auto-decline"), timeout=30)
    purge_code, _, _ = finish(purging)

    assert code == 0
    assert purge_code == 0


@pytest.fixture
def other_session():
    """A second database session, standing in for an admin request in progress."""
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
        yield connection
        connection.rollback()


def test_p13_booking_held_by_another_request_is_skipped_then_erased_next_run(
    app, make_booking, db, other_session
):
    held, other = make_booking(1, 1), make_booking(2, 2)
    other_session.execute("SELECT id FROM bookings WHERE id = %s FOR UPDATE", (held,))

    code, stdout, _ = finish(start_process("purge"), timeout=30)  # would time out if it waited

    assert code == 0
    assert purge_counts(stdout)[0] == 1
    assert (is_erased(db, held), is_erased(db, other)) == (False, True)

    other_session.rollback()
    assert purge_counts(finish(start_process("purge"))[1])[0] == 1
    assert is_erased(db, held) is True


def test_p6_run_as_a_process_reports_like_a_run_in_the_test_process(app, make_booking, db):
    make_booking(1, 1)

    code, stdout, stderr = finish(start_process("purge"))

    assert code == 0
    assert stdout.strip() == "Purge run: 1 erased, 0 addresses removed."
    assert "Purge run: 1 erased, 0 addresses removed." in stderr


def test_p8_real_clock_last_run_is_recent(app):
    """P8 with the real clock: the recorded instant is now, in UTC."""
    before = datetime.now(UTC).replace(microsecond=0)

    assert finish(start_process("purge"))[0] == 0

    recorded = datetime.strptime(health(app)["purge_last_run"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=UTC
    )
    assert before <= recorded <= datetime.now(UTC)


# --- Database: init-db on a table from before F04


def test_database_init_db_lifts_the_old_rule_that_a_booking_must_have_an_address(
    app, make_booking, clock, db
):
    booking_id = make_booking(1, 1)
    # Put the constraint back to how F03 left it: an address is required.
    db.execute("ALTER TABLE bookings DROP CONSTRAINT bookings_erased_or_complete")
    db.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT bookings_erased_or_complete CHECK (
            (erased_at IS NULL AND client_name IS NOT NULL AND client_phone IS NOT NULL
                AND client_email IS NOT NULL AND client_ip IS NOT NULL
                AND guest_count IS NOT NULL AND terms_accepted_at IS NOT NULL
                AND privacy_notice_accepted_at IS NOT NULL)
            OR
            (erased_at IS NOT NULL AND client_name IS NULL AND client_phone IS NULL
                AND client_email IS NULL AND client_ip IS NULL AND guest_count IS NULL
                AND event_details IS NULL AND terms_accepted_at IS NULL
                AND privacy_notice_accepted_at IS NULL)
        )
        """
    )
    before = db.execute("SELECT * FROM bookings").fetchall()

    assert app.test_cli_runner().invoke(args=["init-db"]).exit_code == 0

    assert db.execute("SELECT * FROM bookings").fetchall() == before
    clock.now = NOW + SEVEN_DAYS
    assert purge_counts(run_purge(app).output) == (0, 1)
    assert address(db, booking_id) is None


def test_database_erased_booking_must_have_no_details(app, make_booking, db):
    booking_id = make_booking(1, 1)

    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE bookings SET erased_at = now() WHERE id = %s", (booking_id,))
