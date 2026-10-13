"""The retention purge job (docs/specs/F04.md, P1 to P14)."""

from datetime import timedelta

from app import db
from app.repositories import booking_repository, job_repository
from app.services import clock

JOB_NAME = "purge"
ADDRESS_KEPT_FOR = timedelta(days=7)


def run() -> tuple[int, int]:
    """Erase every due booking, remove old network addresses, and record the run.

    One transaction: if anything fails, nothing is changed and the last-run
    time stays where it was (P8, P9). Returns how many bookings were erased
    and how many other bookings had their address removed.
    """
    now = clock.now_utc()
    with db.connect() as connection:
        # Erase first: an erased booking's address goes with it and is not counted again (P6).
        erased = booking_repository.erase_due(connection, now)
        addresses = booking_repository.remove_addresses(connection, now - ADDRESS_KEPT_FOR)
        job_repository.record_run(connection, JOB_NAME, now)
    return erased, addresses
