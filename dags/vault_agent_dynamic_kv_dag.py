"""
DAG que consume un secreto dinámico generado por Vault Agent y almacenado en el KV.

El agente obtiene credenciales temporales del motor database/ y las publica en
secret/data/airflow/variables/dynamic_db_credentials. Este DAG las lee y ejecuta
una consulta real usando psycopg2.
"""

from __future__ import annotations

import logging
from contextlib import closing

import psycopg2
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.utils.dates import days_ago


@dag(
    dag_id="vault_agent_dynamic_kv",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["hashicorp", "vault", "vault-agent"],
)
def vault_agent_dynamic_kv():
    """Consume credenciales de corta duración publicadas por Vault Agent."""

    @task(task_id="obtener_credenciales")
    def obtener_credenciales() -> dict:
        payload = Variable.get("dynamic_db_credentials", deserialize_json=True)
        logging.info(
            "Vault Agent entregó usuario=%s lease_id=%s con TTL=%s",
            payload.get("username"),
            payload.get("lease_id"),
            payload.get("lease_duration"),
        )
        return payload

    @task(task_id="consultar_inventario")
    def consultar_inventario(credenciales: dict) -> int:
        with closing(
            psycopg2.connect(
                host="demo-db",
                port=5432,
                dbname="demo",
                user=credenciales["username"],
                password=credenciales["password"],
            )
        ) as conn:
            with conn, conn.cursor() as cur:
                cur.execute("SELECT SUM(in_stock) FROM inventory;")
                total = cur.fetchone()[0]
                logging.info("Total de unidades en inventario (Vault Agent): %s", total)
                return total

    credenciales = obtener_credenciales()
    consultar_inventario(credenciales)


dag = vault_agent_dynamic_kv()
