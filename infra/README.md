# Deploying to Azure

Step-by-step commands for the demonstration site. The rules behind them are in `docs/specs/deploy.md`.

Run every command from the repository root, in one terminal session: later steps use the variables set by earlier ones. The commands are written for zsh on macOS.

## What gets created

One resource group holding: the website (a Container App that scales to zero), three jobs (auto-decline at minute 0, purge at minute 30, and `init-db` started by hand), a PostgreSQL Flexible Server (B1ms), a container registry (Basic), a Log Analytics workspace (30 days), and a monthly budget with email alerts.

Secrets never go into a file. The database password and `SECRET_KEY` are made in your shell, passed to Azure as secure parameters, and kept there as Container App secrets.

## Before the first run

```
az login
az account set --subscription "Azure for Students"
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.DBforPostgreSQL --wait
az provider register -n Microsoft.ContainerRegistry --wait
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.Consumption --wait
```

## Try the image locally (optional)

Needs the Docker Compose database running (`make db-up`).

```
docker build -t community-centre:local .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql://community_centre:change-me@host.docker.internal:5432/community_centre \
  -e SECRET_KEY=local -e TEAM_EMAIL=team@example.com \
  community-centre:local
```

Open http://localhost:8000. The admin login does not work over plain HTTP, because its cookie is `Secure`.

## First run

### 1. Names and secrets

```
RG=rg-community-centre
TEAM_EMAIL=<address that should receive booking notifications>
ALERT_EMAIL=Akanksh.Caimi@warwick.ac.uk

DB_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -hex 32)
TAG=$(git rev-parse --short HEAD)
```

`DB_PASSWORD` and `SECRET_KEY` exist only in this terminal. If you close it before step 4 has finished, start again from here. Afterwards you do not need them: a redeploy uses neither.

### 2. Resource group, registry, database, logs and budget

```
az group create -n $RG -l uksouth

az deployment group validate -g $RG -f infra/main.bicep \
  -p deployApps=false dbPassword=$DB_PASSWORD secretKey=$SECRET_KEY \
     teamEmail=$TEAM_EMAIL alertEmail=$ALERT_EMAIL

az deployment group create -g $RG -f infra/main.bicep \
  -p deployApps=false dbPassword=$DB_PASSWORD secretKey=$SECRET_KEY \
     teamEmail=$TEAM_EMAIL alertEmail=$ALERT_EMAIL
```

The database takes several minutes.

If this fails on the budget (some subscriptions, Azure for Students among them, may not support budgets), add `deployBudget=false` to this command and to the one in step 4, and watch the credit balance on the Azure sponsorship page instead.

If it fails because the region is not allowed for your subscription, delete the group (`az group delete -n $RG`) and start step 2 again with another region in place of `uksouth`.

### 3. Build the image in Azure

```
ACR=$(az acr list -g $RG --query "[0].name" -o tsv)
az acr build -r $ACR -t community-centre:$TAG .
```

### 4. The website and the three jobs

```
az deployment group create -g $RG -f infra/main.bicep \
  -p deployApps=true imageTag=$TAG dbPassword=$DB_PASSWORD secretKey=$SECRET_KEY \
     teamEmail=$TEAM_EMAIL alertEmail=$ALERT_EMAIL
```

### 5. Create the tables

```
az containerapp job start -g $RG -n job-init-db
az containerapp job execution list -g $RG -n job-init-db \
  --query "[].{started:properties.startTime, status:properties.status}" -o table
```

Repeat the second command until the status is `Succeeded`.

### 6. Create the admin account (once)

Open the site in a browser first, so that a replica is running, then:

```
SITE=$(az containerapp show -g $RG -n ca-community-centre \
  --query properties.configuration.ingress.fqdn -o tsv)
echo https://$SITE

az containerapp exec -g $RG -n ca-community-centre \
  --command "flask --app app create-admin --email <admin address>"
```

The password is asked for twice at a hidden prompt: 12 to 1024 characters. A second run answers "An admin account already exists."

## Smoke test

### The site is up

```
curl -s https://$SITE/health
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" https://$SITE/
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" https://$SITE/api/v1/no-such-thing
curl -s -o /dev/null -w "%{http_code}\n" http://$SITE/health
```

Expected: `{"auto_decline_last_run":…,"purge_last_run":…,"status":"ok"}`; `200 text/html`; `404 application/json`; and for plain HTTP a redirect (`301`) and never `200`.

Then in a browser: the home page with its pictures, each page from the navigation, `/admin` and a login with the account from step 6.

### The jobs run

After the next full hour and half hour:

```
az containerapp job execution list -g $RG -n job-auto-decline \
  --query "[].{started:properties.startTime, status:properties.status}" -o table
az containerapp job execution list -g $RG -n job-purge \
  --query "[].{started:properties.startTime, status:properties.status}" -o table
curl -s https://$SITE/health
```

Expected: `Succeeded` runs, and both last-run times in `/health` no longer `null`.

### The rate limit tells visitors apart

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

## Redeploy

After merging to `main`. No secret is needed.

```
RG=rg-community-centre
ACR=$(az acr list -g $RG --query "[0].name" -o tsv)
TAG=$(git rev-parse --short HEAD)
IMAGE=$ACR.azurecr.io/community-centre:$TAG

az acr build -r $ACR -t community-centre:$TAG .

az containerapp update -g $RG -n ca-community-centre --image $IMAGE
az containerapp job update -g $RG -n job-auto-decline --image $IMAGE
az containerapp job update -g $RG -n job-purge --image $IMAGE
az containerapp job update -g $RG -n job-init-db --image $IMAGE

az containerapp job start -g $RG -n job-init-db
```

Then repeat "The site is up" from the smoke test.

A change to `infra/main.bicep` itself needs step 4 of the first run again, and that needs the two secrets. If you no longer have them, make new ones as in step 1: the deployment then changes the database password and the stored secrets together.

## Reading the logs

```
az containerapp logs show -g $RG -n ca-community-centre --tail 100
```

The logged emails are here, and so is the admin's password-reset token (`README.md`, "Forgotten password"). The log holds client names and contact details; it is kept 30 days.

## Removing everything

```
az group delete -n rg-community-centre
```

This deletes the database and its backups. It cannot be undone.

## What differs from a developer's machine

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
