# mega_secretaria/app/services/whatsapp_service.py

import httpx
from app.config import settings
import json # Importar json para depuração do payload

async def send_whatsapp_message(phone_number: str, message: str):
    """
    Envia uma mensagem de texto via Evolution API.
    """
    url = f"{settings.EVOLUTION_API_URL}/message/sendText/{settings.EVOLUTION_API_INSTANCE_NAME}"
    headers = {
        "Content-Type": "application/json",
        "apikey": settings.EVOLUTION_API_KEY  # <--- MUDANÇA CRÍTICA: Use "apikey" como no código antigo
    }
    payload = {
        "number": phone_number,
        "options": {
            "delay": 1200,
            "presence": "composing", # Adicionado do código antigo
            "linkPreview": False # Adicionado do código antigo
        },
        "text": message # <--- MUDANÇA CRÍTICA: Use "text" diretamente no payload, como no código antigo
    }

    # Debug logs mais detalhados
    print(f"DEBUG: Tentando enviar mensagem para a URL: {url}")
    print(f"DEBUG: Headers da Requisição: {headers}")
    print(f"DEBUG: Payload da Requisição: {json.dumps(payload, indent=2)}") # Imprime o payload formatado

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0) # httpx usa 'json' para dics
            response.raise_for_status()  # Levanta uma exceção para códigos de status HTTP 4xx/5xx

            print(f"DEBUG: Mensagem enviada com sucesso para {phone_number}. Status HTTP: {response.status_code}")
            print(f"DEBUG: Resposta completa da Evolution API: {response.text}") # Imprime a resposta completa da API
            return response.json()
    except httpx.RequestError as exc:
        print(f"ERRO DE REQUISIÇÃO (httpx.RequestError) ao enviar mensagem para {phone_number}: {exc}")
        return {"status": "error", "message": f"Erro de requisição: {exc}"}
    except httpx.HTTPStatusError as exc:
        # Este bloco DEVE capturar erros como 401 (Auth) ou 400 (Bad Request)
        print(f"ERRO HTTP (httpx.HTTPStatusError) ao enviar mensagem para {phone_number}: Status {exc.response.status_code} - Body: {exc.response.text}")
        return {"status": "error", "message": f"Erro HTTP: {exc.response.status_code} - {exc.response.text}"}
    except Exception as e:
        print(f"ERRO INESPERADO ao enviar mensagem para {phone_number}: {e}")
        import traceback
        traceback.print_exc() # Imprime o rastreamento completo do erro para depuração
        return {"status": "error", "message": f"Erro inesperado: {e}"}