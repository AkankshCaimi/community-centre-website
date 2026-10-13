#!/usr/bin/env bash
# PreToolUse hook: enforces CLAUDE.md rule 4, "Never edit any existing test
# after code is written". Spec: docs/specs/test-edit-guard.md
#
# A test file is locked once git tracks it; untracked test files stay editable.
#
# Reads the tool call as JSON on stdin.
#   exit 0 -> tool call goes ahead
#   exit 2 -> tool call is cancelled and stderr is passed back to the agent

set -u

block() {
  echo "BLOCKED by .claude/hooks/protect-existing-tests.sh: $1" >&2
  exit 2
}

command -v jq >/dev/null 2>&1 || block "jq is not installed, so the tool call could not be checked. Install jq and retry."

input="$(cat)"

path="$(printf '%s' "$input" | jq -er '.tool_input.file_path // .tool_input.notebook_path' 2>/dev/null)" \
  || block "could not read a file path from the hook input, so the tool call could not be checked."

# Resolve a relative path against the session's working directory.
case "$path" in
  /*) ;;
  *)
    cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"
    path="${cwd:-$PWD}/$path"
    ;;
esac

# Claude Code's own files (skills, hooks) are never treated as tests.
case "$path" in
  */.claude/*) exit 0 ;;
esac

name="${path##*/}"
dir="${path%/*}/"

is_test=no
case "$name" in
  test_*.py | *_test.py | conftest.py | test_*.sh) is_test=yes ;;
  *.test.js | *.test.jsx | *.test.ts | *.test.tsx | *.test.mjs | *.test.cjs) is_test=yes ;;
  *.spec.js | *.spec.jsx | *.spec.ts | *.spec.tsx | *.spec.mjs | *.spec.cjs) is_test=yes ;;
esac
case "$dir" in
  */tests/* | */test/* | */__tests__/* | */e2e/*) is_test=yes ;;
esac

[ "$is_test" = yes ] || exit 0

command -v git >/dev/null 2>&1 || block "git is not installed, so the tool call could not be checked. Install git and retry."

# A test file is locked once git tracks it. Ask git from the nearest directory
# that exists, so new files in new directories and tracked files that were
# deleted from disk are both answered correctly.
rel="$name"
base="${path%/*}"
while [ -n "$base" ] && [ ! -d "$base" ]; do
  rel="${base##*/}/$rel"
  base="${base%/*}"
done

# Untracked (new, drafted, ignored, removed from git, or outside any
# repository): still editable.
git -C "${base:-/}" ls-files --error-unmatch -- "$rel" >/dev/null 2>&1 || exit 0

block "$path is a test file tracked by git. CLAUDE.md rule 4: never edit any existing test after code is written. Do not retry this edit and do not change the file another way (for example through Bash or git). If the test fails, change the implementation so it passes. If new behaviour needs covering, create a NEW test file, which is allowed and stays editable until it is added to git. If the test itself is wrong, stop and ask the user to change it."
