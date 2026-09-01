from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.hooks.base import BaseHook
from datetime import datetime

with DAG(
    dag_id="gridpulse_pipeline",
    description="Pipeline GridPulse - etapas separadas (ingestao -> silver -> gold -> previsao)",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["gridpulse"],
) as dag:

    conn = BaseHook.get_connection("gridpulse_postgres")

    env_comum = {
        "POSTGRES_USER": conn.login,
        "POSTGRES_PASSWORD": conn.password,
        "POSTGRES_HOST": conn.host,
        "POSTGRES_PORT": str(conn.port),
        "POSTGRES_DB": conn.schema,
    }

    def criar_task(task_id: str, etapa: str) -> DockerOperator:
        return DockerOperator(
            task_id=task_id,
            image="gridpulse-gp-pipeline:latest",
            command=f"python main.py --etapa {etapa}",
            docker_url="unix://var/run/docker.sock",
            network_mode="gridpulse_default",
            auto_remove="success",
            mount_tmp_dir=False,
            environment=env_comum,
        )

    ingestao_ons = criar_task("ingestao_ons", "ingestao_ons")
    ingestao_openmeteo = criar_task("ingestao_openmeteo", "ingestao_openmeteo")
    silver = criar_task("processamento_silver", "silver")
    gold = criar_task("feature_engineering_gold", "gold")
    prever = criar_task("gerar_previsoes", "prever")

    # Encadeamento: ingestoes rodam em paralelo (fontes independentes),
    # silver so comeca depois que AMBAS terminarem, gold e previsao seguem em sequencia
    [ingestao_ons, ingestao_openmeteo] >> silver >> gold >> prever
