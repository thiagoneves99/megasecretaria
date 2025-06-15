# mega_secretaria/app/main.py

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uvicorn
import os
import traceback # Importar traceback para depuração de erros

from app.config import settings
from app.services.whatsapp_service import send_whatsapp_message
from app.crew import MegaSecretaryCrew
from app.database import engine, Base, get_db
from app.models import MessageLog

# Cria as tabelas no banco de dados (se não existirem)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MegaSecretaria WhatsApp Bot",
    description="Um bot de secretaria inteligente para WhatsApp, integrado com Google Calendar e CrewAI.",
    version="1.0.0",
)

class WebhookMessage(BaseModel):
    # Adapte este modelo para a estrutura exata do webhook da Evolution API
    # Este é um exemplo simplificado. Consulte a documentação da Evolution API.
    instance: str
    data: dict

@app.get("/")
async def root():
    return {"message": "MegaSecretaria está online!"}

@app.post("/webhook/")
async def whatsapp_webhook(
    webhook_data: WebhookMessage,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    print(f"Webhook recebido: {webhook_data.model_dump_json()}")

    # Extrair informações da mensagem
    message_content = webhook_data.data.get('message', {}).get('conversation', '') or \
                      webhook_data.data.get('message', {}).get('extendedTextMessage', {}).get('text', '')

    sender_phone = webhook_data.data.get('key', {}).get('remoteJid', '').replace('@s.whatsapp.net', '')
    
    # PRINTS DE DEBUG PARA VALIDAR O NÚMERO
    print(f"Sender Phone Extraído: {sender_phone}")
    print(f"Allowed Phone Number na Config: {settings.ALLOWED_PHONE_NUMBER}")


    # Criar um log de mensagem inicial
    log_entry = MessageLog(
        phone_number=sender_phone,
        message_content=message_content,
        status="received"
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    try:
        if not message_content:
            print("Mensagem sem conteúdo de texto, ignorando.")
            # Atualiza o log para ignorado e não envia resposta ao usuário
            log_entry.response_content = "Mensagem sem conteúdo de texto."
            log_entry.status = "ignored"
            db.commit()
            raise HTTPException(status_code=200, detail="Mensagem sem conteúdo de texto.")

        # Filtrar mensagens apenas do número permitido
        if sender_phone != settings.ALLOWED_PHONE_NUMBER:
            print(f"!!! ATENÇÃO: Mensagem ignorada de {sender_phone}. Apenas {settings.ALLOWED_PHONE_NUMBER} é permitido. !!!")
            # Atualiza o log para ignorado e não envia resposta ao usuário
            log_entry.response_content = "Número não autorizado."
            log_entry.status = "ignored"
            db.commit()
            raise HTTPException(status_code=200, detail="Número não autorizado.")

        print(f"Roteando requisição para: {message_content}")

        crew_instance = MegaSecretaryCrew(user_message=message_content)
        
        # CORREÇÃO: Usar str() para garantir que é uma string
        routing_result = crew_instance.run_routing_flow()
        intent = str(routing_result).strip().lower() # Já estava correto aqui
        print(f"Intenção detectada: {intent}")

        final_response = ""
        if "gerenciamento de calendário" in intent:
            print("Iniciando fluxo de calendário...")
            crew_result = crew_instance.run_calendar_flow()
            final_response = str(crew_result) # <--- CORREÇÃO APLICADA AQUI
        else:
            print("Iniciando fluxo de outras requisições...")
            crew_result = crew_instance.run_other_flow()
            final_response = str(crew_result) # <--- CORREÇÃO APLICADA AQUI
        
        print(f"Resposta final da CrewAI: {final_response}")
        # NOVO PRINT DE DEBUG ANTES DE CHAMAR O SERVIÇO DE WHATSAPP
        print(f"DEBUG_MAIN: Prestes a chamar send_whatsapp_message para {sender_phone} com a resposta.")
        await send_whatsapp_message(sender_phone, final_response)

        log_entry.response_content = final_response
        log_entry.status = "processed"
        db.commit()

    except HTTPException as http_exc:
        # Se for uma HTTPException, ela já tem o status e detalhes, apenas a re-lançamos
        print(f"HTTPException ocorrida: {http_exc.detail}")
        # O log_entry já foi atualizado antes do raise http_exc
        raise http_exc # Re-lançar para que o FastAPI lide com ela

    except Exception as e:
        error_message = f"Ocorreu um erro ao processar sua requisição: {e}"
        print(f"Erro no processamento da CrewAI para {sender_phone}: {e}")
        traceback.print_exc() # Imprime o rastreamento completo do erro para depuração
        
        # NOVO PRINT DE DEBUG ANTES DE CHAMAR O SERVIÇO DE WHATSAPP NO ERRO
        print(f"DEBUG_MAIN: Chamando send_whatsapp_message com mensagem de erro para {sender_phone}.")
        await send_whatsapp_message(sender_phone, error_message)
        
        log_entry.response_content = error_message
        log_entry.status = "error"
        db.commit()
    finally:
        db.close() # Garante que a sessão do DB seja fechada

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)