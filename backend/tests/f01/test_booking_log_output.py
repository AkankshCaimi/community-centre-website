"""F01 rule E4: the logged emails reach the application's real log output.

Every expected value comes from docs/specs/F01.md.
"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

# Runs the application the way a server would: no test logging set-up, the real
# clock, the application's own CAPTCHA verifier.
SCRIPT = """
import json
from datetime import datetime, timedelta
from app import create_app

app = create_app()
start = (datetime.now() + timedelta(days=30)).replace(hour=10, minute=0)
body = {
    "name": "Alice Example",
    "email": "alice@example.com",
    "phone": "07700 900123",
    "guest_count": 40,
    "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
    "ends_at": (start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
    "terms_accepted": True,
    "privacy_notice_accepted": True,
    "captcha_token": "any-token",
}
response = app.test_client().post("/api/v1/bookings", json=body)
print(response.status_code)
"""


def test_e4_emails_and_captcha_line_reach_standard_error(app):
    # The `app` fixture has created an empty bookings table in the test database.
    environment = dict(
        os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"], TEAM_EMAIL="team@centre.example"
    )

    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.stdout.strip() == "201", result.stderr
    assert "alice@example.com" in result.stderr  # E1: the recipient
    assert "team@centre.example" in result.stderr  # E2: the recipient
    assert "Alice Example" in result.stderr
    assert "CAPTCHA stand-in passed a token." in result.stderr  # C2
