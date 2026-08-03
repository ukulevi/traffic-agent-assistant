#!/bin/sh
set -eu

: "${STWI_TSDB_READER_PASSWORD:?STWI_TSDB_READER_PASSWORD is required}"

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=reader_password="$STWI_TSDB_READER_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE stwi_reader_user LOGIN PASSWORD %L', :'reader_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stwi_reader_user')
\gexec
SQL
