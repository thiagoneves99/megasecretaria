# Escolhe a imagem base
FROM python:3.11-slim

# Evita arquivos .pyc e habilita saída de logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Define um diretório base para o código
WORKDIR /code

# Copia requirements.txt primeiro para otimizar o cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do código do projeto para /code
# A estrutura interna será /code/app, /code/config, etc.
COPY . .

# Define o PYTHONPATH diretamente para /code (Formato Chave=Valor)
ENV PYTHONPATH=/code

# Expõe a porta que o Gunicorn usará
EXPOSE 8000

# Executa o servidor Gunicorn
# O módulo é app.main (arquivo /code/app/main.py)
# O objeto Flask é app
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
