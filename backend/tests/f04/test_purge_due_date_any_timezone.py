"""F04 rule P2: the six-month boundary, pinned on a machine in any time zone.

Every expected value comes from docs/specs/F04.md, rule P2: a booking is due
six calendar months after it was submitted, at the same Europe/London time of
day; at exactly that moment it is due, before it it is not.

The other P2 tests give the same answers only when the machine running them
keeps London time or the booking was submitted in winter. These set the
machine's own time zone far from London, and use a summer submission, so the
rule cannot lean on the machine's clock.
"""

import time
from datetime import datetime, timedelta

import pytest
from f04_helpers import is_erased, purge_counts, run_purge

# Submitted at 09:00 London time on 15 June 2026, in summer time.
SUBMITTED = datetime(2026, 6, 15, 9, 0)
# Six calendar months on, at the same London time of day, in winter time.
DUE = datetime(2026, 12, 15, 9, 0)


@pytest.fixture(params=["Pacific/Auckland", "America/Los_Angeles", "UTC"])
def machine_elsewhere(request, monkeypatch):
    """Run the test as if the machine's own clock were set to another time zone."""
    monkeypatch.setenv("TZ", request.param)
    time.tzset()
    yield request.param
    monkeypatch.undo()
    time.tzset()


@pytest.mark.parametrize(
    "when, due",
    [
        pytest.param(DUE - timedelta(days=1), False, id="six-months-minus-a-day"),
        pytest.param(DUE - timedelta(hours=1), False, id="six-months-minus-an-hour"),
        pytest.param(DUE - timedelta(seconds=1), False, id="six-months-minus-a-second"),
        pytest.param(DUE, True, id="exactly-six-months"),
        pytest.param(DUE + timedelta(seconds=1), True, id="six-months-plus-a-second"),
    ],
)
def test_p2_six_month_boundary_holds_whatever_the_machine_time_zone(
    app, make_booking, clock, db, machine_elsewhere, when, due
):
    clock.now = SUBMITTED
    booking_id = make_booking(1, 1, starts_at="2026-07-10T10:00", ends_at="2026-07-10T14:00")
    clock.now = when

    result = run_purge(app)

    assert result.exit_code == 0
    assert purge_counts(result.output)[0] == (1 if due else 0)
    assert is_erased(db, booking_id) is due
