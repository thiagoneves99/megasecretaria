# mega_secretaria/app/services/whatsapp_service.py

import httpx
from app.config import settings

async def send_whatsapp_message(phone_number: str, message: str ):
    """
    Envia uma mensagem de texto via Evolution API.
    """
    url = f"{settings.EVOLUTION_API_URL}/message/sendText/{settings.EVOLUTION_API_KEY}"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "number": phone_number,
        "options": {
            "delay": 1200
        },
        "textMessage": {
            "text": message
        }
    }

    try:
        async with httpx.AsyncClient( ) as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()  # Levanta uma exceção para códigos de status HTTP 4xx/5xx
            print(f"Mensagem enviada com sucesso para {phone_number}: {response.json()}")
            return response.json()
    except httpx.RequestError as exc:
        print(f"Erro ao enviar mensagem para {phone_number}: {exc}" )
        return {"status": "error", "message": f"Erro de requisição: {exc}"}
    except httpx.HTTPStatusError as exc:
        print(f"Erro HTTP ao enviar mensagem para {phone_number}: {exc.response.status_code} - {exc.response.text}" )
        return {"status": "error", "message": f"Erro HTTP: {exc.response.status_code} - {exc.response.text}"}
    except Exception as e:
        print(f"Erro inesperado ao enviar mensagem para {phone_number}: {e}")
        return {"status": "error", "message": f"Erro inesperado: {e}"}

