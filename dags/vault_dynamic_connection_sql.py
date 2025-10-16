"""
DAG que construye un conn_id dinámico para SQLExecuteQueryOperator usando Vault.
"""

from __future__ import annotations

import logging

from airflow.decorators import dag, task
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.utils.dates import days_ago

from lib.vault_utils import provision_dynamic_sql_connection


@dag(
    dag_id="vault_dynamic_connection_sql",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["hashicorp", "vault", "dynamic-conn"],
)
def vault_dynamic_connection_sql():
    """Genera un conn_id único por ejecución a partir de credenciales dinámicas."""

    @task(task_id="provisionar_conn_id")
    def provisionar_conn_id() -> dict:
        conn_id, credenciales = provision_dynamic_sql_connection()
        logging.info(
            "Conn %s construido con lease_id=%s (TTL=%ss)",
            conn_id,
            credenciales.lease_id,
            credenciales.lease_duration,
        )
        return {
            "conn_id": conn_id,
            "lease_id": credenciales.lease_id,
            "lease_duration": credenciales.lease_duration,
        }

    info = provisionar_conn_id()

    SQLExecuteQueryOperator(
        task_id="ejecutar_consulta_sql",
        conn_id=info["conn_id"],
        sql="""
        SELECT item_name, in_stock
        FROM inventory
        ORDER BY item_name
        LIMIT 5;
        """,
    )


dag = vault_dynamic_connection_sql()
