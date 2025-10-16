#!/usr/bin/env sh
set -eu

FILE_PATH="${1:-}"

if [ -z "${FILE_PATH}" ] || [ ! -f "${FILE_PATH}" ]; then
  echo "[vault-agent] dynamic credentials file not found: ${FILE_PATH}" >&2
  exit 1
fi

echo "[vault-agent] syncing dynamic credentials to Vault KV from ${FILE_PATH}"
vault kv put secret/airflow/variables/dynamic_db_credentials value=@"${FILE_PATH}" >/dev/null

echo "[vault-agent] sync complete"
