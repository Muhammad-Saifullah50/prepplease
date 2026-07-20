#!/bin/sh
# Creates the per-service databases and enables pgvector in each (FR-015a).
# Runs once at first postgres container start via /docker-entrypoint-initdb.d.
set -eu

for db in course_core ingestion exam_sim; do
    echo "Creating database: $db"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
        CREATE DATABASE $db;
EOSQL
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<-EOSQL
        CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
done
