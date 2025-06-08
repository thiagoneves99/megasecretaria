import os
import pickle
from datetime import datetime, timedelta
import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PATH = 'token.pickle'
CREDENTIALS_PATH = 'credentials.json'
CALENDAR_ID = 'primary'  # ou id do calendário que você usa

def get_calendar_service():
    creds = None
    # Verifica se o token já existe
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token_file:
            creds = pickle.load(token_file)
    # Se não tem credenciais válidas, faz o fluxo de login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Erro ao atualizar token: {e}")
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # Salva o token para próximas execuções
        with open(TOKEN_PATH, 'wb') as token_file:
            pickle.dump(creds, token_file)

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Erro ao criar serviço do Google Calendar: {e}")
        return None

def create_calendar_event(service, event_params):
    try:
        event_body = {
            'summary': event_params['summary'],
            'location': event_params.get('location', ''),
            'description': event_params.get('description', ''),
            'start': {
                'dateTime': event_params['start_datetime'],
                'timeZone': event_params.get('timezone', 'America/Sao_Paulo'),
            },
            'end': {
                'dateTime': event_params['end_datetime'],
                'timeZone': event_params.get('timezone', 'America/Sao_Paulo'),
            },
            'attendees': event_params.get('attendees', []),
            'reminders': {
                'useDefault': True,
            },
        }
        event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        return {
            "success": True,
            "message": f"Evento '{event.get('summary')}' criado para {event['start']['dateTime']}"
        }
    except HttpError as e:
        print(f"Erro HTTP ao criar evento: {e}")
        return {"success": False, "message": "Erro ao criar evento no Google Calendar."}
    except Exception as e:
        print(f"Erro ao criar evento: {e}")
        return {"success": False, "message": "Erro inesperado ao criar evento."}

def list_calendar_events(service, start_date, end_date):
    try:
        tz = pytz.timezone("America/Sao_Paulo")
        start_dt = tz.localize(datetime.strptime(start_date, "%Y-%m-%d"))
        end_dt = tz.localize(datetime.strptime(end_date, "%Y-%m-%d")) + timedelta(days=1)
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        lista = []
        for ev in events:
            start = ev['start'].get('dateTime', ev['start'].get('date'))
            end = ev['end'].get('dateTime', ev['end'].get('date'))
            lista.append({
                'id': ev['id'],
                'summary': ev.get('summary', ''),
                'start': start,
                'end': end
            })
        return lista
    except HttpError as e:
        print(f"Erro HTTP ao listar eventos: {e}")
        return []
    except Exception as e:
        print(f"Erro ao listar eventos: {e}")
        return []

def update_calendar_event(service, event_id, updates):
    try:
        event = service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
        for key, value in updates.items():
            if key in ['start_datetime', 'end_datetime']:
                when = 'start' if key == 'start_datetime' else 'end'
                event[when]['dateTime'] = value
                event[when]['timeZone'] = 'America/Sao_Paulo'
            else:
                event[key] = value
        updated_event = service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event).execute()
        return {"success": True, "message": f"Evento '{updated_event.get('summary')}' atualizado com sucesso."}
    except HttpError as e:
        print(f"Erro HTTP ao atualizar evento: {e}")
        return {"success": False, "message": "Erro ao atualizar evento no Google Calendar."}
    except Exception as e:
        print(f"Erro ao atualizar evento: {e}")
        return {"success": False, "message": "Erro inesperado ao atualizar evento."}

def delete_calendar_event(service, event_id):
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        return {"success": True, "message": "Evento deletado com sucesso."}
    except HttpError as e:
        print(f"Erro HTTP ao deletar evento: {e}")
        return {"success": False, "message": "Erro ao deletar evento no Google Calendar."}
    except Exception as e:
        print(f"Erro ao deletar evento: {e}")
        return {"success": False, "message": "Erro inesperado ao deletar evento."}

def check_calendar_availability(service, start_datetime, end_datetime):
    try:
        events = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_datetime,
            timeMax=end_datetime,
            singleEvents=True,
            orderBy='startTime'
        ).execute().get('items', [])
        conflitos = []
        for ev in events:
            conflitos.append({
                'id': ev['id'],
                'summary': ev.get('summary', ''),
                'start': ev['start'].get('dateTime', ev['start'].get('date')),
                'end': ev['end'].get('dateTime', ev['end'].get('date'))
            })
        return conflitos
    except HttpError as e:
        print(f"Erro HTTP ao checar disponibilidade: {e}")
        return []
    except Exception as e:
        print(f"Erro ao checar disponibilidade: {e}")
        return []
