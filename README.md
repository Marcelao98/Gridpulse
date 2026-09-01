# ⚡ GridPulse

Pipeline de dados para previsão de carga elétrica do Sistema Interligado Nacional (SIN), unindo Engenharia Elétrica, Engenharia de Dados e Machine Learning.

O projeto ingere dados públicos de operação do sistema elétrico brasileiro e de clima, processa-os através de uma arquitetura em camadas (medalhão), treina um modelo XGBoost para prever a carga horária das quatro regiões do Brasil, e roda de forma 100% automatizada e orquestrada via Apache Airflow.

---

## 🧱 Arquitetura

O pipeline segue a arquitetura **medalhão** (bronze → silver → gold), com cada camada rodando como uma etapa independente:

```
Fontes (ONS, Open-Meteo)
        │
        ▼
   🥉 Bronze   → ingestão dos dados brutos, sem transformação
        │
        ▼
   🥈 Silver   → junção das fontes, limpeza e padronização
        │
        ▼
   🥇 Gold     → feature engineering + treino/inferência do XGBoost
```

**Fontes de dados:**
- **ONS** (Operador Nacional do Sistema Elétrico) — carga horária das quatro regiões do Brasil (Norte, Nordeste, Sudeste, Sul)
- **Open-Meteo** — temperatura horária por região, usada como proxy climático

Todo o dado transita por **PostgreSQL** — não há uso de arquivos CSV como armazenamento intermediário em nenhuma etapa do pipeline.

## 🌀 Orquestração com Apache Airflow

A pipeline roda de forma **totalmente automatizada e diária**, orquestrada por Airflow. Cada etapa é uma task independente, disparada via `DockerOperator`:

```
[ingestao_ons, ingestao_openmeteo] → processamento_silver → feature_engineering_gold → gerar_previsoes
```

- **Ingestão ONS** e **Ingestão Open-Meteo** rodam em **paralelo** (fontes independentes entre si)
- **Silver** só inicia depois que **ambas** terminarem com sucesso
- **Gold** e **Previsão** seguem em sequência
- Execução agendada via cron (`0 9 * * *`), com retry automático em caso de falha
- Credenciais gerenciadas via **Airflow Connections** — nenhum segredo exposto em código

O `main.py` aceita um argumento `--etapa` (ex: `python main.py --etapa ingestao_ons`), permitindo que cada task do Airflow execute apenas sua etapa correspondente, sem depender de rodar a pipeline inteira.

**O que não está neste repositório** (por ser infraestrutura de execução, não código do projeto — mesmo princípio de não versionar a imagem do Postgres): a configuração completa do Airflow (`docker-compose-airflow.yaml`, o setup oficial da Apache), logs internos e configs geradas automaticamente em tempo de execução. A DAG (`dags/dag_gp.py`), que é código autoral do projeto, está versionada normalmente.

## 🐳 Infraestrutura

O projeto é 100% containerizado com **Docker**:

- Um container roda o **PostgreSQL** (armazenamento das camadas bronze/silver/gold)
- Outro container roda a **pipeline Python**, orquestrado pelo Airflow via Docker Compose

## 📂 Estrutura do repositório

```
GridPulse/
├── dags/               # DAG do Airflow que orquestra a pipeline
├── ingestion/          # Scripts de ingestão (camada bronze) — ONS e Open-Meteo
├── processing/         # Processamento e limpeza (camada silver)
├── features/           # Feature engineering (camada gold)
├── model/              # Treino e inferência do modelo XGBoost
├── database/           # Conexão e utilitários de banco de dados
├── models/              # Modelos treinados salvos (.joblib)
├── logs/                 # Logs de execução da pipeline
├── main.py             # Executa a pipeline completa, ou uma etapa isolada via --etapa
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env                 # Credenciais (não versionado)
```

## 📊 Análises exploratórias

Antes da construção da pipeline, o projeto partiu de uma série de notebooks de análise exploratória sobre consumo e carga elétrica no Brasil (dados EPE, ONS e INMET/Open-Meteo) — cobrindo desde a visão macro de duas décadas até a granularidade horária do sistema, incluindo a modelagem inicial com XGBoost que deu origem ao modelo em produção aqui.

📓 *Repositório dos notebooks: [link a adicionar]*

## 🛠️ Stack Técnica

| Categoria | Ferramentas |
|---|---|
| Linguagem | Python 3.11 |
| Banco de Dados | PostgreSQL, SQLAlchemy |
| Manipulação de Dados | Pandas, NumPy |
| Machine Learning | XGBoost, Scikit-learn |
| Orquestração | Apache Airflow (DockerOperator, Connections) |
| Infraestrutura | Docker, Docker Compose |
| Versionamento | Git |

## 📌 Status do projeto

- ✅ Pipeline completa rodando ponta a ponta (ingestão → bronze → silver → gold → previsão), containerizada
- ✅ Modelo XGBoost treinado e validado (MAPE médio de 2,77% no conjunto de teste)
- ✅ Orquestração completa com **Apache Airflow** — execução diária automatizada, tasks paralelas/sequenciais, credenciais seguras via Connections
- 🚧 Monitoramento e alertas de falha — em construção
- 🚧 Deploy em nuvem — próximo passo

---

*Este README é uma primeira versão e será expandido com mais detalhes de uso, exemplos de execução e resultados.*
