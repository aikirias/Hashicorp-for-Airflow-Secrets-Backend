# Project Airflow Hashi

Instancia de Apache Airflow que utiliza HashiCorp Vault como backend de secretos y
demuestra tres patrones distintos de integración con motores KV y Database.

## Componentes principales

- **Airflow (webserver, scheduler, init)**: imagen personalizada basada en `apache/airflow:2.8.1`
  con los providers de HashiCorp y Postgres, montando `./dags`, `./plugins`, `./logs` y `./config`.
- **Vault**: despliegue en modo dev escuchando en `8200` con token `root`.
- **Vault Agent**: consulta credenciales dinámicas del motor `database/` y las sincroniza hacia KV.
- **PostgreSQL**:
  - `postgres-airflow`: base de metadatos de Airflow.
  - `demo-db`: base de ejemplo contra la que se ejecutan las consultas de los DAGs.
- **demo-db-bootstrap**: job puntual que inicializa la tabla `inventory`.
- **vault-setup**: job puntual que prepara Vault (habilita engines, crea roles y secretos iniciales).

Todos los servicios montan volúmenes:

| Servicio               | Volúmenes                                                                              |
|------------------------|----------------------------------------------------------------------------------------|
| Airflow                | `./dags`, `./logs`, `./plugins`, `./config`, `vault-agent-output:/opt/airflow/vault-agent` |
| postgres-airflow       | `postgres-airflow-data:/var/lib/postgresql/data`                                      |
| demo-db                | `demo-db-data:/var/lib/postgresql/data`                                                |
| Vault                  | `vault-data:/vault/data`, `./vault`                                                    |
| Vault Agent            | `./vault-agent`, `vault-agent-output:/vault-agent/output`                              |
| Jobs puntuales         | `./scripts`, `./vault`, `./vault-agent` según corresponda                              |

## Requisitos

- Docker 20+ y Docker Compose v2 (`docker compose`).
- El puerto `8200` libre para exponer Vault y `8080` para Airflow.

## Puesta en marcha

```bash
cd project-airflow-hashi
docker compose up -d --build
```

Una vez que `docker compose ps` muestre todos los contenedores en estado `running`
(los jobs `vault-setup`, `demo-db-bootstrap` y `airflow-init` terminarán en `Exited` 0),
Airflow estará disponible en http://localhost:8080 con usuario `admin` y contraseña `admin`.

Vault (modo dev) queda expuesto en http://localhost:8200 con token `root`.

Para seguir los logs de un servicio:

```bash
docker compose logs -f vault-agent
```

## Configuración de Vault

El script `scripts/init_vault.sh` realiza:

1. Habilita `secret/` (KV v2) y publica:
   - `secret/airflow/connections/kv_postgres` (URI para `postgresql+psycopg2://airflow:airflow@demo-db:5432/demo`).
   - `secret/airflow/variables/sample_message` (texto de ejemplo).
   - `secret/airflow/variables/dynamic_db_credentials` (placeholder que luego mantiene el Vault Agent).
   - `secret/airflow/config/sql_dynamic_base` (plantilla `postgresql+psycopg2://{username}:{password}@demo-db:5432/demo`).
2. Habilita `database/` y configura `database/config/demo-postgres` conectado a `demo-db`.
3. Crea el rol `database/roles/airflow-dynamic-read` con TTL corto y permisos de solo lectura.

El Vault Agent utiliza un `template` (`vault-agent/templates/db-creds.tpl`) para solicitar
`database/creds/airflow-dynamic-read`. El resultado se escribe en
`vault-agent-output:/vault-agent/output/db-creds.json` y, mediante
`vault-agent/scripts/sync_dynamic_creds.sh`, se replica en el KV (`dynamic_db_credentials`).

## DAGs incluidos

1. **`vault_kv_connections_and_variables`** (`dags/kv_secrets_dag.py`)
   - Usa `Variable.get("sample_message")` para mostrar un mensaje almacenado en Vault.
   - Ejecuta `PostgresOperator` sobre `postgres_conn_id="kv_postgres"`, conexión mantenida únicamente en Vault.

2. **`vault_agent_dynamic_kv`** (`dags/vault_agent_dynamic_kv_dag.py`)
   - Consume el valor JSON actualizado por el Vault Agent en `dynamic_db_credentials`.
   - Abre una conexión `psycopg2` con las credenciales efímeras y calcula el stock total.

3. **`vault_dynamic_connection_sql`** (`dags/vault_dynamic_connection_sql.py`)
   - Llama a `lib.vault_utils.provision_dynamic_sql_connection()` para obtener credenciales dinámicas,
     formatear un `conn_uri` con la plantilla del KV y registrar una conexión temporal en el metastore.
   - El `SQLExecuteQueryOperator` recibe el `conn_id` devuelto por la función sin persistir
     manualmente credenciales en Airflow.

Cada DAG se ejecuta bajo demanda (sin schedule) para facilitar las pruebas manuales.

## Datos de ejemplo

El job `demo-db-bootstrap` ejecuta `scripts/bootstrap_demo_db.sql`, creando la tabla `inventory`
con tres filas. Las funciones y operadores de los DAGs consultan esta tabla.

## Limpieza

Para detener y eliminar contenedores y volúmenes:

```bash
docker compose down -v
```

> **Nota:** Vault corre en modo dev. Para producción deberían configurarse storage,
> políticas, autenticación (AppRole/JWT/Kubernetes), rotación de tokens y cifrado adecuados.
