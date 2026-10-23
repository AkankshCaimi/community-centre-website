# Deployment on a free tier

Spec for running the website again after the Azure for Students subscription expired and the Azure deployment went with it. The image, the application and the jobs are the ones of `docs/specs/deploy.md`; this spec changes the host, the database and one line of how the image starts.

Each rule has a number; tests and `infra/README.md` cite it.

## Decided by the author

On 2026-10-22:

- Same Docker image, same application. The only change to the image: gunicorn binds to `0.0.0.0` on the port in the environment variable `PORT`, `8000` when it is not set. Both candidate hosts inject `PORT`.
- Host: Google Cloud Run (project `community-centre`) for the website and the jobs. Render is recorded as the alternative, with its limitation (R1).
- Database: Neon free Postgres. The author creates the Neon project in the browser and pastes the connection string at the secret step. The string carries `sslmode=require`. Neon's free tier needs no card.
- `SECRET_KEY` is made fresh and held as a secret on the host, never in the repository. `.env` stays out of the repository, the upload and the image.
- `TRUSTED_PROXY_HOPS` is set for the new host's proxy and proved by the rate-limit smoke test after the deploy.
- Cloud Run: deployed with `gcloud run deploy --source .`, so the image is built in the cloud; no registry to create or log in to. The website plus two Cloud Run Jobs (auto-decline at minute 0, purge at minute 30) started by Cloud Scheduler. The tables and the admin account are created as before, with the commands documented.
- Neon cold starts are documented. A cron-job.org ping requests `/health`, which reads the database, to keep both Cloud Run and Neon awake.
- The author runs every command and makes every commit.

## Starting the server

| Rule | |
|---|---|
| P1 | The image starts gunicorn with the settings file `backend/gunicorn.conf.py` (in the image at `/app/backend/gunicorn.conf.py`, the working directory). It binds to `0.0.0.0:<PORT>`, where `<PORT>` is the value of the environment variable `PORT`. |
| P2 | With `PORT` unset or empty, it binds to `0.0.0.0:8000`, as before (deploy M3). |
| P3 | A `PORT` that is not a whole number from 1 to 65535, written in the digits 0 to 9 only, with no sign or spaces (`abc`, `0`, `65536`, `-1`, `+80`, `80.5`, ` 8080`, `8080 `, Arabic-Indic `٨٠`), stops gunicorn from starting, with an error that names `PORT`. Binding to some other port instead would leave the host waiting on a port nobody listens on. |
| P4 | The default command still runs 2 workers, no control socket and no access log (deploy M3, NFR5). The address to bind is given only by the settings file: the command has no `--bind`, which would override it. |
| P5 | Nothing else in the image changes: the same `Dockerfile`, the same commands `init-db`, `auto-decline`, `purge` and `create-admin` (deploy M4). `EXPOSE 8000` stays as documentation of the default. |

## Cloud Run

| Rule | |
|---|---|
| C1 | One Cloud Run service, `community-centre`, in region `us-east4`, built from the repository with `gcloud run deploy --source .`. Cloud Build builds the `Dockerfile`; gcloud keeps the image in the Artifact Registry repository `cloud-run-source-deploy`, which it creates by itself. Nothing is pushed from the author's machine. |
| C2 | The service: 1 vCPU, 512 MiB, 0 to 1 instance, public (`--allow-unauthenticated`), CPU only during requests. HTTPS is provided by Cloud Run at the `run.app` address. |
| C3 | Two Cloud Run Jobs from the **same image as the service**, not rebuilt: `job-auto-decline` (`flask --app app auto-decline`) and `job-purge` (`flask --app app purge`). Each runs one task, gives up after 5 minutes and is retried once (as deploy Z4). A third job, `job-init-db` (`flask --app app init-db`), is run by hand. |
| C4 | Cloud Scheduler starts `job-auto-decline` at `0 * * * *` and `job-purge` at `30 * * * *`, both in UTC, through the Cloud Run Admin API, as a service account that may only run jobs. |
| C5 | `DATABASE_URL`, `SECRET_KEY` and `TEAM_EMAIL` are Secret Manager secrets, given to the service and the jobs as environment variables. They are typed or generated in the author's shell and piped to Secret Manager; they appear in no file, no command line and no shell history. |
| C6 | The service and the jobs run as a service account of their own, `community-centre-run`, which may read those three secrets and nothing else. |
| C7 | `TRUSTED_PROXY_HOPS=1`: Cloud Run's front end appends the visitor's address to `X-Forwarded-For`. Proved by U4 of deploy, adapted in `infra/README.md`. |
| C8 | `FRONTEND_DIST` stays as the image sets it. |
| C9 | A `.gcloudignore` in the repository root keeps from the upload to Cloud Build everything `.gitignore` keeps out of git, `.env` among it, and the `.git` folder. The `.dockerignore` still decides what goes into the image (deploy M1). |
| C10 | Artifact Registry keeps the two newest images and deletes the rest, so stored images stay under the free 0.5 GB. |

## Neon

| Rule | |
|---|---|
| N1 | The `DATABASE_URL` is Neon's connection string for a direct connection (connection pooling off, no `-pooler` in the host), with `sslmode=require`. |
| N2 | The tables are created by running `job-init-db` after the first deploy and after every redeploy. `init-db` is safe to repeat (deploy U1). |
| N3 | The admin account is created once with `flask --app app create-admin`, so the password is typed at a hidden prompt (F02 CL1). Cloud Run has no way into a running container, so this runs in the same image on the author's machine, with `docker run -it`, against Neon. |

## Keeping it awake

| Rule | |
|---|---|
| K1 | A cron-job.org job requests `GET https://<site>/health` every 5 minutes. `/health` reads the database (F03 R7), so one request wakes, or keeps awake, both the Cloud Run instance and the Neon compute. |
| K2 | The ping is a convenience, not a dependency: without it the site still works, and the first request after an idle spell waits while Cloud Run starts an instance and Neon resumes its compute, which can take several seconds. `/health` waits only 2 seconds for the database (F03 R7), so on a cold start it may answer `ok` with both last-run times `null`, once. |

## Running it

`infra/README.md`, "Cloud Run and Neon (current)", gives the exact commands, in order, for: the checks before the first run; the first run; creating the tables; creating the admin account; the scheduler; the ping; a smoke test; a redeploy; reading the logs; and removing everything.

| Rule | |
|---|---|
| U1 | A redeploy is `gcloud run deploy --source .` again, then pointing the three jobs at the new image and running `job-init-db`. It needs no secret. |
| U2 | The smoke test checks `/health`, the pages, plain HTTP, that both jobs have run, a cold start, and that the rate limit tells visitors apart (deploy U4). |

## Render, if chosen instead

| Rule | |
|---|---|
| R1 | Render's free tier has no scheduled jobs. On Render free the auto-decline and purge jobs do not run; the README records this as a known limitation, with how they ran on Azure and how they would run on a paid tier. |

## Known limits

- **A billing account is needed on Google Cloud**, even inside the free tier. A budget alert is the safeguard; it warns and does not stop anything.
- **The cold start** of K2, when the ping is not running or misses.
- **The ping uses Neon compute time.** Keeping the compute awake around the clock may use more of the free monthly compute allowance than idling would; check Neon's usage page after the first days (see "Proposed by the implementer").
- **Neon is in `us-east-2`, Cloud Run in `us-east4`**: every database query crosses between providers. Visitors in the UK are an ocean away from both.
- **`TRUSTED_PROXY_HOPS=1` is an assumption** until the rate-limit smoke test has passed.
- **The log holds client details**, as on Azure (deploy, Known limits): Cloud Logging keeps them 30 days by default.
- **The application connects as Neon's owner role.** A weaker database user is not set up.
- **No custom domain.** The site is at the `run.app` address.

## Where this differs

| Earlier document | Now |
|---|---|
| deploy M3: gunicorn on port 8000 | On `PORT`, 8000 when unset (P1, P2). |
| deploy Z1 to Z9: Azure resources | Cloud Run, Cloud Scheduler, Secret Manager and Neon (C1 to C10, N1). The Bicep file stays in the repository as the record of the Azure deployment. |
| deploy U2: `create-admin` inside the website's container | In the same image on the author's machine (N3). |
| deploy Z3: 7 days of backups | Neon's free tier keeps a restore history of hours, not days; the privacy notice's "up to 7 days" still holds. |

## Tests

`backend/tests/deploy/test_port.py` covers P1 to P4: it loads `backend/gunicorn.conf.py` with `PORT` set in different ways, and reads the default command of the `Dockerfile`. The image is checked by building it and starting it with `PORT=8080` (`infra/README.md`, "Try the image locally"). Everything about Cloud Run is checked by the smoke test, after a real deploy.

## Proposed by the implementer

To be confirmed or rejected by the author.

1. Region `us-east4` for Cloud Run and Cloud Scheduler: close to Neon's `us-east-2`, since every request to the site makes queries.
2. The jobs reuse the image the service was built with (C3), instead of `gcloud run jobs deploy --source .` three times: one build, guaranteed the same image, and fewer build minutes.
3. The settings file `backend/gunicorn.conf.py` (P1) instead of a shell-form `CMD` with `${PORT:-8000}`: it can be tested in Python, it keeps the exec-form `CMD`, and it refuses a bad `PORT` (P3).
4. `.gcloudignore` (C9). Without one, gcloud falls back to rules it makes itself; writing it down keeps `.env` out of the upload for certain.
5. The ping every 5 minutes (K1): Neon suspends a compute after 5 minutes without queries. If Neon's usage page shows the free allowance running out, ping only during UK daytime (cron-job.org can limit the hours) and accept cold starts at night.
6. 1 vCPU and 512 MiB (C2): the smallest that runs 2 gunicorn workers comfortably.
7. `TEAM_EMAIL` stays a secret, as on Azure.
8. `create-admin` with `docker run -it` on the author's machine (N3), from an image built locally from the same commit. No `--platform` flag is needed: that image only ever runs on the author's machine.
9. A direct Neon connection instead of the pooled one (N1). The application opens one connection per request and 2 workers need few connections; Neon's pooler (PgBouncer in transaction mode) restricts session features, and nothing is gained from it here.
