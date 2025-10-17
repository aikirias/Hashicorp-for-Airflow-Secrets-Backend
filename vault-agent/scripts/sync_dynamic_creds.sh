#!/usr/bin/env sh
set -eu

FILE_PATH="${1:-}"

if [ -z "${FILE_PATH}" ] || [ ! -f "${FILE_PATH}" ]; then
  echo "[vault-agent] dynamic credentials file not found: ${FILE_PATH}" >&2
  exit 1
fi

echo "[vault-agent] syncing dynamic credentials to Vault KV from ${FILE_PATH}"
vault kv put secret/airflow/variables/dynamic_db_credentials value=@"${FILE_PATH}" >/dev/null

CONN_URI="$(sed -n 's/.*\"conn_uri\": \"\(.*\)\".*/\1/p' "${FILE_PATH}")"

if [ -z "${CONN_URI}" ]; then
  echo "[vault-agent] could not extract conn_uri from ${FILE_PATH}" >&2
  exit 1
fi

echo "[vault-agent] publishing dynamic conn_id vault_agent_postgres"
vault kv put secret/airflow/connections/vault_agent_postgres conn_uri="${CONN_URI}" >/dev/null

echo "[vault-agent] sync complete"
