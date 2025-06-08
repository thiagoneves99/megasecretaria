import os
import json
import requests
import openai
import re
from dotenv import load_dotenv
from google_calendar_client import get_calendar_service, create_calendar_event, list_calendar_events

load_dotenv()

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_TOKEN = os.getenv("EVOLUTION_API_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

allowed_numbers = os.getenv("ALLOWED_NUMBERS", "").split(",")

pending_force_confirmation = {}

def send_whatsapp_message(number, message):
    try:
        payload = {
            "number": number,
            "message": message
        }
        headers = {
            "Authorization": f"Bearer {EVOLUTION_API_TOKEN}",
            "Content-Type": "application/json"
        }
        response = requests.post(EVOLUTION_API_URL, headers=headers, data=json.dumps(payload))
        print(f"Tentando enviar para: {EVOLUTION_API_URL}")
        print(f"Mensagem enviada com sucesso para {number}. Status: {response.status_code}")
    except Exception as e:
        print(f"[ERRO send_whatsapp_message] {e}")

def save_message(sender_number, message, direction="incoming"):
    print(f"Mensagem {direction} de/para {sender_number} salva no banco de dados.")

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    sender_number = data.get("number")
    message_text = data.get("message")

    print(f"--- Webhook Recebido ---")
    print(f"Remetente: {sender_number}")
    print(f"Mensagem: {message_text}")

    save_message(sender_number, message_text, direction="incoming")

    if sender_number not in allowed_numbers:
        print(f"Acesso negado para {sender_number}.")
        return "OK", 200

    print(f"Acesso permitido para: {sender_number}. Processando...")

    if sender_number in pending_force_confirmation:
        if message_text.strip().lower() in ["sim", "s"]:
            print(f"Usuário confirmou criação forçada para {sender_number}")
            pending_action = pending_force_confirmation.pop(sender_number)

            try:
                service = get_calendar_service()
                calendar_action_response = create_calendar_event(service, pending_action["parameters"], force=True)
                ai_response = calendar_action_response["message"]
            except Exception as e:
                ai_response = f"Erro ao criar evento forçado: {e}"

        elif message_text.strip().lower() in ["não", "nao", "n"]:
            print(f"Usuário cancelou criação forçada para {sender_number}")
            pending_force_confirmation.pop(sender_number)
            ai_response = "Entendido. Por favor, informe um novo horário para o evento."

        else:
            ai_response = "Por favor, responda com 'sim' para confirmar ou 'não' para escolher outro horário."

        print(f"Enviando resposta para {sender_number}: {ai_response}")
        send_whatsapp_message(sender_number, ai_response)
        save_message(sender_number, ai_response, direction="outgoing")
        return "OK", 200

    print(f"Processando mensagem de {sender_number}: {message_text}")

    messages = [
        {"role": "system", "content": "Você é uma assistente pessoal que organiza compromissos no Google Calendar."},
        {"role": "user", "content": message_text}
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0
    )

    assistant_message = response.choices[0].message["content"]
    print(f"Resposta do GPT: {assistant_message}")

    action_match = re.search(r"### Action: (.+)", assistant_message)
    parameters_match = re.search(r"### Parameters:\n(.+)", assistant_message, re.DOTALL)

    service = get_calendar_service()
    ai_response = assistant_message  # fallback

    if action_match and parameters_match:
        action = action_match.group(1).strip()
        parameters_str = parameters_match.group(1).strip()

        try:
            parameters = json.loads(parameters_str)
        except json.JSONDecodeError as e:
            ai_response = f"Erro ao interpretar os parâmetros da ação: {e}"
            print(ai_response)
            send_whatsapp_message(sender_number, ai_response)
            save_message(sender_number, ai_response, direction="outgoing")
            return "OK", 200

        if action == "create_event":
            calendar_action_response = create_calendar_event(service, parameters)

            if calendar_action_response["status"] == "conflict":
                pending_force_confirmation[sender_number] = calendar_action_response["pending_action"]

            ai_response = calendar_action_response["message"]

        elif action == "list_events":
            time_min = parameters.get("time_min")
            time_max = parameters.get("time_max")
            calendar_action_response = list_calendar_events(service, time_min, time_max)
            ai_response = calendar_action_response["message"]

    print(f"Enviando resposta para {sender_number}: {ai_response}")
    send_whatsapp_message(sender_number, ai_response)
    save_message(sender_number, ai_response, direction="outgoing")

    return "OK", 200
