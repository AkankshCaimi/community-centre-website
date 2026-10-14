# make ci

Spec for running the continuous-integration checks on a developer's machine, by the same script GitHub Actions runs.

## Why

A pull request should not be the first place a failure shows up. `make ci` runs what the workflow runs, so a red workflow can be reproduced, and avoided, before pushing.

## One script

`scripts/ci.sh` holds the steps. `make ci` and `.github/workflows/ci.yml` both call it, so the two cannot drift apart. The workflow keeps its two jobs, `lint` and `test`, and its tool versions (Python 3.14, Node 24).

| Rule | |
|---|---|
| S1 | `scripts/ci.sh <stage>` takes exactly one stage: `install`, `lint`, `test` or `all`. Anything else (no stage, an unknown stage, more than one) prints a usage line on standard error, runs nothing and exits with code 2. |
| S2 | `install` runs `make install` and nothing else. |
| S3 | `lint` runs `make lint` and nothing else. |
| S4 | `test` removes the CI database with its data, runs `make test`, then removes the CI database again (D1 to D3). |
| S5 | `all` runs `install`, then `lint`, then `test`, in that order. If `install` fails, nothing else runs. If `lint` fails, `test` still runs, as the two jobs of the workflow both run; the result is then a failure. |
| S6 | The exit code is 0 only if every step of the stage succeeded, otherwise 1. `all` ends with one line per check: `lint: passed` or `lint: FAILED`, and the same for `test`. |
| S7 | The script works from any directory: it finds the repository from its own location and runs every step from the repository root. |
| S8 | `make ci` runs `scripts/ci.sh all`. |
| S9 | In the workflow, the `lint` job runs `scripts/ci.sh install` then `scripts/ci.sh lint`, and the `test` job runs `scripts/ci.sh install` then `scripts/ci.sh test`. The workflow runs no other command. |

## Environment

| Rule | |
|---|---|
| E1 | Every step runs with each variable of `.env.example` set in its environment, with the values written there, except the port (E2). A value already set in the caller's environment for one of these variables is replaced, so a developer's own settings cannot leak in. |
| E2 | The database port is 15432 instead of the port in `.env.example`: `POSTGRES_PORT` is 15432, and in every other value the text `:<port of .env.example>/` becomes `:15432/`. So with today's `.env.example`, `TEST_DATABASE_URL` is `postgresql://community_centre:change-me@localhost:15432/community_centre_test`. |
| E3 | `COMPOSE_PROJECT_NAME` is `community-centre-ci`, so Docker Compose keeps the CI database apart from the development one: a different container and a different volume. |
| E4 | `.env` is never read, created or changed by the script. |
| E5 | The environment is the same on a developer's machine and in GitHub Actions; the script does not ask where it is running. |

## Fresh database

| Rule | |
|---|---|
| D1 | Before `make test`, the script runs `docker compose down --volumes --remove-orphans`, so the database is created from nothing on every run and the first-start scripts in `docker/postgres/init` run every time. |
| D2 | After `make test`, whether it passed or failed, the same command runs again, so nothing is left running. |
| D3 | Both happen under the project name of E3. The development database, its container and its volume are never touched. |
| D4 | If the removal before the run fails (for example Docker is not running), `make test` does not run and the stage fails. |
| D5 | The database counts as ready only when it accepts connections over the network, as the tests connect. On a first start PostgreSQL runs a temporary server for its first-start scripts that answers only inside the container, then restarts; the health check in `docker-compose.yml` therefore asks over the network (`pg_isready -h 127.0.0.1`), so `make test` cannot begin during that restart. |

## Known limits

- **Tool versions are not enforced locally.** The workflow pins Python 3.14 and Node 24; `make ci` uses whatever `python3` and `node` the machine has.
- **`install` reinstalls everything**, as the workflow does on a clean machine: it runs `npm ci`, which removes and reinstalls `frontend/node_modules`.
- **The working tree is tested, not the commit.** A file that exists locally but was never added to git passes here and fails on GitHub.
- **A variable that is only in `.env`, and not in `.env.example`, still reaches the application**, because the application loads `.env` itself for variables that are not set. The workflow has no `.env`.
- **Port 15432 must be free.** It is below the range the operating system hands out for outgoing connections (49152 and up), so no passing connection can take it; a first choice of 55432 was inside that range and one run failed with "address already in use".

## Where this differs

| Earlier document | Now |
|---|---|
| `skeleton.md`: the `db` service "has a health check" | The health check asks over the network (D5). Found by the first `make ci` run: 47 tests failed with "the database system is starting up". |
| `skeleton.md`: the workflow has two jobs, `lint` (`make lint`) and `test` (`make test`); the `test` job first copied `.env.example` to `.env` | The workflow runs `scripts/ci.sh` (S9). There is no `.env` in the workflow; the values of `.env.example` are set in the environment instead (E1), and the port is 15432 (E2). |

## Tests

`tests/ci/test_ci_script.sh` runs the script in a made-up repository with stand-ins for `make` and `docker` that record how they were called and with what environment. It also checks S8 and S9 against the real `Makefile` and workflow. Run it with `bash tests/ci/test_ci_script.sh`.

## Proposed by the implementer

Not yet confirmed by the author:

- Port 15432 and the project name `community-centre-ci`.
- The same port and project name in GitHub Actions as locally (E5), which removes `cp .env.example .env` from the workflow.
- `all` carrying on to `test` when `lint` fails (S5).
- Not enforcing tool versions locally.
- The health check over the network (D5).
