# Componentes y Funcionalidad

## Servicios Principales

### Apache Airflow
- Imagen base: `apache/airflow:2.8.1`, extendida con `apache-airflow-providers-hashicorp`,
  `apache-airflow-providers-postgres` y `hvac`.
- Servicios:
  - `airflow-init`: migra la base, crea usuario admin y deja una conexión
    `demo_postgres`.
  - `airflow-webserver`: expone la UI en `http://localhost:8080`.
  - `airflow-scheduler`: orquesta la ejecución de DAGs.
- Volúmenes montados en `/opt/airflow`:
  - `./dags`, `./plugins`, `./logs`, `./config`.
  - `./vault-agent/output` → `/opt/airflow/vault-agent` para leer el token del agente.
- Backend de secretos configurado con `VaultBackend`:
  ```env
  AIRFLOW__SECRETS__BACKEND=airflow.providers.hashicorp.secrets.vault.VaultBackend
  AIRFLOW__SECRETS__BACKEND_CONF={
    "connections_path": "airflow/connections",
    "variables_path": "airflow/variables",
    "config_path": "airflow/config",
    "mount_point": "secret",
    "kv_engine_version": 2,
    "token_path": "/opt/airflow/vault-agent/agent-token"
  }
  ```

### HashiCorp Vault (modo dev)
- Corre como `vault server -dev` exponiendo `http://localhost:8200` con token
  `root`.
- Volúmenes:
  - `vault-data` (Docker) → `/vault/data`.
  - `./vault` → `/vault/custom` (no se usa actualmente, reservado para archivos).
- Funcionalidades habilitadas por `vault-setup`:
  - `secret/` (KV v2) para conexiones, variables y config de Airflow.
  - `database/` para generar credenciales dinámicas hacia `demo-db`.
  - `auth/approle` con el rol `airflow-agent`.

### Vault Agent
- Imagen `hashicorp/vault:1.15`.
- Autenticación: AppRole (`role_id` y `secret_id` provistos por `vault-setup`).
- `config.hcl` define:
  - `auto_auth` con método `approle` y sink `file` (`/vault-agent/output/agent-token`).
  - Template `db-creds.tpl` para pedir `database/creds/airflow-dynamic-read`.
  - Script `sync_dynamic_creds.sh` que publica el JSON de credenciales en
    `secret/airflow/variables/dynamic_db_credentials`.
- Monta `./vault-agent` completo (config, templates, scripts, output).

### PostgreSQL
- `postgres-airflow`: almacena metadatos; volumen Docker
  `project-airflow-hashi_postgres-airflow-data`.
- `demo-db`: base de ejemplo; volumen
  `project-airflow-hashi_demo-db-data`.
- `demo-db-bootstrap`: ejecuta `scripts/bootstrap_demo_db.sql` para crear la
  tabla `inventory` y datos de prueba.

## DAGs Incluidos

| DAG | Objetivo | Interacción con Vault |
|-----|----------|-----------------------|
| `vault_kv_connections_and_variables` | Demostrar variables y conexiones desde KV | Usa `Variable.get("sample_message")` y `postgres_conn_id="kv_postgres"` (únicamente definido en Vault). |
| `vault_agent_dynamic_kv` | Consumir credenciales publicadas por el Vault Agent | Lee `dynamic_db_credentials` (JSON) y se conecta con `psycopg2`. |
| `vault_dynamic_connection_sql` | Generar un `conn_id` dinámico antes de ejecutar SQL | Llama a `lib.vault_utils.provision_dynamic_sql_connection()`, que pide credenciales dinámicas, arma el URI desde el KV y registra la conexión en el metastore. |

### Utilidades Python (`dags/lib/vault_utils.py`)
- Envoltorio alrededor de `hvac` para:
  - Construir un cliente autenticado usando variables de entorno (`VAULT_ADDR`,
    `VAULT_TOKEN` heredado del sink del agente).
  - Solicitar credenciales dinámicas (`fetch_dynamic_database_secret`).
  - Leer plantillas de conexión (`_get_connection_uri_template`).
  - Crear/actualizar conexiones en Airflow (`_upsert_connection` via sesión).
  - Función pública `provision_dynamic_sql_connection` que devuelve el `conn_id`
    generado y metadatos de la credencial.

## Scripts de Bootstrap

### `scripts/init_vault.sh`
1. Espera a que Vault esté listo.
2. Habilita `secret/` (KV v2).
3. Crea:
   - `secret/airflow/connections/kv_postgres` → `postgresql://postgres:postgres@demo-db:5432/demo`.
   - `secret/airflow/variables/sample_message`.
   - `secret/airflow/variables/dynamic_db_credentials` (placeholder).
   - `secret/airflow/config/sql_dynamic_base`.
4. Habilita `database/`, configura `database/config/demo-postgres` y el rol
   `database/roles/airflow-dynamic-read` con `default_ttl=2m`.
5. Habilita `auth/approle`, crea la policy `airflow-agent` (permisos de lectura/actualización)
   y el rol `airflow-agent`.
6. Extrae `role_id` y `secret_id` a `/vault-agent/approle/`.

### `scripts/bootstrap_demo_db.sh`
- Espera que `demo-db` acepte conexiones.
- Ejecuta `bootstrap_demo_db.sql` para crear la tabla `inventory` e insertar
  registros de prueba.

## Volúmenes Resumen

| Servicio | Volúmenes/fuentes | Destino en contenedor |
|----------|-------------------|-----------------------|
| Airflow (todos) | `./dags`, `./logs`, `./plugins`, `./config`, `./vault-agent/output` | `/opt/airflow/*` |
| Vault | `vault-data`, `./vault` | `/vault/data`, `/vault/custom` |
| Vault Agent | `./vault-agent` | `/vault-agent` (config, templates, scripts, output) |
| postgres-airflow | `project-airflow-hashi_postgres-airflow-data` | `/var/lib/postgresql/data` |
| demo-db | `project-airflow-hashi_demo-db-data` | `/var/lib/postgresql/data` |
