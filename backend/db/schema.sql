-- Schema for docs/design/data-model.md. Applied by `flask --app app init-db`.
-- Safe to run again: nothing here changes a table that already exists.

CREATE TABLE IF NOT EXISTS bookings (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    state                       text        NOT NULL DEFAULT 'submitted'
        CONSTRAINT bookings_state_valid
        CHECK (state IN ('submitted', 'contacted', 'accepted', 'declined')),
    state_changed_at            timestamptz NOT NULL DEFAULT now(),

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

CREATE OR REPLACE FUNCTION bookings_declined_is_final() RETURNS trigger AS $$
BEGIN
    IF OLD.state = 'declined' AND NEW.state <> 'declined' THEN
        RAISE EXCEPTION 'booking % is declined and cannot change state', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER bookings_declined_is_final
    BEFORE UPDATE OF state ON bookings
    FOR EACH ROW EXECUTE FUNCTION bookings_declined_is_final();

CREATE INDEX IF NOT EXISTS bookings_submitted_pending
    ON bookings (submitted_at) WHERE state = 'submitted';
CREATE INDEX IF NOT EXISTS bookings_submitted_not_erased
    ON bookings (submitted_at) WHERE erased_at IS NULL;
CREATE INDEX IF NOT EXISTS bookings_email_active
    ON bookings (lower(client_email)) WHERE state <> 'declined';
CREATE INDEX IF NOT EXISTS bookings_phone_normalized_active
    ON bookings (client_phone_normalized) WHERE state <> 'declined';
CREATE INDEX IF NOT EXISTS bookings_ip_submitted
    ON bookings (client_ip, submitted_at);
CREATE INDEX IF NOT EXISTS bookings_starts_at
    ON bookings (starts_at);
