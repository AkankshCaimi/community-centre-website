"""When scheduled jobs last ran successfully (docs/specs/F03.md, R5)."""

from datetime import datetime

import psycopg


def record_run(connection: psycopg.Connection, job: str, ran_at: datetime) -> None:
    """Record a successful run. The recorded time never moves backwards (R5)."""
    connection.execute(
        """
        INSERT INTO job_runs (job, last_run_at) VALUES (%s, %s)
        ON CONFLICT (job) DO UPDATE
            SET last_run_at = GREATEST(job_runs.last_run_at, EXCLUDED.last_run_at)
        """,
        (job, ran_at),
    )


def last_run(connection: psycopg.Connection, job: str) -> datetime | None:
    row = connection.execute("SELECT last_run_at FROM job_runs WHERE job = %s", (job,)).fetchone()
    return None if row is None else row[0]
