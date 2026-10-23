# community-centre-website
Website for a local community center in Coventry.
It assists the management team with bookings of the hall.
It has a landing page with general imformation and pictures of the community center, along with a form that users can fill to contact the management team.

## Running it locally

```
cp .env.example .env        # then change the values
make install                # backend virtual environment and frontend packages
docker compose up -d --wait db
cd backend && .venv/bin/flask --app app init-db
```

`make test` runs every test (it starts the database first) and `make lint` runs the linters.

## Creating the admin account

There is one admin account. Create it once, after `init-db`:

```
cd backend
.venv/bin/flask --app app create-admin --email admin@example.com
```

The command asks for the password twice at a hidden prompt; it is never given on the command line. The password must be 12 to 1024 characters with no control characters (tabs, line breaks and the like). The command refuses to run if an admin account already exists.

The admin logs in at `/admin`.

### Forgotten password

Emails are not sent yet; they are written to the application log. To reset the password, request a token, read it from the log (the line starting `Token:`), and set the new password. The token is valid for 30 minutes and works once.

```
POST /api/v1/admin/password-reset            {"email": "admin@example.com"}
POST /api/v1/admin/password-reset/confirm    {"token": "<token from the log>", "password": "<new password>"}
```

## The auto-decline job

A booking request left in "submitted" for 48 hours is declined automatically. This is done by a command that must be run **once an hour by a scheduler**; the application has no timer of its own, so if nothing runs the command, nothing is ever auto-declined.

```
cd backend
.venv/bin/flask --app app auto-decline
```

With cron, for example:

```
0 * * * * cd /path/to/community-centre-website/backend && .venv/bin/flask --app app auto-decline
```

Each successful run writes the line `Auto-decline run: N declined.` to the log, and `GET /health` reports `auto_decline_last_run`, the time of the last successful run in UTC (`null` if it has never run). A last-run time more than an hour old means the job is failing or is not being run.

## The purge job

Client details are deleted automatically six months after a request was submitted, leaving only the date and the outcome; the network address a request came from is deleted after 7 days. Like the auto-decline job, this is a command that must be run **once an hour by a scheduler**:

```
cd backend
.venv/bin/flask --app app purge
```

```
5 * * * * cd /path/to/community-centre-website/backend && .venv/bin/flask --app app purge
```

Each successful run writes `Purge run: N erased, M addresses removed.` to the log, and `GET /health` reports `purge_last_run`.

The purge does not reach the application log. While emails are written to the log instead of being sent, the log holds client names and contact details, so whoever keeps the logs must delete them within the same six months.

## Deleting a client's data on request

A client asks by phone or email. On the admin page, under "Delete client data", choose the booking and confirm. A booking's data can be deleted once the booking is declined or its event is over; for an upcoming booking, decline it first. Deletion cannot be undone.

## Terms and privacy notice

The booking form links to `/terms` and `/privacy`. Both show the centre's name, address, phone and email from `frontend/src/centre.js`, which holds placeholders. **Fill in the real details, and have the text checked, before the site goes live.**



## Deployment

Live: **<live URL: the `run.app` address printed by step 4 of the first run>**

The site runs on Google Cloud Run's free tier as one container image that serves the built frontend and the API, with its database on Neon's free tier. Cloud Scheduler runs the auto-decline and purge jobs as Cloud Run Jobs, at minute 0 and minute 30 of every hour. The commands for a first run, a redeploy and the smoke test are in `infra/README.md`; the rules are in `docs/specs/deploy-free.md`.

It ran on Azure Container Apps until the Azure for Students subscription expired in October 2026 (`docs/specs/deploy.md`).

The first visit after a quiet spell can take several seconds while Cloud Run starts the site and Neon wakes the database; a ping every 5 minutes keeps both awake.
