from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from pathlib import Path
import logging
import os


# ── Logging ───────────────────────────────────────────────────────────────────

log_path = Path(__file__).parent.parent / "logs" / "db_connect.log"
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


# ── Variáveis de ambiente ─────────────────────────────────────────────────────

env_path = Path(__file__).parent.parent / ".env"

load_dotenv(dotenv_path=env_path)

USER = os.getenv("POSTGRES_USER")
PASSWORD = os.getenv("POSTGRES_PASSWORD")
HOST = os.getenv("POSTGRES_HOST")
PORT = os.getenv("POSTGRES_PORT")
DB = os.getenv("POSTGRES_DB")


# ── Validação ─────────────────────────────────────────────────────────────────

if not all([USER, PASSWORD, HOST, PORT, DB]):

    logger.error("Variáveis de ambiente não encontradas.")

    raise ValueError(
        "Erro ao carregar as variáveis do arquivo .env."
    )


# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_engine(
    f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}",
    pool_pre_ping=True
)


# ── Teste de conexão ──────────────────────────────────────────────────────────

if __name__ == "__main__":

    try:

        with engine.connect() as conn:

            result = conn.execute(text("SELECT version();"))

            logger.info("Conexão estabelecida com sucesso.")
            logger.info(f"Versão do PostgreSQL: {result.fetchone()[0]}")

    except Exception as e:

        logger.exception(f"Erro ao conectar ao banco: {e}")