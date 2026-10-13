"""F03 rules R5 to R7: /health with a last-run time that has gone stale, and
the warning that names the error when the time cannot be read.

Every expected value comes from docs/specs/F03.md; each test names the rule it checks.
"""

import logging
from datetime import timedelta

from f03_helpers import NOW, run_job

UNREACHABLE = "postgresql://nobody:secret-word@127.0.0.1:1/nowhere"


def health(app):
    response = app.test_client().get("/health")
    assert response.status_code == 200
    return response.get_json()


def test_r5_r6_health_keeps_showing_a_stale_last_run(app, clock):
    """R5: the last-run time goes stale when the job is failing or not being run."""
    assert run_job(app).exit_code == 0  # at 09:00 in London on 10 March, winter

    clock.now = NOW + timedelta(days=30)  # nothing has run the job for 30 days
    assert health(app)["auto_decline_last_run"] == "2026-03-10T09:00:00Z"

    reachable = app.config["DATABASE_URL"]
    app.config["DATABASE_URL"] = UNREACHABLE
    assert run_job(app).exit_code == 1  # and now a run fails: it records nothing
    app.config["DATABASE_URL"] = reachable

    assert health(app) == {
        "status": "ok",
        "auto_decline_last_run": "2026-03-10T09:00:00Z",
        "purge_last_run": None,
    }


def test_r7_warning_names_the_type_of_the_error(app, db, caplog):
    """R7: "Last auto-decline run could not be read: <type of the error>."."""
    db.execute("DROP TABLE job_runs")  # reading it now fails with UndefinedTable
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="app.jobs"):
        health(app)

    lines = [record.getMessage() for record in caplog.records if record.name == "app.jobs"]
    assert lines == ["Last auto-decline run could not be read: UndefinedTable."]
