import os
import pickle
import pytz
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    try:
        token_path = os.getenv("GOOGLE_TOKEN_PATH")
        if not token_path:
            raise ValueError("Variável de ambiente GOOGLE_TOKEN_PATH não está definida.")

        creds = None
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
            else:
                raise ValueError("Credenciais inválidas ou token expirado.")

        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"[ERRO get_calendar_service] {e}")
        return None

def create_calendar_event(service, parameters):
    try:
        summary = parameters.get("summary")
        start_datetime = parameters.get("start_datetime")
        end_datetime = parameters.get("end_datetime")
        timezone = parameters.get("timezone", "America/Sao_Paulo")

        if not summary or not start_datetime:
            return {"status": "error", "message": "Parâmetros summary e start_datetime são obrigatórios"}

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

        created_event = service.events().insert(calendarId='primary', body=event).execute()

        return {
            "status": "success",
            "summary": summary,
            "start": start_datetime,
            "end": end_datetime,
            "htmlLink": created_event.get('htmlLink')
        }

    except Exception as e:
        print(f"[ERRO create_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def list_calendar_events(service, time_min, time_max):
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if not events:
            return {"status": "success", "message": "Nenhum evento encontrado neste intervalo."}

        message = "Eventos encontrados:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'Sem título')
            message += f"- {summary} em {start}\n"

        return {"status": "success", "message": message}

    except Exception as e:
        print(f"[ERRO list_calendar_events] {e}")
        return {"status": "error", "message": str(e)}

def update_calendar_event(service, event_id, updated_event_data):
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        event.update(updated_event_data)

        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()

        return {"status": "success", "message": f"Evento atualizado: {updated_event.get('htmlLink')}"}

    except Exception as e:
        print(f"[ERRO update_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def delete_calendar_event(service, event_id):
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success", "message": "Evento deletado com sucesso."}

    except Exception as e:
        print(f"[ERRO delete_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def check_calendar_availability(service, time_min, time_max):
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if not events:
            return {"status": "success", "message": "O horário está disponível."}
        else:
            return {"status": "success", "message": "O horário já possui eventos agendados."}

    except Exception as e:
        print(f"[ERRO check_calendar_availability] {e}")
        return {"status": "error", "message": str(e)}
