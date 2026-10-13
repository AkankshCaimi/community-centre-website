"""F03 rules J8 to J10 (a run that stops, two runs at once, bookings held elsewhere),
R4 to R6 (failure, last run, /health) and the database change.

Every expected value comes from docs/specs/F03.md; each test names the rule it checks.
"""

import logging
import os
import re
from datetime import timedelta

import psycopg
import pytest
from f03_helpers import HOURS_48, NOW, declined_count, run_job, start_job_process, states

# Makes any change to one particular booking fail inside the database, so a
# run stops part-way through its work.
BREAK_ONE_BOOKING = """
    CREATE FUNCTION refuse_person_3() RETURNS trigger AS $$
    BEGIN
        IF NEW.client_name = 'Person 3' AND NEW.state = 'declined' THEN
            RAISE EXCEPTION 'cannot change the booking of %', NEW.client_name;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER refuse_person_3 BEFORE UPDATE ON bookings
        FOR EACH ROW EXECUTE FUNCTION refuse_person_3();
"""
MEND = "DROP TRIGGER refuse_person_3 ON bookings; DROP FUNCTION refuse_person_3();"


@pytest.fixture
def five_overdue(make_booking, clock):
    made = [make_booking(number, number) for number in range(1, 6)]
    clock.now = NOW + HOURS_48
    return made


@pytest.fixture
def broken(db, five_overdue):
    db.execute(BREAK_ONE_BOOKING)
    yield five_overdue
    db.execute("DROP TRIGGER IF EXISTS refuse_person_3 ON bookings")
    db.execute("DROP FUNCTION IF EXISTS refuse_person_3()")


# --- J8 and R4: a run that stops part-way


def test_j8_run_that_stops_part_way_changes_no_booking(app, broken, db):
    before = db.execute("SELECT * FROM bookings ORDER BY id").fetchall()

    result = run_job(app)

    assert result.exit_code == 1
    assert db.execute("SELECT * FROM bookings ORDER BY id").fetchall() == before
    assert set(states(db).values()) == {("submitted", False)}


def test_j8_next_run_declines_everything_once_the_fault_is_gone(app, broken, db):
    assert run_job(app).exit_code == 1
    db.execute(MEND)

    result = run_job(app)

    assert result.exit_code == 0
    assert declined_count(result.output) == 5
    assert states(db) == {booking_id: ("declined", True) for booking_id in broken}


def test_r4_failed_run_reports_only_the_type_of_the_error(app, broken, caplog):
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        result = run_job(app)

    assert result.exit_code == 1
    records = [record for record in caplog.records if record.name == "app.jobs"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    line = records[0].getMessage()
    assert re.fullmatch(r"Auto-decline run failed: \w+\.", line), line
    assert line in result.stdout
    assert "Auto-decline run:" not in result.stdout  # no heartbeat for a failed run
    everything = result.output + "\n".join(
        record.getMessage() + str(record.exc_info or "") + (record.exc_text or "")
        for record in caplog.records
    )
    for private in ("Person 3", "person3@example.com", "cannot change the booking"):
        assert private not in everything


def test_r4_run_fails_cleanly_when_the_database_cannot_be_reached(app, caplog):
    # Nothing is listening on port 1.
    app.config["DATABASE_URL"] = "postgresql://nobody:nothing@127.0.0.1:1/nowhere"
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        result = run_job(app)

    assert result.exit_code == 1
    lines = [record.getMessage() for record in caplog.records if record.name == "app.jobs"]
    assert len(lines) == 1
    assert re.fullmatch(r"Auto-decline run failed: \w+\.", lines[0])
    assert "nobody" not in result.output
    assert "nothing" not in result.output


# --- R5 and R6: the last run, and /health


def health(app):
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.content_type == "application/json"
    return response.get_json()


def test_r6_health_shows_null_before_any_run(app):
    assert health(app) == {"status": "ok", "auto_decline_last_run": None, "purge_last_run": None}


def test_r5_r6_health_shows_the_instant_of_the_last_successful_run(app, clock):
    clock.now = NOW + timedelta(hours=3, minutes=4, seconds=5)  # 12:04:05 in London, winter

    assert run_job(app).exit_code == 0

    assert health(app) == {
        "status": "ok",
        "auto_decline_last_run": "2026-03-10T12:04:05Z",
        "purge_last_run": None,
    }


def test_r6_last_run_is_reported_in_utc_in_summer(app, clock):
    clock.now = NOW.replace(month=6, hour=14, minute=30)  # 14:30 in London is 13:30 UTC

    run_job(app)

    assert health(app)["auto_decline_last_run"] == "2026-06-10T13:30:00Z"


def test_r5_every_successful_run_moves_the_last_run_on(app, clock):
    run_job(app)
    assert health(app)["auto_decline_last_run"] == "2026-03-10T09:00:00Z"

    clock.now = NOW + timedelta(hours=1)
    run_job(app)

    assert health(app)["auto_decline_last_run"] == "2026-03-10T10:00:00Z"


def test_r5_a_run_with_nothing_to_decline_still_counts(app, make_booking, clock):
    make_booking(1, 1)
    clock.now = NOW + timedelta(hours=1)

    assert declined_count(run_job(app).output) == 0

    assert health(app)["auto_decline_last_run"] == "2026-03-10T10:00:00Z"


def test_r5_failed_run_does_not_move_the_last_run_on(app, broken, clock, db):
    db.execute(MEND)
    clock.now = NOW + timedelta(hours=40)
    run_job(app)  # succeeds: nothing is overdue yet
    db.execute(BREAK_ONE_BOOKING)

    clock.now = NOW + HOURS_48
    assert run_job(app).exit_code == 1

    assert health(app)["auto_decline_last_run"] == "2026-03-12T01:00:00Z"


def test_r6_health_answers_with_null_when_the_database_cannot_be_reached(app, clock):
    run_job(app)
    app.config["DATABASE_URL"] = "postgresql://nobody:nothing@127.0.0.1:1/nowhere"

    assert health(app) == {"status": "ok", "auto_decline_last_run": None, "purge_last_run": None}


# --- J9: two runs at the same instant
#
# These start the command as real processes, as a scheduler would. They use
# the real clock, to which bookings submitted in March 2026 are long overdue.


def finish(process, timeout=60):
    stdout, stderr = process.communicate(timeout=timeout)
    return process.returncode, stdout, stderr


def test_j9_two_runs_at_once_decline_each_booking_exactly_once(app, make_booking, db):
    made = [make_booking(number, number) for number in range(1, 26)]

    first, second = start_job_process(), start_job_process()
    results = [finish(first), finish(second)]

    assert [code for code, _, _ in results] == [0, 0]
    counts = [declined_count(stdout) for _, stdout, _ in results]
    assert sum(counts) == 25
    assert states(db) == {booking_id: ("declined", True) for booking_id in made}


def test_j9_run_as_a_process_reports_like_a_run_in_the_test_process(app, make_booking, db):
    made = [make_booking(number, number) for number in range(1, 4)]

    code, stdout, stderr = finish(start_job_process())

    assert code == 0
    assert stdout.strip() == "Auto-decline run: 3 declined."
    assert "Auto-decline run: 3 declined." in stderr  # the heartbeat reaches the real log
    assert states(db) == {booking_id: ("declined", True) for booking_id in made}


# --- J10: a booking held by another request is skipped, not waited for


@pytest.fixture
def other_session():
    """A second database session, standing in for an admin request in progress."""
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
        yield connection
        connection.rollback()


def hold(other_session, booking_id):
    """Take the lock a state change takes on a booking, and keep it."""
    other_session.execute("SELECT id FROM bookings WHERE id = %s FOR UPDATE", (booking_id,))


def test_j10_held_booking_is_skipped_and_the_rest_are_declined(
    app, make_booking, db, other_session
):
    held, second, third = (make_booking(number, number) for number in range(1, 4))
    hold(other_session, held)

    # If the run waited for the held booking, this would time out.
    code, stdout, _ = finish(start_job_process(), timeout=30)

    assert code == 0
    assert declined_count(stdout) == 2
    assert states(db) == {
        held: ("submitted", False),
        second: ("declined", True),
        third: ("declined", True),
    }


def test_j10_skipped_booking_is_declined_by_the_next_run_if_still_overdue(
    app, make_booking, db, other_session
):
    held = make_booking(1, 1)
    hold(other_session, held)
    assert declined_count(finish(start_job_process(), timeout=30)[1]) == 0

    other_session.rollback()  # the other request ends without changing the booking
    code, stdout, _ = finish(start_job_process())

    assert declined_count(stdout) == 1
    assert states(db)[held] == ("declined", True)


def test_j10_booking_the_admin_moved_meanwhile_is_left_alone(app, make_booking, db, other_session):
    held = make_booking(1, 1)
    hold(other_session, held)
    assert declined_count(finish(start_job_process(), timeout=30)[1]) == 0

    other_session.execute("UPDATE bookings SET state = 'contacted' WHERE id = %s", (held,))
    other_session.commit()
    code, stdout, _ = finish(start_job_process())

    assert declined_count(stdout) == 0
    assert states(db)[held] == ("contacted", False)


def test_j10_a_run_does_not_hold_up_a_public_request(app, make_booking, db, other_session):
    """J11: requests made during a run are answered as usual."""
    held = make_booking(1, 1)
    hold(other_session, held)
    process = start_job_process()

    response = app.test_client().post(
        "/api/v1/bookings",
        json={
            "name": "Someone New",
            "email": "new@example.com",
            "phone": "07700 955555",
            "guest_count": 10,
            "starts_at": "2026-04-20T10:00",
            "ends_at": "2026-04-20T12:00",
            "terms_accepted": True,
            "privacy_notice_accepted": True,
            "captcha_token": "token",
        },
    )

    assert response.status_code == 201
    assert finish(process, timeout=30)[0] == 0


# --- Database: init-db adds the column to an existing table


def test_database_init_db_adds_the_mark_to_an_existing_table(app, make_booking, db):
    booking_id = make_booking(1, 1, details="Birthday party")
    kept = "SELECT id, state, client_name, client_email, event_details, submitted_at FROM bookings"
    before = db.execute(kept).fetchall()
    # Put the table back to how F02 left it.
    db.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS auto_declined")
    db.execute("DROP TABLE IF EXISTS job_runs")

    result = app.test_cli_runner().invoke(args=["init-db"])

    assert result.exit_code == 0
    assert db.execute(kept).fetchall() == before
    assert states(db) == {booking_id: ("submitted", False)}
    assert db.execute("SELECT to_regclass('job_runs') IS NOT NULL").fetchone()[0] is True


def test_database_mark_can_only_be_set_on_a_declined_booking(app, make_booking, db):
    booking_id = make_booking(1, 1)

    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE bookings SET auto_declined = true WHERE id = %s", (booking_id,))
