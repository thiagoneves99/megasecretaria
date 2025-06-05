# app/receptionist.py

from .utils.ai_client import get_ai_response
from .utils.whatsapp_client import send_whatsapp_message
from .utils.db_handler import save_message # Importar save_message

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
    prompt_for_receptionist = f"O usuário ({sender_number}) disse: 
{message_text}

Responda de forma natural e prestativa como uma secretária."

    ai_response = get_ai_response(prompt_for_receptionist)

    if not ai_response:
        ai_response = "Desculpe, não consegui processar sua solicitação no momento. Pode tentar reformular?"

    # Enviar a resposta da IA de volta via WhatsApp
    print(f"Enviando resposta para {sender_number}: {ai_response}")
    send_whatsapp_message(sender_number, ai_response)

    # Salvar a resposta enviada no banco de dados
    save_message(sender_number, ai_response, direction="outgoing")

    # Lógica futura de roteamento (exemplo):
    # ... (código de roteamento comentado permanece o mesmo)

