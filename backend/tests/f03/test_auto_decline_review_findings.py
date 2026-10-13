"""F03 rules the branch review found untested or weakly tested: J8 with R5,
J9 and J10 with runs that really overlap, J11 during a run, R5 and R7.

Every expected value comes from docs/specs/F03.md; each test names the rule it checks.
"""

import logging
import re
import socket
import threading
import time
from datetime import timedelta

import pytest
from f03_helpers import (
    HOURS_48,
    NOW,
    admin_call,
    booking_payload,
    declined_count,
    run_job,
    start_job_process,
    states,
)

# Makes every decline slow and writes it down, so that two runs really overlap
# and a booking changed twice would show up twice.
SLOW_AND_COUNTED = """
    CREATE TABLE decline_log (booking_id bigint NOT NULL);
    CREATE FUNCTION slow_decline() RETURNS trigger AS $$
    BEGIN
        IF NEW.state = 'declined' AND OLD.state <> 'declined' THEN
            INSERT INTO decline_log VALUES (NEW.id);
            PERFORM pg_sleep(0.15);
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER slow_decline BEFORE UPDATE ON bookings
        FOR EACH ROW EXECUTE FUNCTION slow_decline();
"""


@pytest.fixture
def slow_declines(app, db):
    db.execute(SLOW_AND_COUNTED)
    yield
    db.execute("DROP TRIGGER IF EXISTS slow_decline ON bookings")
    db.execute("DROP FUNCTION IF EXISTS slow_decline()")
    db.execute("DROP TABLE IF EXISTS decline_log")


def finish(process, timeout=60):
    stdout, stderr = process.communicate(timeout=timeout)
    return process.returncode, stdout, stderr


def wait_until_a_run_holds_bookings(db, timeout=20):
    """Wait until a run is part-way through changing bookings.

    The slow_declines trigger sleeps inside every decline, so a database
    session waiting in that sleep is a run that holds bookings right now.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sleeping = db.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE wait_event = 'PgSleep'"
        ).fetchone()[0]
        if sleeping:
            return
        time.sleep(0.02)
    raise AssertionError("no run started changing bookings")


# --- J8 with R5: the declines and the record of the run are one step


def test_j8_r5_nothing_is_declined_if_the_run_cannot_be_recorded(app, make_booking, clock, db):
    made = [make_booking(number, number) for number in range(1, 4)]
    clock.now = NOW + HOURS_48
    db.execute("DROP TABLE job_runs")  # the run can decline, but cannot record itself

    result = run_job(app)

    assert result.exit_code == 1
    assert states(db) == {booking_id: ("submitted", False) for booking_id in made}


# --- J9: runs that really overlap


def test_j9_overlapping_runs_change_each_booking_exactly_once(app, make_booking, db, slow_declines):
    made = [make_booking(number, number) for number in range(1, 21)]

    first = start_job_process()
    wait_until_a_run_holds_bookings(db)
    second = start_job_process()  # starts while the first is part-way through
    results = [finish(first), finish(second)]

    assert [code for code, _, _ in results] == [0, 0]
    assert sum(declined_count(stdout) for _, stdout, _ in results) == 20
    assert states(db) == {booking_id: ("declined", True) for booking_id in made}
    changes = [row[0] for row in db.execute("SELECT booking_id FROM decline_log")]
    assert sorted(changes) == sorted(made)  # once each: no booking appears twice


def test_j9_three_overlapping_runs_change_each_booking_exactly_once(
    app, make_booking, db, slow_declines
):
    made = [make_booking(number, number) for number in range(1, 16)]

    processes = [start_job_process() for _ in range(3)]
    results = [finish(process) for process in processes]

    assert [code for code, _, _ in results] == [0, 0, 0]
    assert sum(declined_count(stdout) for _, stdout, _ in results) == 15
    changes = [row[0] for row in db.execute("SELECT booking_id FROM decline_log")]
    assert sorted(changes) == sorted(made)


# --- J10: an admin's change that arrives while a run holds the booking


@pytest.mark.parametrize("target", ["contacted", "accepted"])
def test_j10_admin_change_arriving_during_a_run_is_refused(
    app, admin, make_booking, db, slow_declines, target
):
    made = [make_booking(number, number) for number in range(1, 11)]
    # Log in before the run starts, so the request itself is the only thing racing it.
    client = app.test_client()
    client.post(
        "/api/v1/admin/login",
        json={"email": "admin@centre.example", "password": "correct horse battery"},
        base_url="https://localhost",
    )

    process = start_job_process()
    wait_until_a_run_holds_bookings(db)
    response = client.patch(
        f"/api/v1/admin/bookings/{made[-1]}/state",
        json={"state": target},
        base_url="https://localhost",
    )
    code, stdout, _ = finish(process)

    assert code == 0
    assert declined_count(stdout) == 10
    assert response.status_code == 409
    assert response.get_json() == {"error": "declined_is_final"}
    assert states(db)[made[-1]] == ("declined", True)


# --- J11: requests made during a run are answered as usual


def test_j11_public_request_is_answered_while_a_run_is_in_progress(
    app, make_booking, db, slow_declines
):
    for number in range(1, 21):
        make_booking(number, number)

    process = start_job_process()
    wait_until_a_run_holds_bookings(db)
    started = time.monotonic()
    response = app.test_client().post(
        "/api/v1/bookings",
        json=booking_payload(25, 99),
        environ_base={"REMOTE_ADDR": "203.0.113.200"},
    )
    took = time.monotonic() - started
    still_running = process.poll() is None
    finish(process)

    assert response.status_code == 201
    assert still_running, "the run had already finished, so nothing was tested"
    assert took < 1.0


def test_j11_admin_list_is_answered_while_a_run_is_in_progress(
    app, admin, make_booking, db, slow_declines
):
    for number in range(1, 21):
        make_booking(number, number)

    process = start_job_process()
    wait_until_a_run_holds_bookings(db)
    response = admin_call(app, "GET", "/bookings")
    still_running = process.poll() is None
    finish(process)

    assert response.status_code == 200
    assert response.get_json()["total"] == 20
    assert still_running, "the run had already finished, so nothing was tested"


# --- R5: the last-run time never moves backwards


def health(app):
    return app.test_client().get("/health").get_json()


def test_r5_last_run_does_not_move_backwards(app, clock):
    clock.now = NOW + timedelta(hours=5)
    run_job(app)
    assert health(app)["auto_decline_last_run"] == "2026-03-10T14:00:00Z"

    clock.now = NOW + timedelta(hours=2)  # a run whose clock reads earlier
    assert run_job(app).exit_code == 0

    assert health(app)["auto_decline_last_run"] == "2026-03-10T14:00:00Z"


# --- R7: /health does not wait for a database that never answers


@pytest.fixture
def silent_server():
    """Something that accepts connections on a port and then says nothing."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    accepted = []
    stop = threading.Event()

    def accept():
        listener.settimeout(0.2)
        while not stop.is_set():
            try:
                accepted.append(listener.accept()[0])
            except TimeoutError:
                continue
            except OSError:
                return

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield listener.getsockname()[1]
    stop.set()
    thread.join(timeout=2)
    for connection in accepted:
        connection.close()
    listener.close()


def test_r7_health_gives_up_on_a_database_that_does_not_answer(app, silent_server):
    app.config["DATABASE_URL"] = f"postgresql://nobody:nothing@127.0.0.1:{silent_server}/nowhere"

    started = time.monotonic()
    response = app.test_client().get("/health")
    took = time.monotonic() - started

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "auto_decline_last_run": None,
        "purge_last_run": None,
    }
    assert took < 4.0  # 2 seconds, with room for a slow machine


def test_r7_unreadable_last_run_is_logged_as_a_warning_with_only_the_error_type(app, caplog):
    app.config["DATABASE_URL"] = "postgresql://nobody:secret-word@127.0.0.1:1/nowhere"
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        response = app.test_client().get("/health")

    assert response.get_json() == {
        "status": "ok",
        "auto_decline_last_run": None,
        "purge_last_run": None,
    }
    records = [record for record in caplog.records if record.name == "app.jobs"]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    line = records[0].getMessage()
    assert re.fullmatch(r"Last auto-decline run could not be read: \w+\.", line), line
    assert "secret-word" not in line


def test_r7_nothing_is_logged_when_the_last_run_can_be_read(app, caplog):
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        app.test_client().get("/health")

    assert [record for record in caplog.records if record.name == "app.jobs"] == []


def test_r6_r7_missing_table_reads_as_null_and_is_logged(app, db, caplog):
    db.execute("DROP TABLE job_runs")
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        response = app.test_client().get("/health")

    assert response.get_json() == {
        "status": "ok",
        "auto_decline_last_run": None,
        "purge_last_run": None,
    }
    assert len([record for record in caplog.records if record.name == "app.jobs"]) == 1


def test_database_init_db_again_keeps_an_auto_declined_booking_as_it_is(
    app, make_booking, clock, db
):
    make_booking(1, 1)
    clock.now = NOW + HOURS_48
    run_job(app)
    before = db.execute("SELECT * FROM bookings").fetchall()
    last_run = db.execute("SELECT * FROM job_runs").fetchall()

    assert app.test_cli_runner().invoke(args=["init-db"]).exit_code == 0

    assert db.execute("SELECT * FROM bookings").fetchall() == before
    assert db.execute("SELECT * FROM job_runs").fetchall() == last_run


# --- R4, R6: no database configured at all


@pytest.mark.parametrize("url", [None, ""])
def test_r6_health_answers_with_null_when_no_database_is_configured(app, caplog, url):
    app.config["DATABASE_URL"] = url
    app.config["PROPAGATE_EXCEPTIONS"] = False
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "auto_decline_last_run": None,
        "purge_last_run": None,
    }
    assert len([record for record in caplog.records if record.name == "app.jobs"]) == 1


@pytest.mark.parametrize("url", [None, ""])
def test_r4_run_fails_cleanly_when_no_database_is_configured(app, url):
    app.config["DATABASE_URL"] = url

    result = run_job(app)

    assert result.exit_code == 1
    assert re.fullmatch(r"Auto-decline run failed: \w+\.", result.stdout.strip())
