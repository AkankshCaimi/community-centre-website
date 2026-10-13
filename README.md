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

