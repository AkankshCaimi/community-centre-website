"""Helpers for the F03 tests. Spec: docs/specs/F03.md."""

import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

# "Now" for every F03 test unless a test moves the clock. Europe/London local
# time, in winter and away from any clock change.
NOW = datetime(2026, 3, 10, 9, 0)
HOURS_48 = timedelta(hours=48)

ADMIN_EMAIL = "admin@centre.example"
ADMIN_PASSWORD = "correct horse battery"
TEAM_EMAIL = "team@centre.example"
BASE_URL = "https://localhost"


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
        "terms_accepted": True,
        "privacy_notice_accepted": True,
        "captcha_token": "token",
    }
    body.update(overrides)
    return body


def run_job(app):
    """Run the auto-decline command inside the test process, with the test clock."""
    return app.test_cli_runner().invoke(args=["auto-decline"])


def start_job_process():
    """Start the command as a separate process, as a scheduler would (R1, R2).

    It uses the real clock. Bookings made by these tests were submitted in
    March 2026, so to the real clock they are all long overdue.
    """
    environment = dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"])
    return subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "app", "auto-decline"],
        cwd=BACKEND,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def declined_count(output):
    """The N of the heartbeat line "Auto-decline run: N declined." (R3)."""
    match = re.search(r"^Auto-decline run: (\d+) declined\.$", output, flags=re.MULTILINE)
    assert match is not None, output
    return int(match.group(1))


def states(db):
    """Every booking's state and mark, by ID."""
    return {
        booking_id: (state, auto)
        for booking_id, state, auto in db.execute("SELECT id, state, auto_declined FROM bookings")
    }


def admin_call(app, method, path, body=None):
    """Send one admin request with a session opened at this moment (F02)."""
    client = app.test_client()
    logged_in = client.post(
        "/api/v1/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        base_url=BASE_URL,
    )
    assert logged_in.status_code == 200
    kwargs = {} if body is None else {"json": body}
    return client.open("/api/v1/admin" + path, method=method, base_url=BASE_URL, **kwargs)


def move(app, booking_id, state):
    body = {"state": state, "confirm": True} if state == "declined" else {"state": state}
    response = admin_call(app, "PATCH", f"/bookings/{booking_id}/state", body)
    assert response.status_code == 200, response.get_json()
    return response
