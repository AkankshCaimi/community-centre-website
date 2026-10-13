"""Helpers for the F04 tests. Spec: docs/specs/F04.md."""

import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

# "Now" for every F04 test unless a test moves the clock. Europe/London local
# time, in winter and away from any clock change.
NOW = datetime(2026, 3, 10, 9, 0)
# Six calendar months after NOW, at the same time of day (P2).
SIX_MONTHS_ON = datetime(2026, 9, 10, 9, 0)
SEVEN_DAYS = timedelta(days=7)

ADMIN_EMAIL = "admin@centre.example"
ADMIN_PASSWORD = "correct horse battery"
TEAM_EMAIL = "team@centre.example"
BASE_URL = "https://localhost"

# Every column E1 says is emptied, and every column it says is kept.
EMPTIED = (
    "client_name, client_email, client_phone, host(client_ip), guest_count, event_details,"
    " terms_accepted_at, privacy_notice_accepted_at"
)
KEPT = "id, state, auto_declined, starts_at, ends_at, submitted_at, state_changed_at"


class Clock:
    """Stands in for the CLOCK setting (F01, Replaceable parts)."""

    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


def booking_payload(day, number, **overrides):
    """A valid public booking request (F01) by person `number` on April <day> 2026."""
    body = {
        "name": f"Person {number}",
        "email": f"person{number}@example.com",
        "phone": f"07700 9{number:05d}",
        "guest_count": 40,
        "starts_at": f"2026-04-{day:02d}T10:00",
        "ends_at": f"2026-04-{day:02d}T14:00",
        "details": f"Party {number}",
        "terms_accepted": True,
        "privacy_notice_accepted": True,
        "captcha_token": "token",
    }
    body.update(overrides)
    return body


def logged_in_client(app):
    """A client with an admin session opened at this moment (F02)."""
    client = app.test_client()
    response = client.post(
        "/api/v1/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        base_url=BASE_URL,
    )
    assert response.status_code == 200
    return client


def admin_call(app, method, path, body=None, client=None):
    """Send one admin request, with a fresh session unless a client is given."""
    client = client or logged_in_client(app)
    kwargs = {} if body is None else {"json": body}
    return client.open("/api/v1/admin" + path, method=method, base_url=BASE_URL, **kwargs)


def move(app, booking_id, state):
    body = {"state": state, "confirm": True} if state == "declined" else {"state": state}
    response = admin_call(app, "PATCH", f"/bookings/{booking_id}/state", body)
    assert response.status_code == 200, response.get_json()
    return response


def erase(app, booking_id, client=None, body=None):
    """Ask to erase a booking as an admin (D1)."""
    body = {"confirm": True} if body is None else body
    return admin_call(app, "POST", f"/bookings/{booking_id}/erase", body, client=client)


def run_command(app, name):
    """Run a command inside the test process, with the test clock."""
    return app.test_cli_runner().invoke(args=[name])


def run_purge(app):
    return run_command(app, "purge")


def start_process(name):
    """Start a command as a separate process, as a scheduler would.

    It uses the real clock. Bookings made by these tests were submitted in
    March 2026 or earlier, so to the real clock they are overdue for the
    auto-decline job and, from mid-September 2026, due for the purge.
    """
    environment = dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"])
    return subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "app", name],
        cwd=BACKEND,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def finish(process, timeout=60):
    stdout, stderr = process.communicate(timeout=timeout)
    return process.returncode, stdout, stderr


def purge_counts(output):
    """(N, M) of the heartbeat line "Purge run: N erased, M addresses removed." (P6)."""
    match = re.search(
        r"^Purge run: (\d+) erased, (\d+) addresses removed\.$", output, flags=re.MULTILINE
    )
    assert match is not None, output
    return int(match.group(1)), int(match.group(2))


def is_erased(db, booking_id):
    return (
        db.execute("SELECT erased_at IS NOT NULL FROM bookings WHERE id = %s", (booking_id,))
    ).fetchone()[0]


def emptied(db, booking_id):
    return db.execute(f"SELECT {EMPTIED} FROM bookings WHERE id = %s", (booking_id,)).fetchone()


def kept(db, booking_id):
    return db.execute(f"SELECT {KEPT} FROM bookings WHERE id = %s", (booking_id,)).fetchone()


NOTHING = (None,) * 8
