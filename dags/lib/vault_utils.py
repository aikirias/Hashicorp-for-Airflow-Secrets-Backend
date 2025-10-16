"""
Utilidades compartidas para interactuar con Vault desde los DAGs.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import hvac
from airflow.models import Connection
from airflow.utils.session import provide_session


class VaultAuthenticationError(RuntimeError):
    """Señala un fallo al autenticar contra Vault."""


@dataclass
class DynamicCredential:
    username: str
    password: str
    lease_id: str
    lease_duration: int


def _get_vault_client() -> hvac.Client:
    """Construye un cliente autenticado de Vault usando variables de entorno."""
    addr = os.environ.get("VAULT_ADDR")
    token = os.environ.get("VAULT_TOKEN")
    if not addr or not token:
        raise VaultAuthenticationError("VAULT_ADDR y VAULT_TOKEN deben estar definidos")

    client = hvac.Client(url=addr, token=token)
    if not client.is_authenticated():
        raise VaultAuthenticationError("No fue posible autenticarse contra Vault con el token configurado")
    return client


def fetch_dynamic_database_secret(role: str = "airflow-dynamic-read") -> DynamicCredential:
    """Genera credenciales dinámicas desde el motor database/."""
    client = _get_vault_client()
    secret = client.read(f"database/creds/{role}")
    data = secret["data"]
    return DynamicCredential(
        username=data["username"],
        password=data["password"],
        lease_id=secret["lease_id"],
        lease_duration=secret["lease_duration"],
    )


def _get_connection_uri_template() -> str:
    client = _get_vault_client()
    secret = client.secrets.kv.v2.read_secret_version(path="airflow/config/sql_dynamic_base")
    return secret["data"]["data"]["value"]


@provide_session
def _upsert_connection(conn_id: str, conn_uri: str, session=None) -> None:
    existing = session.query(Connection).filter(Connection.conn_id == conn_id).one_or_none()
    if existing:
        existing.set_uri(conn_uri)
    else:
        session.add(Connection(conn_id=conn_id, uri=conn_uri))
    session.commit()


def provision_dynamic_sql_connection(conn_id_prefix: str = "vault_dynamic_postgres") -> tuple[str, DynamicCredential]:
    """
    Crea (o actualiza) un Connection en Airflow usando credenciales dinámicas de Vault.

    Devuelve el conn_id generado junto con los metadatos de la credencial para que el DAG
    pueda dar seguimiento al lease si lo necesita.
    """
    creds = fetch_dynamic_database_secret()
    template = _get_connection_uri_template()
    conn_uri = template.format(username=creds.username, password=creds.password)
    conn_id = f"{conn_id_prefix}_{uuid.uuid4().hex[:8]}"
    _upsert_connection(conn_id, conn_uri)
    return conn_id, creds
