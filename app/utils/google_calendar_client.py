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

def ensure_rfc3339_with_timezone(dt_str):
    # Se já tem timezone, retorna como está
    if dt_str.endswith("Z") or "+" in dt_str or "-" in dt_str[10:]:
        return dt_str
    else:
        # Default para o Brasil
        return dt_str + "-03:00"

def create_calendar_event(service, parameters):
    try:
        summary = parameters.get("summary")
        start_datetime = parameters.get("start_datetime")
        end_datetime = parameters.get("end_datetime")
        timezone = parameters.get("timezone", "America/Sao_Paulo")
        force_create = parameters.get("force", False)

        if not summary or not start_datetime or not end_datetime:
            return {"status": "error", "message": "Parâmetros summary, start_datetime e end_datetime são obrigatórios."}

        # Verificar conflitos
        start_datetime_rfc = ensure_rfc3339_with_timezone(start_datetime)
        end_datetime_rfc = ensure_rfc3339_with_timezone(end_datetime)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_datetime_rfc,
            timeMax=end_datetime_rfc,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if events and not force_create:
            # Existe conflito, retorna para o receptionist perguntar
            conflicting_events = []
            for event in events:
                conflict_summary = event.get('summary', 'Sem título')
                conflict_start = event['start'].get('dateTime', event['start'].get('date'))
                conflict_end = event['end'].get('dateTime', event['end'].get('date'))
                conflicting_events.append({
                    "summary": conflict_summary,
                    "start": conflict_start,
                    "end": conflict_end
                })

            message = "⚠️ Já existe evento(s) neste horário:\n\n"
            for ce in conflicting_events:
                message += f"- {ce['summary']} das {ce['start']} até {ce['end']}\n"

            message += "\nDeseja marcar este novo evento mesmo assim? (Responda com 'sim' para confirmar ou 'não' para escolher outro horário)."

            return {
                "status": "conflict",
                "message": message,
                "conflicting_events": conflicting_events
            }

        # Se não houver conflito, ou se force_create for True, cria o evento
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

        message = (
            f"✅ Evento criado com sucesso!\n\n"
            f"📌 *{summary}*\n"
            f"🕒 Início: {start_datetime}\n"
            f"🕒 Fim: {end_datetime}\n"
            f"🔗 [Ver no Google Calendar]({created_event.get('htmlLink')})"
        )

        return {
            "status": "success",
            "message": message,
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
        time_min_rfc = ensure_rfc3339_with_timezone(time_min)
        time_max_rfc = ensure_rfc3339_with_timezone(time_max)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min_rfc,
            timeMax=time_max_rfc,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if not events:
            return {"status": "success", "message": "Nenhum evento encontrado neste intervalo."}

        message = "📅 Eventos encontrados:\n"
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
        time_min_rfc = ensure_rfc3339_with_timezone(time_min)
        time_max_rfc = ensure_rfc3339_with_timezone(time_max)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min_rfc,
            timeMax=time_max_rfc,
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
