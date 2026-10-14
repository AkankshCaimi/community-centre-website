#!/usr/bin/env bash
# Tests for the image stage of scripts/ci.sh
# Expected values come from docs/specs/make-ci.md (S1, S5, S6, S9, S10).

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/ci.sh"
WORKFLOW="$REPO_ROOT/.github/workflows/ci.yml"

FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT

# --- Fixture: a made-up repository holding a copy of the script, and stand-ins
# for make and docker that record each call.
REPO="$FIXTURE/repo"
BIN="$FIXTURE/bin"
CALLS="$FIXTURE/calls"
mkdir -p "$REPO/scripts" "$BIN" "$FIXTURE/elsewhere"
cp "$SCRIPT" "$REPO/scripts/ci.sh"
printf 'POSTGRES_PORT=5432\nTEST_DATABASE_URL=postgresql://u:p@localhost:5432/d_test\n' > "$REPO/.env.example"

for tool in make docker; do
    cat > "$BIN/$tool" <<'EOF'
#!/usr/bin/env bash
tool="$(basename "$0")"
echo "$tool $*" >> "$CALLS"
echo "$PWD" > "$CALLS.cwd.$tool.${1:-none}"
case " $FAIL_ON " in *" $tool:${1:-none} "*) exit 1 ;; esac
exit 0
EOF
    chmod +x "$BIN/$tool"
done

PASS=0
FAIL=0
BUILD="docker build --tag community-centre:ci ."
DOWN="docker compose down --volumes --remove-orphans"

ok() { PASS=$((PASS + 1)); echo "PASS  $1"; }
no() { FAIL=$((FAIL + 1)); echo "FAIL  $1"; }

# run <failing steps> <args...>: sets $code, $out and $err.
run() {
    local fail_on="$1"
    shift
    rm -f "$CALLS" "$CALLS".*
    : > "$CALLS"
    out="$(cd "$FIXTURE/elsewhere" && CALLS="$CALLS" FAIL_ON="$fail_on" PATH="$BIN:$PATH" \
        bash "$REPO/scripts/ci.sh" "$@" 2> "$FIXTURE/stderr")"
    code=$?
    err="$(cat "$FIXTURE/stderr")"
}

# check <description> <expected exit code> <expected calls, one per line>
check() {
    local got
    got="$(cat "$CALLS")"
    if [ "$code" -eq "$2" ] && [ "$got" = "$3" ]; then
        ok "$1 (exit $code)"
    else
        no "$1 (want exit $2, got $code; calls: $(echo "$got" | tr '\n' ';'))"
    fi
}

# says <description> <text that standard output must contain, in order>
says() {
    # shellcheck disable=SC2254
    case "$out" in
        $2) ok "$1" ;;
        *) no "$1 (stdout: $(echo "$out" | tr '\n' ';'))" ;;
    esac
}

# --- S10: image builds the image and does nothing else
run "" image
check "S10 image runs one docker build and nothing else" 0 "$BUILD"
if [ "$(cd "$(cat "$CALLS.cwd.docker.build" 2> /dev/null)" 2> /dev/null && pwd -P)" = "$(cd "$REPO" && pwd -P)" ]; then
    ok "S10 the build runs from the repository root"
else
    no "S10 the build runs from the repository root"
fi
run "docker:build" image
check "S10 S6 a Dockerfile that does not build fails the stage" 1 "$BUILD"

# --- S1: image is a stage; the usage line names it
run "" images
check "S1 'images' is refused and runs nothing" 2 ""
case "$err" in
    *image*) ok "S1 the usage line names the image stage" ;;
    *) no "S1 the usage line names the image stage (stderr: $err)" ;;
esac

# --- S5, S6: all runs install, lint, test, image, and reports all three
ALL="make install
make lint
$DOWN
make test
$DOWN
$BUILD"
run "" all
check "S5 all: install, lint, test, then image" 0 "$ALL"
says "S6 all ends with lint, test and image passed, in that order" '*lint: passed*test: passed*image: passed*'

run "docker:build" all
check "S6 all exits 1 when only the image fails" 1 "$ALL"
says "S6 all reports 'image: FAILED'" '*lint: passed*test: passed*image: FAILED*'

run "make:lint" all
check "S5 all still builds the image after a lint that fails" 1 "$ALL"
says "S6 all reports the failed lint and the passed image" '*lint: FAILED*test: passed*image: passed*'

run "make:test" all
check "S5 all still builds the image after tests that fail" 1 "$ALL"
says "S6 all reports the failed tests and the passed image" '*lint: passed*test: FAILED*image: passed*'

run "make:install" all
check "S5 all builds no image after an install that fails" 1 "make install"

# --- S10: build only; nothing pushed, deployed or logged in
for stage in image all; do
    run "" "$stage"
    if grep -qE "push|login|deploy|^az " "$CALLS"; then
        no "S10 $stage pushes, deploys or logs in nowhere (calls: $(tr '\n' ';' < "$CALLS"))"
    else
        ok "S10 $stage pushes, deploys or logs in nowhere"
    fi
done
if grep -E "^ +(- )?(run|uses):" "$WORKFLOW" | grep -qE "docker (push|login)|\baz |azure/|login-action|build-push-action|deploy"; then
    no "S10 the workflow pushes, deploys or logs in nowhere"
else
    ok "S10 the workflow pushes, deploys or logs in nowhere"
fi
if grep -qE "docker (push|login)|\baz " "$SCRIPT"; then
    no "S10 the script pushes, deploys or logs in nowhere"
else
    ok "S10 the script pushes, deploys or logs in nowhere"
fi

# --- S9: the image job of the workflow runs scripts/ci.sh image alone
job="$(awk '/^  image:/{on=1; next} on && /^  [a-z]/{on=0} on' "$WORKFLOW")"
commands="$(echo "$job" | grep -E '^ +- run:' | sed -E 's/^ +- run: *//' | tr '\n' ';')"
if [ "$commands" = "scripts/ci.sh image;" ]; then
    ok "S9 the image job runs scripts/ci.sh image and no other command"
else
    no "S9 the image job runs scripts/ci.sh image and no other command (runs: $commands)"
fi
all_commands="$(grep -E '^ +- run:' "$WORKFLOW" | sed -E 's/^ +- run: *//' | tr '\n' ';')"
want="scripts/ci.sh install;scripts/ci.sh lint;scripts/ci.sh install;scripts/ci.sh test;scripts/ci.sh image;"
if [ "$all_commands" = "$want" ]; then
    ok "S9 the workflow runs the five commands of its three jobs and no other"
else
    no "S9 the workflow runs the five commands of its three jobs and no other (runs: $all_commands)"
fi

# --- S10: there is a Dockerfile to build, in the repository root
if [ -f "$REPO_ROOT/Dockerfile" ]; then ok "S10 the Dockerfile is in the repository root"; else no "S10 the Dockerfile is in the repository root"; fi

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
