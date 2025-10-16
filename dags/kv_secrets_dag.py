"""
DAG que demuestra el uso de conexiones y variables almacenadas en Vault KV.
"""

from __future__ import annotations

import logging

from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.utils.dates import days_ago


@dag(
    dag_id="vault_kv_connections_and_variables",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["hashicorp", "vault", "kv"],
)
def vault_kv_connections_and_variables():
    """
    Recupera una variable y una conexión almacenadas en el path
    secret/data/airflow/** dentro de Vault y las emplea en tareas reales.
    """

    @task(task_id="mostrar_variable")
    def mostrar_variable_desde_vault() -> str:
        mensaje = Variable.get("sample_message")
        logging.info("Mensaje proveniente de Vault KV: %s", mensaje)
        return mensaje

    consulta = PostgresOperator(
        task_id="consultar_inventario",
        postgres_conn_id="kv_postgres",
        sql="SELECT COUNT(*) AS total_items FROM inventory;",
    )

    mostrar_variable_desde_vault() >> consulta


dag = vault_kv_connections_and_variables()
