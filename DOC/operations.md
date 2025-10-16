# Operaciones y Procedimientos

## Puesta en Marcha

1. Clonar el repositorio y posicionarse en `project-airflow-hashi`.
2. Construir e iniciar todos los contenedores:
   ```bash
   docker compose up -d --build
   ```
3. Confirmar que los servicios estén `Up`:
   ```bash
   docker compose ps
   ```
4. Accesos:
   - Airflow UI: `http://localhost:8080` (usuario `admin`, password `admin`).
   - Vault dev UI/API: `http://localhost:8200` (token `root`).

Para detener y eliminar volúmenes:
```bash
docker compose down -v
```

## Validación y Testing

### DAGs
Usar `airflow dags test` desde el scheduler:
```bash
docker compose exec airflow-scheduler airflow dags test <dag_id> 2025-10-17
```
Los DAGs de interés:
- `vault_kv_connections_and_variables`
- `vault_agent_dynamic_kv`
- `vault_dynamic_connection_sql`

### Rotación de Credenciales
- TTL configurado: `2m` (`scripts/init_vault.sh`).
- Para verificar rotación:
  1. Ejecutar `vault_dynamic_connection_sql` y anotar el `username` dinámico que
     aparece en los logs.
  2. Esperar >120 s.
  3. Ejecutar de nuevo y confirmar que el `username` cambió.
  4. Opcional: listar leases activos en Vault
     ```bash
     docker compose exec vault vault list database/creds/airflow-dynamic-read
     ```

## Mantenimiento

### Actualizar la Policy/Role del Agent
Modificar `scripts/init_vault.sh` y volver a ejecutar `vault-setup`:
```bash
docker compose run --rm vault-setup
docker compose restart vault-agent
```

### Ajustar TTL o Plantillas
- Editar `scripts/init_vault.sh` (atributos `default_ttl`, `max_ttl`).
- Modificar `vault-agent/templates/db-creds.tpl` si cambia el formato deseado.
- Regenerar credenciales:
  ```bash
  docker compose run --rm vault-setup
  docker compose restart vault-agent
  ```

### Renovar Dependencias Airflow
Actualizar el `Dockerfile` y reconstruir:
```bash
docker compose build --no-cache airflow-webserver airflow-scheduler airflow-init
docker compose up -d
```

## Resolución de Problemas

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| `airflow-init` falla con “requires token or token_path” | Vault Agent no generó `agent-token` aún | Asegurarse de que `vault-agent` esté `Up` y reiniciar `airflow-init`. |
| `airflow` informa `permission denied` al leer variables | Policy `airflow-agent` no permite lectura | Re-ejecutar `vault-setup` o revisar `scripts/init_vault.sh`. |
| Conexión Postgres falla | Usuario/clave no válidos (KV incorrecto o DB caída) | Revisar `secret/airflow/connections/kv_postgres` y salud de `demo-db`. |
| Vault Agent reporta “no known secret ID” | `secret_id` expiró o no fue escrito | Reejecutar `vault-setup` para emitir nuevos `role_id/secret_id`. |

### Logs útiles
- Airflow scheduler: `docker compose logs -f airflow-scheduler`
- Vault Agent: `docker compose logs -f vault-agent`
- Vault: `docker compose logs -f vault`
- Airflow webserver: `docker compose logs -f airflow-webserver`

## Buenas Prácticas de Producción (Sugerencias)
- Ejecutar Vault en modo HA con storage persistente y TLS.
- Limitar permisos en el sink del agente (chmod 0600) y usar tokens envueltos.
- Integrar un mecanismo de revocación automática y monitoreo de leases.
- Externalizar la configuración sensible (p. ej. usar AppRole + response wrapping).
