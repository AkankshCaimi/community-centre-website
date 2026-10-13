"""Listing bookings and changing their state (docs/specs/F02.md: LI, ST)."""

import re
from datetime import date, datetime

from app import db
from app.models.booking import BookingDetails
from app.repositories import booking_repository
from app.services import clock, email
from app.services.booking_validation import has_control_character, utc_to_london_text

STATES = ("submitted", "contacted", "accepted", "declined")
SORTS = ("submitted_at", "starts_at", "name")
ORDERS = ("desc", "asc")
SEARCH_MAX = 100
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100
# Longer numbers are refused without being converted (LI5).
NUMBER_DIGITS_MAX = 100

_DAY_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_WHOLE_NUMBER = re.compile(r"[0-9]+")


class ValidationFailed(Exception):
    def __init__(self, fields: dict[str, str]):
        super().__init__()
        self.fields = fields


class NotFound(Exception):
    pass


class DeclinedIsFinal(Exception):
    pass


def as_item(booking: BookingDetails) -> dict:
    """A booking in the form of LI8."""
    return {
        "id": booking.id,
        "state": booking.state,
        "name": booking.name,
        "email": booking.email,
        "phone": booking.phone,
        "guest_count": booking.guest_count,
        "starts_at": utc_to_london_text(booking.starts_at),
        "ends_at": utc_to_london_text(booking.ends_at),
        "details": booking.details,
        "submitted_at": utc_to_london_text(booking.submitted_at),
        "auto_declined": booking.auto_declined,
    }


def _day(text: str) -> date | None:
    if not _DAY_SHAPE.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _whole_number(query: dict, name: str, default: int, maximum: int | None, errors: dict) -> int:
    if name not in query:
        return default
    if not _WHOLE_NUMBER.fullmatch(query[name]):
        errors[name] = "invalid"
        return default
    if len(query[name]) > NUMBER_DIGITS_MAX:
        errors[name] = "out_of_range"
        return default
    value = int(query[name])
    if value < 1 or (maximum is not None and value > maximum):
        errors[name] = "out_of_range"
        return default
    return value


def _choice(query: dict, name: str, choices: tuple, default, errors: dict):
    if name not in query:
        return default
    if query[name] not in choices:
        errors[name] = "invalid"
        return default
    return query[name]


def list_bookings(query: dict[str, str]) -> dict:
    """Check the query parameters and return one page of bookings (LI1 to LI8)."""
    errors: dict[str, str] = {}

    state = _choice(query, "state", STATES, None, errors)
    sort = _choice(query, "sort", SORTS, SORTS[0], errors)
    order = _choice(query, "order", ORDERS, ORDERS[0], errors)

    days = {}
    for name in ("from", "to"):
        days[name] = None
        if name in query:
            days[name] = _day(query[name])
            if days[name] is None:
                errors[name] = "invalid"
    if days["from"] and days["to"] and days["to"] < days["from"]:
        errors["to"] = "invalid"

    search = query.get("search", "").strip()
    if len(search) > SEARCH_MAX:
        errors["search"] = "too_long"
    elif has_control_character(search):
        errors["search"] = "invalid"

    page = _whole_number(query, "page", 1, None, errors)
    page_size = _whole_number(query, "page_size", PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, errors)

    if errors:
        raise ValidationFailed(errors)

    filters = (state, days["from"], days["to"], search)
    offset = (page - 1) * page_size
    with db.connect() as connection:
        total = booking_repository.count_matching(connection, *filters)
        # A page past the end is empty; this also keeps a huge page number out of the query.
        bookings = (
            booking_repository.list_matching(connection, *filters, sort, order, page_size, offset)
            if offset < total
            else []
        )

    return {
        "items": [as_item(booking) for booking in bookings],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _booking_id(text: str) -> int:
    # No booking ID has more digits than the largest the table can hold.
    if not _WHOLE_NUMBER.fullmatch(text) or len(text) > len(str(booking_repository.MAX_ID)):
        raise NotFound
    return int(text)


def change_state(booking_id_text: str, body: dict) -> dict:
    """Move a booking to another state (ST1 to ST11). Returns it in the form of LI8."""
    errors: dict[str, str] = {}
    state = body.get("state")
    if not isinstance(state, str):
        errors["state"] = "required"
    elif state not in STATES:
        errors["state"] = "invalid"
    elif state == "declined" and body.get("confirm") is not True:
        errors["confirm"] = "required"
    if errors:
        raise ValidationFailed(errors)

    booking_id = _booking_id(booking_id_text)

    with db.connect() as connection:
        booking = booking_repository.find_for_update(connection, booking_id)
        if booking is None:
            raise NotFound
        if booking.state == "declined":
            raise DeclinedIsFinal
        if booking.state == state:
            return as_item(booking)
        changed = booking_repository.set_state(connection, booking_id, state, clock.now_utc())

    item = as_item(changed)
    if state == "accepted":
        try:
            email.log_booking_accepted(
                changed.email, changed.name, item["starts_at"], item["ends_at"]
            )
        except Exception as error:
            # The change is stored; let the failure log say which booking (F01 P1).
            error.booking_id = booking_id
            raise
    return item
