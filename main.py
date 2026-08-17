import logging
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────

log_path = Path(__file__).parent / "logs" / "main.log"
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

# ── Imports dos módulos ───────────────────────────────────────────────────────

from database.db_connect import engine
from ingestion.ons_raw import ingerir_ons
from ingestion.openmeteo_raw import ingerir_openmeteo
from processing.silver_processing import processar_silver
from features.gold_features import processar_gold
from model.predict import prever

# Obs: o treino (model.train) foi retirado do fluxo automático.
# Ele roda separado, sob demanda: python -m model.train


# ── Pipeline principal ────────────────────────────────────────────────────────

def run():

    logger.info("Iniciando pipeline GridPulse...")

    try:

        logger.info("Etapa 1/4 — Ingestão ONS")
        ingerir_ons()
        logger.info("Ingestão ONS concluída.")

        logger.info("Etapa 2/4 — Ingestão Open-Meteo")
        ingerir_openmeteo()
        logger.info("Ingestão Open-Meteo concluída.")

        logger.info("Etapa 3/4 — Processamento Silver")
        processar_silver()
        logger.info("Processamento Silver concluído.")

        logger.info("Etapa 4/4 — Feature Engineering (Gold)")
        processar_gold()
        logger.info("Feature Engineering Gold concluído.")

        # Gera previsões dos próximos 3 dias
        logger.info("Gerando previsões para os próximos 3 dias...")
        prever()
        logger.info("Previsões concluídas.")

    except Exception as e:

        logger.exception(f"Erro no pipeline: {e}")
        raise

    finally:

        engine.dispose()
        logger.info("Pipeline finalizado.")


if __name__ == "__main__":

    run()
