#!/bin/sh
# Runs once, automatically, via Postgres's docker-entrypoint-initdb.d
# mechanism -- only when the data volume is empty (first boot).
#
# This is a shell script, not Python, even though CLAUDE.md says repo
# tooling under tools/ must be Python: that rule scopes to tools/, not to
# container-init scripts under infra/. It has to be .sh (not .sql) because
# docker-entrypoint-initdb.d only runs .sh/.sql/.sql.gz, and creating two
# databases with env-supplied credentials needs shell $VAR expansion in a
# psql heredoc -- a static .sql file can't reference environment variables.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE USER "$POSTGRES_KEYCLOAK_USER" WITH PASSWORD '$POSTGRES_KEYCLOAK_PASSWORD';
    CREATE DATABASE "$POSTGRES_KEYCLOAK_DB" OWNER "$POSTGRES_KEYCLOAK_USER";

    CREATE USER "$POSTGRES_TRAVEL_USER" WITH PASSWORD '$POSTGRES_TRAVEL_PASSWORD';
    CREATE DATABASE "$POSTGRES_TRAVEL_DB" OWNER "$POSTGRES_TRAVEL_USER";
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_TRAVEL_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
