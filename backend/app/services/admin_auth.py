"""Admin login, sessions and password reset (docs/specs/F02.md: AU, SE, PR)."""

import hashlib
import logging
import secrets
from datetime import timedelta

from app import db
from app.repositories import admin_repository
from app.services import clock, email, passwords
from app.services.passwords import PASSWORD_MAX

logger = logging.getLogger("app.auth")

SESSION_IDLE_LIMIT = timedelta(minutes=30)
RESET_TOKEN_LIFETIME = timedelta(minutes=30)
TOKEN_BYTES = 32
EMAIL_MAX = 254
TOKEN_MAX = 1024


class ValidationFailed(Exception):
    def __init__(self, fields: dict[str, str]):
        super().__init__()
        self.fields = fields


class InvalidCredentials(Exception):
    pass


class InvalidToken(Exception):
    pass


def _hash(secret: str) -> str:
    """The form in which session values and reset tokens are stored (SE2, PR2)."""
    # "surrogatepass" lets any string be hashed; a malformed one simply matches nothing.
    return hashlib.sha256(secret.encode("utf-8", "surrogatepass")).hexdigest()


def _storable_email(email: str) -> str | None:
    """The trimmed email, or None if it is text the database cannot hold."""
    email = email.strip()
    try:
        email.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if "\x00" in email:
        return None
    return email


def _find_admin(connection, email: str):
    """The admin with this email, or None. Text the database cannot hold matches no one."""
    email = _storable_email(email)
    if email is None:
        return None
    return admin_repository.find_admin_by_email(connection, email)


def _text_field(body: dict, name: str, maximum: int) -> tuple[str | None, str | None]:
    value = body.get(name)
    if not isinstance(value, str) or not value:
        return None, "required"
    if len(value) > maximum:
        return None, "too_long"
    return value, None


def _new_password_field(body: dict) -> tuple[str | None, str | None]:
    password = body.get("password")
    if not isinstance(password, str) or not password:
        return None, "required"
    code = passwords.new_password_problem(password)
    return (password, None) if code is None else (None, code)


def _checked(fields: dict[str, tuple]) -> dict[str, str]:
    """The values of the fields, or ValidationFailed naming every refused one."""
    errors = {name: code for name, (_, code) in fields.items() if code is not None}
    if errors:
        raise ValidationFailed(errors)
    return {name: value for name, (value, _) in fields.items()}


def log_in(body: dict) -> tuple[str, str]:
    """Check an email and password. Returns the admin's email and a new session value."""
    values = _checked(
        {
            "email": _text_field(body, "email", EMAIL_MAX),
            "password": _text_field(body, "password", PASSWORD_MAX),
        }
    )

    with db.connect() as connection:
        admin = _find_admin(connection, values["email"])
        if admin is None:
            passwords.spend_time_on(values["password"])
            matches = False
        else:
            matches = passwords.password_matches(admin.password_hash, values["password"])

        if not matches:
            logger.info("Admin login failed.")
            raise InvalidCredentials

        session_value = secrets.token_urlsafe(TOKEN_BYTES)
        admin_repository.insert_session(connection, admin.id, _hash(session_value), clock.now_utc())

    logger.info("Admin login succeeded.")
    return admin.email, session_value


def session_email(session_value: str | None) -> str | None:
    """The admin's email if the session is valid, marking it as used now (SE3)."""
    if not session_value:
        return None
    now = clock.now_utc()
    with db.connect() as connection:
        return admin_repository.use_session(
            connection, _hash(session_value), now - SESSION_IDLE_LIMIT, now
        )


def log_out(session_value: str) -> None:
    with db.connect() as connection:
        admin_repository.delete_session(connection, _hash(session_value))


def request_password_reset(body: dict) -> None:
    """Create a reset token and log the email, if the email is the admin's (PR1, PR2).

    The same work is done whether or not it is (PR8): a token is always made
    and hashed, the same statement always runs, and one log line is always written.
    """
    values = _checked({"email": _text_field(body, "email", EMAIL_MAX)})

    token = secrets.token_urlsafe(TOKEN_BYTES)
    # An empty email matches no account; it stands in for text the database cannot hold.
    wanted = _storable_email(values["email"]) or ""
    with db.connect() as connection:
        admin_email = admin_repository.issue_reset_token(
            connection, wanted, _hash(token), clock.now_utc()
        )

    if admin_email is None:
        logger.info("Password reset requested for an address that is not the admin's.")
    else:
        email.log_password_reset(admin_email, token)


def confirm_password_reset(body: dict) -> None:
    """Set a new password with a valid reset token (PR3 to PR5)."""
    values = _checked(
        {
            "token": _text_field(body, "token", TOKEN_MAX),
            "password": _new_password_field(body),
        }
    )

    with db.connect() as connection:
        admin = admin_repository.find_admin_by_reset_token(
            connection, _hash(values["token"]), clock.now_utc() - RESET_TOKEN_LIFETIME
        )
        if admin is None:
            raise InvalidToken
        admin_repository.replace_password(
            connection, admin.id, passwords.hash_password(values["password"])
        )
        admin_repository.delete_sessions_of(connection, admin.id)
