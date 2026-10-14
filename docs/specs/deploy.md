# Deployment

Spec for running the website on Azure as a demonstration: one container image that serves the built React application and the API, a PostgreSQL server, and the two hourly jobs.

Each rule has a number; tests and the files under `infra/` cite it.

## Decided by the author

On 2026-10-14:

- Azure, one service, the cheapest tiers; region `uksouth`.
- One image: Flask serves the built frontend and the API.
- Azure Container Apps for the website, scaling down to no replica when idle.
- Azure Database for PostgreSQL Flexible Server, Burstable tier, reachable from Azure services only.
- The two jobs as Container Apps Jobs on a schedule: auto-decline at minute 0 and the purge at minute 30 of every hour.
- A budget of 25 a month in the subscription's billing currency, with alerts to the author.
- Secrets live in Azure settings, never in the repository.
- Deployed as a demonstration, with the stand-in CAPTCHA, logged emails and fictional centre details as they are.
- The author runs every command that creates or changes anything in Azure.

## Serving the frontend

The application serves the built frontend only when the setting `FRONTEND_DIST` names the folder holding it (the output of `npm run build`, containing `index.html`). Without the setting nothing changes: this is how the tests and a developer's machine run.

| Rule | |
|---|---|
| G1 | With `FRONTEND_DIST` unset or empty, every address behaves as before this spec. `GET /` answers `404` with `{"error": "not_found"}` (F01 A9). |
| G2 | With it set, a `GET` for an address that names a file inside the folder answers `200` with that file and its content type: `/assets/app.js`, `/favicon.ico`. |
| G3 | With it set, a `GET` for any other address that no route of the application answers gets `200` with `index.html`, as `text/html`. That covers `/`, `/facilities`, `/admin` and unknown addresses such as `/no-such-page`: the React application chooses the page (public pages R1). |
| G4 | Addresses of the API are never answered with the frontend: `/api` and everything under `/api/` that no route answers stays `404` with `{"error": "not_found"}`, as JSON (F01 A9, S4). `/health` is unchanged. |
| G5 | Only `GET` and `HEAD` are answered with the frontend. Any other method on an address without a route stays `404` JSON, as before. |
| G6 | Nothing outside the folder is ever served. An address that tries to leave it (`/../secret`, `/assets/../../secret`, the same with `%2e%2e`) is treated as naming no file: it gets `index.html` (G3), never the file. A folder inside it (`/assets`, `/assets/`) is not a file either. |
| G7 | `index.html` is sent with `Cache-Control: no-cache`, so a visitor gets the new version after a redeploy. Files under `/assets/` are sent with `Cache-Control: public, max-age=31536000, immutable`: their names change whenever their contents do. Other files are sent with `Cache-Control: no-cache`. |
| G8 | Every answer of G2 and G3 carries `X-Content-Type-Options: nosniff`. |
| G9 | If the folder has no `index.html`, G3 answers `404` with `{"error": "not_found"}`. |
| G10 | Serving the frontend reads no database and writes no log line. |

## The image

| Rule | |
|---|---|
| M1 | One `Dockerfile` in the repository root builds the image in two stages: Node 24 runs `npm ci` and `npm run build`; Python 3.14 installs `backend/requirements.txt` and takes the backend and the built frontend. No test, development dependency, `.env` or git data is in the image (`.dockerignore`). |
| M2 | The image runs as a user that is not root. |
| M3 | Its default command is `gunicorn` on port 8000 with 2 workers and `FRONTEND_DIST` set to the built frontend. Access logging stays off, so no visitor's network address reaches the log (NFR5). |
| M4 | The same image runs the commands `flask --app app init-db`, `auto-decline`, `purge` and `create-admin`. |
| M5 | The build fails if the built frontend has no `index.html`, or if the time zone Europe/London cannot be loaded. |

## Production settings

| Setting | Development | Production | Kept as |
|---|---|---|---|
| Web server | Flask's own, for development | gunicorn; debug is off | image |
| `DATABASE_URL` | the Docker Compose database | the Azure server, with `sslmode=require` | secret |
| `SECRET_KEY` | `change-me` | 64 random hex characters, made on the author's machine | secret |
| `TEAM_EMAIL` | an example address | the team's address | secret |
| `TRUSTED_PROXY_HOPS` | 0 | 1: Azure's ingress is the one proxy in front of the application (F01 L6) | setting |
| `FRONTEND_DIST` | unset | `/app/frontend/dist` | image |
| Session cookie | `Secure`, `HttpOnly`, `SameSite=Strict` in the code (F02 SE1) | the same; HTTPS is provided by Azure, and plain HTTP is refused at the ingress | code |
| `.env` | read if present | not in the image | |

## Azure resources

All in one resource group, defined in `infra/main.bicep`.

| Rule | |
|---|---|
| Z1 | A Container App for the website: 0.25 CPU and 0.5 GB of memory, between 0 and 1 replica, public HTTPS ingress to port 8000 with plain HTTP refused. |
| Z2 | Startup, liveness and readiness probes all request `GET /health` on port 8000. |
| Z3 | A PostgreSQL Flexible Server, version 16, `Standard_B1ms` (Burstable), 32 GB, no high availability, backups kept 7 days (the least Azure allows) and not copied to another region. Its public endpoint admits Azure services only (the firewall rule from `0.0.0.0` to `0.0.0.0`); connections need TLS and the password. |
| Z4 | Three Container Apps Jobs from the same image: `job-auto-decline` on the schedule `0 * * * *`, `job-purge` on `30 * * * *` (both UTC), and `job-init-db`, started by hand. Each runs one replica, gives up after 5 minutes, and is retried once if it fails. |
| Z5 | A container registry (Basic) holds the image. The apps pull from it with a managed identity; the registry's admin user stays off. |
| Z6 | A Log Analytics workspace receives the logs and keeps them 30 days, the shortest it allows. |
| Z7 | The database password, `SECRET_KEY` and `TEAM_EMAIL` are passed to the deployment as secure parameters and held as Container Apps secrets. They appear in no file of the repository and in no deployment output. |
| Z8 | A monthly budget on the resource group, 25 in the subscription's billing currency, emails the author at 50%, 80% and 100% of actual cost and at 100% of forecast cost. It can be left out with a parameter, for a subscription that does not support budgets. |

## Running it

`infra/README.md` gives the exact commands for: the checks before the first run; the first run; creating the tables; creating the admin account (one command, run once); a smoke test; a redeploy; reading the logs; and removing everything.

| Rule | |
|---|---|
| U1 | The tables are created by starting `job-init-db`, after the first run and after every redeploy. `init-db` is safe to repeat (skeleton, F03). |
| U2 | The admin account is created once with `flask --app app create-admin`, run inside the website's container, so the password is typed at a hidden prompt (F02 CL1). |
| U3 | A redeploy builds a new image tagged with the commit and points the website and the three jobs at it. It needs no secret. |
| U4 | The smoke test checks `/health`, that both jobs have run, and **that the rate limit tells visitors apart**: after one network address has used its 5 requests of the day (NFR3), a request from a second network must still be accepted, and a request from the first that claims another address in an `X-Forwarded-For` header must still be refused. |

## Known limits

- **This is a demonstration.** The CAPTCHA is a stand-in that passes everything; emails are written to the log, not sent; the centre's details are fictional (F04 T5).
- **The log holds client details**, because the logged emails do (F04). Anyone who can read the Log Analytics workspace can read them, and the admin's password-reset token. The workspace keeps them 30 days.
- **Deleted data stays in the database backups for up to 7 days.** Azure does not allow fewer. The privacy notice says so (F04 T3).
- **The application connects as the database's administrator.** A separate, weaker database user is not set up.
- **The database's public endpoint admits every Azure customer's services**, not only this application; TLS and the password are what protect it.
- **The first visitor after an idle spell waits** while a replica starts.
- **`TRUSTED_PROXY_HOPS=1` is an assumption about Azure's ingress** until the smoke test of U4 has passed. If it is wrong, every visitor shares one allowance of 5 requests a day.
- **`/health` reads the database on every probe** while a replica is running (F03 R7).
- **The Bicep file is checked by compiling it**, not by a test: only a real deployment proves it.
- **No custom domain.** The site is at the address Azure gives the Container App.
- **Prices are not checked here.** The budget alert is the safeguard; it warns and does not stop anything.

## Where this differs

| Earlier document | Now |
|---|---|
| F01 A9: an unknown address under the application answers `404` JSON | Still so everywhere without `FRONTEND_DIST`, and for the API with it. With it, an unknown address outside the API shows the frontend (G3). |
| F03 R2, F04 P1: the jobs run "once an hour by a scheduler outside the application" | Container Apps Jobs, at minutes 0 and 30 (Z4). |
| NFR8: no backups are required | Azure keeps 7 days of backups regardless (Z3). |

## Tests

`backend/tests/deploy/test_serve_frontend.py` covers G1 to G10 with a made-up built frontend in a temporary folder. The image is checked by building it and running it against the Docker Compose database (`infra/README.md`, "Try the image locally"); the Bicep file by `az bicep build`.

## Confirmed by the author

On 2026-10-14, after the files were written, the author confirmed every proposal of the implementer:

- Everything under "Serving the frontend" (G1 to G10), including the cache headers and `nosniff`.
- 2 gunicorn workers, port 8000, and no access log.
- The container sizes, the job limits (5 minutes, one retry) and the resource names in `infra/main.bicep`.
- Alerts at 50%, 80% and 100%.
- `TRUSTED_PROXY_HOPS=1`, still to be proved by the smoke test (U4).

On the same day the author asked for the image to be built in CI: see `docs/specs/make-ci.md`, S10.
