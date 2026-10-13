# Data model

- **Date:** 2026-10-13
- **Sources:** `docs/requirements.md` (FR/NFR numbers below), `docs/reviews/R1.md`, `docs/adr/0001-database-postgresql.md`, author's answers on 2026-10-13
- **Database:** PostgreSQL (ADR 0001)
- **Related:** `application-state-machine.md` (state moves, jobs, and the table of rules that must never break)

Three tables: `bookings`, `admin_users`, `ip_request_log`.

## How the "day" is stored

A booking stores its start and end as UK wall-clock timestamps (`timestamp`, no time zone). The database derives from them the range of calendar days the booking locks:

```
locked_days = [ date of starts_at , date of (ends_at - 1 second) ]   (both ends included)
```

| Booking | `locked_days` |
|---|---|
| 14 Mar 10:00 to 14 Mar 16:00 | 14 Mar |
| 14 Mar 20:00 to 15 Mar 02:00 | 14 Mar and 15 Mar |
| 14 Mar 18:00 to 15 Mar 00:00 | 14 Mar only (ends at midnight, does not run past it) |

`locked_days` is a generated column, so it cannot drift from the start and end times. An exclusion constraint then forbids two non-declined bookings whose `locked_days` overlap. That one constraint gives:

- one non-declined booking per calendar day (FR10);
- a booking past midnight locks both days (FR10);
- the day is freed the moment a booking becomes declined, with no extra code, because declined rows are outside the constraint (FR10, FR12).

## `bookings`

```sql
CREATE TABLE bookings (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    state                       text        NOT NULL DEFAULT 'submitted'
        CONSTRAINT bookings_state_valid
        CHECK (state IN ('submitted', 'contacted', 'accepted', 'declined')),
    state_changed_at            timestamptz NOT NULL DEFAULT now(),

    -- UK wall-clock time of the event
    starts_at                   timestamp   NOT NULL,
    ends_at                     timestamp   NOT NULL,
    locked_days                 daterange   GENERATED ALWAYS AS (
        daterange(starts_at::date, (ends_at - interval '1 second')::date, '[]')
    ) STORED,

    -- client details; all set to NULL when the booking is erased
    client_name                 text,
    client_phone                text,
    client_email                text,
    guest_count                 integer,
    event_details               text,
    terms_accepted_at           timestamptz,
    privacy_notice_accepted_at  timestamptz,

    submitted_at                timestamptz NOT NULL DEFAULT now(),
    erased_at                   timestamptz,

    CONSTRAINT bookings_min_one_hour
        CHECK (ends_at >= starts_at + interval '1 hour'),

    CONSTRAINT bookings_one_per_day
        EXCLUDE USING gist (locked_days WITH &&) WHERE (state <> 'declined'),

    CONSTRAINT bookings_erased_or_complete CHECK (
        (erased_at IS NULL
            AND client_name IS NOT NULL
            AND client_phone IS NOT NULL
            AND client_email IS NOT NULL
            AND guest_count IS NOT NULL
            AND terms_accepted_at IS NOT NULL
            AND privacy_notice_accepted_at IS NOT NULL)
        OR
        (erased_at IS NOT NULL
            AND client_name IS NULL
            AND client_phone IS NULL
            AND client_email IS NULL
            AND guest_count IS NULL
            AND event_details IS NULL
            AND terms_accepted_at IS NULL
            AND privacy_notice_accepted_at IS NULL)
    )
);
```

### Declined is final

```sql
CREATE FUNCTION bookings_declined_is_final() RETURNS trigger AS $$
BEGIN
    IF OLD.state = 'declined' AND NEW.state <> 'declined' THEN
        RAISE EXCEPTION 'booking % is declined and cannot change state', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bookings_declined_is_final
    BEFORE UPDATE OF state ON bookings
    FOR EACH ROW EXECUTE FUNCTION bookings_declined_is_final();
```

The trigger blocks only the state change. A declined booking can still be erased (FR18, NFR7).

### Columns

| Column | Type | Constraint | From |
|---|---|---|---|
| `id` | `bigint` identity | primary key | |
| `state` | `text` | one of the four states; default `submitted` | FR11 |
| `state_changed_at` | `timestamptz` | not null | |
| `starts_at`, `ends_at` | `timestamp` | not null; end at least 1 hour after start | FR5, FR13 |
| `locked_days` | `daterange` | generated; no overlap among non-declined rows | FR10 |
| `client_name`, `client_phone`, `client_email` | `text` | required until erased | FR5 |
| `guest_count` | `integer` | required until erased | FR5 |
| `event_details` | `text` | optional | FR5 |
| `terms_accepted_at`, `privacy_notice_accepted_at` | `timestamptz` | both required until erased (the two ticks) | FR5 |
| `submitted_at` | `timestamptz` | not null; never updated | FR12, NFR7 |
| `erased_at` | `timestamptz` | set when personal details are erased | FR18, NFR7 |

### Erasure

Erasing a booking (by the admin, FR18, or automatically at 6 months, NFR7) sets every client column to `NULL` and sets `erased_at`. What remains is the date (`starts_at`, `ends_at`, `locked_days`) and the `state`. An erased booking that is not declined still locks its day.

### Indexes

| Index | Purpose |
|---|---|
| primary key on `id` | lookups |
| gist index behind `bookings_one_per_day` | the day lock; "is this day free?" |
| `(submitted_at) WHERE state = 'submitted'` | the 48-hour auto-decline job |
| `(submitted_at) WHERE erased_at IS NULL` | the 6-month removal job |
| `(lower(client_email)) WHERE state <> 'declined'` | the 2-slot limit |
| `(client_phone) WHERE state <> 'declined'` | the 2-slot limit |
| `(starts_at)` | admin page sorting by event date |

No indexes are defined for admin search and filter (FR9), because which fields they cover is not decided.

## `admin_users`

```sql
CREATE TABLE admin_users (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email                       text        NOT NULL,
    password_hash               text        NOT NULL,
    password_reset_token_hash   text,
    password_reset_expires_at   timestamptz,
    created_at                  timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX admin_users_email_unique ON admin_users (lower(email));
```

| Column | Type | Constraint | From |
|---|---|---|---|
| `email` | `text` | not null; unique ignoring case | NFR1 |
| `password_hash` | `text` | not null; the password itself is never stored | NFR1 |
| `password_reset_token_hash`, `password_reset_expires_at` | `text`, `timestamptz` | null unless a reset is in progress | NFR1 (reset by email) |

There is no failed-attempt counter or lockout column: no action is taken after repeated wrong passwords (NFR1). The table does not limit itself to one row; "one admin account for now" is not enforced in the database.

## `ip_request_log`

One row per booking request created, used for the limit of 5 requests per network address in a rolling 24 hours (NFR3).

```sql
CREATE TABLE ip_request_log (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ip            inet        NOT NULL,
    requested_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ip_request_log_ip_time ON ip_request_log (ip, requested_at);
```

The check before accepting a submission:

```sql
SELECT count(*) FROM ip_request_log
WHERE ip = :ip AND requested_at > now() - interval '24 hours';
-- refuse the submission if the count is 5 or more
```

The table is deliberately not linked to `bookings`, so a network address is never stored against a named client.

## What the database does not enforce

These rules are enforced in the application; see the rules table in `application-state-machine.md`.

- No past date or time, and at most 6 months in advance (FR13): depends on the current time.
- 5 requests per 24 hours per network address (NFR3) and 2 held slots per phone or email (FR15): counting rules across rows.
- Guest-count bounds and field lengths (FR16): the values are not decided yet. Once they are, they can become `CHECK` constraints.
- Who may change a state (FR11).

## Points for the author

Design choices I made that you have not decided, and gaps I found. None are settled by the requirements.

1. **Ending exactly at midnight** locks only the first day. I read "runs past midnight" as strictly after 00:00.
2. **Wall-clock time.** Start and end are stored as UK local time with no time zone. On the two clock-change days a year, an event across the change is measured an hour out. R1 lists the clock-change days as not discussed.
3. **What is erased.** FR18 says only date and state remain, so `guest_count`, `event_details` and the two tick timestamps are erased along with name, phone and email.
4. **What counts as a request for the 5-a-day limit.** I log a row only when a booking request is actually created. Submissions refused for a taken day, bad input or a failed CAPTCHA do not count.
5. **Keeping network addresses.** Rows are only needed for 24 hours. I propose the hourly job deletes older rows. R1 still lists "whether the network address is stored, for how long, and whether it appears in the privacy notice" as open.
6. **Matching phone and email for the 2-slot limit.** Email is compared ignoring case. Phone is compared as typed, so `07700 900123` and `+447700900123` count as different people. No normalisation rule is decided.
7. **Password reset.** The token columns are needed for "reset by email"; how long a reset link stays valid is not decided.
8. **Multiple centres (NFR6).** There is no `centre_id`. Adding centres later means adding that column and including it in `bookings_one_per_day`.
9. **No history of state changes.** Only the latest `state_changed_at` is kept; who changed a state and when is not recorded.
10. **Admin sessions** (NFR2, ADR 0004) are not in this model; where sessions are stored is not decided.
