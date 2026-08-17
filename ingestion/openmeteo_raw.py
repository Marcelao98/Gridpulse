import requests
import pandas as pd
import logging

from datetime import datetime
from pathlib import Path
from sqlalchemy import text

from database.db_connect import engine


# ── Logging ───────────────────────────────────────────────────────────────

log_path = Path(__file__).parent.parent / "logs" / "openmeteo_raw.log"
log_path.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ── Configuração das regiões ──────────────────────────────────────────────

REGIOES_COORDS = {
    "SUDESTE": {
        "lat": -23.55,
        "lon": -46.63,
        "cidade": "São Paulo"
    },
    "NORDESTE": {
        "lat": -3.73,
        "lon": -38.52,
        "cidade": "Fortaleza"
    },
    "NORTE": {
        "lat": -3.10,
        "lon": -60.02,
        "cidade": "Manaus"
    },
    "SUL": {
        "lat": -30.03,
        "lon": -51.23,
        "cidade": "Porto Alegre"
    },
}


# ── Funções ───────────────────────────────────────────────────────────────

def criar_tabela():
    """Cria o schema bronze e a tabela raw_openmeteo."""

    with engine.connect() as conn:

        conn.execute(text("""
            CREATE SCHEMA IF NOT EXISTS bronze;
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bronze.raw_openmeteo (
                time                   TIMESTAMP,
                temperature_2m         FLOAT,
                relative_humidity_2m   FLOAT,
                precipitation          FLOAT,
                cloud_cover            FLOAT,
                regiao                 TEXT,
                cidade                 TEXT,
                inserted_at            TIMESTAMP DEFAULT NOW()
            );
        """))

        conn.commit()

    logger.info(
        "Tabela bronze.raw_openmeteo verificada/criada."
    )


def get_data_mais_recente():
    """Retorna o timestamp mais recente."""

    with engine.connect() as conn:

        result = conn.execute(
            text(
                "SELECT MAX(time) "
                "FROM bronze.raw_openmeteo"
            )
        )

        return result.fetchone()[0]


def baixar_openmeteo(lat, lon, inicio, fim):
    """Baixa dados horários do Open-Meteo."""

    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": inicio,
        "end_date": fim,
        "hourly": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "precipitation,"
            "cloud_cover"
        ),
        "timezone": "America/Sao_Paulo"
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    df = pd.DataFrame(
        response.json()["hourly"]
    )

    df["time"] = pd.to_datetime(
        df["time"]
    )

    return df


def salvar_no_banco(df):
    """Salva no PostgreSQL."""

    cols = [
        "time",
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "cloud_cover",
        "regiao",
        "cidade"
    ]

    df[cols].to_sql(
        "raw_openmeteo",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )

    logger.info(
        f"{len(df):,} linhas salvas."
    )


# ── Pipeline principal ────────────────────────────────────────────────────

def ingerir_openmeteo():

    criar_tabela()

    data_mais_recente = get_data_mais_recente()

    if data_mais_recente is None:

        logger.info(
            "Banco vazio — baixando histórico completo..."
        )

        inicio = "2019-01-01"

        fim = datetime.now().strftime(
            "%Y-%m-%d"
        )

        dfs = []

        for regiao, info in REGIOES_COORDS.items():

            logger.info(
                f"Baixando {regiao} "
                f"({info['cidade']})..."
            )

            df = baixar_openmeteo(
                info["lat"],
                info["lon"],
                inicio,
                fim
            )

            df["regiao"] = regiao
            df["cidade"] = info["cidade"]

            dfs.append(df)

            logger.info(
                f"{len(df):,} registros baixados."
            )

        df_total = pd.concat(
            dfs,
            ignore_index=True
        )

        salvar_no_banco(df_total)

    else:

        logger.info(
            f"Último registro: "
            f"{data_mais_recente}"
        )

        inicio = data_mais_recente.strftime(
            "%Y-%m-%d"
        )

        fim = datetime.now().strftime(
            "%Y-%m-%d"
        )

        dfs = []

        for regiao, info in REGIOES_COORDS.items():

            logger.info(
                f"Baixando {regiao} "
                f"({info['cidade']})..."
            )

            df = baixar_openmeteo(
                info["lat"],
                info["lon"],
                inicio,
                fim
            )

            df["regiao"] = regiao
            df["cidade"] = info["cidade"]

            df_novo = df[
                df["time"] > data_mais_recente
            ]

            dfs.append(df_novo)

            logger.info(
                f"{len(df_novo):,} "
                f"novos registros."
            )

        df_total = pd.concat(
            dfs,
            ignore_index=True
        )

        if df_total.empty:

            logger.info(
                "Nenhum dado novo encontrado."
            )

        else:

            salvar_no_banco(df_total)


if __name__ == "__main__":

    ingerir_openmeteo()

    engine.dispose()