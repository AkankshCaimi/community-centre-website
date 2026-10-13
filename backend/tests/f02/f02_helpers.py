"""Helpers for the F02 tests. Spec: docs/specs/F02.md."""

from datetime import datetime

# "Now" for every F02 test unless a test moves the clock. Europe/London local time.
NOW = datetime(2026, 3, 10, 9, 0)

ADMIN_EMAIL = "admin@centre.example"
ADMIN_PASSWORD = "correct horse battery"  # 21 characters
TEAM_EMAIL = "team@centre.example"
BASE_URL = "https://localhost"
ADMIN = "/api/v1/admin"
NOT_AUTHENTICATED = {"error": "not_authenticated"}


class Clock:
    """Stands in for the CLOCK setting (F01, Replaceable parts)."""

    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


class FakeCaptcha:
    """Stands in for the CAPTCHA_VERIFIER setting; passes everything."""

    def __call__(self, token, ip):
        return True


def call(client, method, path, body=None, **kwargs):
    """Send a request to the admin API over HTTPS, with a JSON body if one is given."""
    if body is not None:
        kwargs["json"] = body
    return client.open(ADMIN + path, method=method, base_url=BASE_URL, **kwargs)


def login(client, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    return call(client, "POST", "/login", {"email": email, "password": password})


def session_cookie(response):
    """The Set-Cookie header for admin_session, as (value, set of lower-case attributes)."""
    for header in response.headers.getlist("Set-Cookie"):
        first, *attributes = [part.strip() for part in header.split(";")]
        name, _, value = first.partition("=")
        if name == "admin_session":
            return value, {attribute.lower() for attribute in attributes}
    return None


def create_admin(app, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, repeat=None):
    """Run the create-admin command (CL1), typing the password at its two prompts."""
    typed = f"{password}\n{password if repeat is None else repeat}\n"
    return app.test_cli_runner().invoke(args=["create-admin", "--email", email], input=typed)


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


def iso(moment):
    """Format a datetime in the form of F01 V5."""
    return moment.strftime("%Y-%m-%dT%H:%M")
