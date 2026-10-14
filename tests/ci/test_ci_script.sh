#!/usr/bin/env bash
# Tests for scripts/ci.sh
# Expected values come from docs/specs/make-ci.md.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/ci.sh"

FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT

# --- Fixture: a made-up repository holding a copy of the script, and stand-ins
# for make and docker that record each call and the environment they saw.
REPO="$FIXTURE/repo"
BIN="$FIXTURE/bin"
CALLS="$FIXTURE/calls"
mkdir -p "$REPO/scripts" "$BIN" "$FIXTURE/elsewhere"
[ -f "$SCRIPT" ] && cp "$SCRIPT" "$REPO/scripts/ci.sh"

cat > "$REPO/.env.example" <<'EOF'
# A comment, and a blank line below.

SECRET_KEY=change-me
POSTGRES_USER=community_centre
POSTGRES_PASSWORD=change-me
POSTGRES_DB=community_centre
POSTGRES_PORT=5432
DATABASE_URL=postgresql://community_centre:change-me@localhost:5432/community_centre
TEST_DATABASE_URL=postgresql://community_centre:change-me@localhost:5432/community_centre_test
TEAM_EMAIL=team@example.com
TRUSTED_PROXY_HOPS=0
EOF
printf 'SECRET_KEY=the-developers-own\nPOSTGRES_PORT=5432\n' > "$REPO/.env"

for tool in make docker; do
    cat > "$BIN/$tool" <<'EOF'
#!/usr/bin/env bash
tool="$(basename "$0")"
echo "$tool $*" >> "$CALLS"
echo "$PWD" > "$CALLS.cwd.$tool"
env > "$CALLS.env.$tool.${1:-none}"
case " $FAIL_ON " in *" $tool:${1:-none} "*) exit 1 ;; esac
exit 0
EOF
    chmod +x "$BIN/$tool"
done

PASS=0
FAIL=0
DOWN="docker compose down --volumes --remove-orphans"

ok() { PASS=$((PASS + 1)); echo "PASS  $1"; }
no() { FAIL=$((FAIL + 1)); echo "FAIL  $1"; }

# run <failing steps> <args...>: runs the script from another directory, with
# the developer's own settings in the environment. Sets $code, $out and $err.
run() {
    local fail_on="$1"
    shift
    rm -f "$CALLS" "$CALLS".*
    : > "$CALLS"
    out="$(cd "$FIXTURE/elsewhere" && CALLS="$CALLS" FAIL_ON="$fail_on" PATH="$BIN:$PATH" \
        POSTGRES_PORT=5432 SECRET_KEY=the-developers-own COMPOSE_PROJECT_NAME=development \
        TEST_DATABASE_URL=postgresql://dev:dev@localhost:5432/development \
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

# seen <description> <tool.step> <variable> <expected value>
seen() {
    local got
    got="$(grep "^$3=" "$CALLS.env.$2" 2> /dev/null | cut -d= -f2-)"
    if [ "$got" = "$4" ]; then ok "$1"; else no "$1 (want $3=$4, got '$got')"; fi
}

# --- S1: exactly one known stage, otherwise usage, exit 2, nothing runs
for arguments in "" "deploy" "lint test" "ALL" "--help"; do
    # shellcheck disable=SC2086
    run "" $arguments
    check "S1 '$arguments' is refused and runs nothing" 2 ""
    case "$err" in
        *[Uu]sage*) ok "S1 '$arguments' prints a usage line on standard error" ;;
        *) no "S1 '$arguments' prints a usage line on standard error (stderr: $err)" ;;
    esac
done

# --- S2, S3: install and lint each run one make target and nothing else
run "" install
check "S2 install runs make install only" 0 "make install"
run "" lint
check "S3 lint runs make lint only" 0 "make lint"

# --- S4, D1, D2: test removes the CI database, runs make test, removes it again
run "" test
check "S4 D1 D2 test: remove database, make test, remove database" 0 "$DOWN
make test
$DOWN"

# --- S5: all runs install, lint, test in that order
run "" all
check "S5 all: install, lint, then test with its fresh database" 0 "make install
make lint
$DOWN
make test
$DOWN"

# --- S6: one line per check at the end of all
case "$out" in
    *"lint: passed"*"test: passed"*) ok "S6 all ends with 'lint: passed' and 'test: passed'" ;;
    *) no "S6 all ends with 'lint: passed' and 'test: passed' (stdout: $out)" ;;
esac

# --- S6: exit code 1 when a step fails
run "make:install" install
check "S6 install that fails exits 1" 1 "make install"
run "make:lint" lint
check "S6 lint that fails exits 1" 1 "make lint"

# --- D2: the database is removed even when the tests fail
run "make:test" test
check "S6 D2 failing tests exit 1 and the database is still removed" 1 "$DOWN
make test
$DOWN"

# --- D4: no test run if the database cannot be removed first
run "docker:compose" test
if [ "$code" -eq 1 ] && ! grep -q "^make" "$CALLS"; then
    ok "D4 make test does not run when the removal before it fails (exit 1)"
else
    no "D4 make test does not run when the removal before it fails (exit $code; calls: $(tr '\n' ';' < "$CALLS"))"
fi

# --- S5: a failed install stops everything; a failed lint does not stop test
run "make:install" all
check "S5 all stops after an install that fails" 1 "make install"
run "make:lint" all
check "S5 all still runs test after a lint that fails, and exits 1" 1 "make install
make lint
$DOWN
make test
$DOWN"
case "$out" in
    *"lint: FAILED"*"test: passed"*) ok "S6 all reports 'lint: FAILED' and 'test: passed'" ;;
    *) no "S6 all reports 'lint: FAILED' and 'test: passed' (stdout: $out)" ;;
esac
run "make:test" all
check "S6 all exits 1 when only test fails" 1 "make install
make lint
$DOWN
make test
$DOWN"
case "$out" in
    *"lint: passed"*"test: FAILED"*) ok "S6 all reports 'lint: passed' and 'test: FAILED'" ;;
    *) no "S6 all reports 'lint: passed' and 'test: FAILED' (stdout: $out)" ;;
esac

# --- S7: every step runs from the repository root, wherever the script is called from
run "" all
for tool in make docker; do
    if [ "$(cd "$(cat "$CALLS.cwd.$tool" 2> /dev/null)" 2> /dev/null && pwd -P)" = "$(cd "$REPO" && pwd -P)" ]; then
        ok "S7 $tool runs from the repository root"
    else
        no "S7 $tool runs from the repository root (ran in '$(cat "$CALLS.cwd.$tool" 2> /dev/null)')"
    fi
done

# --- E1 to E3: the environment of every step
URL="postgresql://community_centre:change-me@localhost:15432/community_centre"
for step in make.install make.lint make.test docker.compose; do
    seen "E1 $step sees SECRET_KEY from .env.example, not the caller's" "$step" SECRET_KEY "change-me"
    seen "E1 $step sees POSTGRES_USER" "$step" POSTGRES_USER "community_centre"
    seen "E1 $step sees POSTGRES_PASSWORD" "$step" POSTGRES_PASSWORD "change-me"
    seen "E1 $step sees POSTGRES_DB" "$step" POSTGRES_DB "community_centre"
    seen "E1 $step sees TEAM_EMAIL" "$step" TEAM_EMAIL "team@example.com"
    seen "E1 $step sees TRUSTED_PROXY_HOPS" "$step" TRUSTED_PROXY_HOPS "0"
    seen "E2 $step sees POSTGRES_PORT 15432" "$step" POSTGRES_PORT "15432"
    seen "E2 $step sees DATABASE_URL on port 15432" "$step" DATABASE_URL "$URL"
    seen "E2 $step sees TEST_DATABASE_URL on port 15432, not the caller's" "$step" TEST_DATABASE_URL "${URL}_test"
    seen "E3 $step sees the CI project name, not the caller's" "$step" COMPOSE_PROJECT_NAME "community-centre-ci"
done

# --- E4: .env is left exactly as it was
if [ "$(cat "$REPO/.env")" = "$(printf 'SECRET_KEY=the-developers-own\nPOSTGRES_PORT=5432\n')" ]; then
    ok "E4 .env is unchanged"
else
    no "E4 .env is unchanged"
fi
rm "$REPO/.env"
run "" all
if [ "$code" -eq 0 ] && [ ! -e "$REPO/.env" ]; then
    ok "E4 all passes without a .env and does not create one"
else
    no "E4 all passes without a .env and does not create one (exit $code)"
fi

# --- E5: the same in GitHub Actions
rm -f "$CALLS".*
( cd "$FIXTURE/elsewhere" && CALLS="$CALLS" FAIL_ON="" PATH="$BIN:$PATH" CI=true GITHUB_ACTIONS=true \
    bash "$REPO/scripts/ci.sh" test > /dev/null 2>&1 )
seen "E5 in GitHub Actions make test sees the same TEST_DATABASE_URL" make.test TEST_DATABASE_URL "${URL}_test"
seen "E5 in GitHub Actions make test sees the same project name" make.test COMPOSE_PROJECT_NAME "community-centre-ci"

# --- S8: make ci runs scripts/ci.sh all
if [ "$(make -C "$REPO_ROOT" -n ci 2> /dev/null)" = "scripts/ci.sh all" ]; then
    ok "S8 make ci runs scripts/ci.sh all"
else
    no "S8 make ci runs scripts/ci.sh all (make -n ci: $(make -C "$REPO_ROOT" -n ci 2>&1 | head -1))"
fi

# --- S9: the commands of the workflow
WORKFLOW="$REPO_ROOT/.github/workflows/ci.yml"
commands="$(grep -E '^ +- run:' "$WORKFLOW" | sed -E 's/^ +- run: *//' | tr '\n' ';')"
want="scripts/ci.sh install;scripts/ci.sh lint;scripts/ci.sh install;scripts/ci.sh test;"
if [ "$commands" = "$want" ]; then
    ok "S9 the workflow runs install+lint and install+test through the script"
else
    no "S9 the workflow runs install+lint and install+test through the script (runs: $commands)"
fi
if [ -x "$SCRIPT" ]; then ok "S9 scripts/ci.sh is executable"; else no "S9 scripts/ci.sh is executable"; fi

# --- D5: the health check asks over the network
if grep -q 'pg_isready -h 127.0.0.1 ' "$REPO_ROOT/docker-compose.yml"; then
    ok "D5 the database health check asks over the network"
else
    no "D5 the database health check asks over the network"
fi

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
