# Deployment

The site runs on Google Cloud Run with a Neon database, both on free tiers. It ran on Azure Container Apps until the Azure for Students subscription expired in October 2026; the Azure commands are kept below as the record of that deployment.

## Cloud Run and Neon (current)

The site runs on Google Cloud Run's free tier, with its database on Neon's free tier. The rules behind these commands are in `docs/specs/deploy-free.md`. The Azure deployment it replaced is kept below, under "Azure Container Apps (until October 2026)", as the record of how it ran.

Run every command from the repository root, in one terminal session: later steps use the variables set by earlier ones. The commands are written for zsh on macOS and need the Google Cloud CLI (`brew install --cask google-cloud-sdk`) and Docker (`colima start`) for the admin step.

### What gets created

In the Google Cloud project `community-centre`, region `us-east4`:

- the website, a Cloud Run service built from this repository by Cloud Build, scaling to zero;
- three Cloud Run Jobs from the same image: `job-auto-decline`, `job-purge`, and `job-init-db` run by hand;
- two Cloud Scheduler jobs that start auto-decline at minute 0 and the purge at minute 30 of every hour, UTC;
- three Secret Manager secrets: `database-url`, `secret-key`, `team-email`;
- two service accounts: `community-centre-run` (the website and the jobs, may read the three secrets) and `community-centre-scheduler` (may start the two hourly jobs);
- the Artifact Registry repository `cloud-run-source-deploy`, which gcloud creates by itself on the first deploy to keep the built image.

The database is a Neon project you create in the browser. A cron-job.org job keeps both awake.

Secrets never go into a file, a command line or the shell history: they are typed at a hidden prompt or generated, and piped straight into Secret Manager.

### Before the first run

#### Neon

1. Sign in at https://console.neon.tech and create a project (Postgres 16 or later, any region; `us-east-2` is close to `us-east4`).
2. On the project dashboard, open **Connect**. Turn **Connection pooling off**, so the string's host has no `-pooler`: the application opens one connection per request and needs no pooler, and a direct connection avoids the pooler's limits on session features.
3. Copy the connection string. It must contain `sslmode=require`; leave `channel_binding=require` in if Neon shows it. Keep it on the clipboard for step 3 of the first run, and do not paste it anywhere else.

#### Google Cloud

```
PROJECT_ID=community-centre
REGION=us-east4

gcloud auth login
gcloud projects describe $PROJECT_ID || gcloud projects create $PROJECT_ID
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

If `projects create` answers that the ID is taken (project IDs are unique across all of Google Cloud), choose another, set `PROJECT_ID` to it, and use it everywhere below.

Cloud Run needs a billing account linked to the project, even within the free tier:

```
gcloud billing accounts list
BILLING=<ACCOUNT_ID from the list>
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING
gcloud billing projects describe $PROJECT_ID --format='value(billingEnabled)'
```

Expected: `True`. Then a budget alert, the safeguard if anything leaves the free tier. Write the amount in the billing account's currency (`gcloud billing accounts describe $BILLING` shows it), for example `5GBP` or `5USD`:

```
gcloud services enable billingbudgets.googleapis.com
gcloud billing budgets create --billing-account=$BILLING \
  --display-name=community-centre --budget-amount=5GBP \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.8 --threshold-rule=percent=1.0
```

The alerts go to the billing account's administrators by email. They warn and stop nothing.

Turn on the services used:

```
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com
```

### Try the image locally (optional)

Checks that the image listens on the port it is given (spec P1). Needs the Docker Compose database running (`make db-up`).

```
docker build -t community-centre:local .
docker run --rm -p 8080:8080 -e PORT=8080 \
  -e DATABASE_URL=postgresql://community_centre:change-me@host.docker.internal:5432/community_centre \
  -e SECRET_KEY=local -e TEAM_EMAIL=team@example.com \
  community-centre:local
```

In another terminal: `curl -s http://localhost:8080/health`. Expected: `{"auto_decline_last_run":…,"purge_last_run":…,"status":"ok"}`, and the container's log shows `Listening at: http://0.0.0.0:8080`. Without `-e PORT=8080` (and with `-p 8000:8000`) it listens on 8000, as before.

### First run

#### 1. Names

```
PROJECT_ID=community-centre
REGION=us-east4
SERVICE=community-centre
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
RUN_SA=community-centre-run@$PROJECT_ID.iam.gserviceaccount.com
SCHED_SA=community-centre-scheduler@$PROJECT_ID.iam.gserviceaccount.com
SECRETS=DATABASE_URL=database-url:latest,SECRET_KEY=secret-key:latest,TEAM_EMAIL=team-email:latest
```

#### 2. Service accounts and the build's permission

```
gcloud iam service-accounts create community-centre-run \
  --display-name="Community centre website and jobs"
gcloud iam service-accounts create community-centre-scheduler \
  --display-name="Starts the community centre hourly jobs"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/run.builder
```

The last command lets Cloud Build, which runs as the project's default compute account, build from source and store the image. Without it a new project's first `--source` deploy fails with a permission error naming that account.

#### 3. Secrets

The connection string, at a hidden prompt (paste it, press Enter):

```
read -rs "DATABASE_URL?Neon connection string: "; echo
case "$DATABASE_URL" in *sslmode=require*) echo "sslmode ok" ;; *) echo "MISSING sslmode=require" ;; esac
printf '%s' "$DATABASE_URL" | gcloud secrets create database-url --data-file=-
unset DATABASE_URL
```

If it says `MISSING sslmode=require`, do not continue: run `gcloud secrets delete database-url` if the secret was created, copy the string from Neon again, and repeat.

A fresh `SECRET_KEY`, generated straight into Secret Manager and never shown:

```
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create secret-key --data-file=-
```

The team's address:

```
read -r "TEAM_EMAIL?Address that should receive booking notifications: "
printf '%s' "$TEAM_EMAIL" | gcloud secrets create team-email --data-file=-
```

Let the website and the jobs read the three, and nothing else:

```
for SECRET in database-url secret-key team-email; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member=serviceAccount:$RUN_SA --role=roles/secretmanager.secretAccessor
done
```

#### 4. The website

```
gcloud run deploy $SERVICE --source . \
  --service-account=$RUN_SA \
  --allow-unauthenticated \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=1 --cpu-throttling \
  --set-env-vars=TRUSTED_PROXY_HOPS=1 \
  --set-secrets=$SECRETS
```

The first time, gcloud asks to create the Artifact Registry repository `cloud-run-source-deploy`: answer `Y`. Cloud Build then builds the `Dockerfile` (a few minutes) and Cloud Run starts it. Cloud Run sets `PORT` (8080) itself. The command ends with the service's URL.

```
URL=$(gcloud run services describe $SERVICE --format='value(status.url)')
echo $URL
```

Keep only the two newest images, so stored images stay under the free 0.5 GB:

```
cat > /tmp/cleanup-policy.json <<'EOF'
[
  {"name": "keep-two-newest", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}},
  {"name": "delete-the-rest", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}
]
EOF
gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy \
  --location=$REGION --policy=/tmp/cleanup-policy.json --no-dry-run
```

#### 5. The jobs

The jobs use the exact image the website runs, by its digest, so nothing is built twice:

```
REVISION=$(gcloud run services describe $SERVICE --format='value(status.latestReadyRevisionName)')
IMAGE=$(gcloud run revisions describe $REVISION --format='value(status.imageDigest)')
echo $IMAGE

for JOB in auto-decline purge init-db; do
  gcloud run jobs deploy job-$JOB --image=$IMAGE \
    --command=flask --args=--app,app,$JOB \
    --service-account=$RUN_SA \
    --tasks=1 --max-retries=1 --task-timeout=5m \
    --cpu=1 --memory=512Mi \
    --set-secrets=$SECRETS
done
```

`echo $IMAGE` should print an address ending in `@sha256:` and a long hexadecimal digest. If it is empty, the website's deploy in step 4 did not finish: run step 4 again.

#### 6. Create the tables

```
gcloud run jobs execute job-init-db --wait
```

Expected: the execution completes. Its log says `Database schema applied.`:

```
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="job-init-db"' \
  --limit=5 --format='value(textPayload)'
```

#### 7. Create the admin account (once)

Cloud Run has no way into a running container, so this runs the same commit's image on your machine, against Neon. The password is typed at a hidden prompt (12 to 1024 characters, twice). Docker must be running (`colima start`).

```
docker build -t community-centre:local .
DATABASE_URL=$(gcloud secrets versions access latest --secret=database-url)
docker run -it --rm -e DATABASE_URL community-centre:local \
  flask --app app create-admin --email <admin address>
unset DATABASE_URL
```

`-e DATABASE_URL` with no value passes the variable from your shell, so the string is not on the command line. A second run answers "An admin account already exists."

#### 8. The hourly schedule

Let the scheduler's account start the two jobs, then schedule them:

```
for JOB in auto-decline purge; do
  gcloud run jobs add-iam-policy-binding job-$JOB \
    --member=serviceAccount:$SCHED_SA --role=roles/run.invoker
done

gcloud scheduler jobs create http run-auto-decline --location=$REGION \
  --schedule="0 * * * *" --time-zone=UTC \
  --uri="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/job-auto-decline:run" \
  --http-method=POST --oauth-service-account-email=$SCHED_SA

gcloud scheduler jobs create http run-purge --location=$REGION \
  --schedule="30 * * * *" --time-zone=UTC \
  --uri="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/job-purge:run" \
  --http-method=POST --oauth-service-account-email=$SCHED_SA
```

The free tier covers three scheduler jobs per billing account; this uses two.

#### 9. The ping (cron-job.org)

Neon suspends its compute after 5 minutes without queries, and Cloud Run stops its instance after a spell without requests. One request to `/health`, which reads the database, wakes both.

1. Sign up at https://cron-job.org (free) and confirm the email.
2. **Create cronjob**:
   - Title: `community-centre health`
   - URL: the value of `echo $URL/health`
   - Execution schedule: **Every 5 minutes**
3. Under **Advanced**: request method `GET`; timeout 30 seconds; treat redirects as failure off.
4. Under **Notifications**: notify on failure, and when the job is disabled after too many failures.
5. Save, then **Test run**. Expected: status `200`, body `{"auto_decline_last_run":…,"status":"ok"}`.

After a few days, check **Usage** in the Neon console. If the free monthly compute allowance is running short, set the cron-job.org schedule to UK daytime hours only (for example every 5 minutes from 07:00 to 22:00, time zone Europe/London) and accept a cold start for the first visitor at night.

### Smoke test

#### The site is up

```
curl -s $URL/health; echo
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" $URL/
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" $URL/api/v1/no-such-thing
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://${URL#https://}/health
```

Expected, in order:

1. `{"auto_decline_last_run":…,"purge_last_run":…,"status":"ok"}`;
2. `200 text/html; charset=utf-8`;
3. `404 application/json`;
4. a redirect (`301`, `302` or `307`) to the `https://` address, and never `200`.

Then in a browser, at `$URL`: the home page with its pictures, each page from the navigation, `/terms`, `/privacy`, `/admin`, and a login with the account from step 7. The login only works over HTTPS: its cookie is `Secure`.

#### The jobs run

Start each once now, rather than waiting for the hour:

```
gcloud scheduler jobs run run-auto-decline --location=$REGION
gcloud scheduler jobs run run-purge --location=$REGION
```

A minute later:

```
gcloud run jobs executions list --job=job-auto-decline --limit=3
gcloud run jobs executions list --job=job-purge --limit=3
curl -s $URL/health; echo
```

Expected: a completed execution of each (`✔`, 1/1 tasks succeeded), and both last-run times in `/health` no longer `null`. After the next full hour and half hour, run the three commands again: there should be a new execution of each, started by the scheduler, and later last-run times.

If an execution is missing, `gcloud scheduler jobs describe run-auto-decline --location=$REGION` shows the last attempt's status. A `PERMISSION_DENIED` there means the `run.invoker` binding of step 8 is missing.

#### A cold start

Pause the cron-job.org job, wait 20 minutes (the Cloud Run instance stops, the Neon compute suspends), then:

```
for i in 1 2; do curl -s -w "  %{http_code} in %{time_total}s\n" $URL/health; done
```

Expected: both `200`. The first takes several seconds: Cloud Run starts an instance and Neon resumes its compute. The second is quick. If the database is still waking up, the first may show `null` for both last-run times: `/health` waits only 2 seconds for the database (F03 R7) and still answers `ok`, with a warning `could not be read: OperationalError` in the log. That is a cold start, not a fault. The second request shows the real times.

Resume the cron-job.org job afterwards.

#### The rate limit tells visitors apart

This proves `TRUSTED_PROXY_HOPS=1` is right for Cloud Run (spec C7). **Do it last**: it uses up the allowance of your own network for 24 hours and leaves test requests, which lapse by themselves after 48 hours (or decline them on the admin page).

1. From your computer, six requests. Each is a different person on a different day, so only the rate limit can refuse one:

   ```
   for i in 1 2 3 4 5 6; do
     DAY=$(date -v+$((20 + i))d +%F)
     curl -s -o /dev/null -w "request $i: %{http_code}\n" $URL/api/v1/bookings \
       -H "Content-Type: application/json" \
       -d "{\"name\":\"Rate Test $i\",\"email\":\"rate$i@example.com\",\"phone\":\"07700 90010$i\",\"guest_count\":40,\"starts_at\":\"${DAY}T10:00\",\"ends_at\":\"${DAY}T14:00\",\"terms_accepted\":true,\"privacy_notice_accepted\":true,\"captcha_token\":\"token\"}"
   done
   ```

   Expected: `201` five times, then `429`.

2. From the same computer, claim to be someone else:

   ```
   DAY=$(date -v+30d +%F)
   curl -s -o /dev/null -w "spoofed: %{http_code}\n" $URL/api/v1/bookings \
     -H "Content-Type: application/json" -H "X-Forwarded-For: 203.0.113.9" \
     -d "{\"name\":\"Rate Test 7\",\"email\":\"rate7@example.com\",\"phone\":\"07700 900107\",\"guest_count\":40,\"starts_at\":\"${DAY}T10:00\",\"ends_at\":\"${DAY}T14:00\",\"terms_accepted\":true,\"privacy_notice_accepted\":true,\"captcha_token\":\"token\"}"
   ```

   Expected: `429`. A `201` means the application believes an address the visitor made up.

3. From a phone on mobile data (not your Wi-Fi), fill in the booking form on the site.

   Expected: the request is accepted. "Too many responses submitted" means the application sees one address for every visitor.

4. Confirm which address was recorded for your own requests. In the Neon console, **SQL Editor**:

   ```
   SELECT name, client_ip FROM bookings WHERE name LIKE 'Rate Test%' ORDER BY id;
   ```

   Expected: your own public address (compare with `curl -s https://api.ipify.org`) on every row, and the phone's on its booking. A Google address (for example `169.254.…` or one in `35.…`) means the application is reading the wrong entry of `X-Forwarded-For`.

If step 1 never reaches `429`, or steps 2 to 4 fail, the setting is wrong: tell the developer before the site is shared. The likely change is `TRUSTED_PROXY_HOPS=2` (`gcloud run services update $SERVICE --update-env-vars=TRUSTED_PROXY_HOPS=2`), then this whole test again on another day.

### Redeploy

After merging to `main`. No secret is needed: the service keeps its settings and secrets.

```
PROJECT_ID=community-centre
REGION=us-east4
SERVICE=community-centre
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

git switch main && git pull
gcloud run deploy $SERVICE --source .

REVISION=$(gcloud run services describe $SERVICE --format='value(status.latestReadyRevisionName)')
IMAGE=$(gcloud run revisions describe $REVISION --format='value(status.imageDigest)')
for JOB in auto-decline purge init-db; do
  gcloud run jobs update job-$JOB --image=$IMAGE
done

gcloud run jobs execute job-init-db --wait
URL=$(gcloud run services describe $SERVICE --format='value(status.url)')
```

Then repeat "The site is up" from the smoke test.

To change a secret, add a new version: for example `openssl rand -hex 32 | tr -d '\n' | gcloud secrets versions add secret-key --data-file=-`, then `gcloud run services update $SERVICE --update-secrets=SECRET_KEY=secret-key:latest` to start a new revision that reads it. Changing `SECRET_KEY` logs the admin out.

### Reading the logs

```
gcloud run services logs read $SERVICE --limit=100
gcloud logging read 'resource.type="cloud_run_job"' --limit=50 --format='value(timestamp, resource.labels.job_name, textPayload)'
```

The logged emails are here, and so is the admin's password-reset token (`README.md`, "Forgotten password"). The log holds client names and contact details; Cloud Logging keeps it 30 days.

### Removing everything

```
gcloud projects delete $PROJECT_ID
```

This deletes the website, the jobs, the schedule, the secrets and the images; a deleted project can be restored for 30 days. The database is separate: delete the project in the Neon console (**Settings**, **Delete project**), which cannot be undone. Disable the cron-job.org job too.

### If Render instead

Render's free web service runs the same image (it also sets `PORT`) and would take the same `DATABASE_URL`, `SECRET_KEY`, `TEAM_EMAIL` and a `TRUSTED_PROXY_HOPS` proved by the same rate-limit test. **Its free tier has no scheduled jobs** (spec R1), so on Render free:

- **Auto-decline does not run.** Requests left in "submitted" stay there; the admin has to decline them by hand. `/health` shows `auto_decline_last_run` falling behind.
- **The purge does not run.** Client details are not deleted after six months, nor network addresses after 7 days, which the privacy notice promises. Run `flask --app app purge` by hand (as in step 7, with `docker run`) at least weekly, or do not take real bookings.

On Azure the two ran as Container Apps Jobs on a schedule, at minute 0 and minute 30 of every hour (below, and `docs/specs/deploy.md`, Z4). On a paid Render plan they would be two Render Cron Jobs from the same image, with the commands `flask --app app auto-decline` (schedule `0 * * * *`) and `flask --app app purge` (`30 * * * *`) and the same environment as the website.

### What differs from a developer's machine

| | Development | Cloud Run |
|---|---|---|
| Web server | `flask run`, debug possible | gunicorn, 2 workers, debug off, on `PORT` |
| Frontend | Vite, on its own port | built into the image and served by Flask (`FRONTEND_DIST`) |
| Database | Docker Compose | Neon, TLS required |
| `SECRET_KEY`, database password | `change-me` in `.env` | random, held in Secret Manager |
| `TRUSTED_PROXY_HOPS` | 0 | 1 |
| Jobs | run by hand | Cloud Run Jobs, started hourly by Cloud Scheduler |
| `.env` | read | not uploaded, not in the image |
| HTTPS | none | at Cloud Run's front end; plain HTTP redirected |

## Azure Container Apps (until October 2026)

The subscription behind this has expired and these resources no longer exist.

Step-by-step commands for the demonstration site. The rules behind them are in `docs/specs/deploy.md`.

Run every command from the repository root, in one terminal session: later steps use the variables set by earlier ones. The commands are written for zsh on macOS.

### What gets created

One resource group holding: the website (a Container App that scales to zero), three jobs (auto-decline at minute 0, purge at minute 30, and `init-db` started by hand), a PostgreSQL Flexible Server (B1ms), a container registry (Basic), a Log Analytics workspace (30 days), and a monthly budget with email alerts.

Secrets never go into a file. The database password and `SECRET_KEY` are made in your shell, passed to Azure as secure parameters, and kept there as Container App secrets.

### Before the first run

```
az login
az account set --subscription "Azure for Students"
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.DBforPostgreSQL --wait
az provider register -n Microsoft.ContainerRegistry --wait
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.Consumption --wait
```

### Try the image locally (optional)

Needs the Docker Compose database running (`make db-up`).

```
docker build -t community-centre:local .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql://community_centre:change-me@host.docker.internal:5432/community_centre \
  -e SECRET_KEY=local -e TEAM_EMAIL=team@example.com \
  community-centre:local
```

Open http://localhost:8000. The admin login does not work over plain HTTP, because its cookie is `Secure`.

### First run

#### 1. Names and secrets

```
RG=rg-community-centre
LOC=francecentral
TEAM_EMAIL=<address that should receive booking notifications>
ALERT_EMAIL=Akanksh.Caimi@warwick.ac.uk

DB_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -hex 32)
TAG=$(git rev-parse --short HEAD)
```

`DB_PASSWORD` and `SECRET_KEY` exist only in this terminal. If you close it before step 4 has finished, start again from here. Afterwards you do not need them: a redeploy uses neither.

#### 2. Resource group, registry, database, logs and budget

```
az group create -n $RG -l $LOC

az deployment group validate -g $RG -n base -f infra/main.bicep \
  -p deployApps=false dbPassword=$DB_PASSWORD secretKey=$SECRET_KEY \
     teamEmail=$TEAM_EMAIL alertEmail=$ALERT_EMAIL

az deployment group create -g $RG -n base -f infra/main.bicep \
  -p deployApps=false dbPassword=$DB_PASSWORD secretKey=$SECRET_KEY \
     teamEmail=$TEAM_EMAIL alertEmail=$ALERT_EMAIL
```

The database takes several minutes.

If this fails on the budget (some subscriptions, Azure for Students among them, may not support budgets), add `deployBudget=false` to this command and to the one in step 4, and watch the credit balance on the Azure sponsorship page instead.

If it fails because the region is not allowed for your subscription, delete the group (`az group delete -n $RG`), set `LOC` to another region and start step 2 again.

#### 3. Build the image and push it

The image is built on your machine, for the processor Azure runs on, and pushed to the registry. Docker must be running (`colima start`).

```
ACR=$(az acr list -g $RG --query "[0].name" -o tsv)
IMAGE=$ACR.azurecr.io/community-centre:$TAG

az acr login -n $ACR
docker buildx build --platform linux/amd64 --load -t $IMAGE .
docker push $IMAGE
```

On an Apple-silicon Mac the build is emulated and takes a few minutes.

#### 4. The website and the three jobs

```
az deployment group validate -g $RG -n apps -f infra/main.bicep \
  -p deployApps=true imageTag=$TAG dbPassword=$DB_PASSWORD secretKey=$SECRET_KEY \
     teamEmail=$TEAM_EMAIL alertEmail=$ALERT_EMAIL

az deployment group create -g $RG -n apps -f infra/main.bicep \
  -p deployApps=true imageTag=$TAG dbPassword=$DB_PASSWORD secretKey=$SECRET_KEY \
     teamEmail=$TEAM_EMAIL alertEmail=$ALERT_EMAIL
```

#### 5. Create the tables

```
az containerapp job start -g $RG -n job-init-db
az containerapp job execution list -g $RG -n job-init-db \
  --query "[].{started:properties.startTime, status:properties.status}" -o table
```

Repeat the second command until the status is `Succeeded`.

#### 6. Create the admin account (once)

Open the site in a browser first, so that a replica is running, then:

```
SITE=$(az containerapp show -g $RG -n ca-community-centre \
  --query properties.configuration.ingress.fqdn -o tsv)
echo https://$SITE

az containerapp exec -g $RG -n ca-community-centre \
  --command "flask --app app create-admin --email <admin address>"
```

The password is asked for twice at a hidden prompt: 12 to 1024 characters. A second run answers "An admin account already exists."

### Smoke test

#### The site is up

```
curl -s https://$SITE/health
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" https://$SITE/
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" https://$SITE/api/v1/no-such-thing
curl -s -o /dev/null -w "%{http_code}\n" http://$SITE/health
```

Expected: `{"auto_decline_last_run":…,"purge_last_run":…,"status":"ok"}`; `200 text/html`; `404 application/json`; and for plain HTTP a redirect (`301`) and never `200`.

Then in a browser: the home page with its pictures, each page from the navigation, `/admin` and a login with the account from step 6.

#### The jobs run

After the next full hour and half hour:

```
az containerapp job execution list -g $RG -n job-auto-decline \
  --query "[].{started:properties.startTime, status:properties.status}" -o table
az containerapp job execution list -g $RG -n job-purge \
  --query "[].{started:properties.startTime, status:properties.status}" -o table
curl -s https://$SITE/health
```

Expected: `Succeeded` runs, and both last-run times in `/health` no longer `null`.

#### The rate limit tells visitors apart

This proves `TRUSTED_PROXY_HOPS=1` is right for Azure. **Do it last**: it uses up the allowance of your own network for 24 hours and leaves five test requests, which lapse by themselves after 48 hours (or decline them on the admin page).

1. From your computer, send six requests. Each is a different person on a different day, so only the rate limit can refuse one:

   ```
   for i in 1 2 3 4 5 6; do
     DAY=$(date -v+$((20 + i))d +%F)
     curl -s -o /dev/null -w "request $i: %{http_code}\n" https://$SITE/api/v1/bookings \
       -H "Content-Type: application/json" \
       -d "{\"name\":\"Rate Test $i\",\"email\":\"rate$i@example.com\",\"phone\":\"07700 90010$i\",\"guest_count\":40,\"starts_at\":\"${DAY}T10:00\",\"ends_at\":\"${DAY}T14:00\",\"terms_accepted\":true,\"privacy_notice_accepted\":true,\"captcha_token\":\"token\"}"
   done
   ```

   Expected: `201` five times, then `429`.

2. From the same computer, claim to be someone else:

   ```
   DAY=$(date -v+30d +%F)
   curl -s -o /dev/null -w "spoofed: %{http_code}\n" https://$SITE/api/v1/bookings \
     -H "Content-Type: application/json" -H "X-Forwarded-For: 203.0.113.9" \
     -d "{\"name\":\"Rate Test 7\",\"email\":\"rate7@example.com\",\"phone\":\"07700 900107\",\"guest_count\":40,\"starts_at\":\"${DAY}T10:00\",\"ends_at\":\"${DAY}T14:00\",\"terms_accepted\":true,\"privacy_notice_accepted\":true,\"captcha_token\":\"token\"}"
   ```

   Expected: `429`. A `201` means the application believes an address the visitor made up.

3. From a phone on mobile data (not your Wi-Fi), fill in the booking form on the site.

   Expected: the request is accepted. "Too many responses submitted" means the application sees one address for every visitor.

If step 1 never reaches `429`, or step 2 or 3 fails, the setting is wrong: tell the developer before the site is shared.

### Redeploy

After merging to `main`. No secret is needed.

```
RG=rg-community-centre
ACR=$(az acr list -g $RG --query "[0].name" -o tsv)
TAG=$(git rev-parse --short HEAD)
IMAGE=$ACR.azurecr.io/community-centre:$TAG

az acr login -n $ACR
docker buildx build --platform linux/amd64 --load -t $IMAGE .
docker push $IMAGE

az containerapp update -g $RG -n ca-community-centre --image $IMAGE
az containerapp job update -g $RG -n job-auto-decline --image $IMAGE
az containerapp job update -g $RG -n job-purge --image $IMAGE
az containerapp job update -g $RG -n job-init-db --image $IMAGE

az containerapp job start -g $RG -n job-init-db
```

Then repeat "The site is up" from the smoke test.

A change to `infra/main.bicep` itself needs step 4 of the first run again, and that needs the two secrets. If you no longer have them, make new ones as in step 1: the deployment then changes the database password and the stored secrets together.

### Notes from the first deployment

What the first real deployment, on an Azure for Students subscription, ran into. The commands above already allow for all of it.

#### The environment must not be an express environment

The first deployment failed at the three jobs with "Job resources are not supported on express environments". Azure had created the Container Apps environment in express mode, which has no jobs. `infra/main.bicep` now sets `environmentMode: 'WorkloadProfiles'` with the `Consumption` profile (spec Z9).

An environment that already exists in express mode has to go first, with the website in it. Whether Azure would change the mode of an existing environment in place is not known, so remove both and let step 4 create them again. The database, the registry and the logs are not touched; the site gets a new address.

```
az containerapp delete -g $RG -n ca-community-centre --yes
az containerapp env delete -g $RG -n cae-community-centre --yes
```

Then run step 4 of the first run. To see the mode of an environment:

```
az rest --method get --url "$(az containerapp env show -g $RG -n cae-community-centre --query id -o tsv)?api-version=2026-07-01" \
  --query properties.environmentMode -o tsv
```

Expected after the fix: `WorkloadProfiles`.

#### ACR Tasks are not permitted

`az acr build` is refused on this subscription. The image is therefore built locally with `docker buildx build --platform linux/amd64 --load` and pushed with `docker push`, after `az acr login` (step 3 and "Redeploy"). `--platform linux/amd64` matters on an Apple-silicon Mac: without it the image is built for the wrong processor and the container does not start in Azure.

#### Each deployment phase needs its own name

Without `-n`, both phases are named `main` after the file, and the second collides with the first. The commands name them: `-n base` for step 2 and `-n apps` for step 4.

#### The region

The resources are in `francecentral`. `LOC` in step 1 sets it.

### Reading the logs

```
az containerapp logs show -g $RG -n ca-community-centre --tail 100
```

The logged emails are here, and so is the admin's password-reset token (`README.md`, "Forgotten password"). The log holds client names and contact details; it is kept 30 days.

### Removing everything

```
az group delete -n rg-community-centre
```

This deletes the database and its backups. It cannot be undone.

### What differs from a developer's machine

| | Development | Azure |
|---|---|---|
| Web server | `flask run`, debug possible | gunicorn, 2 workers, debug off |
| Frontend | Vite, on its own port | built into the image and served by Flask (`FRONTEND_DIST`) |
| Database | Docker Compose | Flexible Server, TLS required |
| `SECRET_KEY`, database password | `change-me` in `.env` | random, held as Azure secrets |
| `TRUSTED_PROXY_HOPS` | 0 | 1 |
| Jobs | run by hand | Container Apps Jobs, hourly |
| `.env` | read | not in the image |
| HTTPS | none | at Azure's ingress; plain HTTP refused |
