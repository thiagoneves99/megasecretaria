import os
import pickle
import datetime
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    token_path = os.getenv('GOOGLE_TOKEN_PATH')

    if not token_path:
        print("[ERRO] Variável de ambiente GOOGLE_TOKEN_PATH não está definida.")
        return None

    if not os.path.exists(token_path):
        print(f"[ERRO] Arquivo token.pickle não encontrado no caminho: {token_path}")
        return None

    creds = None
    with open(token_path, 'rb') as token_file:
        creds = pickle.load(token_file)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, 'wb') as token_file:
                    pickle.dump(creds, token_file)
            except Exception as e:
                print(f"[ERRO] Falha ao atualizar token: {e}")
                return None
        else:
            print("[ERRO] Token expirado e sem refresh_token disponível.")
            return None

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"[ERRO] Falha ao criar serviço Google Calendar: {e}")
        return None


def create_calendar_event(service, event_data):
    """
    event_data exemplo esperado:
    {
        "summary": "Reunião com Patricia",
        "location": "Online",
        "description": "Discussão de projeto",
        "start": {"dateTime": "2025-06-08T20:00:00-03:00"},
        "end": {"dateTime": "2025-06-08T21:00:00-03:00"},
        "attendees": [{"email": "patricia@example.com"}]
    }
    """
    try:
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        return {"status": "success", "message": f"Evento criado: {event.get('htmlLink')}", "event_id": event.get('id')}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_calendar_events(service, time_min=None, time_max=None):
    try:
        time_min = time_min or datetime.datetime.utcnow().isoformat() + 'Z'
        time_max = time_max or (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        return {"status": "success", "events": events}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def update_calendar_event(service, event_id, updated_event_data):
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        event.update(updated_event_data)
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return {"status": "success", "message": f"Evento atualizado: {updated_event.get('htmlLink')}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def delete_calendar_event(service, event_id):
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success", "message": "Evento deletado com sucesso."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_calendar_availability(service, time_min, time_max):
    """
    Verifica se há eventos no período informado.
    time_min e time_max no formato ISO 8601 com timezone, ex: '2025-06-08T20:00:00-03:00'
    """
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if events:
            return {"status": "success", "available": False, "events": events}
        else:
            return {"status": "success", "available": True, "events": []}
    except Exception as e:
        return {"status": "error", "message": str(e)}
