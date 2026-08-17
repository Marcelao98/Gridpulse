
from sqlalchemy import create_engine, text

USER = "postgres"
PASSWORD = "154313"
HOST = "localhost"
PORT = "5432"

# Conecta no banco padrão 'postgres' pra poder criar o GridPulse
engine = create_engine(
    f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/postgres",
    isolation_level="AUTOCOMMIT"  # necessário pra CREATE DATABASE funcionar
)

try:
    with engine.connect() as conn:
        # Verifica se já existe pra não dar erro se rodar duas vezes
        result = conn.execute(text(
            "SELECT 1 FROM pg_database WHERE datname = 'gridpulse'"
        ))
        
        if not result.fetchone():
            conn.execute(text("CREATE DATABASE gridpulse"))
            print("Banco 'gridpulse' criado com sucesso!")
        else:
            print("Banco 'gridpulse' já existe.")

except Exception as e:
    print(f"Erro: {e}")

finally:
    engine.dispose()