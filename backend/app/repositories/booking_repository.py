"""Database access for bookings. Plain SQL; the schema is backend/db/schema.sql."""

from datetime import datetime

import psycopg
from psycopg import errors

from app.models.booking import Booking, BookingRequest

# Any fixed number: every booking submission takes the same lock.
_SUBMISSION_LOCK = 4601


class DayTaken(Exception):
    """Another non-declined booking already holds one of the requested days."""


def lock_submissions(connection: psycopg.Connection) -> None:
    """Make booking submissions take turns until this transaction ends (spec F01, L5)."""
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (_SUBMISSION_LOCK,))


def count_created_since(connection: psycopg.Connection, network: str, since: datetime) -> int:
    """Bookings created from addresses inside `network` later than `since`, in any state."""
    row = connection.execute(
        "SELECT count(*) FROM bookings WHERE client_ip <<= %s::inet AND submitted_at > %s",
        (network, since),
    ).fetchone()
    return row[0]


def count_active_slots(
    connection: psycopg.Connection, email: str, phone_normalized: str, now: datetime
) -> int:
    """Non-declined bookings that end later than `now` and match the email or the phone."""
    row = connection.execute(
        """
        SELECT count(*) FROM bookings
        WHERE state <> 'declined'
          AND ends_at > %s
          AND (lower(client_email) = lower(%s) OR client_phone_normalized = %s)
        """,
        (now, email, phone_normalized),
    ).fetchone()
    return row[0]


def insert(
    connection: psycopg.Connection, request: BookingRequest, ip: str, submitted_at: datetime
) -> Booking:
    """Store a new booking in state 'submitted'. Raises DayTaken if a day is locked."""
    try:
        row = connection.execute(
            """
            INSERT INTO bookings (
                starts_at, ends_at, client_name, client_phone, client_email, client_ip,
                guest_count, event_details, terms_accepted_at, privacy_notice_accepted_at,
                submitted_at, state_changed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, state, starts_at, ends_at
            """,
            (
                request.starts_at,
                request.ends_at,
                request.name,
                request.phone,
                request.email,
                ip,
                request.guest_count,
                request.details,
                submitted_at,
                submitted_at,
                submitted_at,
                submitted_at,
            ),
        ).fetchone()
    except errors.ExclusionViolation as error:
        raise DayTaken from error
    return Booking(id=row[0], state=row[1], starts_at=row[2], ends_at=row[3])
