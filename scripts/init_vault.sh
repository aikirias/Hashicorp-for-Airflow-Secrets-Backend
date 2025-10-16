#!/usr/bin/env sh
set -eu

log() {
  echo "[vault-setup] $*"
}

export VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-root}"

log "waiting for Vault to be ready at ${VAULT_ADDR}..."
until vault status >/dev/null 2>&1; do
  sleep 2
done

log "enabling kv-v2 secrets engine at secret/ (if needed)"
vault secrets enable -path=secret kv-v2 >/dev/null 2>&1 || true

log "publishing baseline Airflow connection and variable in Vault"
vault kv put secret/airflow/connections/kv_postgres \
  conn_uri="postgresql://postgres:postgres@demo-db:5432/demo" >/dev/null

vault kv put secret/airflow/variables/sample_message \
  value="Mensaje inicial proveniente de Vault KV" >/dev/null

log "enabling database secrets engine for dynamic credentials"
vault secrets enable -path=database database >/dev/null 2>&1 || true

log "configuring database root connection"
vault write database/config/demo-postgres \
  plugin_name=postgresql-database-plugin \
  allowed_roles="airflow-dynamic-read" \
  connection_url="postgresql://{{username}}:{{password}}@demo-db:5432/demo?sslmode=disable" \
  username="postgres" \
  password="postgres" >/dev/null

log "creating role for short-lived read credentials"
vault write database/roles/airflow-dynamic-read \
  db_name=demo-postgres \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT CONNECT ON DATABASE demo TO \"{{name}}\"; GRANT USAGE ON SCHEMA public TO \"{{name}}\"; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="2m" \
  max_ttl="10m" >/dev/null

log "ensuring kv placeholder for agent generated variable exists"
vault kv put secret/airflow/variables/dynamic_db_credentials \
  value="{}" >/dev/null

log "ensuring kv placeholder for connection templating"
vault kv put secret/airflow/config/sql_dynamic_base \
  value="postgresql://{username}:{password}@demo-db:5432/demo" >/dev/null

log "enabling approle auth method"
vault auth enable approle >/dev/null 2>&1 || true

log "writing policy for vault agent"
cat <<'EOF' | vault policy write airflow-agent -
path "database/creds/airflow-dynamic-read" {
  capabilities = ["read"]
}

path "secret/data/airflow/connections/*" {
  capabilities = ["read"]
}

path "secret/data/airflow/variables/dynamic_db_credentials" {
  capabilities = ["read", "update"]
}

path "secret/data/airflow/variables/*" {
  capabilities = ["read"]
}

path "secret/data/airflow/config/*" {
  capabilities = ["read"]
}
EOF

log "creating approle for vault agent"
vault write auth/approle/role/airflow-agent \
  token_policies="airflow-agent" \
  token_ttl="2m" \
  token_max_ttl="10m" \
  secret_id_ttl="2m" \
  secret_id_num_uses=0 >/dev/null

log "exporting approle credentials for vault agent"
mkdir -p /vault-agent/approle
vault read -field=role_id auth/approle/role/airflow-agent/role-id >/vault-agent/approle/role_id
vault write -f -field=secret_id auth/approle/role/airflow-agent/secret-id >/vault-agent/approle/secret_id

log "Vault bootstrap complete"
