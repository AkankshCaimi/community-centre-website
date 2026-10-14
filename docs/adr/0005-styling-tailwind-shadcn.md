# ADR 0005: Styling: Tailwind CSS and shadcn/ui vs MUI, Bootstrap and hand-written CSS

- **Status:** Accepted
- **Date:** 2026-10-14
- **Sources:** the author's instructions of 2026-10-14; the reason for rejecting hand-written CSS was given by the author on the same day, after the review of the implementation

## Context

The site is styled by one hand-written stylesheet, `frontend/src/site.css` (rules ST1 to ST9 of `docs/specs/public-pages.md`). The author wants a professional light theme.

## Options considered

| Option | Reasoning recorded |
|---|---|
| Tailwind CSS with shadcn/ui | shadcn components are copied into the repository: owned code, not a black-box dependency. D2C uses Vue; Tailwind transfers. |
| MUI and Bootstrap | rejected — installing and using a library as it ships means the component code is not owned or reviewable in this repository, and both carry a heavier visual signature that fights the minimal brief.. |
| Hand-written CSS | Rejected because a hand-rolled design system is slower to iterate and easier to drift than a utility framework with copied components. |

## Decision

Tailwind CSS with shadcn/ui.

## Consequences

The hand-written rules ST1 to ST9 of `docs/specs/public-pages.md` are retired, and their test `frontend/src/SiteCss.test.js` with them (author's decision, 2026-10-14). The spec is `docs/specs/ui-theme.md`.
