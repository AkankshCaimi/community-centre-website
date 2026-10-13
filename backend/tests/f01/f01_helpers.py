"""Helpers for the F01 tests. Spec: docs/specs/F01.md."""

from datetime import datetime

# "Now" for every F01 test unless a test moves the clock. UK local time.
NOW = datetime(2026, 3, 10, 9, 0)

TEAM_EMAIL = "team@centre.example"
DEFAULT_IP = "203.0.113.10"


class Clock:
    """Stands in for the CLOCK setting (spec: Replaceable parts)."""

    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


class FakeCaptcha:
    """Stands in for the CAPTCHA_VERIFIER setting (spec: Replaceable parts)."""

    def __init__(self):
        self.passes = True
        self.calls = []

    def __call__(self, token, ip):
        self.calls.append((token, ip))
        return self.passes


def iso(moment):
    """Format a datetime the way the API expects it (spec V5)."""
    return moment.strftime("%Y-%m-%dT%H:%M")


def person(number):
    """Name, email and phone that match no other person(number)."""
    return {
        "name": f"Person {number}",
        "email": f"person{number}@example.com",
        "phone": f"07700 9{number:05d}",
    }


def payload(**overrides):
    """A request that passes every rule in the spec when NOW is unchanged."""
    body = {
        "name": "Alice Example",
        "email": "alice@example.com",
        "phone": "07700 900123",
        "guest_count": 40,
        "starts_at": "2026-04-01T10:00",
        "ends_at": "2026-04-01T14:00",
        "details": "Birthday party",
        "terms_accepted": True,
        "privacy_notice_accepted": True,
        "captcha_token": "token-from-widget",
    }
    body.update(overrides)
    return body


def without(body, *fields):
    return {key: value for key, value in body.items() if key not in fields}


def post(client, body, ip=DEFAULT_IP, headers=None):
    return client.post(
        "/api/v1/bookings", json=body, environ_base={"REMOTE_ADDR": ip}, headers=headers
    )


def post_raw(client, data, content_type="application/json", ip=DEFAULT_IP):
    """Send a body exactly as given, for requests that json= cannot produce."""
    return client.post(
        "/api/v1/bookings",
        data=data,
        content_type=content_type,
        environ_base={"REMOTE_ADDR": ip},
    )
