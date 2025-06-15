# mega_secretaria/app/tools/google_calendar_tools.py

import os
import datetime
import pickle
from datetime import datetime, timezone
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
    time_max: Optional[str] = Field(default=None, description="Data e hora máxima para filtrar eventos (formato ISO 8601, ex: '2025-06-13T23:59:59Z').")
    query: Optional[str] = Field(default=None, description="Texto para buscar em eventos (título, descrição, local).") # Adicionado para busca
    event_id: Optional[str] = Field(default=None, description="ID específico do evento a ser buscado.") # Adicionado para busca por ID


class ListCalendarEventsTool(BaseTool):
    name: str = "Listar Eventos do Google Calendar"
    description: str = "Lista eventos do Google Calendar. Pode filtrar por um número máximo de resultados, um intervalo de tempo (time_min e time_max), uma query de texto ou um ID de evento específico."
    args_schema: Type[BaseModel] = ListCalendarEventsInput

    def _run(self, max_results: int = 10, time_min: Optional[str] = None, time_max: Optional[str] = None, query: Optional[str] = None, event_id: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()
            
            # Se um event_id for fornecido, tenta buscar apenas aquele evento
            if event_id:
                try:
                    event = service.events().get(calendarId='primary', eventId=event_id).execute()
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    start_obj = datetime.fromisoformat(start)
                    start_formatted = start_obj.strftime('%d/%m/%Y às %H:%M')
                    return (f"Evento encontrado por ID:\n"
                            f"- {event['summary']} (Início: {start_formatted}, ID: {event['id']})")
                except HttpError as e:
                    if e.resp.status == 404:
                        return f"Evento com ID '{event_id}' não encontrado."
                    raise # Re-lança outros erros HTTP
                
            now_utc = datetime.now(timezone.utc).isoformat()
            
            list_params = {
                'calendarId': 'primary',
                'timeMin': time_min if time_min else now_utc,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            if time_max:
                list_params['timeMax'] = time_max
            if query: # Adiciona a query de texto
                list_params['q'] = query

            events_result = service.events().list(**list_params).execute()
            events = events_result.get('items', [])

            if not events:
                return "Nenhum evento encontrado para o período especificado ou com a query."
            
            events_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                start_obj = datetime.fromisoformat(start)
                start_formatted = start_obj.strftime('%d/%m/%Y às %H:%M')
                # Inclui o ID do evento para futuras operações de update/delete
                events_list.append(f"- {event['summary']} (Início: {start_formatted}, ID: {event['id']})")
            
            return "Eventos encontrados:\n" + "\n".join(events_list)
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao listar eventos do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao listar eventos: {e}"

# --- NOVAS FERRAMENTAS ---

class GetEventIdByDetailsInput(BaseModel):
    summary: str = Field(description="Título exato do evento a ser encontrado.")
    start_datetime: str = Field(description="Data e hora de início exata do evento no formato 'YYYY-MM-DDTHH:MM:SS'.")

class GetEventIdByDetailsTool(BaseTool):
    name: str = "Obter ID de Evento por Detalhes"
    description: str = "Busca o ID de um evento no Google Calendar usando o título e a data/hora de início exatos. Útil para encontrar o ID antes de deletar ou atualizar."
    args_schema: Type[BaseModel] = GetEventIdByDetailsInput

    def _run(self, summary: str, start_datetime: str) -> str:
        try:
            service = get_google_calendar_service()
            
            # Formata a data/hora de início para o fuso horário correto e ISO 8601
            # Garante que time_min e time_max cobrem um pequeno intervalo para a busca exata
            start_obj = datetime.fromisoformat(start_datetime)
            time_min_utc = start_obj.astimezone(timezone.utc).isoformat()
            
            # Define um pequeno intervalo para garantir que o evento exato seja encontrado
            # Adiciona 1 minuto ao time_max para cobrir eventos que começam exatamente no 'start_datetime'
            time_max_utc = (start_obj + datetime.timedelta(minutes=1)).astimezone(timezone.utc).isoformat()


            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min_utc,
                timeMax=time_max_utc,
                q=summary, # Busca pelo resumo/título
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])

            if not events:
                return f"Nenhum evento encontrado com o título '{summary}' e início em '{start_datetime}'. Verifique o título e a data/hora."
            
            # Filtra eventos que correspondem exatamente à data e hora de início
            found_events = []
            for event in events:
                event_start = event['start'].get('dateTime', event['start'].get('date'))
                event_start_obj = datetime.fromisoformat(event_start)
                
                # Compara considerando fuso horário ou ajustando
                if event_start_obj.replace(tzinfo=None) == start_obj.replace(tzinfo=None): # Ignora tz para comparação se o input não tem tz
                    found_events.append(event)

            if not found_events:
                 return f"Nenhum evento encontrado com o título '{summary}' e início em '{start_datetime}'. Verifique o título e a data/hora."
            
            if len(found_events) > 1:
                # Se houver mais de um, precisa de desambiguação, ou retorna o primeiro e alerta.
                # Por simplicidade, vamos retornar o primeiro e alertar para o agente tratar.
                return (f"Múltiplos eventos encontrados com o título '{summary}' e início em '{start_datetime}'. "
                        f"Retornando o ID do primeiro: {found_events[0]['id']}. Por favor, seja mais específico se precisar de um evento diferente.")
            
            return found_events[0]['id']

        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao buscar o ID do evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao buscar o ID do evento: {e}"


class UpdateCalendarEventInput(BaseModel):
    event_id: str = Field(description="ID do evento a ser atualizado.")
    summary: Optional[str] = Field(default=None, description="Novo título ou resumo do evento.")
    start_datetime: Optional[str] = Field(default=None, description="Nova data e hora de início do evento no formato 'YYYY-MM-DDTHH:MM:SS'.")
    end_datetime: Optional[str] = Field(default=None, description="Nova data e hora de término do evento no formato 'YYYY-MM-DDTHH:MM:SS'.")
    description: Optional[str] = Field(default=None, description="Nova descrição detalhada do evento.")
    location: Optional[str] = Field(default=None, description="Novo local do evento.")
    attendees: Optional[list[str]] = Field(default=None, description="Nova lista de e-mails dos participantes.")
    
class UpdateCalendarEventTool(BaseTool):
    name: str = "Atualizar Evento no Google Calendar"
    description: str = "Atualiza um evento existente no Google Calendar. Requer o ID do evento e os campos a serem alterados. Se o ID não for fornecido, use 'Obter ID de Evento por Detalhes' primeiro."
    args_schema: Type[BaseModel] = UpdateCalendarEventInput

    def _run(self, event_id: str, summary: Optional[str] = None, start_datetime: Optional[str] = None, end_datetime: Optional[str] = None, description: Optional[str] = None, location: Optional[str] = None, attendees: Optional[list[str]] = None) -> str:
        try:
            service = get_google_calendar_service()
            
            # Primeiro, obtém o evento existente para não sobrescrever campos não fornecidos
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            
            # Atualiza os campos se novos valores forem fornecidos
            if summary is not None:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if location is not None:
                event['location'] = location
            if start_datetime is not None:
                event['start']['dateTime'] = start_datetime
                event['start']['timeZone'] = 'America/Sao_Paulo'
            if end_datetime is not None:
                event['end']['dateTime'] = end_datetime
                event['end']['timeZone'] = 'America/Sao_Paulo'
            if attendees is not None:
                event['attendees'] = [{'email': email} for email in attendees]
            
            updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            
            start_obj = datetime.fromisoformat(updated_event['start'].get('dateTime', updated_event['start'].get('date')))
            end_obj = datetime.fromisoformat(updated_event['end'].get('dateTime', updated_event['end'].get('date')))

            return (f"Evento atualizado com sucesso! Link: {updated_event.get('htmlLink')} | "
                    f"Nome: {updated_event['summary']} | "
                    f"Data: {start_obj.strftime('%d/%m/%Y')} | "
                    f"Início: {start_obj.strftime('%H:%M')} | "
                    f"Término: {end_obj.strftime('%H:%M')}")

        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            if error.resp.status == 404:
                return f"Erro: Evento com ID '{event_id}' não encontrado para atualização."
            return f"Ocorreu um erro ao atualizar o evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao atualizar o evento: {e}"

class DeleteCalendarEventInput(BaseModel):
    event_id: str = Field(description="ID do evento a ser deletado.")

class DeleteCalendarEventTool(BaseTool):
    name: str = "Deletar Evento no Google Calendar"
    description: str = "Deleta um evento existente no Google Calendar. Requer o ID do evento. Se o ID não for fornecido, use 'Obter ID de Evento por Detalhes' primeiro."
    args_schema: Type[BaseModel] = DeleteCalendarEventInput

    def _run(self, event_id: str) -> str:
        try:
            service = get_google_calendar_service()
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return f"Evento com ID '{event_id}' deletado com sucesso."
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            if error.resp.status == 404:
                return f"Erro: Evento com ID '{event_id}' não encontrado para exclusão."
            return f"Ocorreu um erro ao deletar o evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao deletar o evento: {e}"