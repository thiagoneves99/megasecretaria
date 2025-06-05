# Escolhe a imagem base
FROM python:3.11-slim

# Evita arquivos .pyc e habilita saída de logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Define o diretório de trabalho
WORKDIR /app

# Copia e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para /app
COPY . .

# Expõe a porta que o Gunicorn usará
EXPOSE 8000

# Executa o servidor Gunicorn; 
# “main:app” deve apontar para seu Flask app, ex: app = Flask(__name__) em main.py
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "main:app"]
