# mega_secretaria/app/main.py

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uvicorn
import os

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
    # A estrutura exata pode variar. Verifique a documentação da Evolution API.
    try:
        message_type = webhook_data.data.get("key", {}).get("remoteJid")
        if not message_type or not message_type.endswith("@s.whatsapp.net"):
            print("Mensagem não é de um chat individual ou formato inesperado.")
            return {"status": "ignoring", "message": "Not a direct message or unexpected format"}

        # O remoteJid é o número do remetente (ex: 5521971189190@s.whatsapp.net)
        sender_phone_full = webhook_data.data.get("key", {}).get("remoteJid")
        sender_phone = sender_phone_full.split('@')[0] if sender_phone_full else None
        
        message_text = webhook_data.data.get("message", {}).get("conversation")
        if not message_text:
            message_text = webhook_data.data.get("message", {}).get("extendedTextMessage", {}).get("text")

        if not sender_phone or not message_text:
            print("Número do remetente ou texto da mensagem não encontrado.")
            return {"status": "error", "message": "Sender phone or message text not found"}

    except Exception as e:
        print(f"Erro ao parsear webhook data: {e}")
        raise HTTPException(status_code=400, detail=f"Erro ao parsear webhook data: {e}")

    # Log da mensagem recebida
    log_entry = MessageLog(
        phone_number=sender_phone,
        message_content=message_text,
        status="received"
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    # Verificar se o número está autorizado
    if sender_phone != settings.ALLOWED_PHONE_NUMBER:
        response_message = "Desculpe, este serviço está disponível apenas para números autorizados."
        background_tasks.add_task(send_whatsapp_message, sender_phone, response_message)
        log_entry.response_content = response_message
        log_entry.status = "unauthorized"
        db.commit()
        print(f"Requisição do número não autorizado: {sender_phone}")
        return {"status": "unauthorized", "message": "Phone number not allowed"}

    # Processar a mensagem com CrewAI em segundo plano
    background_tasks.add_task(process_message_with_crewai, sender_phone, message_text, log_entry.id)

    return {"status": "processing", "message": "Message received and being processed"}

async def process_message_with_crewai(phone_number: str, message_text: str, log_id: int):
    db = next(get_db()) # Obtém uma nova sessão de DB para a tarefa em background
    log_entry = db.query(MessageLog).filter(MessageLog.id == log_id).first()

    try:
        crew_instance = MegaSecretaryCrew(user_message=message_text)

        # Primeiro, rotear a requisição
        print(f"Roteando requisição para: {message_text}")
        routing_result = crew_instance.run_routing_flow()
        
        # A saída da tarefa de roteamento é uma string simples
        intent = routing_result.strip().lower()
        print(f"Intenção detectada: {intent}")

        final_response = ""
        if "gerenciamento de calendário" in intent:
            print("Iniciando fluxo de calendário...")
            crew_result = crew_instance.run_calendar_flow()
            final_response = crew_result
        else:
            print("Iniciando fluxo de outras requisições...")
            crew_result = crew_instance.run_other_flow()
            final_response = crew_result
        
        print(f"Resposta final da CrewAI: {final_response}")
        await send_whatsapp_message(phone_number, final_response)
        
        log_entry.response_content = final_response
        log_entry.status = "processed"
        db.commit()

    except Exception as e:
        error_message = f"Ocorreu um erro ao processar sua requisição: {e}"
        print(f"Erro no processamento da CrewAI para {phone_number}: {e}")
        await send_whatsapp_message(phone_number, error_message)
        
        log_entry.response_content = error_message
        log_entry.status = "error"
        db.commit()
    finally:
        db.close() # Garante que a sessão do DB seja fechada

if __name__ == "__main__":
    # Este bloco é para execução local, mas no EasyPanel o Uvicorn será iniciado diretamente.
    uvicorn.run(app, host="0.0.0.0", port=8000)

