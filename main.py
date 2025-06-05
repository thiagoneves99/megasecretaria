# app/main.py

from flask import Flask, request, jsonify
import json
import os

# Importar configurações e funções necessárias
from config.settings import ALLOWED_PHONE_NUMBER, WEBHOOK_URL # Importa o número permitido e a URL do webhook
from .receptionist import handle_incoming_message
from .utils.db_handler import initialize_database, save_message # Importa funções do DB

app = Flask(__name__)

# --- Inicialização do Banco de Dados ---
# Garante que a tabela de conversas exista ao iniciar a aplicação
initialize_database()
# -------------------------------------

# Validação simples para garantir que a variável ALLOWED_PHONE_NUMBER foi carregada
if not ALLOWED_PHONE_NUMBER:
    print("ERRO CRÍTICO: ALLOWED_PHONE_NUMBER não definido nas variáveis de ambiente!")
    # Idealmente, impedir a inicialização da aplicação ou logar um erro grave

@app.route("/")
def health_check():
    """Endpoint básico para verificar se a aplicação está rodando."""
    return jsonify({"status": "ok", "message": "Mega Secretary Webhook Receiver is running!"}), 200

@app.route("/webhook", methods=["POST"])
def evolution_webhook():
    """Recebe notificações de webhook da Evolution API."""
    data = request.json
    print("\n--- Webhook Recebido ---")
    # print(json.dumps(data, indent=2)) # Descomente para debug detalhado

    try:
        if data.get("event") == "messages.upsert" and data.get("data") and data["data"].get("message"):
            message_data = data["data"]["message"]
            sender_info = data["data"].get("key", {})
            sender_number_full = sender_info.get("remoteJid")
            message_content = message_data.get("conversation") or \
                              message_data.get("extendedTextMessage", {}).get("text")

            if not sender_number_full or not message_content:
                print("Webhook ignorado: Informações essenciais ausentes.")
                return jsonify({"status": "ignored", "reason": "missing data"}), 200

            sender_number = sender_number_full.split("@")[0]

            print(f"Remetente: {sender_number}")
            print(f"Mensagem: {message_content}")

            # Salva a mensagem recebida ANTES de verificar o acesso
            # Assim, temos registro de todas as tentativas de contato
            save_message(sender_number, message_content, direction="incoming")

            normalized_allowed_number = ALLOWED_PHONE_NUMBER.lstrip("+")
            normalized_sender_number = sender_number.lstrip("+")

            if normalized_sender_number != normalized_allowed_number:
                print(f"Acesso negado para: {sender_number}. Número permitido: {ALLOWED_PHONE_NUMBER}")
                return jsonify({"status": "denied", "reason": "unauthorized sender"}), 403

            print(f"Acesso permitido para: {sender_number}. Processando...")
            # Chama o handler da recepcionista (que agora também pode salvar a msg de saída)
            handle_incoming_message(sender_number, message_content)

            return jsonify({"status": "received", "processed": True}), 200
        else:
            event_type = data.get("event", "desconhecido")
            print(f"Webhook ignorado: Evento 	'{event_type}	' não processado.")
            return jsonify({"status": "ignored", "reason": "not a target message event"}), 200

    except Exception as e:
        print(f"Erro ao processar webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Modificar o receptionist.py para chamar save_message para mensagens de saída
# (A fazer na próxima etapa se necessário, ou já ajustar agora)

if __name__ == "__main__":
    print(f"Iniciando servidor Flask para webhook em http://0.0.0.0:5001")
    print(f"Endpoint do Webhook: /webhook")
    print(f"Número permitido: {ALLOWED_PHONE_NUMBER}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)), debug=False)

