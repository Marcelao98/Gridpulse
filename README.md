# ⚡ GridPulse

Pipeline de dados para previsão de carga elétrica do Sistema Interligado Nacional (SIN), unindo Engenharia Elétrica, Engenharia de Dados e Machine Learning.

O projeto ingere dados públicos de operação do sistema elétrico brasileiro e de clima, processa-os através de uma arquitetura em camadas (medalhão), e treina um modelo XGBoost para prever a carga horária das quatro regiões do Brasil.

---

## 🧱 Arquitetura

O pipeline segue a arquitetura **medalhão** (bronze → silver → gold), com cada camada rodando como um script independente:

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

## 🐳 Infraestrutura

O projeto é 100% containerizado com **Docker**:

- Um container roda o **PostgreSQL** (armazenamento das camadas bronze/silver/gold)
- Outro container roda a **pipeline Python** (ingestão → processamento → feature engineering → inferência), orquestrados via **Docker Compose**

## 📂 Estrutura do repositório

```
GridPulse/
├── ingestion/       # Scripts de ingestão (camada bronze) — ONS e Open-Meteo
├── processing/       # Processamento e limpeza (camada silver)
├── features/          # Feature engineering (camada gold)
├── model/             # Treino e inferência do modelo XGBoost
├── database/         # Conexão e utilitários de banco de dados
├── models/            # Modelos treinados salvos (.joblib)
├── logs/                # Logs de execução da pipeline
├── main.py            # Orquestra o pipeline (ingestão → processamento → previsão)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env                # Credenciais (não versionado)
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
| Infraestrutura | Docker, Docker Compose |
| Versionamento | Git |

## 📌 Status do projeto

- ✅ Pipeline completa rodando ponta a ponta (ingestão → bronze → silver → gold → previsão), containerizada
- ✅ Modelo XGBoost treinado e validado (MAPE médio de 2,77% no conjunto de teste)
- 🚧 Monitoramento automatizado da execução diária — em construção
- 🚧 Orquestração e agendamento automático com **Apache Airflow** — em desenvolvimento

---

*Este README é uma primeira versão e será expandido com mais detalhes de uso, exemplos de execução e resultados.*
