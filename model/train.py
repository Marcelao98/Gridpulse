import numpy as np
import pandas as pd
import logging
import joblib

from pathlib import Path
from datetime import datetime
from sqlalchemy import text
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error

from database.db_connect import engine


# ── Logging ───────────────────────────────────────────────────────────────

log_path = Path(__file__).parent.parent / "logs" / "train.log"
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

TARGET      = 'carga_mwmed'
SPLIT_DATA  = pd.Timestamp('2026-01-01')
MODEL_PATH  = Path(__file__).parent.parent / "models" / "xgboost.joblib"


# ── Funções ───────────────────────────────────────────────────────────────

def criar_tabela_metricas():
    """Cria a tabela de métricas de treino na gold."""

    with engine.connect() as conn:

        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gold.train_metrics (
                treino_em     TIMESTAMP,
                regiao        TEXT,
                mae           FLOAT,
                mape          FLOAT,
                n_treino      INTEGER,
                n_teste       INTEGER,
                inserted_at   TIMESTAMP DEFAULT NOW()
            );
        """))

        conn.commit()

    logger.info("Tabela gold.train_metrics verificada/criada.")


def carregar_gold():
    """Lê os dados da camada gold."""

    logger.info("Carregando gold.gold_features...")

    df = pd.read_sql(
        "SELECT * FROM gold.gold_features ORDER BY regiao, timestamp",
        engine
    )

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    logger.info(f"Gold carregada: {len(df):,} linhas.")

    return df


def mape(y_true, y_pred):
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100


def treinar():

    criar_tabela_metricas()

    df = carregar_gold()

    # Split temporal
    train = df[df['timestamp'] <  SPLIT_DATA]
    test  = df[df['timestamp'] >= SPLIT_DATA].copy()

    logger.info(f"Treino: {len(train):,} | Teste: {len(test):,}")
    logger.info(f"Período teste: {test['timestamp'].min()} → {test['timestamp'].max()}")

    X_train = train[FEATURES].astype(float)
    y_train = train[TARGET]

    X_test  = test[FEATURES].astype(float)

    # Treino
    logger.info("Treinando XGBoost...")

    model = XGBRegressor(
        objective='reg:squarederror',
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    logger.info("Treino concluído.")

    # Previsão no período de teste
    test['pred_xgb'] = model.predict(X_test)

    # Métricas por região
    treino_em = datetime.now()
    metricas  = []

    for regiao in test['regiao'].unique():

        sub = test[test['regiao'] == regiao]

        mae_val  = round(mean_absolute_error(sub[TARGET], sub['pred_xgb']), 1)
        mape_val = round(mape(sub[TARGET], sub['pred_xgb']), 2)

        logger.info(f"{regiao} → MAE: {mae_val} | MAPE: {mape_val}%")

        metricas.append({
            'treino_em': treino_em,
            'regiao':    regiao,
            'mae':       mae_val,
            'mape':      mape_val,
            'n_treino':  len(train[train['regiao'] == regiao]),
            'n_teste':   len(sub)
        })

    # Salva métricas na gold
    df_metricas = pd.DataFrame(metricas)
    df_metricas.to_sql(
        'train_metrics', engine,
        schema='gold',
        if_exists='append',
        index=False
    )

    logger.info("Métricas salvas na gold.train_metrics.")

    # Salva modelo em disco
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    logger.info(f"Modelo salvo em {MODEL_PATH}")


if __name__ == "__main__":

    treinar()

    engine.dispose()