# app/utils/whatsapp_client.py

import requests
import json
from config import settings

# Nome da instância da Evolution API
INSTANCE_NAME = "Megasecretaria"

# Monta a URL base correta (sem a porta, conforme descoberto)
BASE_API_URL = settings.EVOLUTION_API_URL

# Monta a URL completa para envio de texto, incluindo o nome da instância
SEND_URL = f"{BASE_API_URL}/message/sendText/{INSTANCE_NAME}"

HEADERS = {
    "apikey": settings.EVOLUTION_API_KEY,
    "Content-Type": "application/json"
}

def send_whatsapp_message(recipient_number: str, message: str):
    """Envia uma mensagem de texto via Evolution API."""
    payload = {
        "number": recipient_number,
        "options": {
            "delay": 1200,
            "presence": "composing", # Simula digitação
            "linkPreview": False
        },
        "textMessage": {
            "text": message
        }
    }

    try:
        print(f"Tentando enviar para: {SEND_URL}") # Log para debug
        response = requests.post(SEND_URL, headers=HEADERS, data=json.dumps(payload), timeout=30)
        response.raise_for_status()  # Lança exceção para erros HTTP (4xx ou 5xx)
        print(f"Mensagem enviada com sucesso para {recipient_number}. Status: {response.status_code}")
        # print(f"Resposta da API: {response.text}") # Descomente para debug detalhado
        return True
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para {recipient_number}: {e}")
        # Tentar logar a resposta se houver, mesmo em caso de erro
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f"Resposta de erro da API: Status {e.response.status_code}, Body: {e.response.text}")
            except Exception as inner_e:
                print(f"Não foi possível ler a resposta de erro da API: {inner_e}")
        return False

