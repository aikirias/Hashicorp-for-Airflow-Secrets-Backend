"""DAG que consume las credenciales dinámicas publicadas por Vault Agent en el KV."""

from __future__ import annotations

import logging

from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.utils.dates import days_ago


@dag(
    dag_id="vault_agent_dynamic_kv",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["hashicorp", "vault", "vault-agent"],
)
def vault_agent_dynamic_kv() -> None:
    """Lee el payload del KV y ejecuta la consulta reutilizando el conn_id dinámico."""

    @task(task_id="registrar_credenciales")
    def registrar_credenciales() -> None:
        payload = Variable.get("dynamic_db_credentials", deserialize_json=True)
        logging.info(
            "Vault Agent entregó usuario=%s lease_id=%s con TTL=%s",
            payload.get("username"),
            payload.get("lease_id"),
            payload.get("lease_duration"),
        )

    ejecutar_consulta = SQLExecuteQueryOperator(
        task_id="ejecutar_consulta_sql",
        conn_id="vault_agent_postgres",
        sql="""
        SELECT SUM(in_stock) AS total_inventario
        FROM inventory;
        """,
    )

    registrar_credenciales() >> ejecutar_consulta


dag = vault_agent_dynamic_kv()
