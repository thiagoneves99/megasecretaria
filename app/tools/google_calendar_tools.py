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

    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            # Logar o erro, mas permitir que o fluxo continue para tentar re-autenticar
            print(f"Erro ao carregar token.pickle: {e}")
            creds = None

    # Se não houver credenciais válidas ou se o token expirou/foi corrompido, tenta reautenticar.
    # Em um ambiente de produção sem UI, você precisaria de um método de autenticação diferente
    # (e.g., Service Account ou OAuth 2.0 com fluxo de autorização manual pré-executado).
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise GoogleCalendarAuthError(f"Falha ao refrescar token do Google Calendar: {e}")
        else:
            # Para deploy, assumimos que o token já foi gerado.
            # Se estiver testando localmente pela primeira vez, você precisaria do fluxo interativo:
            # flow = InstalledAppFlow.from_client_secrets_file(
            #     'credentials.json', SCOPES)
            # creds = flow.local_server_redirect()
            # print("Nenhuma credencial encontrada ou válida. Por favor, gere o token.pickle manualmente.")
            # raise GoogleCalendarAuthError("Credenciais do Google Calendar não encontradas ou inválidas. Por favor, autentique-se.")

            # Em um ambiente de produção sem interação, você precisa de um token.pickle válido previamente gerado.
            raise GoogleCalendarAuthError("Credenciais do Google Calendar não encontradas ou inválidas. Garanta que o token.pickle esteja presente e válido.")

        # Salva as credenciais para a próxima execução
        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        except Exception as e:
            print(f"Aviso: Não foi possível salvar o token atualizado em {token_path}: {e}")

    service = build('calendar', 'v3', credentials=creds)
    return service

# --- Ferramenta para Criar Eventos ---
class CreateCalendarEventSchema(BaseModel):
    summary: str = Field(description="O título ou nome do evento.")
    start_datetime: datetime = Field(description="A data e hora de início do evento no formato ISO 8601 (ex: '2024-12-31T23:59:59').")
    end_datetime: Optional[datetime] = Field(description="A data e hora de término do evento no formato ISO 8601. Se não fornecido, será definido como 1 hora após o início.", default=None)
    description: Optional[str] = Field(description="Uma descrição para o evento.", default=None)
    location: Optional[str] = Field(description="O local do evento.", default=None)

class CreateCalendarEventTool(BaseTool):
    name: str = "Create Calendar Event"
    description: str = "Cria um novo evento no Google Calendar."
    args_schema: Type[BaseModel] = CreateCalendarEventSchema

    def _run(self, summary: str, start_datetime: datetime, end_datetime: Optional[datetime] = None, description: Optional[str] = None, location: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()

            # Se end_datetime não for fornecido, define como 1 hora após start_datetime
            if end_datetime is None:
                end_datetime = start_datetime + datetime.timedelta(hours=1)

            event = {
                'summary': summary,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'America/Sao_Paulo', # Ajuste conforme necessário
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'America/Sao_Paulo', # Ajuste conforme necessário
                },
            }

            event = service.events().insert(calendarId='primary', body=event).execute()

            # Formata a data para exibição
            start_dt_formatted = start_datetime.strftime('%d/%m/%Y às %H:%M')
            end_dt_formatted = end_datetime.strftime('%H:%M') if end_datetime else "não especificado"

            return (
                f"✅ Evento Criado com Sucesso!\n\n"
                f"*Nome:* {event.get('summary')}\n"
                f"*Data:* {start_datetime.strftime('%d/%m/%Y')}\n"
                f"*Início:* {start_datetime.strftime('%H:%M')}\n"
                f"*Término:* {end_datetime.strftime('%H:%M')}\n"
                f"*ID:* {event.get('id')}\n"
            )
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao criar o evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao criar o evento: {e}"

# --- Ferramenta para Listar Eventos ---
class ListCalendarEventsSchema(BaseModel):
    time_min: Optional[datetime] = Field(description="O início do período para listar eventos (formato ISO 8601). Se não fornecido, será a data e hora atual.", default_factory=lambda: datetime.now(timezone.utc).isoformat())
    time_max: Optional[datetime] = Field(description="O fim do período para listar eventos (formato ISO 8601). Se não fornecido, será 7 dias a partir de time_min.", default=None)
    query: Optional[str] = Field(description="Termo de busca para filtrar eventos por título ou descrição.", default=None)
    max_results: int = Field(description="O número máximo de eventos a serem retornados.", default=10)

class ListCalendarEventsTool(BaseTool):
    name: str = "List Calendar Events"
    description: str = "Lista eventos futuros do Google Calendar. Pode ser filtrado por período e termo de busca. Retorna uma lista formatada de eventos ou uma mensagem de que nenhum evento foi encontrado."
    args_schema: Type[BaseModel] = ListCalendarEventsSchema

    def _run(self, time_min: Optional[datetime] = None, time_max: Optional[datetime] = None, query: Optional[str] = None, max_results: int = 10) -> str:
        try:
            service = get_google_calendar_service()

            now = datetime.now(timezone.utc)
            if time_min is None:
                time_min = now
            if time_max is None:
                time_max = now + datetime.timedelta(days=7) # Default to 7 days if not specified

            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z' if time_min.tzinfo is None else time_min.isoformat(),
                timeMax=time_max.isoformat() + 'Z' if time_max.tzinfo is None else time_max.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime',
                q=query
            ).execute()
            events = events_result.get('items', [])

            if not events:
                return "✅ Nenhum compromisso agendado para o período especificado."

            output = "Eventos encontrados:\n"
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                # Tenta parsear as datas para um formato mais legível, considerando fuso horário
                try:
                    start_dt = datetime.fromisoformat(start)
                    # Converter para o fuso horário de São Paulo para exibição, se necessário
                    # Note: 'America/Sao_Paulo' ZoneInfo pode precisar ser importado ou definido globalmente
                    # from zoneinfo import ZoneInfo
                    # sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
                    # start_dt = start_dt.astimezone(sao_paulo_tz)
                    start_display = start_dt.strftime('%d/%m/%Y às %H:%M')
                except ValueError:
                    start_display = start # Fallback se não conseguir parsear

                try:
                    end_dt = datetime.fromisoformat(end)
                    # end_dt = end_dt.astimezone(sao_paulo_tz)
                    end_display = end_dt.strftime('%H:%M')
                except ValueError:
                    end_display = end # Fallback

                output += f"- Nome: {event['summary']}\n"
                output += f"  Início: {start_display}\n"
                if 'dateTime' in event['end']: # Só mostra o término se for um evento com hora
                    output += f"  Término: {end_display}\n"
                output += f"  ID: {event['id']}\n\n"

            # A FERRAMENTA DEVE RETORNAR APENAS A LISTA DE EVENTOS OU A MENSAGEM DE NENHUM ENCONTRADO
            # A FRASE AMIGÁVEL SERÁ ADICIONADA PELO AGENTE, NÃO PELA FERRAMENTA.
            return output.strip() # Remove o último \n extra

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