# mega_secretaria/app/tools/google_calendar_tools.py

import os
import datetime
import pickle
from datetime import datetime, timezone # ATUALIZADO: Importar datetime e timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config import settings
from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field

# Se modificar esses escopos, delete o arquivo token.pickle existente.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarAuthError(Exception ):
    """Exceção personalizada para erros de autenticação do Google Calendar."""
    pass

def get_google_calendar_service():
    """
    Autentica e retorna o serviço da API do Google Calendar.
    Usa o token.pickle para carregar credenciais. Se o token não existir ou for inválido,
    ele tentará gerar um novo (o que exigiria interação do usuário, mas para o deploy
    assumimos que o token já existe e é válido).
    """
    creds = None
    token_path = settings.GOOGLE_TOKEN_PATH

    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Erro ao carregar token.pickle: {e}. Tentando reautenticar.")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Erro ao atualizar token: {e}. O token pode estar revogado ou inválido. Por favor, gere um novo token.pickle.")
                raise GoogleCalendarAuthError("Falha ao atualizar token do Google Calendar. Gere um novo token.pickle.")
        else:
            print("Nenhum token válido encontrado. Por favor, certifique-se de que 'token.pickle' esteja presente e válido no caminho especificado.")
            print(f"Caminho esperado do token: {token_path}")
            raise GoogleCalendarAuthError("Token do Google Calendar não encontrado ou inválido. Por favor, pré-gere o arquivo token.pickle.")

        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        except Exception as e:
            print(f"Aviso: Não foi possível salvar o token atualizado em {token_path}: {e}")

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f'Ocorreu um erro ao construir o serviço do Google Calendar: {error}')
        raise GoogleCalendarAuthError(f"Erro ao conectar ao Google Calendar API: {error}")


class CreateCalendarEventInput(BaseModel):
    summary: str = Field(description="Título ou resumo do evento.")
    start_datetime: str = Field(description="Data e hora de início do evento no formato 'YYYY-MM-DDTHH:MM:SS'. Ex: '2025-12-25T10:00:00'.")
    end_datetime: str = Field(description="Data e hora de término do evento no formato 'YYYY-MM-DDTHH:MM:SS'. Ex: '2025-12-25T11:00:00'.")
    description: Optional[str] = Field(default=None, description="Descrição detalhada do evento.")
    location: Optional[str] = Field(default=None, description="Local do evento.")
    attendees: Optional[list[str]] = Field(default=None, description="Lista de e-mails dos participantes. Ex: ['email1@example.com', 'email2@example.com'].")

class CreateCalendarEventTool(BaseTool):
    name: str = "Criar Evento no Google Calendar"
    description: str = "Cria um novo evento no Google Calendar com base nos detalhes fornecidos."
    args_schema: Type[BaseModel] = CreateCalendarEventInput

    def _run(self, summary: str, start_datetime: str, end_datetime: str, description: Optional[str] = None, location: Optional[str] = None, attendees: Optional[list[str]] = None) -> str:
        try:
            service = get_google_calendar_service()
            event = {
                'summary': summary,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_datetime,
                    'timeZone': 'America/Sao_Paulo',
                },
                'end': {
                    'dateTime': end_datetime,
                    'timeZone': 'America/Sao_Paulo',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 10},
                    ],
                },
            }
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]

            event = service.events().insert(calendarId='primary', body=event).execute()
            
            # NOVO: Retorna uma string estruturada para o agente formatar
            start_obj = datetime.fromisoformat(start_datetime)
            end_obj = datetime.fromisoformat(end_datetime)
            
            return (f"Evento criado com sucesso! Link: {event.get('htmlLink')} | "
                    f"Nome: {summary} | "
                    f"Data: {start_obj.strftime('%d/%m/%Y')} | "
                    f"Início: {start_obj.strftime('%H:%M')} | "
                    f"Término: {end_obj.strftime('%H:%M')}")

        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao criar o evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao criar o evento: {e}"

class ListCalendarEventsInput(BaseModel):
    max_results: int = Field(default=10, description="Número máximo de eventos a serem listados.")
    time_min: Optional[str] = Field(default=None, description="Data e hora mínima para filtrar eventos (formato ISO 8601, ex: '2025-06-13T00:00:00Z'). Se não fornecido, lista eventos a partir de agora.")
    # NOVO: Adicionado time_max para limitar a busca a um dia específico
    time_max: Optional[str] = Field(default=None, description="Data e hora máxima para filtrar eventos (formato ISO 8601, ex: '2025-06-13T23:59:59Z').")

class ListCalendarEventsTool(BaseTool):
    name: str = "Listar Eventos do Google Calendar"
    description: str = "Lista eventos do Google Calendar. Pode filtrar por um número máximo de resultados e um intervalo de tempo (time_min e time_max)."
    args_schema: Type[BaseModel] = ListCalendarEventsInput

    # ATUALIZADO: _run agora aceita time_max
    def _run(self, max_results: int = 10, time_min: Optional[str] = None, time_max: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()
            now_utc = datetime.now(timezone.utc).isoformat()
            
            # ATUALIZADO: Incluir timeMax na chamada da API se for fornecido
            list_params = {
                'calendarId': 'primary',
                'timeMin': time_min if time_min else now_utc,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            if time_max:
                list_params['timeMax'] = time_max

            events_result = service.events().list(**list_params).execute()
            events = events_result.get('items', [])

            if not events:
                return "Nenhum evento encontrado para o período especificado."
            
            events_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Formata a data/hora para ser mais legível
                start_obj = datetime.fromisoformat(start)
                start_formatted = start_obj.strftime('%d/%m/%Y às %H:%M')
                events_list.append(f"- {event['summary']} (Início: {start_formatted})")
            
            return "Eventos encontrados:\n" + "\n".join(events_list)
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao listar eventos do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao listar eventos: {e}"