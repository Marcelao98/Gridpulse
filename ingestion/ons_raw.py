import requests
import pandas as pd

from io import BytesIO
from datetime import datetime
from sqlalchemy import text

from database.db_connect import engine


# ── Funções ────────────────────────────────────────────────────────────────

def criar_tabela():
    """Cria o schema bronze e a tabela raw_ons, se não existirem."""

    with engine.connect() as conn:

        conn.execute(text("""
            CREATE SCHEMA IF NOT EXISTS bronze;
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bronze.raw_ons (
                id_subsistema             TEXT,
                nom_subsistema            TEXT,
                din_instante              TIMESTAMP,
                val_cargaenergiahomwmed   FLOAT,
                inserted_at               TIMESTAMP DEFAULT NOW()
            );
        """))

        conn.commit()

    print("✅ Tabela bronze.raw_ons verificada/criada.")


def get_data_mais_recente():
    """Retorna a data mais recente salva no banco."""

    with engine.connect() as conn:

        result = conn.execute(
            text("SELECT MAX(din_instante) FROM bronze.raw_ons")
        )

        return result.fetchone()[0]


def baixar_carga_ons(anos):

    base_url = (
        "https://ons-aws-prod-opendata.s3.amazonaws.com/"
        "dataset/curva-carga-ho/CURVA_CARGA_{}.xlsx"
    )

    dfs = []

    for ano in anos:

        print(f"Baixando {ano}...")

        try:

            response = requests.get(
                base_url.format(ano),
                timeout=60
            )

            if response.status_code == 200:

                df = pd.read_excel(
                    BytesIO(response.content)
                )

                dfs.append(df)

                print(f"✅ {ano} OK")

            else:

                print(
                    f"⚠️ {ano} não encontrado "
                    f"({response.status_code})"
                )

        except Exception as e:

            print(f"❌ Erro em {ano}: {e}")

    if dfs:

        return pd.concat(
            dfs,
            ignore_index=True
        )

    return None


def salvar_no_banco(df):

    cols = [
        "id_subsistema",
        "nom_subsistema",
        "din_instante",
        "val_cargaenergiahomwmed"
    ]

    df[cols].to_sql(
        "raw_ons",
        engine,
        schema="bronze",
        if_exists="append",
        index=False
    )

    print(f"✅ {len(df):,} linhas salvas.")


# ── Pipeline principal ─────────────────────────────────────────────────────

def ingerir_ons():

    criar_tabela()

    data_mais_recente = get_data_mais_recente()

    if data_mais_recente is None:

        print(
            "Banco vazio — baixando histórico completo..."
        )

        anos = list(
            range(2019, datetime.now().year + 1)
        )

        df = baixar_carga_ons(anos)

        if df is not None:

            df["din_instante"] = pd.to_datetime(
                df["din_instante"]
            )

            salvar_no_banco(df)

    else:

        print(
            f"Último registro: {data_mais_recente}"
        )

        ano_atual = datetime.now().year

        df = baixar_carga_ons([ano_atual])

        if df is not None:

            df["din_instante"] = pd.to_datetime(
                df["din_instante"]
            )

            df_novo = df[
                df["din_instante"] > data_mais_recente
            ]

            if df_novo.empty:

                print("Nenhum dado novo.")

            else:

                print(
                    f"{len(df_novo):,} novos registros."
                )

                salvar_no_banco(df_novo)


if __name__ == "__main__":

    ingerir_ons()

    engine.dispose()