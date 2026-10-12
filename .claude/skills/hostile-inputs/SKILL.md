---
name: hostile-inputs
description: Attack an endpoint or form like a bad user, before its PR. Use when the user asks to attack, abuse-test or list hostile inputs for an endpoint or form, or runs /hostile-inputs.
---

# Hostile inputs

Attack an endpoint or form like a bad user, before its PR.

## Rules

- List hostile inputs: odd unicode, huge payloads, wrong dates, double submits, missing fields, wrong content type.
- For each one: what does the SPEC say should happen? If the spec is silent, flag it for me. Don't guess.
- Make your own category list first, then I merge with mine.

## How a run goes

1. Find the endpoint or form I named and its spec in `docs/specs/`. If I have not named one, or there is no spec, ask.
2. Write your own list of hostile-input categories for this target. The six above are the minimum, not the whole list. Do this before asking to see mine.
3. Stop and wait for my categories. Merge the two lists.
4. For each category, give concrete inputs for this target and, next to each, what the spec says should happen, quoting the spec line.
5. Where the spec says nothing, write "SPEC SILENT" and what is undecided. Do not fill the gap with what the code does or what seems sensible.
6. End with the list of SPEC SILENT items for me to decide.
