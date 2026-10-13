from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BookingRequest:
    """A booking request that has passed validation (spec F01, V1 to V12).

    `starts_at` and `ends_at` are points in time in UTC.
    """

    name: str
    email: str
    phone: str
    guest_count: int
    starts_at: datetime
    ends_at: datetime
    details: str | None
    captcha_token: str


@dataclass(frozen=True)
class Booking:
    """A stored booking, as far as the public API reports it."""

    id: int
    state: str
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class BookingDetails:
    """A stored booking with its client details, as the admin sees it (F02 LI8)."""

    id: int
    state: str
    name: str | None
    email: str | None
    phone: str | None
    guest_count: int | None
    starts_at: datetime
    ends_at: datetime
    details: str | None
    submitted_at: datetime
    auto_declined: bool
    erased: bool
