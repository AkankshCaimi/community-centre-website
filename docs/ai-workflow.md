# How Claude Code was run on this project

A booking form for a community centre is a small problem. Most stacks would give you something usable in a weekend, and several tools would do it in an afternoon. I built it with the full works anyway: written specs, a state machine, database-enforced invariants, mutation-tested suites, review on every change, and a deployment at the end.

A system this size does not need that much process to work. It needs it to stay maintainable, and I wanted the practice. The interesting part of this project was never the product. It was working out what it takes to direct a coding agent through a complete system and keep its output correct at every step, because that is the job I want. This document is about the directing.

## Contents

- [The split](#the-split)
- [Why every commit is mine](#why-every-commit-is-mine)
- [Planning with the agent](#planning-with-the-agent)
- [Keeping tests honest](#keeping-tests-honest)
- [What the agent got wrong](#what-the-agent-got-wrong)
- [One feature, start to finish](#one-feature-start-to-finish)
- [Deployment](#deployment)
- [Where to look](#where-to-look)

## The split

| Area | Claude Code | Me |
|---|---|---|
| Requirements | asked the questions, flagged ambiguities, wrote the approved updates | made every decision, approved every change |
| Specs | drafted from my decisions | reviewed and approved every one |
| Tests | wrote them from the specs | watched them fail, kept them locked |
| Code | wrote all of it | reviewed every diff |
| Commits | none, ever | all of them |
| Deployment | wrote every command | ran each one by hand |

## Why every commit is mine

The agent could have run `git commit` and `git merge` at any point. The agent never committed or merged a PR. It ran fast-forward syncs and the lock's untrack-and-re-add steps under my instruction. The reasons are structural rather than preference.

The git history is the audit trail of who decided what. A commit message such as "requirements v1, cancellation rules decided in review" only means something because a person made those decisions and then made the commit. Let the agent commit, and provenance collapses. The log stops being evidence of judgement and becomes just output.

The second reason is that merging is approval, and nothing in this workflow is allowed to approve its own work. The agent writes code. A separate instance reviews it with fresh context. The merge still belongs to a human, every time. The line held for the whole project: **the agent proposes, I commit.**

## Planning with the agent

Plan mode was the default, set in project settings rather than requested in prompts. That matters. An instruction can be forgotten under context pressure. A setting cannot.

Every feature started the same way: a document I had written first, then an interrogation. The interrogation ran through the `spec-review` skill (`.claude/skills/spec-review/SKILL.md`). Its first run, on the brief and the requirements, is recorded in `docs/reviews/R1.md`.

The unseeded list rule is the important part. Feed the agent your own edge case list and it stops at your list. Make it generate its own first and it goes past it. On hostile inputs for the admin API it produced fifteen categories against my six, including session fixation and reset token flooding, both of which I had missed.

The first requirements interrogation produced thirty-one decisions in one sitting: whether a request locks the whole calendar day, whether declined is final, the forty-eight-hour auto-decline, how deletion blanks personal fields while keeping the date and state. All of them are mine. The agent asked well, and the answers went into the requirements through a plan I approved, with every changed line tied to the decision it came from.

Technical choices ran through the same loop. I wrote a one-line instinct for each decision in a decisions draft, then had the agent format them into four ADRs under a rule that it records my reasoning and invents no reasons of its own. The calls are mine, the formatting is its.

The last piece is the **"Proposed by the implementer"** convention. Anywhere the spec was silent and the agent had to choose something, it logged the choice in a dedicated section instead of burying it in code. I confirmed or rejected each item, and confirmed items moved into the spec with a date. Every feature went through this. The code contains no undocumented decisions, and the specs contain no decisions I did not make.

## Keeping tests honest

An agent that writes code and then writes the tests for that code will produce tests that agree with the code. That is the default behaviour and it verifies nothing. The testing setup exists to break that agreement.

### Four locks

1. **Expected values come from the spec, never from the implementation.** A `CLAUDE.md` rule, repeated in the test-writing prompt with an instruction to cite the acceptance criterion each expected value checks.
2. **Tests are committed before the code exists, with the failing run captured.** From the public pages onward, `docs/reviews/` holds a red log per feature; the red runs of F01 to F04 were not captured in the repository. A test that has never failed is not evidence of anything.
3. **Tracked tests are immutable to the agent, enforced by a `PreToolUse` hook.** Not an instruction, a script. Any edit to a git-tracked test file is blocked, and the block message tells the agent not to retry, to change the implementation instead, and, if the test itself is wrong, to stop and ask me. The lock applies to tracked files only, so drafting stays possible. When a test is genuinely wrong, I edit it by hand, and each of those edits is a commit whose message says so.
4. **Mutation tested on the four feature branches F01 to F04 (91.5 to 91.7 percent); the remaining branches were docs, config and presentational.** Coverage tells you a line ran. Mutation tells you a test fails when the code is wrong.

### What the locks caught

- The reviewer caught a test taking its expected wording from the source file it was testing. The wording now lives in the spec, and the test was rewritten from it.
- A mutation run left two survivors in one function. Direct inspection traced them to a regular expression in a test that accepted any word where the spec required a specific one. The mutation score was not pointing at weak code. It was pointing at a weak test.
- The agent found fifteen of its own draft tests passing for the wrong reason: "nothing was logged" checks that passed because nothing had happened at all. It tightened each one before I ever saw them.

The principle behind all four locks is the same. Every check derives from something the agent did not write, the spec, or something it did not see, a fresh context.

## What the agent got wrong

This is the section that matters most. Each entry records what it did, which layer caught it, and what changed.

### Every visitor shared one rate limit

Requests arriving in IPv4-mapped IPv6 form, the `::ffff:1.2.3.4` notation, were all counted as a single address. Every visitor behind that representation would have shared one allowance of five requests per day. The agent that wrote the rate limit could not see the bug. The fresh-context reviewer found it, because it read the code as a stranger.

### `OPTIONS` answered 200 with HTML

The spec required a JSON `405`. The hostile input pass had listed `OPTIONS` as untested; the reviewer probed it and found the `200`. Fixed with a failing test first.

### Client details could reach the logs

A failed database insert would have written the database error text, which includes the values it failed to insert, straight into the log. Caught in review. The fix logs the error type and booking id, nothing else, and a spec rule now covers untrusted text in logs as a class.

### A focus ring that passed its test and failed users

The ring existed and the test only checked for the presence of a ring class. Measured, the ring sat at 2.1:1 against white, under the 3:1 requirement, and it was the only focus mark on filled buttons. The reviewer computed the contrast. The fix is full-strength rings, plus new contrast tests that measure instead of checking for a class name.

### A proposed loophole, refused

When a styling test conflicted with the new setup, the agent named a way around it, a second stylesheet the test could not see. It said it would not do that without my say, and recommended retiring the test instead.

### The fix ladder

When a bug appears, the fix climbs a ladder:

1. Patch the line.
2. Add the regression test.
3. Fix the spec.
4. Fix the design.
5. Add a rule or a hook.

You stop when the class of error is dead, not when the symptom is gone. Every entry above also appears in `docs/ai-errata.md`, with the layer that caught it and the fix.

## One feature, start to finish

F02, the admin side, is representative. The F01 implementation prompt shows the technique:

```text
Implement F01 so the tests pass, following CLAUDE.md.
You may not modify anything under tests/. If you believe a test is
wrong, stop and explain which acceptance criterion it misreads.
Keep the diff small. When finished, list every file changed and why.
```

### The numbers

| Stage | Result |
|---|---|
| Spec | Drafted by the agent from my rules, with fourteen implementer proposals, each confirmed or amended by me before any test existed. |
| Failing tests | 271 backend and 52 frontend tests committed failing. The red run is recorded in the PR description; the log was not committed. |
| Implementation | To green. No tracked test edited by the agent. |
| Hostile inputs | Fifteen categories generated unseeded. I accepted all fifteen. |
| Review | Seven blocking findings on the first pass. The crashes were fixed with a failing test first; the rest were settled by my decisions. None on the second pass. |
| Mutation | 91.7 percent, 1,364 of 1,487 mutants killed, survivors accounted for in the PR description. |

The full suite stands at **951 backend and 435 frontend tests**. F01 scored 91.5 percent on mutation with the same survivor accounting.

## Deployment

The agent wrote the whole deployment: the container image, the infrastructure files, the command sequence. It ran nothing that created or changed anything in Azure; read-only queries only, while diagnosing. I executed every command by hand and pasted each failure back for diagnosis. Same loop as everything else: the agent as author, me as operator. The system runs on Azure Container Apps with Postgres behind it.

## Where to look

| Where | What it shows |
|---|---|
| `git log` | The commit sequence is the project history, one feature per branch, checkpoints inside each. |
| `docs/reviews/` | A red log per feature from the public pages onward, the failing runs that predate the code. |
| `docs/ai-errata.md` | Every catch, the layer that caught it, and the fix. |
| `docs/specs/` | The specs, including the confirmed implementer proposals with dates. |
| The PR descriptions of F01 to F04 (#7 to #10) | Test counts, mutation scores and rollback notes per feature. |
