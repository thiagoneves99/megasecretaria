import os
import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_token_path():
    token_path = os.getenv('GOOGLE_TOKEN_PATH')
    if not token_path:
        raise Exception("Variável de ambiente GOOGLE_TOKEN_PATH não configurada")
    return token_path

def get_calendar_service():
    try:
        token_path = get_token_path()
        creds = None
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        else:
            raise Exception(f"Arquivo de token não encontrado no caminho: {token_path}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError:
                    raise Exception("Token expirado e não foi possível renovar.")
            else:
                raise Exception("Credenciais inválidas e sem token válido.")

        service = build('calendar', 'v3', credentials=creds)
        return service

    except Exception as e:
        print(f"[ERRO] Falha ao obter serviço do Google Calendar: {e}")
        return None

def create_calendar_event(service, parameters):
    try:
        summary = parameters.get('summary')
        start_str = parameters.get('start_datetime')  # ISO 8601 string esperado

        if not summary or not start_str:
            return {"status": "error", "message": "Parâmetros summary e start_datetime são obrigatórios"}

        dt_inicio = datetime.fromisoformat(start_str)
        dt_fim = dt_inicio + timedelta(hours=1)  # Evento dura 1 hora por padrão

        evento = {
            'summary': summary,
            'start': {
                'dateTime': dt_inicio.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
            'end': {
                'dateTime': dt_fim.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
        }

        evento_criado = service.events().insert(calendarId='primary', body=evento).execute()
        return {"status": "success", "message": f"Evento '{summary}' criado com ID {evento_criado.get('id')}"}

    except HttpError as error:
        return {"status": "error", "message": f"Erro na API do Google Calendar: {error}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_calendar_events(service, time_min, time_max):
    try:
        events_result = service.events().list(
            calendarId='primary', timeMin=time_min,
            timeMax=time_max, singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])
        return {"status": "success", "events": events}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def update_calendar_event(service, event_id, updated_event_data):
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        event.update(updated_event_data)
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return {"status": "success", "message": f"Evento {event_id} atualizado com sucesso"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def delete_calendar_event(service, event_id):
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success", "message": f"Evento {event_id} deletado com sucesso"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_calendar_availability(service, time_min, time_max):
    try:
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}]
        }
        freebusy_result = service.freebusy().query(body=body).execute()
        busy_times = freebusy_result['calendars']['primary']['busy']
        return {"status": "success", "busy": busy_times}
    except Exception as e:
        return {"status": "error", "message": str(e)}
