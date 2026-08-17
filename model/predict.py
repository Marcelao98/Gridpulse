import numpy as np
import pandas as pd
import logging
import joblib

from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text

from database.db_connect import engine


# ── Logging ───────────────────────────────────────────────────────────────

log_path = Path(__file__).parent.parent / "logs" / "predict.log"
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


# ── Configuração ──────────────────────────────────────────────────────────

FEATURES = [
    'hora', 'hora_sin', 'hora_cos',
    'dia_semana', 'dia_sin', 'dia_cos',
    'mes', 'e_fds', 'e_feriado',
    'temperatura_c', 'temp_lag_3h', 'temp_lag_24h',
    'carga_lag_24h', 'carga_lag_168h', 'carga_roll_24h',
    'regiao_enc'
]

MODEL_PATH  = Path(__file__).parent.parent / "models" / "xgboost.joblib"
DIAS_AHEAD  = 1


# ── Funções ───────────────────────────────────────────────────────────────

def criar_tabela_predicoes():
    """Cria a tabela de previsões na gold."""

    with engine.connect() as conn:

        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gold.predictions (
                timestamp       TIMESTAMP,
                regiao          TEXT,
                pred_carga_mwmed FLOAT,
                gerado_em       TIMESTAMP DEFAULT NOW()
            );
        """))

        conn.commit()

    logger.info("Tabela gold.predictions verificada/criada.")


def carregar_historico():
    """Carrega o histórico recente da gold para construir os lags."""

    # Precisamos de pelo menos 168h (7 dias) de histórico para os lags
    logger.info("Carregando histórico recente da gold...")

    df = pd.read_sql("""
        SELECT *
        FROM gold.gold_features
        WHERE timestamp >= NOW() - INTERVAL '10 days'
        ORDER BY regiao, timestamp
    """, engine)

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    logger.info(f"Histórico carregado: {len(df):,} linhas.")

    return df


def gerar_timestamps_futuros(df, dias=DIAS_AHEAD):
    """Gera os timestamps das próximas N*24 horas a partir do último registro."""

    ultimo = df['timestamp'].max()
    logger.info(f"Último timestamp na gold: {ultimo}")

    timestamps = [
        ultimo + timedelta(hours=h)
        for h in range(1, dias * 24 + 1)
    ]

    return timestamps


def construir_features_futuras(df_hist, timestamps):
    """Constrói o DataFrame de features para os timestamps futuros."""

    import holidays
    br_holidays = holidays.Brazil(years=range(2019, 2030))

    regioes     = df_hist['regiao'].unique()
    regiao_enc  = {r: i for i, r in enumerate(sorted(regioes))}

    rows = []

    for regiao in regioes:

        hist_reg = df_hist[df_hist['regiao'] == regiao].sort_values('timestamp')

        for ts in timestamps:

            hora       = ts.hour
            dia_semana = ts.dayofweek
            mes        = ts.month
            e_fds      = int(dia_semana >= 5)
            e_feriado  = int(ts.date() in br_holidays)

            hora_sin = np.sin(2 * np.pi * hora / 24)
            hora_cos = np.cos(2 * np.pi * hora / 24)
            dia_sin  = np.sin(2 * np.pi * dia_semana / 7)
            dia_cos  = np.cos(2 * np.pi * dia_semana / 7)

            # Lags de carga — busca no histórico
            def get_lag_carga(horas):
                ts_lag = ts - timedelta(hours=horas)
                row = hist_reg[hist_reg['timestamp'] == ts_lag]
                return row['carga_mwmed'].values[0] if len(row) > 0 else np.nan

            def get_lag_temp(horas):
                ts_lag = ts - timedelta(hours=horas)
                row = hist_reg[hist_reg['timestamp'] == ts_lag]
                return row['temperatura_c'].values[0] if len(row) > 0 else np.nan

            def get_roll_24h():
                ts_inicio = ts - timedelta(hours=25)
                ts_fim    = ts - timedelta(hours=1)
                janela = hist_reg[
                    (hist_reg['timestamp'] > ts_inicio) &
                    (hist_reg['timestamp'] <= ts_fim)
                ]['carga_mwmed']
                return janela.mean() if len(janela) > 0 else np.nan

            # Temperatura futura — usa a última disponível como proxy
            ultima_temp = hist_reg['temperatura_c'].iloc[-1] if len(hist_reg) > 0 else np.nan

            rows.append({
                'timestamp':       ts,
                'regiao':          regiao,
                'hora':            hora,
                'hora_sin':        hora_sin,
                'hora_cos':        hora_cos,
                'dia_semana':      dia_semana,
                'dia_sin':         dia_sin,
                'dia_cos':         dia_cos,
                'mes':             mes,
                'e_fds':           e_fds,
                'e_feriado':       e_feriado,
                'temperatura_c':   ultima_temp,
                'temp_lag_3h':     get_lag_temp(3),
                'temp_lag_24h':    get_lag_temp(24),
                'carga_lag_24h':   get_lag_carga(24),
                'carga_lag_168h':  get_lag_carga(168),
                'carga_roll_24h':  get_roll_24h(),
                'regiao_enc':      regiao_enc[regiao]
            })

    df_future = pd.DataFrame(rows)

    logger.info(df_future.isna().sum())

    logger.info(f"Features futuras construídas: {len(df_future):,} linhas.")

    return df_future


def salvar_predicoes(df_pred):
    """Salva as previsões na tabela gold.predictions."""

    df_pred[['timestamp', 'regiao', 'pred_carga_mwmed']].to_sql(
        'predictions', engine,
        schema='gold',
        if_exists='append',
        index=False
    )

    logger.info(f"{len(df_pred):,} previsões salvas em gold.predictions.")


# ── Pipeline principal ────────────────────────────────────────────────────

def prever():

    criar_tabela_predicoes()

    # Carrega modelo
    logger.info(f"Carregando modelo de {MODEL_PATH}...")
    model = joblib.load(MODEL_PATH)

    # Carrega histórico
    df_hist = carregar_historico()

    # Gera timestamps futuros
    timestamps = gerar_timestamps_futuros(df_hist)

    logger.info(f"Prevendo {DIAS_AHEAD} dias: {timestamps[0]} → {timestamps[-1]}")

    # Constrói features
    df_future = construir_features_futuras(df_hist, timestamps)

    # Predição
    df_future['pred_carga_mwmed'] = model.predict(
        df_future[FEATURES].astype(float)
    )

    logger.info(f"\nAmostra das previsões:")
    logger.info(df_future[['timestamp', 'regiao', 'pred_carga_mwmed']].head(8).to_string())

    # Salva no banco
    salvar_predicoes(df_future)


if __name__ == "__main__":

    prever()

    engine.dispose()