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

class GoogleCalendarAuthError(Exception):
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

    # Garante que o diretório do token do Google exista
    os.makedirs(os.path.dirname(token_path), exist_ok=True) # LINHA CORRIGIDA

    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Erro ao carregar token.pickle, será gerado um novo: {e}")
            creds = None

    # Se não houver credenciais válidas, tenta obter novas (para ambiente de desenvolvimento)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Em um ambiente de deploy como o EasyPanel, você precisaria gerar o token.pickle
            # localmente e enviá-lo para o diretório persistente configurado.
            # Este bloco é mais para uso local/desenvolvimento para gerar o token inicial.
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # Descomente a linha abaixo para permitir a autenticação via browser em desenvolvimento local
            # creds = flow.run_local_server(port=0)
            raise GoogleCalendarAuthError("Token do Google Calendar não encontrado ou inválido. Por favor, gere o token.pickle e configure-o no caminho especificado por GOOGLE_TOKEN_PATH.")

        # Salva as credenciais para a próxima execução
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except HttpError as error:
        raise GoogleCalendarAuthError(f"Erro ao construir o serviço do Google Calendar: {error}")
    except Exception as e:
        raise GoogleCalendarAuthError(f"Erro inesperado na autenticação do Google Calendar: {e}")

class CreateCalendarEventInput(BaseModel):
    summary: str = Field(description="Título ou resumo do evento, ex: 'Reunião com o cliente'.")
    start_datetime: str = Field(description="Data e hora de início do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS), ex: '2024-07-15T10:00:00'.")
    end_datetime: str = Field(description="Data e hora de término do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS), ex: '2024-07-15T11:00:00'.")
    description: Optional[str] = Field(None, description="Descrição detalhada do evento.")
    time_zone: Optional[str] = Field("America/Sao_Paulo", description="Fuso horário do evento, ex: 'America/Sao_Paulo'. Padrão é 'America/Sao_Paulo'.")

class CreateCalendarEventTool(BaseTool):
    name: str = "Create Calendar Event"
    description: str = (
        "Cria um novo evento no Google Calendar. "
        "Requer resumo, data/hora de início e término. "
        "Exemplo de uso: CreateCalendarEventTool().run(summary='Reunião de Equipe', start_datetime='2024-07-15T10:00:00', end_datetime='2024-07-15T11:00:00', description='Discussão de projetos', time_zone='America/Sao_Paulo')"
    )
    args_schema: Type[BaseModel] = CreateCalendarEventInput

    def _run(self, summary: str, start_datetime: str, end_datetime: str, description: Optional[str] = None, time_zone: str = "America/Sao_Paulo") -> str:
        try:
            service = get_google_calendar_service()
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_datetime,
                    'timeZone': time_zone,
                },
                'end': {
                    'dateTime': end_datetime,
                    'timeZone': time_zone,
                },
            }
            event = service.events().insert(calendarId='primary', body=event).execute()
            return (f"✅ Evento Criado com Sucesso!\n\n"
                    f"*Nome:* {event.get('summary')}\n"
                    f"*Data:* {datetime.fromisoformat(event['start'].get('dateTime')).strftime('%d/%m/%Y')}\n"
                    f"*Início:* {datetime.fromisoformat(event['start'].get('dateTime')).strftime('%H:%M')}\n"
                    f"*Término:* {datetime.fromisoformat(event['end'].get('dateTime')).strftime('%H:%M')}\n"
                    f"*ID:* {event.get('id')}") # NOVO: Retorna o ID do evento
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao criar evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao criar evento: {e}"


class ListCalendarEventsInput(BaseModel):
    time_min: Optional[str] = Field(None, description="Data e hora mínimas para listar eventos no formato ISO 8601 (YYYY-MM-DDTHH:MM:SSZ). Padrão é a data e hora atuais. Ex: '2024-07-15T00:00:00Z'")
    time_max: Optional[str] = Field(None, description="Data e hora máximas para listar eventos no formato ISO 8601 (YYYY-MM-DDTHH:MM:SSZ). Opcional. Ex: '2024-07-16T23:59:59Z'")
    max_results: int = Field(10, description="Número máximo de eventos a serem retornados. Padrão é 10.")

class ListCalendarEventsTool(BaseTool):
    name: str = "List Calendar Events"
    description: str = (
        "Lista eventos do Google Calendar. "
        "Pode filtrar por período (time_min e time_max) e número máximo de resultados. "
        "time_min padrão é a data e hora atuais. time_max é opcional. "
        "Exemplo de uso: ListCalendarEventsTool().run(time_min='2024-07-15T00:00:00Z', max_results=5)"
    )
    args_schema: Type[BaseModel] = ListCalendarEventsInput

    def _run(self, time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 10) -> str:
        try:
            service = get_google_calendar_service()
            now_utc = datetime.now(timezone.utc).isoformat() + 'Z' # Data e hora atuais em UTC

            # Adiciona timeMax na chamada da API se for fornecido
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
                # NOVO: Inclui o ID do evento para facilitar a exclusão
                events_list.append(f"- {event['summary']} (Início: {start_formatted}, ID: {event.get('id')})")
            
            return "Eventos encontrados:\n" + "\n".join(events_list)
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao listar eventos do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao listar eventos: {e}"

class DeleteCalendarEventInput(BaseModel):
    event_id: str = Field(description="O ID único do evento do Google Calendar a ser deletado.")

class DeleteCalendarEventTool(BaseTool):
    name: str = "Delete Calendar Event"
    description: str = (
        "Deleta um evento existente no Google Calendar usando seu ID. "
        "Exemplo de uso: DeleteCalendarEventTool().run(event_id='meu_id_do_evento')"
    )
    args_schema: Type[BaseModel] = DeleteCalendarEventInput

    def _run(self, event_id: str) -> str:
        try:
            service = get_google_calendar_service()
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return f"✅ Evento com ID '{event_id}' deletado com sucesso."
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            if error.resp.status == 404:
                return f"Erro: Evento com ID '{event_id}' não encontrado."
            return f"Ocorreu um erro ao deletar evento do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao deletar evento: {e}"