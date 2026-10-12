#!/usr/bin/env bash
# Tests for .claude/hooks/protect-existing-tests.sh
# Expected values come from docs/specs/test-edit-guard.md.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/protect-existing-tests.sh"

FIXTURE="$(mktemp -d)"
trap 'rm -r "$FIXTURE"' EXIT

mkdir -p "$FIXTURE/tests" "$FIXTURE/src" "$FIXTURE/docs/specs" "$FIXTURE/.claude/test/refs" "$FIXTURE/web"
touch "$FIXTURE/tests/test_booking.py" \
      "$FIXTURE/src/booking_test.py" \
      "$FIXTURE/src/conftest.py" \
      "$FIXTURE/src/app.py" \
      "$FIXTURE/src/test_run.sh" \
      "$FIXTURE/web/Form.test.jsx" \
      "$FIXTURE/web/form.spec.ts" \
      "$FIXTURE/web/Form.jsx" \
      "$FIXTURE/tests/helpers.py" \
      "$FIXTURE/tests/notebook.ipynb" \
      "$FIXTURE/docs/specs/booking.spec.md" \
      "$FIXTURE/.claude/test/refs/test_example.py"

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

input() { # <tool> <path key> <path>
  printf '{"tool_name":"%s","cwd":"%s","tool_input":{"%s":"%s"}}' "$1" "$FIXTURE" "$2" "$3"
}

# Spec row 1: existing test file -> exit 2, BLOCKED
check "Edit existing tests/test_booking.py"   2 yes "$(input Edit file_path "$FIXTURE/tests/test_booking.py")"
check "Write existing tests/test_booking.py"  2 yes "$(input Write file_path "$FIXTURE/tests/test_booking.py")"
check "MultiEdit existing *_test.py"          2 yes "$(input MultiEdit file_path "$FIXTURE/src/booking_test.py")"
check "Edit existing conftest.py"             2 yes "$(input Edit file_path "$FIXTURE/src/conftest.py")"
check "Edit existing test_*.sh"               2 yes "$(input Edit file_path "$FIXTURE/src/test_run.sh")"
check "Edit existing *.test.jsx"              2 yes "$(input Edit file_path "$FIXTURE/web/Form.test.jsx")"
check "Edit existing *.spec.ts"               2 yes "$(input Edit file_path "$FIXTURE/web/form.spec.ts")"
check "Edit existing file under tests/"       2 yes "$(input Edit file_path "$FIXTURE/tests/helpers.py")"
check "NotebookEdit existing under tests/"    2 yes "$(input NotebookEdit notebook_path "$FIXTURE/tests/notebook.ipynb")"
check "Edit existing test, relative path"     2 yes "$(input Edit file_path "tests/test_booking.py")"

# Spec row 1: the message names the file path
msg="$(input Edit file_path "$FIXTURE/tests/test_booking.py" | "$HOOK" 2>&1 >/dev/null)"
case "$msg" in
  *"$FIXTURE/tests/test_booking.py"*) PASS=$((PASS + 1)); echo "PASS  block message contains the file path" ;;
  *) FAIL=$((FAIL + 1)); echo "FAIL  block message contains the file path (got: $msg)" ;;
esac

# Spec row 2: test file that does not exist yet -> exit 0, no stderr
check "Write new tests/test_new.py"           0 no "$(input Write file_path "$FIXTURE/tests/test_new.py")"
check "Write new *.test.tsx"                  0 no "$(input Write file_path "$FIXTURE/web/New.test.tsx")"
check "Write new test, relative path"         0 no "$(input Write file_path "tests/test_other.py")"

# Spec row 3: not a test file -> exit 0, no stderr
check "Edit existing src/app.py"              0 no "$(input Edit file_path "$FIXTURE/src/app.py")"
check "Edit existing Form.jsx"                0 no "$(input Edit file_path "$FIXTURE/web/Form.jsx")"
check "Edit existing booking.spec.md"         0 no "$(input Edit file_path "$FIXTURE/docs/specs/booking.spec.md")"
check "Edit existing file under .claude/"     0 no "$(input Edit file_path "$FIXTURE/.claude/test/refs/test_example.py")"

# Spec row 4: unparseable input or no file path -> exit 2, BLOCKED
check "Unparseable input"                     2 yes "this is not json"
check "No file path in input"                 2 yes '{"tool_name":"Edit","tool_input":{}}'

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
