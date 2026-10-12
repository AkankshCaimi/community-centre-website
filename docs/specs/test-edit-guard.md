# Spec: test edit guard

Mechanically enforces rule 4 of `CLAUDE.md`: never edit any existing test after code is written.

## Mechanism

A Claude Code `PreToolUse` hook, registered in `.claude/settings.json` for the tools `Edit`, `Write`, `MultiEdit` and `NotebookEdit`. It runs the executable shell script `.claude/hooks/protect-existing-tests.sh`, which receives the tool call as JSON on stdin.

## Behaviour

| # | Tool call target | Exit code | stderr |
|---|---|---|---|
| 1 | test file that exists on disk | 2 (blocked) | message containing `BLOCKED` and the file path |
| 2 | test file that does not exist yet | 0 (allowed) | empty |
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

**Exists**: the target path exists on disk at the moment of the tool call.

## Out of scope

- Changes made through the `Bash` tool (for example `sed -i`).
- Changes a person makes in their own editor.
