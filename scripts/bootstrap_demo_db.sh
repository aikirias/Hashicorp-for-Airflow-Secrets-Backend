#!/usr/bin/env sh
set -eu

log() {
  echo "[demo-db-bootstrap] $*"
}

until pg_isready -h demo-db -p 5432 -U postgres >/dev/null 2>&1; do
  log "waiting for demo-db to accept connections..."
  sleep 2
done

log "applying bootstrap SQL to demo database"
psql postgresql://postgres:"${PGPASSWORD}"@demo-db:5432/demo -f /scripts/bootstrap_demo_db.sql

log "bootstrap completed"
