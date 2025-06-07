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

    ai_response = get_ai_response(messages_for_ai)

    calendar_action_response = None
    ai_response_clean = re.sub(r"```json|```", "", ai_response).strip()

    try:
        ai_response_json = json.loads(ai_response_clean)
        action = ai_response_json.get("action")
        parameters = ai_response_json.get("parameters", {})

        # Ajusta a duração do evento para 1 hora se for create_event e start_datetime estiver presente
        if action == "create_event":
            start_str = parameters.get("start_datetime")
            if start_str:
                start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S")
                end_dt = start_dt + timedelta(hours=1)
                end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
                parameters["end_datetime"] = end_str
                parameters["timezone"] = "America/Sao_Paulo"

        try:
            service = get_calendar_service()
            if not service:
                ai_response = "Desculpe, não consegui conectar ao Google Calendar no momento."
            else:
                if action == "create_event":
                    calendar_action_response = create_calendar_event(service, parameters)
                elif action == "list_events":
                    calendar_action_response = list_calendar_events(service, parameters.get("time_min"), parameters.get("time_max"))
                elif action == "update_event":
                    calendar_action_response = update_calendar_event(service, parameters.get("event_id"), parameters.get("updated_event_data"))
                elif action == "delete_event":
                    calendar_action_response = delete_calendar_event(service, parameters.get("event_id"))
                elif action == "check_availability":
                    calendar_action_response = check_calendar_availability(service, parameters.get("time_min"), parameters.get("time_max"))
                else:
                    pass
        except Exception as e:
            print(f"[ERRO Google Calendar] {e}")
            ai_response = f"Erro ao acessar Google Calendar: {e}"

    except json.JSONDecodeError:
        pass

    if calendar_action_response:
        if calendar_action_response.get("status") == "success":
            ai_response = f"Operação de calendário realizada com sucesso: {calendar_action_response.get('message', '')}"
        else:
            ai_response = f"Erro na operação de calendário: {calendar_action_response.get('message', '')}"

    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    print(f"Enviando resposta para {sender_number}: {ai_response}")
    send_whatsapp_message(sender_number, ai_response)

    save_message(sender_number, ai_response, direction="outgoing")
