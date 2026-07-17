#!/bin/sh
# Create the integration reader credential from an injected secret.
# The Docker entrypoint sources non-executable .sh init files, so this file is
# intentionally POSIX shell and must not print the password.
set -eu

: "${STWI_READER_PASSWORD:?STWI_READER_PASSWORD is required}"

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=reader_password="$STWI_READER_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE stwi_reader_user LOGIN PASSWORD %L', :'reader_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stwi_reader_user')
\gexec
SQL
