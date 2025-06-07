import os
import pickle
from datetime import datetime, timedelta
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user\"s calendar.
    """
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.pickle") # Default to token.pickle if not set

    creds = None
    # The file token.pickle stores the user\"s access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # This part assumes credentials.json is available for initial auth
            # For server environments, consider using a Service Account or a pre-generated token
            flow = InstalledAppFlow.from_client_config(
                {
                    "web": {
                        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost"]
                    }
                }, SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    try:
        service = build("calendar", "v3", credentials=creds)
        return service

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def create_calendar_event(service, event_data):
    """Creates a new event in the Google Calendar."""
    try:
        # Ensure timezone is set, e.g., 'America/Sao_Paulo' or 'UTC'
        # It's crucial to handle timezones correctly for calendar events.
        # For simplicity, let's assume UTC for now, but it should be configurable.
        timezone = pytz.timezone('America/Sao_Paulo') # Or get from config

        start_datetime_str = f"{event_data['date']}T{event_data['time']}:00"
        # If no end time is provided, assume 1 hour duration
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
    """Lists events from the Google Calendar."""
    try:
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(calendarId='primary', timeMin=time_min or now,
                                            timeMax=time_max,
                                            maxResults=10, singleEvents=True,
                                            orderBy='startTime').execute()
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
    """Updates an existing event in the Google Calendar."""
    # Implement event update logic here
    print("Updating event...")
    return {"status": "success", "message": "Event update logic not yet implemented."}

def delete_calendar_event(service, event_id):
    """Deletes an event from the Google Calendar."""
    # Implement event deletion logic here
    print("Deleting event...")
    return {"status": "success", "message": "Event deletion logic not yet implemented."}

def check_calendar_availability(service, time_min, time_max):
    """Checks availability in the Google Calendar."""
    # Implement availability check logic here
    print("Checking availability...")
    return {"status": "success", "message": "Availability check logic not yet implemented."}


