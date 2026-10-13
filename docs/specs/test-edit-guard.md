# Spec: test edit guard

Mechanically enforces rule 4 of `CLAUDE.md`: never edit any existing test after code is written.

A test file is locked once git tracks it. An untracked test file stays editable, so a test can be drafted and corrected freely until it is added to git.

## Mechanism

A Claude Code `PreToolUse` hook, registered in `.claude/settings.json` for the tools `Edit`, `Write`, `MultiEdit` and `NotebookEdit`. It runs the executable shell script `.claude/hooks/protect-existing-tests.sh`, which receives the tool call as JSON on stdin.

## Behaviour

| # | Tool call target | Exit code | stderr |
|---|---|---|---|
| 1 | test file that git tracks | 2 (blocked) | message containing `BLOCKED` and the file path |
| 2 | test file that git does not track | 0 (allowed) | empty |
| 3 | file that is not a test file | 0 (allowed) | empty |
| 4 | input that cannot be parsed, or no file path in it | 2 (blocked) | message containing `BLOCKED` |

Exit code 2 makes Claude Code cancel the tool call and pass stderr back to the agent. The message must tell the agent why the call was blocked and what it may do instead: change the implementation, or create a new test file.

## Definitions

**Target path**: `tool_input.file_path`, or `tool_input.notebook_path` if the former is absent. A relative path is resolved against the `cwd` field of the input.

**Test file**: a target path that is not under a `.claude/` directory and matches at least one of:

- basename `test_*.py`, `*_test.py` or `conftest.py`
- basename `test_*.sh`
- basename `*.test.<ext>` or `*.spec.<ext>` where `<ext>` is one of `js`, `jsx`, `ts`, `tsx`, `mjs`, `cjs`
- any directory in the path is named `tests`, `test`, `__tests__` or `e2e`

Feature spec documents such as `docs/specs/foo.spec.md` are therefore not test files.

**Tracked by git**: the target path is in the index of the git repository that contains it. Consequences:

| Situation | Tracked? | Result |
|---|---|---|
| committed | yes | blocked |
| staged with `git add` but not yet committed | yes | blocked |
| tracked, but deleted from the working directory | yes | blocked (it cannot be recreated in place) |
| exists on disk, never added to git | no | allowed |
| does not exist yet | no | allowed |
| removed from git with `git rm` or `git rm --cached` | no | allowed |
| ignored by `.gitignore` | no | allowed |
| not inside any git repository | no | allowed |

Whether the file exists on disk no longer matters; only whether git tracks it.

## Out of scope

- Changes made through the `Bash` tool (for example `sed -i`).
- Changes a person makes in their own editor.
- Git operations themselves. A person replaces a tracked test by removing it from git first.
