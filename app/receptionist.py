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

# Controle para evitar criar eventos duplicados repetidamente
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

    text_lower = message_text.strip().lower()

    # 1) Verifica se está aguardando confirmação para criar evento com conflito
    if sender_number in conversation_state and conversation_state[sender_number].get("awaiting_confirmation"):
        resposta = _handle_confirmation_response(sender_number, text_lower)
        return resposta

    # 2) Prepara histórico para contexto da IA
    context_messages = _build_context_messages(history)

    # 3) Dados de data/hora para o sistema
    brazil_tz = pytz.timezone("America/Sao_Paulo")
    now_brazil = datetime.now(brazil_tz)
    current_date = now_brazil.strftime("%Y-%m-%d")
    current_time = now_brazil.strftime("%H:%M")
    tomorrow_date = (now_brazil + timedelta(days=1)).strftime("%Y-%m-%d")

    # 4) Monta mensagem para IA com instruções e contexto
    messages_for_ai = _compose_ai_prompt(context_messages, user_designation, message_text, current_date, current_time, tomorrow_date)

    # 5) Chama IA e processa resposta
    ai_response, calendar_action_response = _process_ai_response(messages_for_ai, sender_number, current_date, current_time)

    # 6) Resposta final, envio e salvamento
    if calendar_action_response:
        ai_response = calendar_action_response.get("message", ai_response)

    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    print(f"Enviando resposta para {sender_number}: {ai_response}")

    send_whatsapp_message(sender_number, ai_response)
    save_message(sender_number, ai_response, direction="outgoing")


def _handle_confirmation_response(sender_number, text_lower):
    state = conversation_state.get(sender_number)
    if text_lower == "sim":
        params = state["pending_event_params"]
        service = get_calendar_service()
        if service:
            calendar_resp = create_calendar_event(service, params, force=True)
            if calendar_resp.get("status") == "success":
                response = calendar_resp.get("message", "Evento criado conforme solicitado.")
                conversation_state.pop(sender_number, None)
            else:
                response = calendar_resp.get("message", "Erro ao criar evento após confirmação. Por favor, tente novamente.")
    elif text_lower in ["não", "nao"]:
        response = "Ok, então escolha outro horário para o evento."
        conversation_state.pop(sender_number, None)
    else:
        response = "Por favor, responda com \'sim\' para confirmar ou \'não\' para escolher outro horário."

    send_whatsapp_message(sender_number, response)
    save_message(sender_number, response, direction="outgoing")
    return response


def _build_context_messages(history):
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    current_tokens = 0
    context = []

    for msg_text, msg_direction in reversed(history):
        role = "user" if msg_direction == "incoming" else "assistant"
        tokens = len(encoding.encode(msg_text))
        if current_tokens + tokens > MAX_TOKENS_HISTORY:
            break
        context.insert(0, {"role": role, "content": msg_text})
        current_tokens += tokens

    return context


def _compose_ai_prompt(context_messages, user_designation, message_text, current_date, current_time, tomorrow_date):
    system_msg = f"""
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

Para \'delete_event\' e \'update_event\', o \'event_id\' é um parâmetro obrigatório. O \'event_id\' deve ser obtido de uma listagem prévia de eventos ou fornecido explicitamente pelo usuário.

Exemplo para deletar um evento:
{{
  "action": "delete_event",
  "parameters": {{
    "event_id": "o_id_do_evento_a_ser_deletado"
  }}
}}

Exemplo para atualizar um evento:
{{
  "action": "update_event",
  "parameters": {{
    "event_id": "o_id_do_evento_a_ser_atualizado",
    "updates": {{
      "summary": "Novo Título do Evento",
      "start_datetime": "YYYY-MM-DD HH:MM",
      "end_datetime": "YYYY-MM-DD HH:MM"
    }}
  }}
}}

5. **Limitações:** Se não souber como responder a uma solicitação ou se ela estiver fora de suas capacidades, informe o usuário educadamente.
6. **Tom de Voz:** Mantenha um tom profissional e prestativo.
</regras_de_interacao>

<informacoes_de_contexto>
Data atual (Brasil): {current_date}
Hora atual (Brasil): {current_time}
Data de amanhã (Brasil): {tomorrow_date}
</informacoes_de_contexto>
"""
    messages = [{"role": "system", "content": system_msg}]
    messages.extend(context_messages)
    messages.append({"role": "user", "content": f"{user_designation} disse: {message_text}"})
    return messages


def _process_ai_response(messages_for_ai, sender_number, current_date, current_time):
    ai_response = get_ai_response(messages_for_ai)
    calendar_action_response = None

    ai_response_clean = re.sub(r"```json|```", "", ai_response).strip()
    try:
        ai_json = json.loads(ai_response_clean)
        if not isinstance(ai_json, dict):
            raise json.JSONDecodeError("AI response is not a valid action JSON", ai_response_clean, 0)
        action = ai_json.get("action")
        parameters = ai_json.get("parameters", {})

        # Ajusta datetime para ISO 8601 com timezone para create_event
        if action == "create_event":
            tz = pytz.timezone(parameters.get("timezone", "America/Sao_Paulo"))

            def parse_dt(dt_str):
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
                parameters["start_datetime"] = parse_dt(parameters["start_datetime"])
            if "end_datetime" in parameters:
                parameters["end_datetime"] = parse_dt(parameters["end_datetime"])

        service = get_calendar_service()
        if not service:
            return "Desculpe, não consegui conectar ao Google Calendar no momento.", None

        global last_event_created
        now = datetime.now()

        if action == "create_event":
            if not parameters.get("summary") or not parameters.get("start_datetime") or not parameters.get("end_datetime"):
                return "Parâmetros summary, start_datetime e end_datetime são obrigatórios para criar evento.", None

            conflicts = check_calendar_availability(service, parameters["start_datetime"], parameters["end_datetime"])
            if conflicts and len(conflicts) > 0:
                # Guarda estado para confirmação
                conversation_state[sender_number] = {
                    "awaiting_confirmation": True,
                    "pending_event_params": parameters
                }

                msg = "⚠️ Já existe evento(s) neste horário:\n\n"
                for ev in conflicts:
                    if not isinstance(ev, dict):
                        print(f"Aviso: Item inesperado na lista de conflitos: {ev}. Pulando.")
                        continue
                    
                    # Extrai as strings de data/hora dos dicionários aninhados
                    start_datetime_str = ev["start"].get("dateTime", ev["start"].get("date"))
                    end_datetime_str = ev["end"].get("dateTime", ev["end"].get("date"))
                    
                    if not isinstance(start_datetime_str, str) or not isinstance(end_datetime_str, str):
                        print(f"Aviso: Data/hora inválida para evento: {ev}. Pulando.")
                        continue

                    try:
                        start_str = datetime.fromisoformat(start_datetime_str).strftime("%d/%m/%Y %H:%M")
                        end_str = datetime.fromisoformat(end_datetime_str).strftime("%d/%m/%Y %H:%M")
                        msg += f"- {ev[\"summary\"]} das {start_str} até {end_str}\n"
                    except ValueError as ve:
                        print(f"Erro ao formatar data/hora para evento {ev.get(\'summary\', \'Sem título\')}: {ve}. Pulando este evento.")
                        continue
                msg += "\nDeseja marcar este novo evento mesmo assim? (Responda com \'sim\' para confirmar ou \'não\' para escolher outro horário)."

                return msg, None
            else:
                # Evita duplicação recente
                is_duplicate = (
                    last_event_created["summary"] == parameters["summary"] and
                    last_event_created["start"] == parameters["start_datetime"] and
                    last_event_created["timestamp"] and (now - last_event_created["timestamp"]).total_seconds() < 180
                )
                if is_duplicate:
                    return "Este evento já foi criado recentemente.", None

                create_resp = create_calendar_event(service, parameters)
                last_event_created = {
                    "summary": parameters["summary"],
                    "start": parameters["start_datetime"],
                    "timestamp": now
                }
                return create_resp.get("message", "Evento criado com sucesso."), None

        elif action == "list_events":
            start = parameters.get("start_date", current_date)
            end = parameters.get("end_date", current_date)
            events = list_calendar_events(service, start, end)
            if not events:
                return "Nenhum evento encontrado no período solicitado.", None
            msg = "Eventos:\n"
            for ev in events:
                start_str = datetime.fromisoformat(ev["start"].get("dateTime", ev["start"].get("date"))).strftime("%d/%m/%Y %H:%M")
                end_str = datetime.fromisoformat(ev["end"].get("dateTime", ev["end"].get("date"))).strftime("%d/%m/%Y %H:%M")
                msg += f"- {ev['summary']} das {start_str} até {end_str}\n"
            return msg, None

        elif action == "update_event":
            event_id = parameters.get("event_id")
            updates = parameters.get("updates", {})
            if not event_id or not updates:
                return "Parâmetros event_id e updates são obrigatórios para atualizar evento.", None
            resp = update_calendar_event(service, event_id, updates)
            return resp.get("message", "Evento atualizado."), None

        elif action == "delete_event":
            event_id = parameters.get("event_id")
            if not event_id:
                return "Parâmetro event_id é obrigatório para deletar evento.", None
            resp = delete_calendar_event(service, event_id)
            return resp.get("message", "Evento deletado."), None

        elif action == "check_availability":
            start = parameters.get("start_datetime")
            end = parameters.get("end_datetime")
            if not start or not end:
                return "Parâmetros start_datetime e end_datetime são obrigatórios para checar disponibilidade.", None
            conflicts = check_calendar_availability(service, start, end)
            if conflicts and len(conflicts) > 0:
                return "O horário está ocupado por outro evento.", None
            else:
                return "O horário está disponível.", None

    except json.JSONDecodeError:
        # Resposta normal (não JSON)
        return ai_response, None

    except Exception as e:
        print(f"Erro ao processar resposta IA: {e}")
        return "Erro interno ao processar a solicitação.", None
