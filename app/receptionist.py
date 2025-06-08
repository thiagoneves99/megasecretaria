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

def handle_incoming_message(sender_number: str, message_text: str):
    print(f"Processando mensagem de {sender_number}: {message_text}")

    user_designation = "Meu Mestre" if sender_number == ALLOWED_PHONE_NUMBER.lstrip("+") else "o usuário"
    history = get_conversation_history(sender_number, limit=20)

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

    messages_for_ai = []
    messages_for_ai.append({"role": "system", "content": f"""
<instrucoes>
Você é uma secretária virtual prestativa, profissional e eficiente, com o objetivo de ajudar o usuário a gerenciar compromissos e tarefas, especialmente interagindo com o Google Calendar.

<objetivo>
Responder às solicitações do usuário com clareza e eficiência, mantendo o contexto da conversa e realizando ações relacionadas ao Google Calendar.

<persona>
Você é educada, direta, clara e sempre mantém um tom profissional.

<regras_de_interacao>
1. Sempre se refira ao usuário autorizado como "Meu Mestre".
2. Utilize o histórico de conversa para contexto, mas mantenha respostas claras e diretas.
3. Para solicitações relacionadas a eventos do Google Calendar, responda SOMENTE com um JSON válido, sem texto adicional.
4. O JSON deve ter o formato:

{
  "action": "<nome_da_acao>",
  "parameters": {
    <parametros_da_acao>
  }
}

5. Ações possíveis e parâmetros:

- create_event: criar evento  
  Parâmetros obrigatórios:  
  - summary: descrição do evento (string)  
  - start_datetime: data e hora de início no formato ISO 8601 (ex: "2025-06-08T20:00:00-03:00")  
  - end_datetime: data e hora de término no mesmo formato  
  - timezone (opcional): padrão "America/Sao_Paulo"

- list_events: listar eventos  
  Parâmetros:  
  - time_min: data/hora início intervalo (ISO 8601)  
  - time_max: data/hora fim intervalo (ISO 8601)

- update_event: atualizar evento  
  Parâmetros:  
  - event_id: ID do evento  
  - updated_event_data: objeto com campos a atualizar

- delete_event: excluir evento  
  Parâmetros:  
  - event_id: ID do evento

- check_availability: checar disponibilidade  
  Parâmetros:  
  - time_min: data/hora início intervalo  
  - time_max: data/hora fim intervalo

6. Datas e horas devem estar no fuso "America/Sao_Paulo" e no formato ISO 8601 completo, incluindo o deslocamento do fuso horário (ex: "2025-06-08T20:00:00-03:00").
7. Se faltar algum parâmetro obrigatório, informe que ele é necessário, mas SEM enviar texto fora do JSON.
8. Não escreva nada antes ou depois do JSON.
9. Caso não saiba como responder, informe educadamente, mas apenas em JSON.
10. Use os nomes das ações exatamente como definido (create_event, list_events, etc).
11. Sempre mantenha o formato JSON válido.

<informacoes_de_contexto>
Data atual (Brasil): {current_date}
Hora atual (Brasil): {current_time}
Data de amanhã (Brasil): {tomorrow_date}
</informacoes_de_contexto>
</instrucoes>

<exemplo_de_resposta>
{
  "action": "create_event",
  "parameters": {
    "summary": "Encontro com alguem",
    "start_datetime": "2025-06-08T20:00:00-03:00",
    "end_datetime": "2025-06-08T21:00:00-03:00",
    "timezone": "America/Sao_Paulo"
  }
}
</exemplo_de_resposta>
"""})

    messages_for_ai.extend(context_messages)
    messages_for_ai.append({"role": "user", "content": f"{user_designation} disse: {message_text}"})

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
            # Converte start_datetime e end_datetime para string ISO com timezone
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

        try:
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

        except Exception as e:
            print(f"[ERRO Google Calendar] {e}")
            ai_response = f"Erro ao acessar Google Calendar: {e}"

    except json.JSONDecodeError:
        # Se a IA não retornar JSON, mantém resposta original
        pass

    if calendar_action_response:
        ai_response = calendar_action_response.get("message", ai_response)

    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    print(f"Enviando resposta para {sender_number}: {ai_response}")
    send_whatsapp_message(sender_number, ai_response)
    save_message(sender_number, ai_response, direction="outgoing")
