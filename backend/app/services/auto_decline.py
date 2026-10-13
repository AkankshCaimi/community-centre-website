"""The 48-hour auto-decline job (docs/specs/F03.md)."""

import logging
from datetime import UTC, timedelta

import psycopg

from app import db
from app.repositories import booking_repository, job_repository
from app.services import clock

logger = logging.getLogger("app.jobs")

JOB_NAME = "auto-decline"
OVERDUE_AFTER = timedelta(hours=48)
# How long /health waits for the database before reporting no last run (R7).
HEALTH_GIVES_UP_AFTER_SECONDS = 2


def run() -> int:
    """Decline every overdue booking and record the run. Returns how many were declined.

    The declines and the record of the run are one transaction: if anything
    fails, no booking is changed and the last-run time stays where it was (J8, R5).
    """
    now = clock.now_utc()
    with db.connect() as connection:
        declined = booking_repository.auto_decline_overdue(connection, now - OVERDUE_AFTER, now)
        job_repository.record_run(connection, JOB_NAME, now)
    return declined


def last_run_texts(jobs: tuple[str, ...]) -> dict[str, str | None]:
    """When each job last ran successfully, in UTC, for /health (R6; F04 P8).

    None for a job that has never run, and for every job if the database
    cannot be read (R7). The two are told apart in the log: an unreadable
    database writes one warning there, with the type of the error only (F01 P1).
    """
    try:
        with db.connect(give_up_after=HEALTH_GIVES_UP_AFTER_SECONDS) as connection:
            ran_at = {job: job_repository.last_run(connection, job) for job in jobs}
    except psycopg.Error as error:
        logger.warning("Last auto-decline run could not be read: %s.", type(error).__name__)
        return dict.fromkeys(jobs)
    return {
        job: None if moment is None else moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        for job, moment in ran_at.items()
    }
