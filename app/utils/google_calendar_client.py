import os
import pickle
from datetime import datetime, timedelta
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    """Inicializa o serviço do Google Calendar com as credenciais já existentes."""
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.pickle")

    creds = None
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Erro ao tentar atualizar token expirado: {e}")
                return None
        else:
            print("Token inválido e não é possível atualizar. Favor gerar um novo token.pickle manualmente.")
            return None

    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def create_calendar_event(service, event_data):
    """Cria um novo evento no Google Calendar."""
    try:
        timezone = pytz.timezone('America/Sao_Paulo')

        start_datetime_str = f"{event_data['date']}T{event_data['time']}:00"
        end_time_obj = datetime.strptime(start_datetime_str, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=1)
        end_datetime_str = end_time_obj.strftime("%Y-%m-%dT%H:%M:%S")

        event = {
            'summary': event_data.get('title', 'Novo Evento'),
            'location': event_data.get('location', ''),
            'description': event_data.get('description', ''),
            'start': {
                'dateTime': start_datetime_str,
                'timeZone': timezone.zone,
            },
            'end': {
                'dateTime': end_datetime_str,
                'timeZone': timezone.zone,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"Event created: {event.get('htmlLink')}")
        return {"status": "success", "message": f"Evento '{event.get('summary')}' criado com sucesso! Link: {event.get('htmlLink')}"}
    except HttpError as error:
        print(f"An error occurred creating event: {error}")
        return {"status": "error", "message": f"Erro ao criar evento: {error}"}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"status": "error", "message": f"Erro inesperado ao criar evento: {e}"}

def list_calendar_events(service, time_min=None, time_max=None):
    """Lista eventos do Google Calendar."""
    try:
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min or now,
            timeMax=time_max,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return {"status": "success", "message": "Nenhum evento encontrado."}
        else:
            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_list.append(f"{event['summary']} ({start})")
            return {"status": "success", "message": "Eventos encontrados:", "events": event_list}
    except HttpError as error:
        print(f"An error occurred listing events: {error}")
        return {"status": "error", "message": f"Erro ao listar eventos: {error}"}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"status": "error", "message": f"Erro inesperado ao listar eventos: {e}"}

def update_calendar_event(service, event_id, updated_event_data):
    """Atualiza um evento existente no Google Calendar."""
    print("Updating event...")
    return {"status": "success", "message": "Logica de atualização de evento ainda não implementada."}

def delete_calendar_event(service, event_id):
    """Exclui um evento do Google Calendar."""
    print("Deleting event...")
    return {"status": "success", "message": "Logica de exclusão de evento ainda não implementada."}

def check_calendar_availability(service, time_min, time_max):
    """Verifica a disponibilidade no Google Calendar."""
    print("Checking availability...")
    return {"status": "success", "message": "Logica de verificação de disponibilidade ainda não implementada."}
