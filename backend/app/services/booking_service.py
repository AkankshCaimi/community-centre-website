"""Submitting a booking request: the order of checks O1 of docs/specs/F01.md."""

import ipaddress
from datetime import timedelta

from app import db
from app.models.booking import Booking
from app.repositories import booking_repository
from app.repositories.booking_repository import DayTaken
from app.services import captcha, clock, email
from app.services.booking_validation import normalize_phone, validate

RATE_LIMIT = 5
RATE_WINDOW = timedelta(hours=24)
SLOT_LIMIT = 2
IPV6_BLOCK_BITS = 64


class ValidationFailed(Exception):
    def __init__(self, fields: dict[str, str]):
        super().__init__()
        self.fields = fields


class CaptchaFailed(Exception):
    pass


class RateLimited(Exception):
    pass


class NotAccepted(Exception):
    """The slot limit is reached or a day is taken. Deliberately one error for both (G1)."""


def normalize_address(ip: str) -> str:
    """The address as stored and counted: IPv4 written in IPv6 form becomes IPv4 (spec L1)."""
    address = ipaddress.ip_address(ip)
    if address.version == 6 and address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(address)


def rate_limit_network(ip: str) -> str:
    """The block of addresses that shares one rate limit with `ip` (spec L1)."""
    address = ipaddress.ip_address(ip)
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/{IPV6_BLOCK_BITS}", strict=False))
    return str(address)


def submit_booking(body: dict, ip: str) -> Booking:
    """Check a booking request and store it. Raises on the first check that fails."""
    now_local, now = clock.read()
    ip = normalize_address(ip)

    request, errors = validate(body, now_local, now)
    if request is None:
        raise ValidationFailed(errors)

    if not captcha.verify(request.captcha_token, ip):
        raise CaptchaFailed

    with db.connect() as connection:
        booking_repository.lock_submissions(connection)

        recent = booking_repository.count_created_since(
            connection, rate_limit_network(ip), now - RATE_WINDOW
        )
        if recent >= RATE_LIMIT:
            raise RateLimited

        held = booking_repository.count_active_slots(
            connection, request.email, normalize_phone(request.phone), now
        )
        if held >= SLOT_LIMIT:
            raise NotAccepted

        try:
            booking = booking_repository.insert(connection, request, ip, now)
        except DayTaken as taken:
            raise NotAccepted from taken

    try:
        email.log_client_confirmation(request)
        email.log_team_notification(request)
    except Exception as error:
        # The booking is stored; let the failure log say which one (P1).
        error.booking_id = booking.id
        raise
    return booking
