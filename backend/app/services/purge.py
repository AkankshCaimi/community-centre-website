"""The retention purge job (docs/specs/F04.md, P1 to P14)."""

from datetime import datetime, timedelta

from app import db
from app.repositories import booking_repository, job_repository
from app.services import clock
from app.services.booking_validation import LONDON, london_to_utc, months_after

JOB_NAME = "purge"
RETENTION_MONTHS = 6
ADDRESS_KEPT_FOR = timedelta(days=7)
# Six calendar months are never shorter than this, so a booking submitted more
# recently cannot be due. It only narrows which bookings are looked at.
SHORTEST_RETENTION = timedelta(days=180)


def due_at(submitted_at: datetime) -> datetime:
    """The instant a booking's details are due to be erased (P2).

    Six calendar months after it was submitted, worked out on the
    Europe/London clock exactly as the booking form works out "six months
    ahead" (F01 V7), so the two rules cannot drift apart.
    """
    submitted_local = submitted_at.astimezone(LONDON).replace(tzinfo=None)
    return london_to_utc(months_after(submitted_local, RETENTION_MONTHS))


def run() -> tuple[int, int]:
    """Erase every due booking, remove old network addresses, and record the run.

    One transaction: if anything fails, nothing is changed and the last-run
    time stays where it was (P8, P9). Returns how many bookings were erased
    and how many other bookings had their address removed.
    """
    now = clock.now_utc()
    with db.connect() as connection:
        candidates = booking_repository.lock_unerased_submitted_by(
            connection, now - SHORTEST_RETENTION
        )
        due = [booking_id for booking_id, submitted_at in candidates if due_at(submitted_at) <= now]
        # Erase first: an erased booking's address goes with it and is not counted again (P6).
        erased = booking_repository.erase_many(connection, due, now)
        addresses = booking_repository.remove_addresses(connection, now - ADDRESS_KEPT_FOR)
        job_repository.record_run(connection, JOB_NAME, now)
    return erased, addresses
