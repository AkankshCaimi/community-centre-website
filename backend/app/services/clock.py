"""The application's clock.

docs/specs/F01.md, Replaceable parts; docs/specs/F02.md, CK1 and CK2.
"""

from datetime import UTC, datetime

from flask import current_app

from app.services.booking_validation import LONDON, london_to_utc


def exact_now() -> datetime:
    """The real clock: the current instant, in UTC."""
    return datetime.now(UTC)


def read() -> tuple[datetime, datetime]:
    """Now, read once from the configured CLOCK.

    Returns the Europe/London local time without a time zone, and the same
    instant in UTC. A clock that gives a time with its own time zone is taken
    as that exact instant; one that gives a local time without a zone is
    converted, with the hour repeated in autumn meaning its first occurrence.
    """
    value = current_app.config.get("CLOCK", exact_now)()
    if value.tzinfo is None:
        return value, london_to_utc(value)
    return value.astimezone(LONDON).replace(tzinfo=None), value.astimezone(UTC)


def now_utc() -> datetime:
    """Now as a point in time in UTC."""
    return read()[1]
