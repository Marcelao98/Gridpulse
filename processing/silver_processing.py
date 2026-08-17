import pandas as pd
import logging
from pathlib import Path
from sqlalchemy import text
from database.db_connect import engine

# ── Logging ───────────────────────────────────────────────────────────────────
log_path = Path(__file__).parent.parent / "logs" / "silver_features.log"
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


# ── Funções ───────────────────────────────────────────────────────────────────

def criar_tabela():
    """Cria o schema silver e a tabela silver_features se não existirem."""
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS silver;"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS silver.silver_features (
                timestamp      TIMESTAMP,
                regiao         TEXT,
                carga_mwmed    FLOAT,
                temperatura_c  FLOAT,
                hora           INTEGER,
                mes            INTEGER,
                data           DATE,
                inserted_at    TIMESTAMP DEFAULT NOW()
            );
        """))
        conn.commit()
    logger.info("Tabela silver.silver_features verificada/criada.")


def get_data_mais_recente():
    """Retorna o timestamp mais recente já processado na silver."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT MAX(timestamp) FROM silver.silver_features")
        )
        return result.fetchone()[0]


def carregar_bronze():
    """Lê os dados brutos das tabelas bronze."""
    logger.info("Carregando bronze.raw_ons...")
    df_carga = pd.read_sql("SELECT * FROM bronze.raw_ons", engine)

    logger.info("Carregando bronze.raw_openmeteo...")
    df_temp = pd.read_sql("SELECT * FROM bronze.raw_openmeteo", engine)

    return df_carga, df_temp


def processar(df_carga, df_temp):
    """Aplica as transformações e retorna o DataFrame processado."""

    # Padroniza nome de região
    df_carga['regiao'] = df_carga['nom_subsistema'].str.replace(
        'SUDESTE/CENTRO-OESTE', 'SUDESTE', regex=False
    )

    # Merge por timestamp + região
    df = (df_carga
          .merge(
              df_temp[['time', 'temperature_2m', 'regiao']],
              left_on=['din_instante', 'regiao'],
              right_on=['time', 'regiao'],
              how='inner'
          )
          .drop(columns=['time', 'nom_subsistema', 'id_subsistema', 'inserted_at'])
          .rename(columns={
              'din_instante':           'timestamp',
              'val_cargaenergiahomwmed': 'carga_mwmed',
              'temperature_2m':          'temperatura_c',
          }))

    df['hora'] = df['timestamp'].dt.hour
    df['mes']  = df['timestamp'].dt.month
    df['data'] = df['timestamp'].dt.date

    logger.info(f"Shape após processamento: {df.shape}")
    logger.info(f"Período: {df['timestamp'].min()} → {df['timestamp'].max()}")
    logger.info(f"Nulos: {df.isna().sum().sum()}")

    return df


def salvar_no_banco(df):
    """Salva o DataFrame processado na tabela silver.silver_features."""
    cols = ['timestamp', 'regiao', 'carga_mwmed', 'temperatura_c', 'hora', 'mes', 'data']
    df[cols].to_sql(
        'silver_features', engine,
        schema='silver',
        if_exists='append',
        index=False
    )
    logger.info(f"{len(df):,} linhas salvas na silver.")


# ── Pipeline principal ────────────────────────────────────────────────────────

def processar_silver():
    criar_tabela()

    data_mais_recente = get_data_mais_recente()

    df_carga, df_temp = carregar_bronze()
    df = processar(df_carga, df_temp)

    if data_mais_recente is None:
        logger.info("Silver vazia — processando histórico completo...")
        salvar_no_banco(df)

    else:
        logger.info(f"Último registro silver: {data_mais_recente} — processando apenas dados novos...")
        df_novo = df[df['timestamp'] > data_mais_recente]

        if df_novo.empty:
            logger.info("Nenhum dado novo para processar.")
        else:
            logger.info(f"{len(df_novo):,} novos registros.")
            salvar_no_banco(df_novo)


if __name__ == "__main__":
    processar_silver()
    engine.dispose()