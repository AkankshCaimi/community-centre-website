"""Validation of a booking request: rules V1 to V14 of docs/specs/F01.md."""

import calendar
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.booking import BookingRequest

LONDON = ZoneInfo("Europe/London")

NAME_MAX = 100
EMAIL_MAX = 254
PHONE_MAX = 30
DETAILS_MAX = 2000
CAPTCHA_TOKEN_MAX = 2048
GUESTS_MIN = 1
GUESTS_MAX = 250
PHONE_DIGITS_MIN = 7
PHONE_DIGITS_MAX = 15
MIN_DURATION = timedelta(hours=1)
MAX_DURATION = timedelta(hours=12)
MONTHS_AHEAD = 6

TIME_FORMAT = "%Y-%m-%dT%H:%M"
_TIME_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}")
_PHONE_SHAPE = re.compile(r"[0-9+ \-]+")
# Unicode control characters and unpaired surrogates.
_CONTROL_CATEGORIES = ("Cc", "Cs")


def london_to_utc(local: datetime) -> datetime:
    """A Europe/London local time as a point in time in UTC.

    A time in the hour repeated when the clocks go back means its first occurrence.
    """
    return local.replace(tzinfo=LONDON, fold=0).astimezone(UTC)


def utc_to_london_text(moment: datetime) -> str:
    """A point in time as Europe/London local text in the form of V5."""
    return moment.astimezone(LONDON).strftime(TIME_FORMAT)


def exists_in_london(local: datetime) -> bool:
    """False for a local time in the hour skipped when the clocks go forward."""
    return london_to_utc(local).astimezone(LONDON).replace(tzinfo=None) == local


def normalize_phone(phone: str) -> str:
    """The phone as compared for the slot limit (spec L2)."""
    compact = re.sub(r"[ -]", "", phone)
    if compact.startswith("+44"):
        return "0" + compact[3:]
    return compact


def months_after(moment: datetime, months: int) -> datetime:
    """The same day and time `months` later, or the last day of a shorter month (V7)."""
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _has_control_character(text: str, allowed: str = "") -> bool:
    return any(
        unicodedata.category(character) in _CONTROL_CATEGORIES and character not in allowed
        for character in text
    )


def _trimmed_text(value) -> str | None:
    """The trimmed string, or None if the value is not a string or is empty after trimming."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _check_name(value) -> tuple[str | None, str | None]:
    name = _trimmed_text(value)
    if name is None:
        return None, "required"
    if len(name) > NAME_MAX:
        return None, "too_long"
    if _has_control_character(name):
        return None, "invalid"
    return name, None


def _email_is_valid(email: str) -> bool:
    if _has_control_character(email):
        return False
    if any(character.isspace() for character in email):
        return False
    if email.count("@") != 1:
        return False
    local, domain = email.split("@")
    if not local:
        return False
    return "." in domain and not domain.startswith(".") and not domain.endswith(".")


def _check_email(value) -> tuple[str | None, str | None]:
    email = _trimmed_text(value)
    if email is None:
        return None, "required"
    if len(email) > EMAIL_MAX:
        return None, "too_long"
    if not _email_is_valid(email):
        return None, "invalid"
    return email, None


def _check_phone(value) -> tuple[str | None, str | None]:
    phone = _trimmed_text(value)
    if phone is None:
        return None, "required"
    if len(phone) > PHONE_MAX:
        return None, "too_long"
    if not _PHONE_SHAPE.fullmatch(phone):
        return None, "invalid"
    digits = len(re.findall(r"[0-9]", phone))
    if not PHONE_DIGITS_MIN <= digits <= PHONE_DIGITS_MAX:
        return None, "invalid"
    return phone, None


def _check_guest_count(body: dict) -> tuple[int | None, str | None]:
    if "guest_count" not in body:
        return None, "required"
    value = body["guest_count"]
    # bool is a subclass of int, and JSON decimals arrive as float.
    if type(value) is not int:
        return None, "invalid"
    if not GUESTS_MIN <= value <= GUESTS_MAX:
        return None, "out_of_range"
    return value, None


def _check_time(body: dict, field: str) -> tuple[datetime | None, str | None]:
    """The time as a point in UTC, or the code for why it is refused (V5)."""
    if field not in body:
        return None, "required"
    value = body[field]
    if not isinstance(value, str) or not _TIME_SHAPE.fullmatch(value):
        return None, "invalid"
    try:
        local = datetime.strptime(value, TIME_FORMAT)
    except ValueError:
        return None, "invalid"
    if not exists_in_london(local):
        return None, "invalid"
    return london_to_utc(local), None


def _check_details(value) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, "invalid"
    if _has_control_character(value, allowed="\n"):
        return None, "invalid"
    if len(value) > DETAILS_MAX:
        return None, "too_long"
    return value or None, None


def _check_captcha_token(value) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value:
        return None, "required"
    if len(value) > CAPTCHA_TOKEN_MAX:
        return None, "too_long"
    return value, None


def validate(body: dict, now_local: datetime) -> tuple[BookingRequest | None, dict[str, str]]:
    """Check a request body against V1 to V12.

    `now_local` is the current Europe/London local time. Returns the request,
    or the failing fields with their codes.
    """
    errors: dict[str, str] = {}

    def record(field: str, result: tuple):
        value, code = result
        if code is not None:
            errors[field] = code
        return value

    name = record("name", _check_name(body.get("name")))
    email = record("email", _check_email(body.get("email")))
    phone = record("phone", _check_phone(body.get("phone")))
    guest_count = record("guest_count", _check_guest_count(body))
    starts_at = record("starts_at", _check_time(body, "starts_at"))
    ends_at = record("ends_at", _check_time(body, "ends_at"))
    details = record("details", _check_details(body.get("details")))
    captcha_token = record("captcha_token", _check_captcha_token(body.get("captcha_token")))

    if starts_at is not None:
        if starts_at <= london_to_utc(now_local):
            errors["starts_at"] = "in_past"
        elif starts_at > london_to_utc(months_after(now_local, MONTHS_AHEAD)):
            errors["starts_at"] = "too_far_ahead"

    if starts_at is not None and ends_at is not None:
        duration = ends_at - starts_at
        if duration < MIN_DURATION:
            errors["ends_at"] = "duration_too_short"
        elif duration > MAX_DURATION:
            errors["ends_at"] = "duration_too_long"

    for tick in ("terms_accepted", "privacy_notice_accepted"):
        if body.get(tick) is not True:
            errors[tick] = "required"

    if errors:
        return None, errors

    return (
        BookingRequest(
            name=name,
            email=email,
            phone=phone,
            guest_count=guest_count,
            starts_at=starts_at,
            ends_at=ends_at,
            details=details,
            captcha_token=captcha_token,
        ),
        {},
    )
