# mega_secretaria/Dockerfile

# Use uma imagem base Python mais recente com uma versão mais nova do Debian
FROM python:3.11-slim-bookworm

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Instala as dependências de sistema necessárias para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Uvicorn irá rodar
EXPOSE 8000

# Comando para iniciar a aplicação usando Uvicorn
# O --host 0.0.0.0 é necessário para que a aplicação seja acessível de fora do contêiner
# O --port 8000 é a porta padrão que o EasyPanel espera
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
