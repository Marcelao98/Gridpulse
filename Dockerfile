# Imagem base do Python
FROM python:3.11-slim

# Diretório onde o código vai morar dentro do container
WORKDIR /app

# libgomp1 é necessária pro xgboost rodar
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copia só o requirements primeiro (assim o Docker reusa esse passo
# em builds futuros se você não mudar as dependências, ficando mais rápido)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agora copia o resto do código do projeto
COPY . .

# Comando que roda quando o container sobe
# TROQUE "main.py" pelo arquivo que efetivamente inicia sua pipeline
CMD ["python", "main.py"]
