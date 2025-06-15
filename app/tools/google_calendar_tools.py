# mega_secretaria/app/tools/google_calendar_tools.py

import os
import pickle
from datetime import datetime, timezone, timedelta
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
            # Em caso de erro ao carregar o token, forçar reautenticação (ou assumir que o token será gerado externamente)
            print(f"Erro ao carregar token.pickle: {e}. Será necessário um novo token.")
            creds = None

    # Se não há credenciais válidas, tentar obtê-las (isso funcionaria em ambiente local com browser)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise GoogleCalendarAuthError(f"Falha ao refresh do token: {e}. O token pode estar revogado ou os escopos são insuficientes.")
        else:
            # Em um ambiente de servidor (como Docker/EasyPanel), a geração interativa de um novo token não é possível.
            # O token.pickle deve ser gerado localmente e copiado para o volume persistente do servidor.
            # Se você chegou aqui e creds é None, significa que token.pickle não existe ou é inválido
            # e você está em um ambiente sem UI para o fluxo de autenticação.
            raise GoogleCalendarAuthError(
                "Credenciais do Google Calendar ausentes ou inválidas. "
                "Por favor, gere o arquivo 'token.pickle' localmente e o disponibilize no caminho configurado."
            )
    
    # Salva as credenciais atualizadas (especialmente após um refresh)
    try:
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    except Exception as e:
        print(f"Aviso: Não foi possível salvar o token.pickle atualizado: {e}")

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        raise GoogleCalendarAuthError(f"Erro ao construir o serviço do Google Calendar: {e}")


# Modelos Pydantic para entrada das ferramentas
class CreateCalendarEventInput(BaseModel):
    summary: str = Field(description="Título ou nome do evento.")
    start_datetime: str = Field(description="Data e hora de início do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS), por exemplo, '2023-10-27T10:00:00'.")
    end_datetime: Optional[str] = Field(description="Data e hora de término do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Se não fornecido, será calculado com base na duração padrão (1 hora).", default=None)
    description: Optional[str] = Field(description="Descrição detalhada do evento.", default=None)
    location: Optional[str] = Field(description="Local do evento.", default=None)

class ListCalendarEventsInput(BaseModel):
    max_results: int = Field(description="Número máximo de eventos a serem retornados.", default=10)
    time_min: Optional[str] = Field(description="Data e hora mínima (início do período de busca) no formato ISO 8601 com 'Z' para UTC, por exemplo, '2023-10-27T00:00:00Z'. Se não fornecido, usará a data e hora atual.", default=None)
    time_max: Optional[str] = Field(description="Data e hora máxima (fim do período de busca) no formato ISO 8601 com 'Z' para UTC, por exemplo, '2023-10-27T23:59:59Z'. Usado para filtrar eventos dentro de um dia específico. Se não fornecido, listará eventos futuros a partir de time_min.", default=None)
    query: Optional[str] = Field(description="Palavra-chave para filtrar eventos por título.", default=None)

class UpdateCalendarEventInput(BaseModel):
    event_id: str = Field(description="O ID único do evento a ser atualizado.")
    summary: Optional[str] = Field(description="Novo título do evento.", default=None)
    start_datetime: Optional[str] = Field(description="Nova data e hora de início do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS).", default=None)
    end_datetime: Optional[str] = Field(description="Nova data e hora de término do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS).", default=None)
    description: Optional[str] = Field(description="Nova descrição detalhada do evento.", default=None)
    location: Optional[str] = Field(description="Novo local do evento.", default=None)

class DeleteCalendarEventInput(BaseModel):
    event_id: str = Field(description="O ID único do evento a ser deletado.")

class GetEventIdByDetailsInput(BaseModel):
    summary: str = Field(description="O título exato do evento a ser encontrado.")
    start_datetime: Optional[str] = Field(description="A data e hora de início aproximada do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Ajuda a refinar a busca.", default=None)
    end_datetime: Optional[str] = Field(description="A data e hora de término aproximada do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Ajuda a refinar a busca.", default=None)
    # Adicionado um parâmetro para procurar em um intervalo se as datas exatas não forem fornecidas
    search_days_around_start: int = Field(description="Número de dias para procurar o evento ao redor do 'start_datetime' fornecido. Útil se a data/hora exata não for conhecida. Padrão para 0 (apenas o dia exato).", default=0)


class CreateCalendarEventTool(BaseTool):
    name: str = "Criar Evento no Google Calendar"
    description: str = (
        "Cria um novo evento no Google Calendar. "
        "Requer o título (summary) e a data/hora de início (start_datetime). "
        "A hora de término (end_datetime) é opcional; se não fornecida, o evento terá duração padrão de 1 hora. "
        "Exemplo de uso: `Criar Evento no Google Calendar(summary='Reunião de Equipe', start_datetime='2023-11-15T10:00:00', description='Discutir projetos', location='Sala A')`"
    )
    args_schema: Type[BaseModel] = CreateCalendarEventInput

    def _run(self, summary: str, start_datetime: str, end_datetime: Optional[str] = None, description: Optional[str] = None, location: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()
            
            # Converte a string de data/hora para objeto datetime
            start_dt_obj = datetime.fromisoformat(start_datetime)
            
            # Se end_datetime não for fornecido, calcula 1 hora depois de start_datetime
            if not end_datetime:
                end_dt_obj = start_dt_obj + timedelta(hours=1)
                end_datetime = end_dt_obj.isoformat()
            else:
                end_dt_obj = datetime.fromisoformat(end_datetime) # Verifica se o end_datetime é válido

            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_datetime,
                    'timeZone': 'America/Sao_Paulo', # Supondo fuso horário padrão para criação
                },
                'end': {
                    'dateTime': end_datetime,
                    'timeZone': 'America/Sao_Paulo', # Supondo fuso horário padrão para criação
                },
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            
            # Formata a saída para ser mais amigável
            start_formatted = datetime.fromisoformat(event['start']['dateTime']).strftime('%d/%m/%Y às %H:%M')
            end_formatted = datetime.fromisoformat(event['end']['dateTime']).strftime('%d/%m/%Y às %H:%M')

            return (f"✅ Evento Criado com Sucesso!\n\n"
                            f"*Nome:* {event['summary']}\n"
                            f"*Data:* {datetime.fromisoformat(event['start']['dateTime']).strftime('%d/%m/%Y')}\n"
                            f"*Início:* {start_formatted.split(' ')[2]}\n" # Pega apenas a hora
                            f"*Término:* {end_formatted.split(' ')[2]}\n" # Pega apenas a hora
                            f"*ID:* {event['id']}")

        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao criar o evento do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao criar o evento: {e}"

class ListCalendarEventsTool(BaseTool):
    name: str = "Listar Eventos do Google Calendar"
    description: str = (
        "Lista eventos do Google Calendar. "
        "Pode filtrar por número máximo de resultados (max_results), "
        "período (time_min e time_max no formato ISO 8601 com 'Z' para UTC, e.g., '2023-10-27T00:00:00Z'), "
        "e palavra-chave no título (query). "
        "Exemplo de uso: `Listar Eventos do Google Calendar(time_min='2023-11-01T00:00:00Z', time_max='2023-11-30T23:59:59Z', query='Reunião')`"
    )
    args_schema: Type[BaseModel] = ListCalendarEventsInput

    def _run(self, max_results: int = 10, time_min: Optional[str] = None, time_max: Optional[str] = None, query: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()
            
            now_utc = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z' # Current time in UTC

            # Garante que timeMin seja fornecido ou usa o tempo atual
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
                list_params['q'] = query # 'q' é o parâmetro de query para a API

            events_result = service.events().list(**list_params).execute()
            events = events_result.get('items', [])

            if not events:
                return "Nenhum evento encontrado para o período especificado ou com a query."
            
            events_list = []
            for i, event in enumerate(events):
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Formata a data/hora para ser mais legível
                start_obj = datetime.fromisoformat(start)
                # Formata para o fuso horário de São Paulo para exibição, se for um datetime
                if 'dateTime' in event['start']:
                    # Define o fuso horário de São Paulo
                    sao_paulo_tz = timezone(timedelta(hours=-3)) # UTC-3 para São Paulo
                    start_obj_local = start_obj.astimezone(sao_paulo_tz)
                    start_formatted = start_obj_local.strftime('%d/%m/%Y às %H:%M')
                else: # É um evento de dia inteiro, sem hora
                    start_formatted = start_obj.strftime('%d/%m/%Y')
                
                # Adiciona o ID do evento na saída
                event_id = event.get('id', 'N/A')
                events_list.append(f"{i+1}. **Título:** {event['summary']}\n    - **Data:** {start_formatted.split(' ')[0]}\n    - **Início:** {'N/A' if 'date' in event['start'] else start_formatted.split(' ')[2]}\n    - **ID:** {event_id}")
            
            return f"✅ Aqui estão seus eventos:\n\n" + "\n\n".join(events_list) + "\n\nSe precisar de mais informações ou de ajuda com outro evento, é só avisar!"
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao listar eventos do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao listar eventos: {e}"

class UpdateCalendarEventTool(BaseTool):
    name: str = "Atualizar Evento no Google Calendar"
    description: str = (
        "Atualiza um evento existente no Google Calendar usando o ID do evento. "
        "Pode alterar título (summary), data/hora de início (start_datetime), "
        "data/hora de término (end_datetime), descrição (description) e local (location). "
        "Pelo menos um campo para atualização além do event_id deve ser fornecido. "
        "Exemplo de uso: `Atualizar Evento no Google Calendar(event_id='abcdef123', start_datetime='2023-11-16T15:00:00', location='Sala B')`"
    )
    args_schema: Type[BaseModel] = UpdateCalendarEventInput

    def _run(self, event_id: str, summary: Optional[str] = None, start_datetime: Optional[str] = None, end_datetime: Optional[str] = None, description: Optional[str] = None, location: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()

            # Primeiro, recupere o evento existente para não sobrescrever campos não especificados
            event = service.events().get(calendarId='primary', eventId=event_id).execute()

            # Atualiza os campos fornecidos
            if summary is not None:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if location is not None:
                event['location'] = location
            
            if start_datetime is not None:
                event['start']['dateTime'] = start_datetime
                # Se start_datetime é atualizado e end_datetime não, recalcula end_datetime se for um evento com horário
                if 'dateTime' in event['end'] and end_datetime is None:
                    try:
                        start_dt_obj = datetime.fromisoformat(start_datetime)
                        old_end_dt_obj = datetime.fromisoformat(event['end']['dateTime'])
                        old_start_dt_obj = datetime.fromisoformat(event['start']['dateTime'])
                        duration = old_end_dt_obj - old_start_dt_obj
                        # Se a duração for 0, ou negativa (o que não deveria acontecer), ou muito grande, assume 1h
                        if duration <= timedelta(minutes=0) or duration > timedelta(hours=24):
                            duration = timedelta(hours=1)
                        event['end']['dateTime'] = (start_dt_obj + duration).isoformat()
                    except ValueError: # Caso fromisoformat falhe (data inválida)
                        event['end']['dateTime'] = (datetime.fromisoformat(start_datetime) + timedelta(hours=1)).isoformat()
                elif 'date' in event['end'] and end_datetime is None: # Se era um evento de dia inteiro, mantém como dia inteiro ou força 1h
                     event['end']['date'] = (datetime.fromisoformat(start_datetime)).strftime('%Y-%m-%d')
            
            if end_datetime is not None:
                event['end']['dateTime'] = end_datetime

            # Garante que timeZone esteja presente se for evento com dateTime
            if 'dateTime' in event['start'] and 'timeZone' not in event['start']:
                event['start']['timeZone'] = 'America/Sao_Paulo'
            if 'dateTime' in event['end'] and 'timeZone' not in event['end']:
                event['end']['timeZone'] = 'America/Sao_Paulo'


            updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            
            # Formata a saída para ser mais amigável
            start_formatted = datetime.fromisoformat(updated_event['start'].get('dateTime', updated_event['start'].get('date'))).strftime('%d/%m/%Y às %H:%M')
            end_formatted = datetime.fromisoformat(updated_event['end'].get('dateTime', updated_event['end'].get('date'))).strftime('%d/%m/%Y às %H:%M')

            return (f"✅ Evento Atualizado com Sucesso!\n\n"
                            f"*Nome:* {updated_event['summary']}\n"
                            f"*Data:* {start_formatted.split(' ')[0]}\n"
                            f"*Início:* {'N/A' if 'date' in updated_event['start'] else start_formatted.split(' ')[2]}\n"
                            f"*Término:* {'N/A' if 'date' in updated_event['end'] else end_formatted.split(' ')[2]}\n"
                            f"*ID:* {updated_event['id']}")

        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            if error.resp.status == 404:
                return f"Evento com ID '{event_id}' não encontrado."
            return f"Ocorreu um erro ao atualizar o evento do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao atualizar o evento: {e}"

class DeleteCalendarEventTool(BaseTool):
    name: str = "Deletar Evento no Google Calendar"
    description: str = (
        "Deleta um evento do Google Calendar usando o ID do evento. "
        "Exemplo de uso: `Deletar Evento no Google Calendar(event_id='abcdef123')`"
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
                return f"Evento com ID '{event_id}' não encontrado."
            return f"Ocorreu um erro ao deletar o evento do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao deletar o evento: {e}"

class GetEventIdByDetailsTool(BaseTool):
    name: str = "Obter ID de Evento por Detalhes"
    description: str = (
        "Busca o ID de um evento no Google Calendar usando o título (summary) e, opcionalmente, "
        "a data/hora de início (start_datetime) ou um intervalo de busca (search_days_around_start). "
        "Útil quando o ID do evento não é conhecido. "
        "Retorna o ID do evento se encontrado, ou uma mensagem de erro/não encontrado. "
        "Se múltiplas correspondências forem encontradas, pedirá mais detalhes. "
        "Exemplo de uso: `Obter ID de Evento por Detalhes(summary='Reunião de Projeto', start_datetime='2023-11-15T09:00:00')`"
    )
    args_schema: Type[BaseModel] = GetEventIdByDetailsInput

    def _run(self, summary: str, start_datetime: Optional[str] = None, end_datetime: Optional[str] = None, search_days_around_start: int = 0) -> str:
        try:
            service = get_google_calendar_service()
            
            list_params = {
                'calendarId': 'primary',
                'singleEvents': True,
                'orderBy': 'startTime',
                'q': summary # Filtra por query de texto
            }

            now_utc = datetime.now(timezone.utc)
            time_min_search = None
            time_max_search = None

            if start_datetime:
                start_dt_obj = datetime.fromisoformat(start_datetime)
                # Adiciona ou subtrai dias para o intervalo de busca
                time_min_search = (start_dt_obj - timedelta(days=search_days_around_start)).isoformat(timespec='seconds') + 'Z'
                
                if not end_datetime:
                    # Se não há end_datetime, assume um período razoável para busca (e.g., até o final do dia + search_days_around_start)
                    # Adiciona 1 dia para incluir o dia completo se search_days_around_start for 0
                    time_max_search = (start_dt_obj.replace(hour=23, minute=59, second=59) + timedelta(days=search_days_around_start)).isoformat(timespec='seconds') + 'Z'
                else:
                    time_max_search = datetime.fromisoformat(end_datetime).isoformat(timespec='seconds') + 'Z'
            else:
                # Se nenhuma data é fornecida, busca a partir de agora para o futuro próximo (e.g., próximos 7 dias)
                time_min_search = now_utc.isoformat(timespec='seconds') + 'Z'
                time_max_search = (now_utc + timedelta(days=7)).isoformat(timespec='seconds') + 'Z'

            list_params['timeMin'] = time_min_search
            list_params['timeMax'] = time_max_search
            
            # Ajusta maxResults para buscar mais eventos na faixa de tempo para encontrar o correto
            list_params['maxResults'] = 20 # Aumentar o limite para garantir que encontre

            events_result = service.events().list(**list_params).execute()
            events = events_result.get('items', [])

            matching_events = []
            for event in events:
                # O filtro 'q' da API do Google Calendar já faz uma boa parte do trabalho.
                # Podemos adicionar uma verificação extra aqui se o summary for muito genérico
                # e quisermos uma correspondência exata de título.
                if event.get('summary', '').lower() == summary.lower():
                    matching_events.append(event)
            
            if not matching_events:
                return "Nenhum evento encontrado com os detalhes fornecidos."
            
            if len(matching_events) > 1:
                # Se houver múltiplos eventos com o mesmo título, listar para desambiguação
                event_details = []
                sao_paulo_tz = timezone(timedelta(hours=-3)) # UTC-3 para São Paulo

                for event in matching_events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    start_obj = datetime.fromisoformat(start)
                    if 'dateTime' in event['start']:
                        start_obj_local = start_obj.astimezone(sao_paulo_tz)
                        date_formatted = start_obj_local.strftime('%d/%m/%Y %H:%M')
                    else:
                        date_formatted = start_obj.strftime('%d/%m/%Y')
                    event_details.append(f" - Título: {event['summary']}, Data: {date_formatted}, ID: {event['id']}")
                return f"Múltiplos eventos encontrados com o título '{summary}'. Por favor, forneça mais detalhes (data/hora específica) para identificar o evento:\n" + "\n".join(event_details)

            # Se exatamente um evento for encontrado
            return matching_events[0]['id']

        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao buscar o ID do evento do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao buscar o ID do evento: {e}"