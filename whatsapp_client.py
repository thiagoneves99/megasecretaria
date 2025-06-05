# app/utils/whatsapp_client.py

import requests
import json
from config.settings import EVOLUTION_API_URL, EVOLUTION_API_KEY

# Placeholder para a instância da Evolution API (ajustar conforme a biblioteca real ou chamadas diretas)
INSTANCE_NAME = "default" # Ou o nome da sua instância na Evolution API

API_ENDPOINT = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"

HEADERS = {
    "apikey": EVOLUTION_API_KEY,
    "Content-Type": "application/json"
}

def send_whatsapp_message(recipient_number, message_text):
    """Envia uma mensagem de texto via Evolution API."""
    payload = json.dumps({
        "number": recipient_number,
        "options": {
            "delay": 1200,
            "presence": "composing", # Simula digitação
            "linkPreview": False
        },
        "textMessage": {
            "text": message_text
        }
    })

    try:
        response = requests.post(API_ENDPOINT, headers=HEADERS, data=payload, timeout=30)
        response.raise_for_status() # Lança exceção para respostas de erro (4xx ou 5xx)
        print(f"Mensagem enviada para {recipient_number}: {response.status_code}")
        print(f"Resposta API: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar mensagem para {recipient_number}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Detalhes do erro: {e.response.text}")
        return None

# Outras funções podem ser adicionadas aqui (enviar mídia, etc.)

