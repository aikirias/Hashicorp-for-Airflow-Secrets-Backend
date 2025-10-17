"""
DAG que consume el conn_id dinámico publicado por el Vault Agent en el KV.

El agente mantiene `secret/data/airflow/connections/vault_agent_postgres`
actualizado con credenciales rotadas; Airflow lo lee directamente como cualquier
otro conn_id gracias al backend de secretos de Vault.
"""

from __future__ import annotations

import logging

from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.utils.dates import days_ago

CONN_ID = "vault_agent_postgres"
VARIABLE_KEY = "dynamic_db_credentials"


@dag(
    dag_id="vault_agent_conn_id",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["hashicorp", "vault", "vault-agent", "conn-id"],
)
def vault_agent_conn_id():
    """
    Ejecuta una consulta usando el conn_id sincronizado por el Vault Agent.

    Además registra las credenciales dinámicas vigentes (vía Variable) para
    facilitar la observabilidad del proceso de rotación.
    """

    @task(task_id="registrar_credenciales")
    def registrar_credenciales() -> None:
        payload = Variable.get(VARIABLE_KEY, deserialize_json=True)
        logging.info(
            "Credencial dinámica activa conn_id=%s usuario=%s lease=%s ttl=%ss",
            CONN_ID,
            payload.get("username"),
            payload.get("lease_id"),
            payload.get("lease_duration"),
        )

    ejecutar_select = SQLExecuteQueryOperator(
        task_id="consultar_items_con_conn_id",
        conn_id=CONN_ID,
        sql="""
        SELECT item_name, in_stock
        FROM inventory
        ORDER BY item_name
        """,
    )

    registrar_credenciales() >> ejecutar_select


dag = vault_agent_conn_id()
