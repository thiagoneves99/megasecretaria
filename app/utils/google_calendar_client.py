import os
import pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from datetime import datetime, timedelta
import pytz

def get_calendar_service():
    try:
        token_path = os.getenv("GOOGLE_TOKEN_PATH")
        if not token_path or not os.path.exists(token_path):
            print("[ERRO Google Calendar] Variável de ambiente GOOGLE_TOKEN_PATH não definida ou arquivo não encontrado.")
            return None

        with open(token_path, "rb") as token:
            creds = pickle.load(token)

        service = build("calendar", "v3", credentials=creds)
        return service

    except Exception as e:
        print(f"[ERRO Google Calendar] Falha ao obter serviço: {e}")
        return None

def create_calendar_event(service, parameters):
    try:
        summary = parameters.get("summary")
        start_datetime = parameters.get("start_datetime")

        # Se a IA mandou separado (start_date + start_time), montamos start_datetime
        if not start_datetime:
            start_date = parameters.get("start_date")
            start_time = parameters.get("start_time")
            if start_date and start_time:
                start_datetime = f"{start_date}T{start_time}:00"

        # Verificação final
        if not summary or not start_datetime:
            return {"status": "error", "message": "Parâmetros summary e start_datetime são obrigatórios"}

        # Definir timezone fixo para SP
        timezone = "America/Sao_Paulo"

        # Criar datetimes para início e fim (1 hora de duração)
        start_dt = datetime.strptime(start_datetime, "%Y-%m-%dT%H:%M:%S")
        start_dt = pytz.timezone(timezone).localize(start_dt)
        end_dt = start_dt + timedelta(hours=1)

        event_body = {
            "summary": summary,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": timezone,
            },
        }

        event = service.events().insert(calendarId="primary", body=event_body).execute()
        return {"status": "success", "message": f"Evento criado: {event.get('htmlLink')}"}

    except Exception as e:
        print(f"[ERRO Google Calendar] {e}")
        return {"status": "error", "message": str(e)}

def list_calendar_events(service, time_min=None, time_max=None):
    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        events_list = []
        for event in events:
            events_list.append({
                "summary": event.get("summary"),
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date"))
            })

        return {"status": "success", "message": events_list}

    except Exception as e:
        print(f"[ERRO Google Calendar] {e}")
        return {"status": "error", "message": str(e)}

def update_calendar_event(service, event_id, updated_event_data):
    try:
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        event.update(updated_event_data)

        updated_event = service.events().update(calendarId="primary", eventId=event["id"], body=event).execute()
        return {"status": "success", "message": f"Evento atualizado: {updated_event.get('htmlLink')}"}

    except Exception as e:
        print(f"[ERRO Google Calendar] {e}")
        return {"status": "error", "message": str(e)}

def delete_calendar_event(service, event_id):
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"status": "success", "message": "Evento deletado com sucesso"}

    except Exception as e:
        print(f"[ERRO Google Calendar] {e}")
        return {"status": "error", "message": str(e)}

def check_calendar_availability(service, time_min, time_max):
    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        is_available = len(events) == 0

        return {
            "status": "success",
            "message": "Disponível" if is_available else "Indisponível"
        }

    except Exception as e:
        print(f"[ERRO Google Calendar] {e}")
        return {"status": "error", "message": str(e)}
