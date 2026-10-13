# ADR 0004: Authentication: session cookies vs JWT

- **Status:** Accepted
- **Date:** 2026-10-13
- **Sources:** `docs/decisions-draft.md`, `docs/requirements.md`, `docs/reviews/R1.md`

## Context

Only the admin page is behind authentication (`requirements.md`, NFR1). Clients submit the booking form without an account.

Sessions expire after 30 minutes of inactivity (`requirements.md`, NFR2).

Decisions in `R1.md` that concern authentication:

- One admin account for now, linked to an email, used by one person (decision 26).
- Password reset is by email (decision 27).
- Nothing happens after repeated wrong password attempts (decision 28).

## Options

| Option | Reasoning recorded |
|---|---|
| Session cookies | "avoid the risk of tokens being stolen" (`decisions-draft.md`) |
| JWT | Rejected for the risk of tokens being stolen (`decisions-draft.md`) |

## Decision

Session cookies over JWT, to avoid the risk of tokens being stolen.

## Consequences

None recorded yet.
