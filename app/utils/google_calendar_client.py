import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta

TOKEN_PATH = 'token.pickle'  # Ajuste conforme o caminho do seu arquivo de token
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    try:
        creds = None
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'rb') as token_file:
                creds = pickle.load(token_file)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(TOKEN_PATH, 'wb') as token_file:
                        pickle.dump(creds, token_file)
                    print("[OK] Token atualizado com sucesso.")
                except Exception as e:
                    print(f"[ERRO] Falha ao atualizar token: {e}")
                    return None
            else:
                print("[ERRO] Token inválido e não é possível atualizar.")
                return None

        service = build('calendar', 'v3', credentials=creds)
        print("[OK] Serviço do Google Calendar criado com sucesso.")
        return service

    except Exception as e:
        print(f"[ERRO get_calendar_service] {e}")
        return None

def create_calendar_event(service, event_data):
    try:
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        return {"status": "success", "message": f"Evento criado: {event.get('htmlLink')}"}
    except HttpError as e:
        print(f"[ERRO create_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def list_calendar_events(service, time_min=None, time_max=None):
    try:
        time_min = time_min or datetime.utcnow().isoformat() + 'Z'  # 'Z' indica UTC
        time_max = time_max or (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary', timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy='startTime').execute()
        events = events_result.get('items', [])
        return {"status": "success", "events": events}
    except HttpError as e:
        print(f"[ERRO list_calendar_events] {e}")
        return {"status": "error", "message": str(e)}

def update_calendar_event(service, event_id, updated_event_data):
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        event.update(updated_event_data)
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return {"status": "success", "message": f"Evento atualizado: {updated_event.get('htmlLink')}"}
    except HttpError as e:
        print(f"[ERRO update_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def delete_calendar_event(service, event_id):
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success", "message": "Evento deletado com sucesso."}
    except HttpError as e:
        print(f"[ERRO delete_calendar_event] {e}")
        return {"status": "error", "message": str(e)}

def check_calendar_availability(service, time_min, time_max):
    try:
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}]
        }
        events = service.freebusy().query(body=body).execute()
        busy_times = events['calendars']['primary'].get('busy', [])
        if busy_times:
            return {"status": "success", "available": False, "busy_times": busy_times}
        else:
            return {"status": "success", "available": True}
    except HttpError as e:
        print(f"[ERRO check_calendar_availability] {e}")
        return {"status": "error", "message": str(e)}
