# mega_secretaria/app/main.py

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc # NOVO: Importar desc para ordenar
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
    # Prioriza 'conversation', depois 'extendedTextMessage.text'
    message_content = webhook_data.data.get('message', {}).get('conversation', '')
    if not message_content:
        message_content = webhook_data.data.get('message', {}).get('extendedTextMessage', {}).get('text', '')

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
    db.refresh(log_entry) # Para ter o ID e timestamp atualizados

    # Verificar se o número é permitido e se há conteúdo para processar
    if not message_content:
        print("Mensagem sem conteúdo de texto, ignorando.")
        log_entry.response_content = "Mensagem sem conteúdo de texto."
        log_entry.status = "ignored"
        db.commit()
        raise HTTPException(status_code=200, detail="Mensagem sem conteúdo de texto.")

    if settings.ALLOWED_PHONE_NUMBER and sender_phone != settings.ALLOWED_PHONE_NUMBER:
        print(f"!!! ATENÇÃO: Mensagem ignorada de {sender_phone}. Apenas {settings.ALLOWED_PHONE_NUMBER} é permitido. !!!")
        log_entry.response_content = "Número não autorizado."
        log_entry.status = "ignored"
        db.commit()
        raise HTTPException(status_code=200, detail="Número não autorizado.")
    
    # Se chegou até aqui, a mensagem é válida para processamento, delega para background
    background_tasks.add_task(process_message_in_background, sender_phone, message_content, log_entry.id, db)
    
    return {"status": "processing", "message": "Mensagem recebida e será processada."}


async def process_message_in_background(sender_phone: str, user_message: str, log_id: int, db: Session):
    # Re-obtem o log_entry dentro da função de background para garantir que a sessão está ativa e o objeto persistente
    log_entry = db.query(MessageLog).filter(MessageLog.id == log_id).first()
    if not log_entry:
        print(f"Erro: Log entry com ID {log_id} não encontrado para atualização.")
        return # Ou trate o erro de outra forma

    try:
        # NOVO: Buscar histórico da conversa
        # Limita o histórico a, por exemplo, as últimas 5 mensagens (excluindo a atual que está sendo processada)
        # Isso evita que o histórico fique muito longo e consuma muitos tokens.
        conversation_history = db.query(MessageLog)\
                                 .filter(MessageLog.phone_number == sender_phone)\
                                 .filter(MessageLog.id != log_id) \
                                 .order_by(desc(MessageLog.timestamp))\
                                 .limit(5).all()
        
        # Inverter a ordem para que as mensagens mais antigas venham primeiro
        conversation_history.reverse()

        # Formatar o histórico para ser injetado nos prompts
        formatted_history = []
        for msg in conversation_history:
            if msg.message_content:
                # Certifica-se de que a mensagem do usuário está claramente identificada
                formatted_history.append(f"User: {msg.message_content}")
            if msg.response_content:
                # Certifica-se de que a resposta do assistente está claramente identificada
                formatted_history.append(f"Assistant: {msg.response_content}")
        
        history_string = "\n".join(formatted_history)
        if history_string:
            # Adiciona um cabeçalho e rodapé para o bloco de histórico no prompt
            history_string = f"\n----- Histórico da Conversa -----\n{history_string}\n---------------------------------\n"
        else:
            history_string = "" # Se não houver histórico, string vazia

        print(f"Histórico para {sender_phone}:\n{history_string}")


        # 1. Fluxo de roteamento
        crew_instance = MegaSecretaryCrew(user_message=user_message)
        print(f"Roteando requisição para: {user_message}")
        
        # Passar o histórico para a tarefa de roteamento
        routing_result = crew_instance.run_routing_flow(history=history_string) 
        intent = str(routing_result).strip().lower() 
        print(f"Intenção detectada: {intent}")

        final_response = ""

        if "gerenciamento de calendário" in intent:
            print("Iniciando fluxo de gerenciamento de calendário...")
            # Passar o histórico também para o fluxo de calendário
            crew_result = crew_instance.run_calendar_flow(history=history_string) 
            final_response = str(crew_result)
        else: # Assumed to be "outra_requisição" or other non-calendar intent
            print("Iniciando fluxo de outras requisições...")
            # Passar o histórico para o fluxo de chat geral
            crew_result = crew_instance.run_other_flow(history=history_string)
            final_response = str(crew_result)
        
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
        # Não enviar mensagem de erro para o usuário se for um erro controlado de filtro
        if http_exc.status_code not in [200]: # Não logar como erro se for 200 (ignorados)
             # Logar o erro apenas se não for um caso de ignorado (status_code 200)
            log_entry.response_content = f"Erro controlado: {http_exc.detail}"
            log_entry.status = "error_controlled"
            db.commit()
        raise http_exc 

    except Exception as e:
        error_message = f"Desculpe, ocorreu um erro inesperado ao processar sua requisição. Por favor, tente novamente mais tarde."
        print(f"Erro inesperado no processamento da CrewAI para {sender_phone}: {e}")
        traceback.print_exc() # Imprime o rastreamento completo do erro para depuração
        
        # NOVO PRINT DE DEBUG ANTES DE CHAMAR O SERVIÇO DE WHATSAPP NO ERRO
        print(f"DEBUG_MAIN: Chamando send_whatsapp_message com mensagem de erro para {sender_phone}.")
        await send_whatsapp_message(sender_phone, error_message)
        
        log_entry.response_content = error_message
        log_entry.status = "error"
        db.commit()

    finally:
        # Garante que a sessão do banco de dados seja fechada corretamente, mesmo em caso de erro
        db.close() 

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)