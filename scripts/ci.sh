#!/usr/bin/env bash
# The continuous-integration checks, as run by `make ci` and by GitHub Actions.
# Spec: docs/specs/make-ci.md.

set -u

CI_PORT=15432
CI_PROJECT=community-centre-ci

usage() {
    echo "Usage: scripts/ci.sh install|lint|test|image|all" >&2
    exit 2
}

[ $# -eq 1 ] || usage
case "$1" in
    install | lint | test | image | all) ;;
    *) usage ;;
esac

cd "$(dirname "$0")/.." || exit 1

# The values of .env.example, on the CI port (E1, E2). .env is not read (E4).
example_port="$(sed -n 's/^POSTGRES_PORT=//p' .env.example)"
while IFS= read -r line; do
    case "$line" in
        "" | "#"*) continue ;;
    esac
    name="${line%%=*}"
    value="${line#*=}"
    export "$name=${value//:$example_port\//:$CI_PORT/}"
done < .env.example
export POSTGRES_PORT="$CI_PORT"
export COMPOSE_PROJECT_NAME="$CI_PROJECT"

remove_database() {
    docker compose down --volumes --remove-orphans
}

run_test() {
    remove_database || return 1
    make test
    local result=$?
    remove_database || return 1
    return "$result"
}

# Build only: nothing is pushed or deployed (S10).
build_image() {
    docker build --tag community-centre:ci .
}

report() {
    if [ "$2" -eq 0 ]; then echo "$1: passed"; else echo "$1: FAILED"; fi
}

case "$1" in
    install) make install || exit 1 ;;
    lint) make lint || exit 1 ;;
    test) run_test || exit 1 ;;
    image) build_image || exit 1 ;;
    all)
        make install || exit 1
        make lint
        lint=$?
        run_test
        test=$?
        build_image
        image=$?
        echo
        report lint "$lint"
        report test "$test"
        report image "$image"
        [ "$lint" -eq 0 ] && [ "$test" -eq 0 ] && [ "$image" -eq 0 ] || exit 1
        ;;
esac
