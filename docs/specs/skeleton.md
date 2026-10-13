# Spec: project skeleton

The empty project that later features are built into: a Flask backend, a React frontend, PostgreSQL through Docker Compose, a test runner, and lint and CI tooling. It contains no booking features.

Sources: `docs/adr/0001-database-postgresql.md`, `docs/adr/0002-backend-flask.md`, `docs/adr/0003-frontend-react.md`.

## Backend

Flask application in `backend/`, created by an application factory `create_app()` in `backend/app/__init__.py`.

### Directory structure

| Directory | Holds |
|---|---|
| `backend/app/api` | HTTP endpoints |
| `backend/app/services` | business rules |
| `backend/app/repositories` | database access |
| `backend/app/models` | data structures |
| `backend/tests` | tests |

`models`, `services` and `repositories` are empty packages in the skeleton.

### Configuration

Configuration is read from environment variables. A `.env` file in the repository root is loaded into the environment when the application starts; variables already set in the environment take precedence over the file.

| Variable | Used for |
|---|---|
| `SECRET_KEY` | Flask secret key |
| `DATABASE_URL` | PostgreSQL connection for the application |
| `TEST_DATABASE_URL` | PostgreSQL connection for the tests |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | the Docker Compose database |

`.env` is never committed. `.env.example` is committed, lists every variable above, and contains no real secret.

### Health endpoint

| Request | Response status | Response content type | Response body |
|---|---|---|---|
| `GET /health` | `200` | `application/json` | `{"status": "ok"}` |

The endpoint does not need a database connection.

## Frontend

React application in `frontend/`, built with Vite. The skeleton renders a single placeholder page with the heading "Community Centre". It has no routing and makes no calls to the backend.

## Infrastructure

`docker-compose.yml` in the repository root defines one service, `db`, running PostgreSQL 16. It takes its user, password, database name and port from `.env`, has a health check, and keeps its data in a named volume. On first start it also creates a second, empty database for the tests, named `<POSTGRES_DB>_test`.

## Tests

- pytest, run from `backend/`.
- Tests run against the PostgreSQL from Docker Compose. `make test` starts the `db` service, waits until it is healthy, then runs pytest.
- A `db_connection` fixture connects to `TEST_DATABASE_URL`. A test that uses it fails, not skips, when the database cannot be reached.
- Smoke test: `backend/tests/test_health.py` requests `GET /health` and checks the three response values in the table above.

## Tooling

| Command | Does |
|---|---|
| `make test` | starts the database, runs the backend tests |
| `make lint` | runs `ruff check` on the backend and `eslint` on the frontend |
| `make install` | creates the backend virtual environment and installs backend and frontend dependencies |

GitHub Actions workflow `.github/workflows/ci.yml` runs on every pull request and on pushes to `main`, with two jobs: `lint` (`make lint`) and `test` (`make test`).

`.gitignore` excludes `.env`, Python and Node build output, virtual environments, dependency folders and tool caches.

## Out of scope

- Any booking, admin or email feature.
- Database tables and migrations.
- Frontend tests.
- Running the backend or frontend in Docker; only the database runs in Docker.
- Deployment.
