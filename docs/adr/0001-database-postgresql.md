# ADR 0001: Database: PostgreSQL vs MySQL vs SQLite

- **Status:** Accepted
- **Date:** 2026-10-13
- **Sources:** `docs/decisions-draft.md`, `docs/requirements.md`, `docs/reviews/R1.md`

## Context

The website stores booking requests submitted through the form and shows them on the admin page (`requirements.md`).

`requirements.md` lists "Scalability to expand to multiple centres" as a non-functional requirement (NFR6).

Decisions in `R1.md` that concern stored data:

- Booking request data is kept for 6 months from the day of submission and then removed automatically (decision 20).
- Deleting a client's data erases the personal details from the database; only the date and state remain (decision 23).
- No backups for now (decision 29).

## Options

| Option | Reasoning recorded |
|---|---|
| PostgreSQL | "for scalability" (`decisions-draft.md`) |
| MySQL | None recorded |
| SQLite | None recorded |

## Decision

PostgreSQL, for scalability.

## Consequences

None recorded yet.
