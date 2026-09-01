import argparse
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


# ── Mapeamento etapa -> função ────────────────────────────────────────────────

ETAPAS = {
    "ingestao_ons": ("Ingestão ONS", ingerir_ons),
    "ingestao_openmeteo": ("Ingestão Open-Meteo", ingerir_openmeteo),
    "silver": ("Processamento Silver", processar_silver),
    "gold": ("Feature Engineering (Gold)", processar_gold),
    "prever": ("Geração de Previsões", prever),
}


# ── Execução de uma etapa isolada ─────────────────────────────────────────────

def rodar_etapa(nome_etapa: str):

    if nome_etapa not in ETAPAS:
        raise ValueError(
            f"Etapa '{nome_etapa}' não reconhecida. Opções válidas: {list(ETAPAS.keys())}"
        )

    descricao, funcao = ETAPAS[nome_etapa]

    logger.info(f"Iniciando etapa: {descricao}")

    try:
        funcao()
        logger.info(f"Etapa concluída: {descricao}")

    except Exception as e:
        logger.exception(f"Erro na etapa '{descricao}': {e}")
        raise

    finally:
        engine.dispose()


# ── Pipeline completa (mantém compatibilidade - roda tudo em sequência) ───────

def run():

    logger.info("Iniciando pipeline GridPulse (execução completa)...")

    try:
        for nome_etapa in ETAPAS:
            descricao, funcao = ETAPAS[nome_etapa]
            logger.info(f"Etapa: {descricao}")
            funcao()
            logger.info(f"Concluída: {descricao}")

    except Exception as e:
        logger.exception(f"Erro no pipeline: {e}")
        raise

    finally:
        engine.dispose()
        logger.info("Pipeline finalizado.")


# ── Ponto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Pipeline GridPulse")
    parser.add_argument(
        "--etapa",
        type=str,
        default=None,
        help=f"Roda só uma etapa específica. Opções: {list(ETAPAS.keys())}. "
             f"Se omitido, roda a pipeline completa (comportamento antigo).",
    )
    args = parser.parse_args()

    if args.etapa:
        rodar_etapa(args.etapa)
    else:
        run()
