import pytz
from datetime import datetime, timedelta
import json
import re

from .google_calendar_client import (
    get_calendar_service, create_calendar_event, list_calendar_events,
    update_calendar_event, delete_calendar_event, check_calendar_availability
)

# Controle para evitar criar eventos duplicados repetidamente
last_event_created = {
    "summary": None,
    "start": None,
    "timestamp": None
}

def handle_calendar_action(sender_number, ai_response_or_text_lower, conversation_state):
    global last_event_created

    # Se for uma resposta de confirmação (sim/não)
    if isinstance(ai_response_or_text_lower, str):
        text_lower = ai_response_or_text_lower
        state = conversation_state.get(sender_number)
        if text_lower == "sim":
            params = state["pending_event_params"]
            service = get_calendar_service()
            if service:
                calendar_resp = create_calendar_event(service, params)
                if calendar_resp.get("status") == "success":
                    response = calendar_resp.get("message", "Evento criado conforme solicitado.")
                    conversation_state.pop(sender_number, None)
                else:
                    response = calendar_resp.get("message", "Erro ao criar evento após confirmação. Por favor, tente novamente.")
            else:
                response = "Desculpe, não consegui conectar ao Google Calendar no momento."
        elif text_lower in ["não", "nao"]:
            response = "Ok, então escolha outro horário para o evento."
            conversation_state.pop(sender_number, None)
        else:
            response = "Por favor, responda com \'sim\' para confirmar ou \'não\' para escolher outro horário."
        return response

    # Se for uma ação de calendário vinda da IA
    ai_json = ai_response_or_text_lower
    action = ai_json.get("action")
    parameters = ai_json.get("parameters", {})

    service = get_calendar_service()
    if not service:
        return "Desculpe, não consegui conectar ao Google Calendar no momento."

    now = datetime.now()

    if action == "create_event":
        # Ajusta datetime para ISO 8601 com timezone para create_event
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

        if not parameters.get("summary") or not parameters.get("start_datetime") or not parameters.get("end_datetime"):
            return "Parâmetros summary, start_datetime e end_datetime são obrigatórios para criar evento."

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
                    print(f"Erro ao formatar data/hora para evento {ev.get(\"summary\", \"Sem título\")}: {ve}. Pulando este evento.")
                    continue
            msg += "\nDeseja marcar este novo evento mesmo assim? (Responda com \'sim\' para confirmar ou \'não\' para escolher outro horário)."

            return msg
        else:
            # Evita duplicação recente
            is_duplicate = (
                last_event_created["summary"] == parameters["summary"] and
                last_event_created["start"] == parameters["start_datetime"] and
                last_event_created["timestamp"] and (now - last_event_created["timestamp"]).total_seconds() < 180
            )
            if is_duplicate:
                return "Este evento já foi criado recentemente."

            create_resp = create_calendar_event(service, parameters)
            last_event_created = {
                "summary": parameters["summary"],
                "start": parameters["start_datetime"],
                "timestamp": now
            }
            return create_resp.get("message", "Evento criado com sucesso.")

    elif action == "list_events":
        # Obtém a data atual para o caso de não ser fornecida
        brazil_tz = pytz.timezone("America/Sao_Paulo")
        now_brazil = datetime.now(brazil_tz)
        current_date = now_brazil.strftime("%Y-%m-%d")

        start = parameters.get("start_date", current_date)
        end = parameters.get("end_date", current_date)
        events = list_calendar_events(service, start, end)
        if not events:
            return "Nenhum evento encontrado no período solicitado."
        msg = "Eventos:\n"
        for ev in events:
            start_str = datetime.fromisoformat(ev["start"].get("dateTime", ev["start"].get("date"))).strftime("%d/%m/%Y %H:%M")
            end_str = datetime.fromisoformat(ev["end"].get("dateTime", ev["end"].get("date"))).strftime("%d/%m/%Y %H:%M")
            msg += f"- {ev[\"summary\"]} das {start_str} até {end_str}\n"
        return msg

    elif action == "update_event":
        event_id = parameters.get("event_id")
        updates = parameters.get("updates", {})
        if not event_id or not updates:
            return "Parâmetros event_id e updates são obrigatórios para atualizar evento."
        resp = update_calendar_event(service, event_id, updates)
        return resp.get("message", "Evento atualizado.")

    elif action == "delete_event":
        event_id = parameters.get("event_id")
        if not event_id:
            return "Parâmetro event_id é obrigatório para deletar evento."
        resp = delete_calendar_event(service, event_id)
        return resp.get("message", "Evento deletado.")

    elif action == "check_availability":
        start = parameters.get("start_datetime")
        end = parameters.get("end_datetime")
        if not start or not end:
            return "Parâmetros start_datetime e end_datetime são obrigatórios para checar disponibilidade."
        conflicts = check_calendar_availability(service, start, end)
        if conflicts and len(conflicts) > 0:
            return "O horário está ocupado por outro evento."
        else:
            return "O horário está disponível."

    return "Desculpe, não consegui processar a ação de calendário solicitada."

