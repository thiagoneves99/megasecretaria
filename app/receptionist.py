from .utils.ai_client import get_ai_response
from .utils.whatsapp_client import send_whatsapp_message
from .utils.db_handler import save_message, get_conversation_history
from config.settings import ALLOWED_PHONE_NUMBER
import tiktoken
import json
import re
from datetime import datetime, timedelta
import pytz

# Importar o novo módulo que irá lidar com as ações do calendário
from .utils.calendar_manager import handle_calendar_action

MAX_TOKENS_HISTORY = 1000

# Estado da conversa para cada usuário (em memória)
conversation_state = {}

def handle_incoming_message(sender_number: str, message_text: str):
    global conversation_state

    print(f"Processando mensagem de {sender_number}: {message_text}")

    user_designation = "Meu Mestre" if sender_number == ALLOWED_PHONE_NUMBER.lstrip("+") else "o usuário"
    history = get_conversation_history(sender_number, limit=20)

    text_lower = message_text.strip().lower()

    # 1) Verifica se está aguardando confirmação para criar evento com conflito
    if sender_number in conversation_state and conversation_state[sender_number].get("awaiting_confirmation"):
        # Delega a resposta de confirmação para o calendar_manager
        resposta = handle_calendar_action(sender_number, text_lower, conversation_state)
        if resposta:
            send_whatsapp_message(sender_number, resposta)
            save_message(sender_number, resposta, direction="outgoing")
            return

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
    ai_response = get_ai_response(messages_for_ai)

    # 6) Tenta processar a resposta da IA como uma ação de calendário
    calendar_action_response = None
    ai_response_clean = re.sub(r"```json|```", "", ai_response).strip()
    try:
        ai_json = json.loads(ai_response_clean)
        if isinstance(ai_json, dict) and "action" in ai_json and "parameters" in ai_json:
            # Delega a ação do calendário para o calendar_manager
            calendar_action_response = handle_calendar_action(sender_number, ai_json, conversation_state)
            if calendar_action_response:
                ai_response = calendar_action_response

    except json.JSONDecodeError:
        # Não é um JSON, continua com a resposta da IA como texto normal
        pass
    except Exception as e:
        print(f"Erro ao processar JSON da IA ou ação de calendário: {e}")
        # Se houver erro no JSON ou na ação, ainda tenta usar a resposta original da IA
        pass

    # 7) Resposta final, envio e salvamento
    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    print(f"Enviando resposta para {sender_number}: {ai_response}")

    send_whatsapp_message(sender_number, ai_response)
    save_message(sender_number, ai_response, direction="outgoing")


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


