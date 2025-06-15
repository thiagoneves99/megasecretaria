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
            print(f"Erro ao carregar token.pickle: {e}")
            creds = None

    # Se não há credenciais válidas ou expiraram e não podem ser renovadas
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expirado, tentando renovar...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Erro ao renovar token: {e}. Será necessário reautenticar manualmente se em ambiente local.")
                raise GoogleCalendarAuthError("Falha ao renovar as credenciais do Google Calendar.")
        else:
            # Em um ambiente de servidor, você não pode interagir com o navegador.
            # O token.pickle DEVE ser gerado previamente através de um script local
            # e depois transferido para o servidor.
            # Para desenvolvimento local, você pode descomentar o fluxo abaixo:
            # flow = InstalledAppFlow.from_client_secrets_file(
            #     'credentials.json', SCOPES)
            # creds = flow.run_local_server(port=0)
            # Comentar ou remover esta parte para ambiente de produção sem UI.
            raise GoogleCalendarAuthError("Credenciais do Google Calendar não encontradas ou inválidas. Por favor, autentique manualmente e forneça o token.pickle.")

        # Salva as credenciais atualizadas (ou recém-obtidas)
        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        except Exception as e:
            print(f"Erro ao salvar token.pickle: {e}")

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        raise GoogleCalendarAuthError(f"Falha ao construir o serviço da API do Google Calendar: {e}")

# --- Ferramenta para Criar Eventos ---
class CreateCalendarEventSchema(BaseModel):
    summary: str = Field(description="Título do evento (ex: 'Reunião com Cliente')")
    start_datetime: str = Field(description="Data e hora de início do evento no formato ISO 8601 (ex: '2025-06-15T10:00:00-03:00')")
    end_datetime: Optional[str] = Field(description="Data e hora de término do evento no formato ISO 8601 (ex: '2025-06-15T11:00:00-03:00'). Opcional.", default=None)
    description: Optional[str] = Field(description="Descrição detalhada do evento. Opcional.", default=None)
    location: Optional[str] = Field(description="Local do evento. Opcional.", default=None)

class CreateCalendarEventTool(BaseTool):
    name: str = "Create Calendar Event"
    description: str = "Cria um novo evento no Google Calendar."
    args_schema: Type[BaseModel] = CreateCalendarEventSchema

    def _run(self, summary: str, start_datetime: str, end_datetime: Optional[str] = None, description: Optional[str] = None, location: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()

            # Se end_datetime não for fornecido, assume 1 hora de duração
            if not end_datetime:
                start_dt_obj = datetime.fromisoformat(start_datetime)
                end_dt_obj = start_dt_obj + datetime.timedelta(hours=1)
                end_datetime = end_dt_obj.isoformat()

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
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            
            # Extrair e formatar a data de início para a resposta
            start_info = event['start'].get('dateTime', event['start'].get('date'))
            start_dt_obj = datetime.fromisoformat(start_info)
            date_formatted = start_dt_obj.strftime('%d/%m/%Y')
            start_time_formatted = start_dt_obj.strftime('%H:%M')

            # Extrair e formatar a data de término
            end_info = event['end'].get('dateTime', event['end'].get('date'))
            end_dt_obj = datetime.fromisoformat(end_info)
            end_time_formatted = end_dt_obj.strftime('%H:%M')

            return (f"✅ Evento Criado com Sucesso!\n\n"
                    f"*Nome:* {event.get('summary', 'N/A')}\n"
                    f"*Data:* {date_formatted}\n"
                    f"*Início:* {start_time_formatted}\n"
                    f"*Término:* {end_time_formatted}\n"
                    f"*ID:* {event['id']}") # Adicionado o ID

        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao criar o evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao criar o evento: {e}"


# --- Ferramenta para Listar Eventos ---
class ListCalendarEventsSchema(BaseModel):
    time_min: Optional[str] = Field(description="Data e hora mínima para buscar eventos no formato ISO 8601 (ex: '2025-06-15T00:00:00Z'). Padrão para o início do dia atual se omitido.", default=None)
    time_max: Optional[str] = Field(description="Data e hora máxima para buscar eventos no formato ISO 8601 (ex: '2025-06-15T23:59:59Z'). Opcional.", default=None)
    max_results: int = Field(description="Número máximo de eventos a serem retornados. Padrão para 10.", default=10)
    query: Optional[str] = Field(description="Termo de busca para filtrar eventos por título ou descrição. Opcional.", default=None)

class ListCalendarEventsTool(BaseTool):
    name: str = "List Calendar Events"
    description: str = "Lista os eventos futuros do Google Calendar. Pode filtrar por período ou termo de busca."
    args_schema: Type[BaseModel] = ListCalendarEventsSchema

    def _run(self, time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 10, query: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()
            
            now = datetime.now(timezone.utc)
            # Definir now_utc com fuso horário para comparação e uso na API
            now_utc = now.isoformat().replace("+00:00", "Z")

            list_params = {
                'calendarId': 'primary',
                'timeMin': time_min if time_min else now_utc,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            if time_max:
                list_params['timeMax'] = time_max
            if query:
                list_params['q'] = query # 'q' é o parâmetro para busca de texto

            events_result = service.events().list(**list_params).execute()
            events = events_result.get('items', [])

            if not events:
                return "Nenhum evento encontrado para o período ou termo de busca especificado."
            
            events_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Formata a data/hora para ser mais legível
                start_obj = datetime.fromisoformat(start)
                start_formatted = start_obj.strftime('%d/%m/%Y às %H:%M')
                
                # Adicionado o ID do evento para facilitar a deleção
                event_id = event['id']
                summary = event['summary']
                
                events_list.append(f"- {summary} (Início: {start_formatted}, ID: {event_id})")
            
            return "Eventos encontrados:\n" + "\n".join(events_list)
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao listar eventos do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao listar os eventos: {e}"

# --- NOVO: Ferramenta para Deletar Eventos ---
class DeleteCalendarEventSchema(BaseModel):
    event_id: str = Field(description="O ID único do evento a ser deletado.")

class DeleteCalendarEventTool(BaseTool):
    name: str = "Delete Calendar Event"
    description: str = "Deleta um evento específico do Google Calendar usando seu ID. O ID é retornado pela ferramenta List Calendar Events."
    args_schema: Type[BaseModel] = DeleteCalendarEventSchema

    def _run(self, event_id: str) -> str:
        try:
            service = get_google_calendar_service()
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return f"✅ Evento com ID '{event_id}' deletado com sucesso."
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            if error.resp.status == 404:
                return f"Erro: Evento com ID '{event_id}' não encontrado ou já foi deletado."
            return f"Ocorreu um erro ao deletar o evento do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao deletar o evento: {e}"