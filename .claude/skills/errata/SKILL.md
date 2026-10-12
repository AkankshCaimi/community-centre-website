---
name: errata
description: Log an AI mistake we caught, when output was confidently wrong. Use when the user says the AI got something wrong and wants it recorded, or runs /errata.
---

# Errata

Log an AI mistake we caught, when output was confidently wrong.

## Rules

- Add to `docs/ai-errata.md`: date, what was generated, what was wrong, how we caught it, error type (hallucinated API / hidden error / bad test / misread requirement / security gap).
- Then ask: has this TYPE happened before? If yes, propose a new `CLAUDE.md` rule or hook to stop the class. Show me before applying.

## How a run goes

1. Collect the five fields from the conversation. Ask me for any you cannot fill; do not invent them.
2. Pick exactly one error type from the list above. If none fits, say so and ask me.
3. Append the entry to `docs/ai-errata.md`, newest last. Create the file with a `# AI errata` heading if it does not exist. Never change or remove earlier entries.
4. Read the earlier entries and count those with the same error type. Tell me the count and which entries they are.
5. If there is at least one earlier entry of that type, propose one `CLAUDE.md` rule or one hook that would stop the whole class, not only this instance. Show me the exact text or script.
6. Wait. Change `CLAUDE.md`, `.claude/settings.json` or `.claude/hooks/` only after I say yes.

## Entry format

```markdown
## YYYY-MM-DD: <short title>

- **Generated:** what the AI produced
- **Wrong:** what was wrong with it
- **Caught by:** how we caught it
- **Type:** hallucinated API | hidden error | bad test | misread requirement | security gap
```
