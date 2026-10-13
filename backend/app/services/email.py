"""Emails for a new booking: rules E1 to E3 and P1 of docs/specs/F01.md.

Emails are written to the log, not sent.
"""

import logging
import re

from flask import current_app

from app.models.booking import BookingRequest
from app.services.booking_validation import utc_to_london_text

logger = logging.getLogger("app.email")

# Line feed, carriage return, vertical tab, form feed, next line, line and paragraph separator.
_LINE_BREAKS = re.compile("[\n\r\v\f\x85\u2028\u2029]+")


def single_line(text: str) -> str:
    """Client text with each run of line breaks collapsed to one space (P1)."""
    return _LINE_BREAKS.sub(" ", text)


def log_client_confirmation(request: BookingRequest) -> None:
    logger.info(
        "To: %s\nSubject: We have received your booking request\n\n"
        "Dear %s,\n\n"
        "We have received your booking request from %s to %s.\n"
        "The management team will contact you to confirm the details.",
        single_line(request.email),
        single_line(request.name),
        utc_to_london_text(request.starts_at),
        utc_to_london_text(request.ends_at),
    )


def log_team_notification(request: BookingRequest) -> None:
    logger.info(
        "To: %s\nSubject: New booking request\n\n"
        "Name: %s\nEmail: %s\nPhone: %s\nGuests: %s\nFrom: %s\nTo: %s\nDetails: %s",
        current_app.config.get("TEAM_EMAIL"),
        single_line(request.name),
        single_line(request.email),
        single_line(request.phone),
        request.guest_count,
        utc_to_london_text(request.starts_at),
        utc_to_london_text(request.ends_at),
        single_line(request.details or ""),
    )
