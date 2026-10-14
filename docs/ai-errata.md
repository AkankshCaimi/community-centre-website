# AI errata

Compiled 2026-10-14 from the development session record.

Each entry records what happened, which layer caught it, and the fix. Entries are in the order they happened.

| # | Entry | Feature | Caught by |
|---|---|---|---|
| 1 | [Every IPv4-mapped visitor shared one rate limit](#1-every-ipv4-mapped-visitor-shared-one-rate-limit) | F01 | Reviewer agent |
| 2 | [`OPTIONS` answered `200` with HTML](#2-options-answered-200-with-html) | F01 | Reviewer agent |
| 3 | [Client details could reach the log through database error text](#3-client-details-could-reach-the-log-through-database-error-text) | F01 | Reviewer agent |
| 4 | [Fifteen draft tests passed for the wrong reason](#4-fifteen-draft-tests-passed-for-the-wrong-reason) | F02 | The agent's own red-run check |
| 5 | [An editor stripped invisible characters from a locked test](#5-an-editor-stripped-invisible-characters-from-a-locked-test) | F03 | Test run after the edit |
| 6 | [A test accepted any word as the error type](#6-a-test-accepted-any-word-as-the-error-type) | F03 | Mutation testing |
| 7 | [The author's paste error in a locked test edit](#7-the-authors-paste-error-in-a-locked-test-edit) | Centre details | Test run after the edit |
| 8 | [A second stylesheet would have got past a test](#8-a-second-stylesheet-would-have-got-past-a-test) | UI theme | The agent, stopping to ask; refused by the author |
| 9 | [The focus ring passed its test and failed contrast](#9-the-focus-ring-passed-its-test-and-failed-contrast) | UI theme | Reviewer agent |
| 10 | [Six false claims in the workflow document](#10-six-false-claims-in-the-workflow-document) | `docs/ai-workflow.md` | Audit against the repository |

## 1. Every IPv4-mapped visitor shared one rate limit

- **What happened:** the rate limit counts every IPv6 address in the same /64 block as one network address. Addresses arriving in IPv4-mapped form (`::ffff:1.2.3.4`) all fall in one such block, so every visitor reaching the application that way would have shared a single allowance of five requests a day.
- **Caught by:** the reviewer agent, reading the code with fresh context. The agent that wrote the rate limit had not seen it.
- **Fix:** test-first. Rule L1 of `docs/specs/F01.md` now says an IPv4 address written in IPv6 form is that IPv4 address and is stored as such; `backend/app/services/booking_service.py` unwraps it before counting.

## 2. `OPTIONS` answered `200` with HTML

- **What happened:** `OPTIONS /api/v1/bookings` returned `200` with `text/html` and an empty body. Rule A10 requires `405` with `{"error": "method_not_allowed"}`, and every response must be JSON. Flask answers `OPTIONS` automatically unless told not to.
- **Caught by:** the reviewer agent, which probed the endpoint. The hostile-input pass before it had listed `HEAD` and `OPTIONS` as covered by A10 but not tested.
- **Fix:** test-first. A10 now names `OPTIONS` and `HEAD` explicitly; the route is declared without the automatic `OPTIONS` answer, and `HEAD` is tested too.

## 3. Client details could reach the log through database error text

- **What happened:** if the database insert failed unexpectedly, the error's message would have been written to the log. Database error messages can quote the values they failed to insert, which are the client's details.
- **Caught by:** the reviewer agent, as a non-blocking finding.
- **Fix:** test-first. Rule P1 of `docs/specs/F01.md` makes this a class: on an unexpected failure the log line holds only the error's type and, if one was stored, the booking's ID; the error's message is never logged, and line breaks in every client-supplied value written to the log are collapsed.

## 4. Fifteen draft tests passed for the wrong reason

- **What happened:** while checking the F02 red run, fifteen of the agent's own draft tests passed with no F02 code in place. Most were "nothing was logged" checks that were true only because nothing had happened at all.
- **Caught by:** the agent's own check of the red run, before checkpoint 2 was committed.
- **Fix:** a status assertion added to each, so all fifteen fail until the feature exists. They were untracked drafts at the time, so no locked test was edited.

## 5. An editor stripped invisible characters from a locked test

- **What happened:** for F03 the author hand-edited `backend/tests/f02/test_admin_booking_state.py` to add `"auto_declined": False` to one expected item. On save, the editor also stripped two invisible line-separator characters (U+2028) from a different test, `test_st7_line_breaks_in_the_name_are_collapsed`. Its final check became `assert "" not in text`, which fails against any code, because an empty string is in every string. The root cause was the agent's: it had written the character into the test file literally, where the escape `"\u2028"` would have survived any editor.
- **Caught by:** the test run after the edit. The agent did not touch the locked file and reported the two lost characters.
- **Fix:** on the author's instruction, the committed file was restored and changed through the hook's untrack-and-re-add route: the one intended line added, and the two characters written as the escape `"\u2028"`.

## 6. A test accepted any word as the error type

- **What happened:** two mutants of `last_run_texts` in `backend/app/services/auto_decline.py` survived. Both make the `/health` warning name `None` or `NoneType` instead of the error's real type. They survived because the F03 R7 test matched the error type with `\w+`, which accepts any word.
- **Caught by:** mutation testing, followed by running each mutant against the tests directly. The score was pointing at a weak test, not weak code.
- **Fix:** a new test in `backend/tests/f03/test_health_stale_and_unreadable.py` requires the exact line "Last auto-decline run could not be read: UndefinedTable." It kills both mutants. The original locked test is unchanged.

## 7. The author's paste error in a locked test edit

- **What happened:** when the fictional centre details were changed, the author hand-edited two locked test files. Line 141 of `frontend/src/PublicPages.test.jsx` (rule L3) received the list meant for the other file: it expected the centre's name in the footer, which shows the address, phone and email, and it dropped "Open 24 hours", so that check would have been lost.
- **Caught by:** the test run after the edit: 7 failures in the footer tests. The agent did not touch the locked file and gave the exact replacement line.
- **Fix:** the author re-edited line 141 by hand with the address, phone, email and "Open 24 hours". All 382 frontend tests then passed, and the footer check still includes "Open 24 hours".

## 8. A second stylesheet would have got past a test

- **What happened:** moving to Tailwind conflicted with the locked `SiteCss.test.js`, which failed on any `@import` in `site.css` and expected the old colour names. The test read only `site.css`, so a second stylesheet imported from `main.jsx` would have passed it while breaking the rule it was written for.
- **Caught by:** the agent, which named the loophole and stopped to ask instead of using it. The author refused it permanently.
- **Fix:** `SiteCss.test.js` was retired by the author on the record, together with rules ST1 to ST9. Rule T5 of `docs/specs/ui-theme.md` says exactly one stylesheet loads and that a test is never routed around with a second stylesheet; `frontend/src/UiTheme.test.jsx` enforces it.

## 9. The focus ring passed its test and failed contrast

- **What happened:** the keyboard focus ring was drawn at 50% strength, about 2.1:1 against white and against the shaded dialog background, under the 3:1 that WCAG asks for. Filled buttons have no border, so the faint ring was their only focus mark. The test only checked that a ring class was present.
- **Caught by:** the reviewer agent, which computed the contrast.
- **Fix:** a full-strength 2px ring with a 2px offset on every focusable element, through one base rule. Rules T6 to T8 of `docs/specs/ui-theme.md` and 16 tests in `frontend/src/ThemeContrast.test.js` measure contrast instead of checking for a class name; 9 of them failed before the fix (`docs/reviews/theme-contrast-red.log`). The reviewer's re-check put the weakest pair at 4.72:1.

## 10. Six false claims in the workflow document

- **What happened:** the first version of `docs/ai-workflow.md` made six claims the record did not support: a red log per feature, including `docs/reviews/F02-red.log`, which was never committed; `docs/ai-errata.md`, which did not exist; survivors and test counts explained in PR descriptions, all of which were empty; five blocking F02 review findings, each fixed test-first, where the first pass had seven and not all were fixed with tests; the `OPTIONS` bug credited to the hostile-input pass instead of the reviewer; and requirements and a hook message described in a way the record contradicts. Two numbers were also wrong: the F02 mutation count (it was F04's) and the frontend test total.
- **Caught by:** an audit of every number, path and claim against the repository, the git history, the GitHub pull requests and the session record, before the document shipped.
- **Fix:** the claims were corrected in the document, this file was compiled, and PR descriptions for F01 to F04 were written for the author to add.
