#!/bin/sh
# Runs once, when the database volume is first created.
# Creates the empty database the tests connect to.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE DATABASE \"${POSTGRES_DB}_test\";"
