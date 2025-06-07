# app/receptionist.py

from .utils.ai_client import get_ai_response
from .utils.whatsapp_client import send_whatsapp_message
from .utils.db_handler import save_message, get_conversation_history # Importar save_message e get_conversation_history
from .utils.google_calendar_client import get_calendar_service, create_calendar_event, list_calendar_events, update_calendar_event, delete_calendar_event, check_calendar_availability # Importar funções do Google Calendar
from config.settings import ALLOWED_PHONE_NUMBER # Importar o número permitido
import tiktoken # Importar tiktoken para contagem de tokens
import json # Importar json para parsing de respostas da IA
from datetime import datetime, timedelta

# Mapeamento inicial de intenções para agentes (placeholder)
AGENT_MAP = {
    "informacao_geral": "handle_general_info",
    "agendar_reuniao": "handle_scheduling",
    # Adicionar mais agentes conforme necessário
}

def handle_incoming_message(sender_number: str, message_text: str):
    """Processa uma mensagem recebida, interage com a IA, responde e salva a resposta."""
    print(f"Processando mensagem de {sender_number}: {message_text}")

    # Nota: A mensagem recebida já foi salva em main.py antes da verificação de acesso.

    # Usar IA para entender a intenção e gerar uma resposta
    if sender_number == ALLOWED_PHONE_NUMBER.lstrip("+"):
        user_designation = "Meu Mestre"
    else:
        user_designation = "o usuário"

    # Recuperar histórico de conversas
    history = get_conversation_history(sender_number, limit=20)

    # Limitar histórico por tokens
    MAX_TOKENS_HISTORY = 1000  # Ajuste este valor conforme necessário
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    
    current_history_tokens = 0
    context_messages = []

    for msg_text, msg_direction in reversed(history): # Inverter para adicionar do mais antigo ao mais novo
        role = "user" if msg_direction == "incoming" else "assistant"
        message_tokens = len(encoding.encode(msg_text))
        
        if current_history_tokens + message_tokens > MAX_TOKENS_HISTORY:
            break
        
        context_messages.insert(0, {"role": role, "content": msg_text})
        current_history_tokens += message_tokens

    # Obter a data atual para fornecer à IA
    current_date = datetime.now().strftime("%Y-%m-%d")
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Construir o prompt com base no histórico e data atual
    messages_for_ai = []
    messages_for_ai.append({"role": "system", "content": f"""
<instruções>
A seguir você encontrará todas as instruções necessárias para realizar seu trabalho como uma secretária virtual. Siga à risca as instruções.

<objetivo>
Atender às solicitações do usuário de forma prestativa, eficiente e natural, mantendo o contexto da conversa. Você também é capaz de interagir com o Google Calendar para gerenciar eventos.

<persona>
Você é uma secretária virtual prestativa, eficiente e profissional. Seu objetivo principal é auxiliar o usuário em suas tarefas e responder às suas perguntas de forma clara e concisa. Você deve ser educada e sempre manter um tom de voz adequado.

<regras_de_interacao>
1.  **Saudação ao Usuário Autorizado:** Sempre se refira ao usuário autorizado (identificado como \"Meu Mestre\") como \"Meu Mestre\" em suas respostas.
2.  **Memória de Conversa:** Utilize o histórico de conversas fornecido para manter o contexto e fornecer respostas mais relevantes.
3.  **Respostas Claras e Concisas:** Forneça informações diretas e evite divagações.
4.  **Interação com Google Calendar:** Se a solicitação do usuário for relacionada a eventos no Google Calendar (criar, listar, atualizar, excluir, verificar disponibilidade), você deve identificar a intenção e os parâmetros necessários para a ação. **Sua resposta DEVE ser um objeto JSON no formato: `{{"action": "<nome_da_acao>", "parameters": {{<parametros_da_acao>}}}}`. As ações possíveis são: `create_event`, `list_events`, `update_event`, `delete_event`, `check_availability`. Se não for uma ação de calendário, responda em texto natural.**
    *   **Datas:** Sempre use o formato `YYYY-MM-DD`. Se o usuário disser "hoje", use `{current_date}`. Se disser "amanhã", use `{tomorrow_date}`. Se disser um dia da semana sem data específica (ex: "próxima segunda"), calcule a data correta a partir de `{current_date}`.
    *   **Horários:** Sempre use o formato `HH:MM` (24 horas).
5.  **Limitações:** Se não souber como responder a uma solicitação ou se a solicitação estiver fora de suas capacidades, informe o usuário de forma educada e sugira que ele reformule a pergunta ou procure ajuda em outro lugar.
6.  **Tom de Voz:** Mantenha um tom de voz profissional e prestativo.
</regras_de_interacao>

<informacoes_de_contexto>
Data atual: {current_date}
Data de amanhã: {tomorrow_date}
</informacoes_de_contexto>
"""})
    messages_for_ai.extend(context_messages)
    messages_for_ai.append({"role": "user", "content": f"{user_designation} disse: {message_text}"})

    ai_response = get_ai_response(messages_for_ai)

    calendar_action_response = None
    try:
        # Tenta interpretar a resposta da IA como JSON
        ai_response_json = json.loads(ai_response)
        action = ai_response_json.get("action")
        parameters = ai_response_json.get("parameters", {})

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
                # Se a IA retornou JSON mas a ação não é reconhecida, trata como texto normal
                pass

    except json.JSONDecodeError:
        # Se não for JSON, continua como resposta de texto normal
        pass

    if calendar_action_response:
        # Aqui você formataria a resposta do calendário para o usuário
        # Por enquanto, vamos apenas retornar uma mensagem genérica ou o status
        if calendar_action_response.get("status") == "success":
            ai_response = f"Operação de calendário realizada com sucesso: {calendar_action_response.get("message", "")}"
        else:
            ai_response = f"Erro na operação de calendário: {calendar_action_response.get("message", "")}"

    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    # Enviar a resposta da IA de volta via WhatsApp
    print(f"Enviando resposta para {sender_number}: {ai_response}")
    send_whatsapp_message(sender_number, ai_response)

    # Salvar a resposta enviada no banco de dados
    save_message(sender_number, ai_response, direction="outgoing")

    # Lógica futura de roteamento (exemplo):
    # ... (código de roteamento comentado permanece o mesmo)



