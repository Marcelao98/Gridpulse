import numpy as np
import pandas as pd
import logging
import holidays

from pathlib import Path
from sqlalchemy import text
from sklearn.preprocessing import LabelEncoder

from database.db_connect import engine


# ── Logging ───────────────────────────────────────────────────────────────

log_path = Path(__file__).parent.parent / "logs" / "gold_features.log"
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


# ── Funções ───────────────────────────────────────────────────────────────

def criar_tabela():
    """Cria o schema gold e a tabela gold_features."""

    with engine.connect() as conn:

        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gold.gold_features (
                timestamp         TIMESTAMP,
                regiao            TEXT,
                carga_mwmed       FLOAT,
                temperatura_c     FLOAT,
                hora              INTEGER,
                hora_sin          FLOAT,
                hora_cos          FLOAT,
                dia_semana        INTEGER,
                dia_sin           FLOAT,
                dia_cos           FLOAT,
                mes               INTEGER,
                e_fds             INTEGER,
                e_feriado         INTEGER,
                temp_lag_3h       FLOAT,
                temp_lag_24h      FLOAT,
                carga_lag_24h     FLOAT,
                carga_lag_168h    FLOAT,
                carga_roll_24h    FLOAT,
                regiao_enc        INTEGER,
                inserted_at       TIMESTAMP DEFAULT NOW()
            );
        """))

        conn.commit()

    logger.info("Tabela gold.gold_features verificada/criada.")


def get_data_mais_recente():
    """Retorna o timestamp mais recente já processado na gold."""

    with engine.connect() as conn:

        result = conn.execute(
            text("SELECT MAX(timestamp) FROM gold.gold_features")
        )

        return result.fetchone()[0]


def carregar_silver():
    """Lê os dados da camada silver."""

    logger.info("Carregando silver.silver_features...")

    df = pd.read_sql("SELECT * FROM silver.silver_features", engine)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    logger.info(f"Silver carregada: {len(df):,} linhas.")

    return df


def processar_features(df):
    """Aplica o feature engineering e retorna o DataFrame pronto pro modelo."""

    df = df.copy().sort_values(['regiao', 'timestamp']).reset_index(drop=True)

    # Variáveis temporais
    df['dia_semana'] = df['timestamp'].dt.dayofweek
    df['e_fds']      = (df['dia_semana'] >= 5).astype(int)

    # Cíclicas
    df['hora_sin'] = np.sin(2 * np.pi * df['hora'] / 24)
    df['hora_cos'] = np.cos(2 * np.pi * df['hora'] / 24)
    df['dia_sin']  = np.sin(2 * np.pi * df['dia_semana'] / 7)
    df['dia_cos']  = np.cos(2 * np.pi * df['dia_semana'] / 7)

    # Feriados nacionais
    br_holidays = holidays.Brazil(years=range(2019, 2027))
    df['e_feriado'] = df['timestamp'].dt.date.apply(
        lambda x: 1 if x in br_holidays else 0
    )

    # Lags de carga por região
    for regiao in df['regiao'].unique():
        mask = df['regiao'] == regiao
        s    = df.loc[mask, 'carga_mwmed']
        df.loc[mask, 'carga_lag_24h']  = s.shift(24)
        df.loc[mask, 'carga_lag_168h'] = s.shift(168)
        df.loc[mask, 'carga_roll_24h'] = s.shift(1).rolling(24).mean()

    # Lags de temperatura por região
    for regiao in df['regiao'].unique():
        mask = df['regiao'] == regiao
        t    = df.loc[mask, 'temperatura_c']
        df.loc[mask, 'temp_lag_3h']  = t.shift(3)
        df.loc[mask, 'temp_lag_24h'] = t.shift(24)

    # Encoding
    le = LabelEncoder()
    df['regiao_enc'] = le.fit_transform(df['regiao'])

    # Remove nulos gerados pelos lags
    df = df.dropna().reset_index(drop=True)

    logger.info(f"Shape após feature engineering: {df.shape}")
    logger.info(f"Período: {df['timestamp'].min()} → {df['timestamp'].max()}")
    logger.info(f"Nulos: {df.isna().sum().sum()}")

    return df


def salvar_no_banco(df):
    """Salva o DataFrame na tabela gold.gold_features."""

    cols = [
        'timestamp', 'regiao', 'carga_mwmed', 'temperatura_c',
        'hora', 'hora_sin', 'hora_cos',
        'dia_semana', 'dia_sin', 'dia_cos',
        'mes', 'e_fds', 'e_feriado',
        'temp_lag_3h', 'temp_lag_24h',
        'carga_lag_24h', 'carga_lag_168h', 'carga_roll_24h',
        'regiao_enc'
    ]

    df[cols].to_sql(
        'gold_features', engine,
        schema='gold',
        if_exists='append',
        index=False
    )

    logger.info(f"{len(df):,} linhas salvas na gold.")


# ── Pipeline principal ────────────────────────────────────────────────────

def processar_gold():

    criar_tabela()

    data_mais_recente = get_data_mais_recente()

    df = carregar_silver()
    df = processar_features(df)

    if data_mais_recente is None:

        logger.info("Gold vazia — processando histórico completo...")
        salvar_no_banco(df)

    else:

        logger.info(f"Último registro gold: {data_mais_recente} — processando apenas dados novos...")

        df_novo = df[df['timestamp'] > data_mais_recente]

        if df_novo.empty:
            logger.info("Nenhum dado novo para processar.")
        else:
            logger.info(f"{len(df_novo):,} novos registros.")
            salvar_no_banco(df_novo)


if __name__ == "__main__":

    processar_gold()

    engine.dispose()