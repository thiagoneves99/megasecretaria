from .utils.ai_client import get_ai_response
from .utils.whatsapp_client import send_whatsapp_message
from .utils.db_handler import save_message, get_conversation_history
from .utils.google_calendar_client import (
    get_calendar_service, create_calendar_event, list_calendar_events,
    update_calendar_event, delete_calendar_event, check_calendar_availability
)
from config.settings import ALLOWED_PHONE_NUMBER
import tiktoken
import json
import re
from datetime import datetime, timedelta
import pytz

MAX_TOKENS_HISTORY = 1000

# Controle simples para evitar criar eventos duplicados
last_event_created = {
    "summary": None,
    "start": None,
    "timestamp": None
}

# Estado da conversa para cada usuário (em memória)
conversation_state = {}

def handle_incoming_message(sender_number: str, message_text: str):
    global last_event_created, conversation_state

    print(f"Processando mensagem de {sender_number}: {message_text}")

    user_designation = "Meu Mestre" if sender_number == ALLOWED_PHONE_NUMBER.lstrip("+") else "o usuário"
    history = get_conversation_history(sender_number, limit=20)

    # Normaliza texto para facilitar lógica
    text_lower = message_text.strip().lower()

    # 1) Verifica se está aguardando confirmação do usuário para criar evento mesmo com conflito
    if sender_number in conversation_state and conversation_state[sender_number].get("awaiting_confirmation"):
        if text_lower == "sim":
            params = conversation_state[sender_number]["pending_event_params"]
            service = get_calendar_service()
            if service:
                calendar_action_response = create_calendar_event(service, params)
                response = calendar_action_response.get("message", "Evento criado conforme solicitado.")
            else:
                response = "Não foi possível acessar o calendário para criar o evento."
            # Limpa estado após confirmação
            conversation_state.pop(sender_number, None)
            send_whatsapp_message(sender_number, response)
            save_message(sender_number, response, direction="outgoing")
            return
        elif text_lower in ["não", "nao"]:
            response = "Ok, então escolha outro horário para o evento."
            conversation_state.pop(sender_number, None)
            send_whatsapp_message(sender_number, response)
            save_message(sender_number, response, direction="outgoing")
            return
        else:
            # Resposta inválida
            response = "Por favor, responda com 'sim' para confirmar ou 'não' para escolher outro horário."
            send_whatsapp_message(sender_number, response)
            save_message(sender_number, response, direction="outgoing")
            return

    # 2) Monta histórico para contexto de IA
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    current_history_tokens = 0
    context_messages = []

    for msg_text, msg_direction in reversed(history):
        role = "user" if msg_direction == "incoming" else "assistant"
        message_tokens = len(encoding.encode(msg_text))
        if current_history_tokens + message_tokens > MAX_TOKENS_HISTORY:
            break
        context_messages.insert(0, {"role": role, "content": msg_text})
        current_history_tokens += message_tokens

    brazil_timezone = pytz.timezone("America/Sao_Paulo")
    now_brazil = datetime.now(brazil_timezone)
    current_date = now_brazil.strftime("%Y-%m-%d")
    current_time = now_brazil.strftime("%H:%M")
    tomorrow_date = (now_brazil + timedelta(days=1)).strftime("%Y-%m-%d")

    # 3) Mensagens para a IA
    messages_for_ai = []
    messages_for_ai.append({"role": "system", "content": f"""
<instrucoes>
A seguir você encontrará todas as instruções necessárias para realizar seu trabalho como uma secretária virtual. Siga à risca as instruções.

<objetivo>
Atender às solicitações do usuário de forma prestativa, eficiente e natural, mantendo o contexto da conversa. Você também é capaz de interagir com o Google Calendar para gerenciar eventos.

<persona>
Você é uma secretária virtual prestativa, eficiente e profissional. Seu objetivo principal é auxiliar o usuário em suas tarefas e responder às suas perguntas de forma clara e concisa. Você deve ser educada e sempre manter um tom de voz adequado.

<regras_de_interacao>
1. **Saudação ao Usuário Autorizado:** Sempre se refira ao usuário autorizado (identificado como "Meu Mestre") como "Meu Mestre" em suas respostas.
2. **Memória de Conversa:** Utilize o histórico de conversas fornecido para manter o contexto e fornecer respostas mais relevantes.
3. **Respostas Claras e Concisas:** Forneça informações diretas e evite divagações.
4. **Interação com Google Calendar:** Se a solicitação do usuário for relacionada a eventos no Google Calendar (criar, listar, atualizar, excluir, verificar disponibilidade), você DEVE responder SOMENTE com um objeto JSON no seguinte formato:

{{
  "action": "<nome_da_acao>",
  "parameters": {{
    <parametros_da_acao>
  }}
}}

IMPORTANTE: NÃO escreva nenhum texto antes ou depois do JSON. A resposta deve começar com o caractere {{ e ser um JSON válido.

As ações possíveis são: create_event, list_events, update_event, delete_event, check_availability.

- Datas: Use sempre o formato YYYY-MM-DD. "Hoje" corresponde a {current_date}, "amanhã" a {tomorrow_date}.
- Horários: Use sempre o formato HH:MM (24 horas), considerando o fuso horário do Brasil (America/Sao_Paulo).

5. **Limitações:** Se não souber como responder a uma solicitação ou se ela estiver fora de suas capacidades, informe o usuário educadamente.
6. **Tom de Voz:** Mantenha um tom profissional e prestativo.
</regras_de_interacao>

<informacoes_de_contexto>
Data atual (Brasil): {current_date}
Hora atual (Brasil): {current_time}
Data de amanhã (Brasil): {tomorrow_date}
</informacoes_de_contexto>
"""})
    messages_for_ai.extend(context_messages)
    messages_for_ai.append({"role": "user", "content": f"{user_designation} disse: {message_text}"})

    # 4) Chama a IA
    ai_response = get_ai_response(messages_for_ai)

    calendar_action_response = None
    ai_response_clean = re.sub(r"```json|```", "", ai_response).strip()

    try:
        ai_response_json = json.loads(ai_response_clean)
        action = ai_response_json.get("action")
        parameters = ai_response_json.get("parameters", {})

        # Ajustar datetime para ISO 8601 com timezone se for create_event
        if action == "create_event":
            tz = pytz.timezone(parameters.get("timezone", "America/Sao_Paulo"))

            def parse_datetime(dt_str):
                try:
                    dt = datetime.fromisoformat(dt_str)
                    if dt.tzinfo is None:
                        dt = tz.localize(dt)
                    else:
                        dt = dt.astimezone(tz)
                    return dt.isoformat()
                except Exception:
                    return dt_str

            if "start_datetime" in parameters:
                parameters["start_datetime"] = parse_datetime(parameters["start_datetime"])
            if "end_datetime" in parameters:
                parameters["end_datetime"] = parse_datetime(parameters["end_datetime"])

        service = get_calendar_service()
        if not service:
            ai_response = "Desculpe, não consegui conectar ao Google Calendar no momento."
        else:
            global last_event_created
            current_time_check = datetime.now()

            if action == "create_event":
                # Verifica parâmetros mínimos
                if not parameters.get("summary") or not parameters.get("start_datetime") or not parameters.get("end_datetime"):
                    ai_response = "Parâmetros summary, start_datetime e end_datetime são obrigatórios para criar evento."
                else:
                    # Verifica eventos conflitantes
                    conflitantes = check_calendar_availability(service, parameters["start_datetime"], parameters["end_datetime"])
                    if conflitantes and len(conflitantes) > 0:
                        # Guarda estado para confirmação
                        conversation_state[sender_number] = {
                            "awaiting_confirmation": True,
                            "pending_event_params": parameters
                        }

                        # Formata mensagem de conflito
                        msg = "⚠️ Já existe evento(s) neste horário:\n\n"
                        for ev in conflitantes:
                            start_str = datetime.fromisoformat(ev["start"]).strftime("%d/%m/%Y %H:%M")
                            end_str = datetime.fromisoformat(ev["end"]).strftime("%d/%m/%Y %H:%M")
                            msg += f"- {ev['summary']} das {start_str} até {end_str}\n"
                        msg += "\nDeseja marcar este novo evento mesmo assim? (Responda com 'sim' para confirmar ou 'não' para escolher outro horário)."

                        ai_response = msg
                    else:
                        # Evita duplicação
                        is_duplicate = (
                            last_event_created["summary"] == parameters.get("summary") and
                            last_event_created["start"] == parameters.get("start_datetime") and
                            last_event_created["timestamp"] is not None and
                            (current_time_check - last_event_created["timestamp"]).total_seconds() < 60
                        )
                        if is_duplicate:
                            ai_response = "Evento já foi criado recentemente. Evitando duplicação."
                        else:
                            calendar_action_response = create_calendar_event(service, parameters)
                            last_event_created = {
                                "summary": parameters.get("summary"),
                                "start": parameters.get("start_datetime"),
                                "timestamp": datetime.now()
                            }
            elif action == "list_events":
                calendar_action_response = list_calendar_events(service, parameters.get("time_min"), parameters.get("time_max"))
            elif action == "update_event":
                calendar_action_response = update_calendar_event(service, parameters.get("event_id"), parameters.get("updated_event_data"))
            elif action == "delete_event":
                calendar_action_response = delete_calendar_event(service, parameters.get("event_id"))
            elif action == "check_availability":
                calendar_action_response = check_calendar_availability(service, parameters.get("time_min"), parameters.get("time_max"))

    except json.JSONDecodeError:
        # Se a IA não retornar JSON, mantém resposta original
        pass
    except Exception as e:
        print(f"[ERRO no processamento do Google Calendar]: {e}")
        ai_response = f"Erro ao processar sua solicitação: {e}"

    # Se resposta da ação do calendário existir, usa ela
    if calendar_action_response:
        ai_response = calendar_action_response.get("message", ai_response)

    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    print(f"Enviando resposta para {sender_number}: {ai
