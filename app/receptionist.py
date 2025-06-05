# app/receptionist.py

from .utils.ai_client import get_ai_response
from .utils.whatsapp_client import send_whatsapp_message
from .utils.db_handler import save_message, get_conversation_history # Importar save_message e get_conversation_history
from config.settings import ALLOWED_PHONE_NUMBER # Importar o número permitido
import tiktoken # Importar tiktoken para contagem de tokens

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

    # Construir o prompt com base no histórico
    messages_for_ai = []
    messages_for_ai.append({"role": "system", "content": "Você é uma secretária virtual prestativa e eficiente."})
    messages_for_ai.extend(context_messages)
    messages_for_ai.append({"role": "user", "content": f"{user_designation} disse: {message_text}"})

    ai_response = get_ai_response(messages_for_ai)

    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    # Enviar a resposta da IA de volta via WhatsApp
    print(f"Enviando resposta para {sender_number}: {ai_response}")
    send_whatsapp_message(sender_number, ai_response)

    # Salvar a resposta enviada no banco de dados
    save_message(sender_number, ai_response, direction="outgoing")

    # Lógica futura de roteamento (exemplo):
    # ... (código de roteamento comentado permanece o mesmo)

