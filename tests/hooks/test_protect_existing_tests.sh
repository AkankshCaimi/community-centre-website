#!/usr/bin/env bash
# Tests for .claude/hooks/protect-existing-tests.sh
# Expected values come from docs/specs/test-edit-guard.md.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/protect-existing-tests.sh"

FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT

# --- Fixture: a git repository with tracked, staged, untracked and ignored files
REPO="$FIXTURE/repo"
mkdir -p "$REPO/tests" "$REPO/src" "$REPO/web" "$REPO/docs/specs" "$REPO/.claude/test/refs"
git -C "$REPO" init -q

# committed
touch "$REPO/tests/test_booking.py" \
      "$REPO/src/booking_test.py" \
      "$REPO/src/conftest.py" \
      "$REPO/src/test_run.sh" \
      "$REPO/web/Form.test.jsx" \
      "$REPO/web/form.spec.ts" \
      "$REPO/tests/helpers.py" \
      "$REPO/tests/notebook.ipynb" \
      "$REPO/tests/test_deleted.py" \
      "$REPO/tests/test_removed_from_git.py" \
      "$REPO/src/app.py" \
      "$REPO/web/Form.jsx" \
      "$REPO/docs/specs/booking.spec.md" \
      "$REPO/.claude/test/refs/test_example.py"
echo "tests/test_ignored.py" > "$REPO/.gitignore"
git -C "$REPO" add -A
git -C "$REPO" -c user.name=test -c user.email=test@example.com -c commit.gpgsign=false \
    commit -q -m fixture

# staged with git add, not committed
touch "$REPO/tests/test_staged.py"
git -C "$REPO" add tests/test_staged.py

# tracked, but deleted from the working directory
rm "$REPO/tests/test_deleted.py"

# removed from git, still on disk
git -C "$REPO" rm -q --cached tests/test_removed_from_git.py

# on disk, never added to git
touch "$REPO/tests/test_draft.py" "$REPO/web/Draft.test.tsx"

# ignored by .gitignore
touch "$REPO/tests/test_ignored.py"

# --- Fixture: a directory that is not inside any git repository
PLAIN="$FIXTURE/plain"
mkdir -p "$PLAIN/tests"
touch "$PLAIN/tests/test_outside.py"

PASS=0
FAIL=0

# check <description> <expected exit code> <expect BLOCKED in stderr: yes|no> <json input>
check() {
  local desc="$1" want_code="$2" want_blocked="$3" input="$4"
  local stderr code
  stderr="$(printf '%s' "$input" | "$HOOK" 2>&1 >/dev/null)"
  code=$?
  local ok=1
  [ "$code" -eq "$want_code" ] || ok=0
  if [ "$want_blocked" = yes ]; then
    case "$stderr" in *BLOCKED*) ;; *) ok=0 ;; esac
  else
    [ -z "$stderr" ] || ok=0
  fi
  if [ "$ok" -eq 1 ]; then
    PASS=$((PASS + 1))
    echo "PASS  $desc (exit $code)"
  else
    FAIL=$((FAIL + 1))
    echo "FAIL  $desc (want exit $want_code, got $code; stderr: $stderr)"
  fi
}

input() { # <tool> <path key> <path> [cwd]
  printf '{"tool_name":"%s","cwd":"%s","tool_input":{"%s":"%s"}}' "$1" "${4:-$REPO}" "$2" "$3"
}

# Spec row 1: test file that git tracks -> exit 2, BLOCKED
check "Edit committed tests/test_booking.py"      2 yes "$(input Edit file_path "$REPO/tests/test_booking.py")"
check "Write committed tests/test_booking.py"     2 yes "$(input Write file_path "$REPO/tests/test_booking.py")"
check "MultiEdit committed *_test.py"             2 yes "$(input MultiEdit file_path "$REPO/src/booking_test.py")"
check "Edit committed conftest.py"                2 yes "$(input Edit file_path "$REPO/src/conftest.py")"
check "Edit committed test_*.sh"                  2 yes "$(input Edit file_path "$REPO/src/test_run.sh")"
check "Edit committed *.test.jsx"                 2 yes "$(input Edit file_path "$REPO/web/Form.test.jsx")"
check "Edit committed *.spec.ts"                  2 yes "$(input Edit file_path "$REPO/web/form.spec.ts")"
check "Edit committed file under tests/"          2 yes "$(input Edit file_path "$REPO/tests/helpers.py")"
check "NotebookEdit committed under tests/"       2 yes "$(input NotebookEdit notebook_path "$REPO/tests/notebook.ipynb")"
check "Edit committed test, relative path"        2 yes "$(input Edit file_path "tests/test_booking.py")"
check "Edit test staged but not committed"        2 yes "$(input Edit file_path "$REPO/tests/test_staged.py")"
check "Write tracked test deleted from disk"      2 yes "$(input Write file_path "$REPO/tests/test_deleted.py")"

# Spec row 1: the message names the file path
msg="$(input Edit file_path "$REPO/tests/test_booking.py" | "$HOOK" 2>&1 >/dev/null)"
case "$msg" in
  *"$REPO/tests/test_booking.py"*) PASS=$((PASS + 1)); echo "PASS  block message contains the file path" ;;
  *) FAIL=$((FAIL + 1)); echo "FAIL  block message contains the file path (got: $msg)" ;;
esac

# Spec row 2: test file that git does not track -> exit 0, no stderr
check "Edit untracked tests/test_draft.py"        0 no "$(input Edit file_path "$REPO/tests/test_draft.py")"
check "Write untracked tests/test_draft.py"       0 no "$(input Write file_path "$REPO/tests/test_draft.py")"
check "Edit untracked *.test.tsx"                 0 no "$(input Edit file_path "$REPO/web/Draft.test.tsx")"
check "Edit untracked test, relative path"        0 no "$(input Edit file_path "tests/test_draft.py")"
check "Write test that does not exist yet"        0 no "$(input Write file_path "$REPO/tests/test_new.py")"
check "Write new test in a directory not yet made" 0 no "$(input Write file_path "$REPO/tests/unit/booking/test_new.py")"
check "Edit test removed from git, still on disk" 0 no "$(input Edit file_path "$REPO/tests/test_removed_from_git.py")"
check "Edit test ignored by .gitignore"           0 no "$(input Edit file_path "$REPO/tests/test_ignored.py")"
check "Edit test outside any git repository"      0 no "$(input Edit file_path "$PLAIN/tests/test_outside.py" "$PLAIN")"

# Spec row 3: not a test file -> exit 0, no stderr
check "Edit committed src/app.py"                 0 no "$(input Edit file_path "$REPO/src/app.py")"
check "Edit committed Form.jsx"                   0 no "$(input Edit file_path "$REPO/web/Form.jsx")"
check "Edit committed booking.spec.md"            0 no "$(input Edit file_path "$REPO/docs/specs/booking.spec.md")"
check "Edit committed file under .claude/"        0 no "$(input Edit file_path "$REPO/.claude/test/refs/test_example.py")"

# Spec row 4: unparseable input or no file path -> exit 2, BLOCKED
check "Unparseable input"                         2 yes "this is not json"
check "No file path in input"                     2 yes '{"tool_name":"Edit","tool_input":{}}'

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
