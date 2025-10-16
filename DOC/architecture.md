# Arquitectura de la Solución

## Visión General

La solución levanta un entorno local basado en Docker Compose que integra:

- Una instancia personalizada de **Apache Airflow 2.8.1** (scheduler, webserver
  e init job).
- **HashiCorp Vault 1.15** corriendo en modo dev.
- Un **Vault Agent** que obtiene credenciales dinámicas y las publica en el KV.
- Dos bases PostgreSQL:
  - `postgres-airflow`: metastore de Airflow.
  - `demo-db`: base de datos de ejemplo que consumen los DAGs.
- Jobs de bootstrap (`vault-setup`, `demo-db-bootstrap`) para preparar Vault y
  poblar la base demo.

Todos los servicios comparten la red Docker `project-airflow-hashi_airflow`.

### Diagrama Lógico

```
             ┌────────────────────────┐
             │    docker compose      │
             └──────────┬─────────────┘
                        │
        ┌───────────────┼──────────────────┐
        │                                   │
┌───────▼────────┐                 ┌────────▼────────┐
│  Vault (dev)   │                 │  Postgres demo  │
│ - secret/ KV   │                 │  (demo-db)      │
│ - database/    │                 │  inventory tbl  │
└───────┬────────┘                 └────────▲────────┘
        │                                   │
        │  dynamic creds + KV sync          │
┌───────▼────────┐                 ┌────────┴────────┐
│  Vault Agent   │                 │  Postgres meta  │
│ - AppRole      │                 │  (postgres-air) │
│ - file sink    │                 └────────┬────────┘
└───────┬────────┘                          │
        │ agent token                       │
┌───────▼────────┐                          │
│  Airflow       │                          │
│ - webserver    │                          │
│ - scheduler    │                          │
│ - init job     │                          │
│ - DAGs         │                          │
└────────────────┘                          │
   │        │                               │
   │        │ Vault KV / DB                 │
   │        └───────────────────────────────┘
   │
   └─> Usuarios acceden a UI (8080) y Vault Dev (8200)
```

### Flujo de Secretos

1. **Bootstrap**
   - `vault-setup` habilita `secret/` (KV v2), `database/`, crea la policy
     `airflow-agent`, genera AppRole `airflow-agent` y guarda `role_id` /
     `secret_id` en `vault-agent/approle`.
   - `demo-db-bootstrap` crea la tabla `inventory` y la llena con datos.
2. **Vault Agent**
   - Se autentica vía AppRole usando los archivos generados.
   - Obtiene credenciales dinámicas `database/creds/airflow-dynamic-read`.
   - Escribe el token del agente en `vault-agent/output/agent-token`.
   - Sincroniza el JSON con el secreto
     `secret/data/airflow/variables/dynamic_db_credentials`.
3. **Airflow**
   - Lee conexiones, variables y config desde Vault usando el backend oficial
     (`VaultBackend`) y el token provisto por el agente.
   - Los DAGs ejecutan:
     - Lecturas desde `secret/airflow/connections/*` y `secret/airflow/variables/*`.
     - Generación on-demand de credenciales dinámicas (vía utilidades Python
       que también usan el token Vault del agente).

## Consideraciones de Seguridad

- Vault corre en modo **dev** (no seguro para producción) y expone el token
  estático `root`. La AppRole también se crea con TTL corto pero sin políticas
  de rotación adicionales.
- Los volúmenes locales (`./vault-agent/output`, `./config`, `./logs`, etc.)
  se montan en contenedores, por lo que hay acceso a secretos desde la máquina
  host.
- El objetivo del entorno es educativo/demostrativo; para uso productivo se
  recomienda:
  - Desplegar Vault en modo HA con almacenamiento persistente seguro.
  - Configurar autenticación robusta (AppRole con envoltura, Kubernetes, JWT,
    etc.).
  - Gestionar tokens y ficheros de agente en rutas protegidas (no world-readable).
