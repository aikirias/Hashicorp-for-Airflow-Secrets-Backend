# Flujo `vault_agent_dynamic_kv`

Este documento describe, paso a paso, cómo funciona este DAG qué elementos participan en la rotación automática de credenciales usando Vault Agent + KV.

## Visión general

1. Vault Agent obtiene credenciales dinámicas desde el secrets engine `database/` (TTL corto).
2. El agente renderiza un archivo JSON con usuario/contraseña temporales (`vault-agent/output/db-creds.json`).
3. El propio agent, mediante el bloque `template` y el comando asociado, ejecuta `vault-agent/scripts/sync_dynamic_creds.sh`, que publica ese JSON en Vault usando el formato que Airflow espera:
   - Variable: `secret/airflow/variables/dynamic_db_credentials` (payload completo, útil para auditoría, no necesario para el flujo productivo).
   - Conexión: `secret/airflow/connections/vault_agent_postgres` con la clave `conn_uri`, que Airflow utilizará como `conn_id`.
4. El DAG `vault_agent_dynamic_kv` registra la metadata (printea en la primer task las credenciales) y ejecuta un `SQLExecuteQueryOperator` usando `conn_id="vault_agent_postgres"`.
5. Cada vez que Vault Agent renueva el secreto (el TTL expira), la plantilla vuelve a renderizarse y el script se dispara automáticamente, dejando el KV actualizado; las ejecuciones siguientes del DAG reutilizan el mismo `conn_id` pero con credenciales frescas.

## Componentes clave

### 1. Configuración de Vault Agent

- Archivo: `vault-agent/config.hcl`
- Plantilla: `vault-agent/templates/db-creds.tpl`
- Token válido: `vault-agent/token` o `/vault-agent/output/agent-token` (generado por el agent).

Ejemplo del bloque `template`:
```hcl
template {
  source      = "/vault-agent/templates/db-creds.tpl"
  destination = "/vault-agent/output/db-creds.json"
  command     = "/vault-agent/scripts/sync_dynamic_creds.sh /vault-agent/output/db-creds.json"
}
```
Cada render ejecuta el script, eliminando pasos manuales.

El JSON resultante es similar a:
```json
{
  "username": "v-token-...",
  "password": "...",
  "lease_id": "database/creds/...",
  "lease_duration": 900,
  "conn_uri": "postgresql://v-token-...@demo-db:5432/demo"
}
```

### 2. Script de sincronización (`vault-agent/scripts/sync_dynamic_creds.sh`)

- Requiere un token: toma el valor de `VAULT_TOKEN` o del archivo `/vault-agent/output/agent-token`.
- Publica en Vault con:
  ```bash
  vault kv put secret/airflow/variables/dynamic_db_credentials value=@<json>
  vault kv put secret/airflow/connections/vault_agent_postgres conn_uri="${CONN_URI}"
  ```
- Al estar ligado al block `template`, se ejecuta siempre que el agent renueva la credencial. No hay pasos manuales.

### 3. Backend de Airflow

`AIRFLOW__SECRETS__BACKEND` apunta a `VaultBackend`, lo que hace que, si existe:
```
secret/airflow/connections/vault_agent_postgres
└── data: { "conn_uri": "postgresql://..." }
```
Airflow resuelva `conn_id="vault_agent_postgres"` sin registrar nada en la metastore. Las variables se leen con `Variable.get()`.

### 4. DAG `vault_agent_dynamic_kv`

Código relevante:
```python
@task
def registrar_credenciales():
    payload = Variable.get("dynamic_db_credentials", deserialize_json=True)
    logging.info("usuario=%s lease_id=%s ttl=%s", ...)

SQLExecuteQueryOperator(
    task_id="ejecutar_consulta_sql",
    conn_id="vault_agent_postgres",
    sql="SELECT SUM(in_stock) AS total_inventario FROM inventory;",
)
```
El operador SQL usa el mismo `conn_id`; cuando el agent actualiza el KV, la consulta usa credenciales nuevas automáticamente.

## ¿Cómo se dispara la rotación?

- Vault (modo file + AppRole) renueva el secret en `database/creds/airflow-dynamic-read` según TTL.
- El template del agent se vuelve a renderizar. Como el bloque `template` tiene un `command`, inmediatamente se ejecuta `sync_dynamic_creds.sh`. Ese script:
  1. Lee el JSON generado.
  2. Usa el token del agent (`/vault-agent/output/agent-token`) para autenticarse.
  3. Publica el payload en las rutas KV (`variables/...` y `connections/...`).
- Airflow no interviene en la rotación; en cada intento de usar `conn_id="vault_agent_postgres"` obtiene el `conn_uri` más reciente.

Es decir: la rotación ocurre automáticamente cada vez que el secrets engine expira el lease (o cuando forzás una ejecución del template). No hay que disparar scripts externos ni jobs adicionales.

## Cómo probar el flujo

1. **Generar credenciales (opcional)**
   ```bash
   docker compose exec vault-agent \
     /vault-agent/scripts/sync_dynamic_creds.sh /vault-agent/output/db-creds.json
   ```
   Verás `[vault-agent] sync complete`, indicando que el KV quedó actualizado.

2. **Verificar en Vault**
   ```bash
   docker compose exec vault sh -c 'vault kv get secret/airflow/connections/vault_agent_postgres'
   docker compose exec vault sh -c 'vault kv get secret/airflow/variables/dynamic_db_credentials'
   ```
   Confirmá la versión y TTL.

3. **Ejecutar el DAG**
   ```bash
   docker compose exec airflow-webserver airflow dags trigger vault_agent_dynamic_kv
   ```

4. **Revisar logs**
   - `registrar_credenciales` loguea usuario/lease/TTL.
   - `ejecutar_consulta_sql` (SQLExecuteQueryOperator) debe finalizar en `success` y mostrar `Rows affected`.

5. **Rotar credenciales**
   Podés dejar que el TTL venza o volver a correr el command; en la siguiente ejecución, el DAG seguirá usando el mismo `conn_id` pero con credenciales nuevas.

## Consideraciones

- El AppRole/token usado por Vault Agent debe tener los permisos definidos en `scripts/init_vault.sh` (lectura en `database/creds/...`, update en `secret/airflow/...`).
- Si regenerás secret-id o reiniciás Vault, actualizá los archivos en `vault-agent/approle/` y el token en `/vault-agent/output/agent-token`.
- El script llama a la CLI `vault`; si empaquetás el agente en otra imagen, asegurate de incluir los binarios/certs.
- Las conexiones dinámicas no aparecen en la UI de Airflow; se consumen exclusivamente vía `conn_id`.

Con este circuito, cada renovación automática del secrets engine actualiza `vault_agent_postgres`; cualquier DAG que refiera ese `conn_id` obtiene credenciales frescas sin intervención manual.

## Referencias

- [Airflow – HashiCorp Vault Secrets Backend](https://airflow.apache.org/docs/apache-airflow-providers-hashicorp/stable/secrets-backends/hashicorp-vault.html)
- [Airflow Provider HashiCorp](https://airflow.apache.org/docs/apache-airflow-providers-hashicorp/stable/index.html)
- [Vault – Database Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/databases)
- [Vault – KV Secrets Engine v2](https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2)
- [Vault Agent Templates](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/template)


