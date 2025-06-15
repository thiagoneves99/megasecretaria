# mega_secretaria/app/tools/google_calendar_tools.py

import os
import datetime
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config import settings
from crewai_tools import BaseTool
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

    # O arquivo token.pickle armazena os tokens de acesso e atualização do usuário, e é
    # criado automaticamente quando o fluxo de autorização é concluído pela primeira vez.
    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Erro ao carregar token.pickle: {e}. Tentando reautenticar.")
            creds = None

    # Se não houver credenciais (válidas) disponíveis, permita que o usuário faça login.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Erro ao atualizar token: {e}. O token pode estar revogado ou inválido. Por favor, gere um novo token.pickle.")
                raise GoogleCalendarAuthError("Falha ao atualizar token do Google Calendar. Gere um novo token.pickle.")
        else:
            # Em um ambiente de servidor sem UI, esta parte do código não funcionará
            # para gerar um novo token. É crucial que o token.pickle seja pré-gerado.
            print("Nenhum token válido encontrado. Por favor, certifique-se de que 'token.pickle' esteja presente e válido no caminho especificado.")
            print(f"Caminho esperado do token: {token_path}")
            raise GoogleCalendarAuthError("Token do Google Calendar não encontrado ou inválido. Por favor, pré-gere o arquivo token.pickle.")

        # Salva as credenciais para a próxima execução
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
                    'timeZone': 'America/Sao_Paulo', # Ajuste o fuso horário conforme necessário
                },
                'end': {
                    'dateTime': end_datetime,
                    'timeZone': 'America/Sao_Paulo', # Ajuste o fuso horário conforme necessário
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
            return f"Evento criado com sucesso: {event.get('htmlLink')}"
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao criar o evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao criar o evento: {e}"

class ListCalendarEventsInput(BaseModel):
    max_results: int = Field(default=10, description="Número máximo de eventos a serem listados.")
    time_min: Optional[str] = Field(default=None, description="Data e hora mínima para filtrar eventos (formato ISO 8601, ex: '2025-06-13T00:00:00Z'). Se não fornecido, lista eventos a partir de agora.")

class ListCalendarEventsTool(BaseTool):
    name: str = "Listar Eventos do Google Calendar"
    description: str = "Lista os próximos eventos do Google Calendar. Pode filtrar por um número máximo de resultados e uma data/hora mínima."
    args_schema: Type[BaseModel] = ListCalendarEventsInput

    def _run(self, max_results: int = 10, time_min: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()
            now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indica UTC
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min if time_min else now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            if not events:
                return "Nenhum evento futuro encontrado."
            
            events_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                events_list.append(f"- {event['summary']} ({start} a {end})")
            
            return "Eventos encontrados:\n" + "\n".join(events_list)
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao listar eventos do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao listar eventos: {e}"

