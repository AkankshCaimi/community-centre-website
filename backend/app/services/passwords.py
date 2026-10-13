"""Password hashing with Argon2id (docs/specs/F02.md, AU4)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.services.booking_validation import has_control_character

PASSWORD_MIN = 12
PASSWORD_MAX = 1024

_hasher = PasswordHasher()  # Argon2id with the library's recommended costs
_dummy_hash: str | None = None


def new_password_problem(password: str) -> str | None:
    """Why a new password is refused, as a code, or None if it is acceptable (CL2, PR5)."""
    if len(password) < PASSWORD_MIN:
        return "too_short"
    if len(password) > PASSWORD_MAX:
        return "too_long"
    if has_control_character(password):
        return "invalid"
    return None


def _as_bytes(password: str) -> bytes:
    """The password as bytes. Any string converts, unpaired surrogates included."""
    return password.encode("utf-8", "surrogatepass")


def hash_password(password: str) -> str:
    return _hasher.hash(_as_bytes(password))


def password_matches(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, _as_bytes(password))
    except (VerificationError, InvalidHashError):
        return False


def spend_time_on(password: str) -> None:
    """Do the work of a password check against no account at all (AU7).

    Used when the email is unknown, so that the time taken does not show
    whether an email belongs to the admin.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("no account has this password")
    password_matches(_dummy_hash, password)
