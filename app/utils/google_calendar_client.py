import os
import pickle
import pytz
import dateutil.parser
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service( ):
    try:
        token_path = os.getenv("GOOGLE_TOKEN_PATH")
        if not token_path:
            raise ValueError("Variável de ambiente GOOGLE_TOKEN_PATH não está definida.")

        creds = None
        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)
            else:
                # Não tenta criar novas credenciais, só dá erro
                raise ValueError("Credenciais inválidas ou token expirado.")

        service = build("calendar", "v3", credentials=creds)
        return service
    except Exception as e:
        print(f"[ERRO get_calendar_service] {e}")
        return None

def ensure_datetime_with_timezone(dt_str, timezone="America/Sao_Paulo"):
    try:
        dt = dateutil.parser.isoparse(dt_str)
        if dt.tzinfo is None:
            tz = pytz.timezone(timezone)
            dt = tz.localize(dt)
        return dt.isoformat()
    except Exception as e:
        print(f"[ERRO ensure_datetime_with_timezone] {e}")
        return dt_str

def format_datetime(datetime_str):
    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        dt_br = dt.astimezone(pytz.timezone("America/Sao_Paulo"))
        return dt_br.strftime("%d/%m/%Y %H:%M")
    except Exception as e:
        print(f"[ERRO format_datetime] {e}")
        return datetime_str

def create_calendar_event(service, parameters):
    try:
        summary = parameters.get("summary")
        start_datetime = parameters.get("start_datetime")
        end_datetime = parameters.get("end_datetime")
        timezone = parameters.get("timezone", "America/Sao_Paulo")

        if not summary or not start_datetime or not end_datetime:
            return {"status": "error", "message": "Parâmetros summary, start_datetime e end_datetime são obrigatórios"}

        start_datetime = ensure_datetime_with_timezone(start_datetime, timezone)
        end_datetime = ensure_datetime_with_timezone(end_datetime, timezone)

        event = {
            "summary": summary,
            "start": {
                "dateTime": start_datetime,
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_datetime,
                "timeZone": timezone,
            },
        }

        created_event = service.events().insert(calendarId="primary", body=event).execute()

        return {
            "status": "success",
            "message": (
                f"✅ Evento criado com sucesso!\n\n"
                f"📌 {summary}\n"
                f"🕒 Início: {format_datetime(start_datetime)}\n"
                f"🕒 Fim: {format_datetime(end_datetime)}"
            )
        }

    except Exception as e:
        print(f"[ERRO create_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def list_calendar_events(service, time_min, time_max):
    try:
        time_min = ensure_datetime_with_timezone(time_min)
        time_max = ensure_datetime_with_timezone(time_max)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return []

        return events

    except Exception as e:
        print(f"[ERRO list_calendar_events] {e}")
        return {"status": "error", "message": str(e)}

def update_calendar_event(service, event_id, updated_event_data):
    try:
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        event.update(updated_event_data)

        updated_event = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()

        return {"status": "success", "message": f"Evento atualizado com sucesso."}

    except Exception as e:
        print(f"[ERRO update_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def delete_calendar_event(service, event_id):
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"status": "success", "message": "Evento deletado com sucesso."}

    except Exception as e:
        print(f"[ERRO delete_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def check_calendar_availability(service, time_min, time_max):
    try:
        time_min = ensure_datetime_with_timezone(time_min)
        time_max = ensure_datetime_with_timezone(time_max)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        cleaned_events = [event for event in events if isinstance(event, dict)]
        return cleaned_events

    except Exception as e:
        print(f"[ERRO check_calendar_availability] {e}")
        return []

