import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env na pasta config
# O caminho é relativo à raiz do projeto onde o main.py será executado
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# Evolution API
EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL')
EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY')

# Webhook
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Security
ALLOWED_PHONE_NUMBER = os.getenv('ALLOWED_PHONE_NUMBER')

# AI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
AI_MODEL_NAME = os.getenv('AI_MODEL_NAME', 'gpt-4o-mini') # Default model

# Database
DATABASE_URL = os.getenv('DATABASE_URL')

# Validações básicas (opcional, mas recomendado)
if not all([EVOLUTION_API_URL, EVOLUTION_API_KEY, WEBHOOK_URL, ALLOWED_PHONE_NUMBER, OPENAI_API_KEY, DATABASE_URL]):
    print("AVISO: Uma ou mais variáveis de ambiente essenciais não foram definidas no arquivo .env!")
    # Poderia lançar um erro aqui para impedir a execução
    # raise ValueError("Variáveis de ambiente essenciais faltando.")

