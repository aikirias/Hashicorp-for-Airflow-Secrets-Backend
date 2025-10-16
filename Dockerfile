FROM apache/airflow:2.8.1

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq \
    && rm -rf /var/lib/apt/lists/*
USER airflow
RUN pip install --no-cache-dir \
    apache-airflow-providers-hashicorp \
    apache-airflow-providers-postgres \
    hvac
