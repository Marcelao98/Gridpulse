from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime

with DAG(
    dag_id="gridpulse_pipeline",
    description="Roda a pipeline completa do GridPulse",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["gridpulse"],
) as dag:

    rodar_pipeline = DockerOperator(
        task_id="rodar_gridpulse",
        image="gridpulse-gp-pipeline:latest",
        docker_url="unix://var/run/docker.sock",
        network_mode="gridpulse_default",
        auto_remove="success",
        mount_tmp_dir=False,
        environment={
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "154313",
            "POSTGRES_HOST": "gp-postgres",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "gridpulse",
        },
    )