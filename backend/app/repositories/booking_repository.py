"""Database access for bookings. Plain SQL; the schema is backend/db/schema.sql."""

from datetime import datetime

import psycopg
from psycopg import errors

from app.models.booking import Booking, BookingDetails, BookingRequest

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


# --- admin (docs/specs/F02.md)

_DETAIL_COLUMNS = """
    id, state, client_name, client_email, client_phone, guest_count,
    starts_at, ends_at, event_details, submitted_at, auto_declined, erased_at IS NOT NULL
"""

# The only ORDER BY expressions a caller can choose between (LI4).
_SORT_EXPRESSIONS = {
    "submitted_at": "submitted_at",
    "starts_at": "starts_at",
    "name": "lower(client_name)",
}
_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}

# The largest ID the bookings table can hold.
MAX_ID = 2**63 - 1


def _details(row) -> BookingDetails:
    return BookingDetails(*row)


def _like_pattern(text: str) -> str:
    """A LIKE pattern matching `text` anywhere, with its wildcards made ordinary (LI3)."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _filters(state, first_day, last_day, search) -> tuple[str, list]:
    conditions, values = ["TRUE"], []
    if state is not None:
        conditions.append("state = %s")
        values.append(state)
    if first_day is not None:
        conditions.append("(starts_at AT TIME ZONE 'Europe/London')::date >= %s")
        values.append(first_day)
    if last_day is not None:
        conditions.append("(starts_at AT TIME ZONE 'Europe/London')::date <= %s")
        values.append(last_day)
    if search:
        conditions.append(
            "(client_name ILIKE %s ESCAPE '\\' OR client_email ILIKE %s ESCAPE '\\'"
            " OR client_phone ILIKE %s ESCAPE '\\')"
        )
        values.extend([_like_pattern(search)] * 3)
    return " AND ".join(conditions), values


def count_matching(connection: psycopg.Connection, state, first_day, last_day, search) -> int:
    where, values = _filters(state, first_day, last_day, search)
    return connection.execute(f"SELECT count(*) FROM bookings WHERE {where}", values).fetchone()[0]


def list_matching(
    connection: psycopg.Connection,
    state,
    first_day,
    last_day,
    search,
    sort: str,
    order: str,
    limit: int,
    offset: int,
) -> list[BookingDetails]:
    """One page of the bookings that pass the filters, in the chosen order (LI1 to LI6)."""
    where, values = _filters(state, first_day, last_day, search)
    direction = _DIRECTIONS[order]
    rows = connection.execute(
        f"""
        SELECT {_DETAIL_COLUMNS} FROM bookings
        WHERE {where}
        ORDER BY {_SORT_EXPRESSIONS[sort]} {direction}, id {direction}
        LIMIT %s OFFSET %s
        """,
        [*values, limit, offset],
    ).fetchall()
    return [_details(row) for row in rows]


def find_for_update(connection: psycopg.Connection, booking_id: int) -> BookingDetails | None:
    """The booking, locked until the transaction ends so state changes take turns (ST11)."""
    if booking_id > MAX_ID:
        return None
    row = connection.execute(
        f"SELECT {_DETAIL_COLUMNS} FROM bookings WHERE id = %s FOR UPDATE", (booking_id,)
    ).fetchone()
    return None if row is None else _details(row)


def set_state(
    connection: psycopg.Connection, booking_id: int, state: str, changed_at: datetime
) -> BookingDetails:
    row = connection.execute(
        f"""
        UPDATE bookings SET state = %s, state_changed_at = %s WHERE id = %s
        RETURNING {_DETAIL_COLUMNS}
        """,
        (state, changed_at, booking_id),
    ).fetchone()
    return _details(row)


# --- auto-decline job (docs/specs/F03.md)


def auto_decline_overdue(
    connection: psycopg.Connection, submitted_by: datetime, now: datetime
) -> int:
    """Decline every booking still in 'submitted' that was submitted at or before `submitted_by`.

    One statement: it changes all of them or, if anything fails, none (J8). A
    booking another request holds at this moment is skipped, not waited for
    (J10), which is also what stops two runs declining the same booking (J9).
    Returns how many were declined.
    """
    return connection.execute(
        """
        UPDATE bookings
        SET state = 'declined', auto_declined = true, state_changed_at = %(now)s
        WHERE id IN (
            SELECT id FROM bookings
            WHERE state = 'submitted' AND submitted_at <= %(submitted_by)s
            FOR UPDATE SKIP LOCKED
        )
        """,
        {"now": now, "submitted_by": submitted_by},
    ).rowcount


# --- erasing client data (docs/specs/F04.md)

# What erasing empties (E1). Everything else about the booking is kept.
_EMPTY_THE_DETAILS = """
    client_name = NULL, client_email = NULL, client_phone = NULL, client_ip = NULL,
    guest_count = NULL, event_details = NULL,
    terms_accepted_at = NULL, privacy_notice_accepted_at = NULL
"""


def erase(connection: psycopg.Connection, booking_id: int, now: datetime) -> BookingDetails:
    """Empty one booking's client details and record when (E1)."""
    row = connection.execute(
        f"""
        UPDATE bookings SET {_EMPTY_THE_DETAILS}, erased_at = %s WHERE id = %s
        RETURNING {_DETAIL_COLUMNS}
        """,
        (now, booking_id),
    ).fetchone()
    return _details(row)


def lock_unerased_submitted_by(
    connection: psycopg.Connection, submitted_by: datetime
) -> list[tuple[int, datetime]]:
    """The ID and submission time of every unerased booking submitted at or before `submitted_by`.

    The rows are locked until the transaction ends, so that a caller can decide
    which of them to erase and no other request changes them meanwhile. A
    booking another request holds is skipped, not waited for (P13).
    """
    return connection.execute(
        """
        SELECT id, submitted_at FROM bookings
        WHERE erased_at IS NULL AND submitted_at <= %s
        ORDER BY id
        FOR UPDATE SKIP LOCKED
        """,
        (submitted_by,),
    ).fetchall()


def erase_many(connection: psycopg.Connection, booking_ids: list[int], now: datetime) -> int:
    """Erase the given bookings (E1). Returns how many were erased."""
    if not booking_ids:
        return 0
    return connection.execute(
        f"""
        UPDATE bookings SET {_EMPTY_THE_DETAILS}, erased_at = %s
        WHERE id = ANY(%s) AND erased_at IS NULL
        """,
        (now, booking_ids),
    ).rowcount


def remove_addresses(connection: psycopg.Connection, submitted_by: datetime) -> int:
    """Empty the network address of every booking submitted at or before `submitted_by` (P4).

    Returns how many addresses were removed.
    """
    return connection.execute(
        """
        UPDATE bookings SET client_ip = NULL
        WHERE id IN (
            SELECT id FROM bookings
            WHERE client_ip IS NOT NULL AND submitted_at <= %s
            FOR UPDATE SKIP LOCKED
        )
        """,
        (submitted_by,),
    ).rowcount
