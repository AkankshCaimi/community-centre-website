"""Logged emails: rules E1 to E3 and P1 of docs/specs/F01.md, ST7 and PR2 of docs/specs/F02.md.

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


def log_booking_accepted(client_email: str, name: str, starts_at: str, ends_at: str) -> None:
    """The confirmation a client gets when their booking is accepted (F02 ST7)."""
    logger.info(
        "To: %s\nSubject: Your booking is confirmed\n\n"
        "Dear %s,\n\n"
        "Your booking from %s to %s has been accepted.",
        single_line(client_email),
        single_line(name),
        starts_at,
        ends_at,
    )


def log_password_reset(admin_email: str, token: str) -> None:
    """The reset email for the admin, with the token on a line of its own (F02 PR2)."""
    logger.info(
        "To: %s\nSubject: Reset your admin password\n\n"
        "Use this token to set a new password. It is valid for 30 minutes.\n"
        "Token: %s",
        single_line(admin_email),
        token,
    )
