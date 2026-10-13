"""F04 rules the branch review found untested or weakly tested: P2 in the hour
repeated when the clocks go back, and P5.

Every expected value comes from docs/specs/F04.md; each test names the rule it checks.
"""

from datetime import UTC, datetime, timedelta

from f04_helpers import NOW, SEVEN_DAYS, SIX_MONTHS_ON, is_erased, purge_counts, run_purge


def test_p2_due_moment_in_the_repeated_hour_is_its_first_occurrence(app, make_booking, clock, db):
    # Submitted at 01:30 London time on 25 April 2026 (00:30 UTC, summer time).
    # Six months on is 01:30 on 25 October, which happens twice that night; the
    # booking is due at the first, which is 00:30 UTC.
    clock.now = datetime(2026, 4, 25, 0, 30, tzinfo=UTC)
    booking_id = make_booking(1, 1, starts_at="2026-05-10T10:00", ends_at="2026-05-10T14:00")

    clock.now = datetime(2026, 10, 25, 0, 29, 59, tzinfo=UTC)
    assert purge_counts(run_purge(app).output)[0] == 0

    clock.now = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert purge_counts(run_purge(app).output)[0] == 1
    assert is_erased(db, booking_id) is True


def test_p2_booking_submitted_in_the_repeated_hour_is_due_six_months_from_that_instant(
    app, make_booking, clock, db
):
    # Submitted at 01:30 London time, second time round, on 25 October 2026
    # (01:30 UTC). Six months on is 01:30 on 25 April 2027, in summer time: 00:30 UTC.
    clock.now = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
    booking_id = make_booking(1, 1, starts_at="2026-11-10T10:00", ends_at="2026-11-10T14:00")

    clock.now = datetime(2027, 4, 25, 0, 29, 59, tzinfo=UTC)
    assert purge_counts(run_purge(app).output)[0] == 0

    clock.now = datetime(2027, 4, 25, 0, 30, tzinfo=UTC)
    assert purge_counts(run_purge(app).output)[0] == 1
    assert is_erased(db, booking_id) is True


def test_p5_booking_that_is_not_due_keeps_every_detail(app, make_booking, clock, db):
    make_booking(1, 1)
    clock.now = NOW + timedelta(days=1)
    newer = make_booking(2, 2)
    everything_but_the_address = (
        "SELECT id, state, auto_declined, starts_at, ends_at, locked_days, submitted_at,"
        " state_changed_at, client_name, client_email, client_phone, client_phone_normalized,"
        " guest_count, event_details, terms_accepted_at, privacy_notice_accepted_at, erased_at"
        " FROM bookings WHERE id = %s"
    )
    before = db.execute(everything_but_the_address, (newer,)).fetchone()
    clock.now = SIX_MONTHS_ON  # the first is due; the second is a day short

    assert purge_counts(run_purge(app).output)[0] == 1

    assert db.execute(everything_but_the_address, (newer,)).fetchone() == before
    assert None not in before[8:11]  # it still has its name, email and phone


def test_p5_booking_past_7_days_keeps_everything_but_its_address(app, make_booking, clock, db):
    booking_id = make_booking(1, 1)
    everything = "SELECT * FROM bookings WHERE id = %s"
    before = db.execute(everything, (booking_id,)).fetchone()
    names = [column.name for column in db.execute(everything, (booking_id,)).description]
    clock.now = NOW + SEVEN_DAYS

    assert purge_counts(run_purge(app).output) == (0, 1)

    after = db.execute(everything, (booking_id,)).fetchone()
    changed = [name for name, old, new in zip(names, before, after, strict=True) if old != new]
    assert changed == ["client_ip"]
