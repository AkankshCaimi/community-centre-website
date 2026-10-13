# Data model

- **Date:** 2026-10-13
- **Sources:** `docs/requirements.md` (FR/NFR numbers below), `docs/reviews/R1.md`, `docs/adr/0001-database-postgresql.md`, author's answers on 2026-10-13, `docs/specs/F01.md`
- **Database:** PostgreSQL (ADR 0001)
- **Related:** `application-state-machine.md` (state moves, jobs, and the table of rules that must never break)

Four tables: `bookings`, `admin_users`, `admin_sessions` (added with F02) and `job_runs` (added with F03). An earlier version had a third, `ip_request_log`; the author decided on 2026-10-13 (F01) to store the network address on the booking instead.

## How the "day" is stored

A booking stores its start and end as points in time in UTC (`timestamptz`). The database converts them to Europe/London local time and derives the range of calendar days the booking locks:

```
locked_days = [ London date of starts_at , London date of (ends_at - 1 second) ]   (both ends included)
```

| Booking (London local time) | `locked_days` |
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
    -- set by the auto-decline job only (F03)
    auto_declined               boolean     NOT NULL DEFAULT false
        CONSTRAINT bookings_auto_declined_is_declined
        CHECK (NOT auto_declined OR state = 'declined'),

    -- start and end of the event, stored in UTC
    starts_at                   timestamptz NOT NULL,
    ends_at                     timestamptz NOT NULL,
    -- the Europe/London calendar days the event covers
    locked_days                 daterange   GENERATED ALWAYS AS (
        daterange(
            (starts_at AT TIME ZONE 'Europe/London')::date,
            ((ends_at AT TIME ZONE 'Europe/London') - interval '1 second')::date,
            '[]'
        )
    ) STORED,

    -- client details; all set to NULL when the booking is erased
    client_name                 text,
    client_phone                text,
    client_email                text,
    client_phone_normalized     text        GENERATED ALWAYS AS (
        regexp_replace(regexp_replace(client_phone, '[ -]', '', 'g'), '^\+44', '0')
    ) STORED,
    client_ip                   inet,
    guest_count                 integer,
    event_details               text,
    terms_accepted_at           timestamptz,
    privacy_notice_accepted_at  timestamptz,

    submitted_at                timestamptz NOT NULL DEFAULT now(),
    erased_at                   timestamptz,

    CONSTRAINT bookings_min_one_hour
        CHECK (ends_at >= starts_at + interval '1 hour'),

    CONSTRAINT bookings_max_twelve_hours
        CHECK (ends_at <= starts_at + interval '12 hours'),

    CONSTRAINT bookings_guest_count_range
        CHECK (guest_count BETWEEN 1 AND 250),

    CONSTRAINT bookings_text_lengths CHECK (
        char_length(client_name) BETWEEN 1 AND 100
        AND char_length(client_email) <= 254
        AND char_length(client_phone) <= 30
        AND char_length(event_details) <= 2000
    ),

    CONSTRAINT bookings_one_per_day
        EXCLUDE USING gist (locked_days WITH &&) WHERE (state <> 'declined'),

    CONSTRAINT bookings_erased_or_complete CHECK (
        (erased_at IS NULL
            AND client_name IS NOT NULL
            AND client_phone IS NOT NULL
            AND client_email IS NOT NULL
            AND client_ip IS NOT NULL
            AND guest_count IS NOT NULL
            AND terms_accepted_at IS NOT NULL
            AND privacy_notice_accepted_at IS NOT NULL)
        OR
        (erased_at IS NOT NULL
            AND client_name IS NULL
            AND client_phone IS NULL
            AND client_email IS NULL
            AND client_ip IS NULL
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
| `state_changed_at` | `timestamptz` | not null; when the booking entered its current state | F02 ST6 |
| `auto_declined` | `boolean` | not null, default false; true only for a booking the auto-decline job declined, and only when the state is `declined` | F03 M1 |
| `starts_at`, `ends_at` | `timestamptz` | not null; stored in UTC; end at least 1 hour and at most 12 hours of elapsed time after start | FR5, FR13, F01 S1, V8 and V9 |
| `locked_days` | `daterange` | generated from the Europe/London local dates; no overlap among non-declined rows | FR10, F01 L3 |
| `client_name`, `client_phone`, `client_email` | `text` | required until erased; at most 100, 30 and 254 characters | FR5, F01 V1 to V3 |
| `client_phone_normalized` | `text` | generated: the phone with spaces and dashes removed, then a leading `+44` replaced by `0` | F01 L2 |
| `client_ip` | `inet` | required until erased | NFR3, F01 L1 and S3 |
| `guest_count` | `integer` | required until erased; 1 to 250 | FR5, F01 V4 |
| `event_details` | `text` | optional; at most 2000 characters | FR5, F01 V10 |
| `terms_accepted_at`, `privacy_notice_accepted_at` | `timestamptz` | both required until erased (the two ticks) | FR5 |
| `submitted_at` | `timestamptz` | not null; never updated | FR12, NFR7 |
| `erased_at` | `timestamptz` | set when personal details are erased | FR18, NFR7 |

### Erasure

Erasing a booking (by the admin, FR18, or automatically at 6 months, NFR7) sets every client column, including `client_ip`, to `NULL` and sets `erased_at`. What remains is the date (`starts_at`, `ends_at`, `locked_days`) and the `state`. An erased booking that is not declined still locks its day.

### Indexes

| Index | Purpose |
|---|---|
| primary key on `id` | lookups |
| gist index behind `bookings_one_per_day` | the day lock; "is this day free?" |
| `(submitted_at) WHERE state = 'submitted'` | the 48-hour auto-decline job (F03 J1) |
| `(submitted_at) WHERE erased_at IS NULL` | the 6-month removal job |
| `(lower(client_email)) WHERE state <> 'declined'` | the 2-slot limit |
| `(client_phone_normalized) WHERE state <> 'declined'` | the 2-slot limit |
| `(client_ip, submitted_at)` | the limit of 5 requests per network address in 24 hours |
| `(starts_at)` | admin page sorting by event date |

No indexes are defined for admin search and filter (FR9), because which fields they cover is not decided.

## `admin_users`

```sql
CREATE TABLE admin_users (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email                       text        NOT NULL,
    password_hash               text        NOT NULL,
    password_reset_token_hash   text,
    password_reset_created_at   timestamptz,
    created_at                  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT admin_users_reset_token_complete CHECK (
        (password_reset_token_hash IS NULL) = (password_reset_created_at IS NULL)
    )
);

CREATE UNIQUE INDEX admin_users_email_unique ON admin_users (lower(email));
```

| Column | Type | Constraint | From |
|---|---|---|---|
| `email` | `text` | not null; unique ignoring case | NFR1, F02 AU1 |
| `password_hash` | `text` | not null; an Argon2id hash, the password itself is never stored | NFR1, F02 AU4 |
| `password_reset_token_hash` | `text` | SHA-256 hash of the reset token; null unless a reset is in progress | F02 PR2 |
| `password_reset_created_at` | `timestamptz` | when the token was created; set and cleared together with the hash | F02 PR4 |

There is no failed-attempt counter or lockout column: no action is taken after repeated wrong passwords (NFR1, F02 AU3). The table does not limit itself to one row; "one admin account" is enforced by the `create-admin` command (F02 CL4), not by the database.

## `admin_sessions`

One row per login session (F02 SE1 to SE7).

```sql
CREATE TABLE admin_sessions (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admin_user_id  bigint      NOT NULL REFERENCES admin_users (id) ON DELETE CASCADE,
    token_hash     text        NOT NULL,
    created_at     timestamptz NOT NULL,
    last_used_at   timestamptz NOT NULL
);

CREATE UNIQUE INDEX admin_sessions_token_hash_unique ON admin_sessions (token_hash);
```

| Column | Type | Constraint | From |
|---|---|---|---|
| `admin_user_id` | `bigint` | not null; the account the session belongs to | F02 SE6, PR3 |
| `token_hash` | `text` | not null, unique; SHA-256 hash of the cookie value, never the value | F02 SE2 |
| `last_used_at` | `timestamptz` | not null; a session is valid for less than 30 minutes after this | F02 SE3 |

Logging out, and resetting the password, delete the rows (F02 SE5, PR3). Expired rows are simply never accepted again; nothing in F02 removes them.

## `job_runs`

When each scheduled job last ran successfully (F03 R5, R6). One row per job.

```sql
CREATE TABLE job_runs (
    job          text        PRIMARY KEY,
    last_run_at  timestamptz NOT NULL
);
```

The auto-decline job writes its row, named `auto-decline`, in the same transaction as its declines, so the time is recorded only if the run succeeded.

## The 5-requests limit (NFR3)

There is no separate log table. The check before accepting a submission counts bookings created from the same network address:

```sql
SELECT count(*) FROM bookings
WHERE client_ip <<= :network AND submitted_at > :now - interval '24 hours';
-- refuse the submission if the count is 5 or more
```

`:network` is the address itself for IPv4 and its /64 block for IPv6 (F01 L1). Bookings in every state count. The network address is now stored against a named client; it is erased with the other client details.

## What the database does not enforce

These rules are enforced in the application; see the rules table in `application-state-machine.md`.

- No past date or time, and at most 6 months in advance (FR13): depends on the current time.
- 5 requests per 24 hours per network address (NFR3) and 2 held slots per phone or email (FR15): counting rules across rows.
- Who may change a state (FR11).

## Points for the author

Design choices I made that you have not decided, and gaps I found. None are settled by the requirements.

1. **Ending exactly at midnight** locks only the first day. I read "runs past midnight" as strictly after 00:00.
2. **Clock changes.** Decided by the author on 2026-10-13 (F01): start and end are stored in UTC, so a booking's length is elapsed time. A local time skipped when the clocks go forward is refused, and a time in the repeated hour means its first occurrence (F01 V5).
3. **What is erased.** FR18 says only date and state remain, so `guest_count`, `event_details` and the two tick timestamps are erased along with name, phone and email.
4. **What counts as a request for the 5-a-day limit.** Only bookings that are actually created count. Submissions refused for a taken day, bad input or a failed CAPTCHA do not.
5. **Keeping network addresses.** The address stays on the booking until the booking is erased, which is up to 6 months, although the limit only needs it for 24 hours. Whether it appears in the privacy notice is still open in R1.
6. **Matching phone and email for the 2-slot limit.** Email is compared ignoring case. Phone is compared after removing spaces and dashes and replacing a leading `+44` with `0` (decided 2026-10-13, F01 L2), so `07700 900123`, `07700-900-123` and `+44 7700 900123` are the same person.
7. **Password reset.** Decided with F02: the token is valid for 30 minutes and only its hash is stored.
8. **Multiple centres (NFR6).** There is no `centre_id`. Adding centres later means adding that column and including it in `bookings_one_per_day`.
9. **No history of state changes.** Only the latest `state_changed_at` is kept; who changed a state and when is not recorded.
10. **Admin sessions.** Decided with F02: sessions are rows in `admin_sessions`, and the cookie holds only a random value whose hash is stored. Rows of expired sessions are never cleaned up.
