# Escolhe a imagem base
FROM python:3.11-slim

# Evita arquivos .pyc e habilita saída de logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# Define o PYTHONPATH diretamente para incluir o diretório /app
ENV PYTHONPATH /app

# Define o diretório de trabalho
WORKDIR /app

# Copia e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para /app
# A estrutura interna será /app/app, /app/config, etc.
COPY . .

# Expõe a porta que o Gunicorn usará
EXPOSE 8000

# Executa o servidor Gunicorn apontando para app/main.py -> app object
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
