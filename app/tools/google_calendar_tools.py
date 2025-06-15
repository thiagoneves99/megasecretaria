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

    if os.makedirs(os.path.dirname(token_path), exist_ok=True) # Garante que o diretório exista
    
    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Erro ao carregar token.pickle: {e}")
            creds = None # Força a reautenticação se o token estiver corrompido

    # Se não há credenciais válidas disponíveis, tenta gerar novas (offline)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expirado, tentando refrescar...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Erro ao refrescar token: {e}. Provavelmente o refresh token também expirou ou foi revogado.")
                raise GoogleCalendarAuthError("Credenciais do Google Calendar precisam ser re-autorizadas manualmente.")
        else:
            # Em um ambiente de produção sem UI, você não deve chegar aqui.
            # Este bloco é mais para desenvolvimento inicial local.
            print("Nenhum token válido encontrado ou token expirado sem refresh_token. Tentando fluxo manual.")
            # Para o deploy, o token.pickle deve ser pré-gerado.
            # Uma alternativa mais robusta para produção seria usar uma Service Account.
            raise GoogleCalendarAuthError("Token do Google Calendar não encontrado ou inválido. Por favor, gere o token.pickle manualmente com as credenciais OAuth 2.0.")

        # Salva as credenciais atualizadas
        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            print("Token do Google Calendar salvo/atualizado com sucesso.")
        except Exception as e:
            print(f"Erro ao salvar token.pickle: {e}")
            # Não levantar erro fatal aqui, apenas logar. A operação pode continuar com as creds em memória.

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except HttpError as error:
        raise GoogleCalendarAuthError(f"Erro na construção do serviço Google Calendar: {error}")
    except Exception as e:
        raise GoogleCalendarAuthError(f"Erro inesperado na autenticação do Google Calendar: {e}")


# --- Ferramenta para Criar Evento ---
class CreateCalendarEventInput(BaseModel):
    summary: str = Field(description="Título ou nome do evento/reunião. Obrigatório.")
    start_datetime: str = Field(description="Data e hora de início do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS), por exemplo, '2023-10-27T10:00:00'. Obrigatório.")
    end_datetime: Optional[str] = Field(description="Data e hora de término do evento no formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Se não fornecido, assumir 1 hora após start_datetime.", default=None)
    description: Optional[str] = Field(description="Descrição detalhada do evento.", default=None)
    location: Optional[str] = Field(description="Local do evento.", default=None)

class CreateCalendarEventTool(BaseTool):
    name: str = "Criar Evento no Google Calendar"
    description: str = "Cria um novo evento no Google Calendar. Requer título, data e hora de início. Pode inferir a data atual se apenas a hora for fornecida."
    args_schema: Type[BaseModel] = CreateCalendarEventInput

    def _run(self, summary: str, start_datetime: str, end_datetime: Optional[str] = None, description: Optional[str] = None, location: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()

            # Tenta converter para objetos datetime
            start_dt_obj = datetime.fromisoformat(start_datetime)
            
            if end_datetime:
                end_dt_obj = datetime.fromisoformat(end_datetime)
            else:
                # Se end_datetime não for fornecido, assume 1 hora de duração
                end_dt_obj = start_dt_obj + datetime.timedelta(hours=1)
            
            # Garante que as datas estejam no fuso horário correto (UTC ou especificado)
            # É crucial que as datas enviadas para a API do Google Calendar incluam informações de fuso horário
            # ou sejam UTC para evitar problemas.
            if start_dt_obj.tzinfo is None:
                # Assumimos que, se não houver tzinfo, é no fuso horário de São Paulo (local)
                # e convertemos para UTC para a API do Google
                sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
                start_dt_obj = start_dt_obj.replace(tzinfo=sao_paulo_tz).astimezone(timezone.utc)
                end_dt_obj = end_dt_obj.replace(tzinfo=sao_paulo_tz).astimezone(timezone.utc)
            else:
                # Se já tem tzinfo, apenas garante que está em UTC para a API
                start_dt_obj = start_dt_obj.astimezone(timezone.utc)
                end_dt_obj = end_dt_obj.astimezone(timezone.utc)


            event = {
                'summary': summary,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_dt_obj.isoformat(),
                    'timeZone': 'UTC', # Ou o fuso horário que você preferir que o Google interprete
                },
                'end': {
                    'dateTime': end_dt_obj.isoformat(),
                    'timeZone': 'UTC',
                },
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            
            # Formata a saída para o usuário
            start_local = start_dt_obj.astimezone(ZoneInfo("America/Sao_Paulo"))
            end_local = end_dt_obj.astimezone(ZoneInfo("America/Sao_Paulo"))

            return (
                f"✅ Evento Criado com Sucesso!\n\n"
                f"*Nome:* {event.get('summary')}\n"
                f"*Data:* {start_local.strftime('%d/%m/%Y')}\n"
                f"*Início:* {start_local.strftime('%H:%M')}\n"
                f"*Término:* {end_local.strftime('%H:%M')}\n"
                f"*ID:* {event.get('id')}" # Adicionado o ID do evento
            )
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao criar o evento no Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao criar o evento: {e}"

# --- Ferramenta para Listar Eventos ---
class ListCalendarEventsInput(BaseModel):
    time_min: Optional[str] = Field(description="Data e hora mínima para listar eventos no formato ISO 8601 (YYYY-MM-DDTHH:MM:SSZ). Se não fornecido, listará a partir de agora.", default=None)
    time_max: Optional[str] = Field(description="Data e hora máxima para listar eventos no formato ISO 8601 (YYYY-MM-DDTHH:MM:SSZ).", default=None)
    max_results: int = Field(description="Número máximo de eventos a serem retornados. Padrão é 10.", default=10)
    query: Optional[str] = Field(description="Texto para filtrar eventos por título/descrição. Se fornecido, só eventos que contenham esse texto serão listados.", default=None)

class ListCalendarEventsTool(BaseTool):
    name: str = "Listar Eventos do Google Calendar"
    description: str = "Lista os próximos eventos do Google Calendar. Pode ser filtrado por data/hora mínima e máxima, e por um texto de busca no título/descrição. Por padrão, lista os próximos 10 eventos a partir de agora."
    args_schema: Type[BaseModel] = ListCalendarEventsInput

    def _run(self, time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 10, query: Optional[str] = None) -> str:
        try:
            service = get_google_calendar_service()
            
            now = datetime.now(timezone.utc)
            now_utc = now.isoformat(timespec='seconds') + 'Z' # Formato RFC3339

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
            if query: # Adiciona o parâmetro de busca por query
                list_params['q'] = query

            events_result = service.events().list(**list_params).execute()
            events = events_result.get('items', [])

            if not events:
                return "Nenhum evento encontrado para o período especificado ou com o termo de busca."
            
            events_list = ["✅ Aqui estão seus eventos:"]
            for i, event in enumerate(events):
                start = event['start'].get('dateTime', event['start'].get('date'))
                
                # Tratar eventos de dia inteiro (que têm 'date' em vez de 'dateTime')
                if 'date' in event['start']:
                    start_obj = datetime.strptime(start, '%Y-%m-%d').date()
                    start_formatted = start_obj.strftime('%d/%m/%Y')
                    time_info = "Dia Inteiro"
                else:
                    start_obj = datetime.fromisoformat(start)
                    start_local = start_obj.astimezone(ZoneInfo("America/Sao_Paulo"))
                    start_formatted = start_local.strftime('%d/%m/%Y')
                    time_info = start_local.strftime('%H:%M')

                events_list.append(
                    f"{i+1}. **Título:** {event['summary']}\n"
                    f"    - **Data:** {start_formatted}\n"
                    f"    - **Início:** {time_info}\n"
                    f"    - **ID:** {event.get('id')}" # Inclui o ID para facilitar a exclusão
                )
            
            return "\n".join(events_list) + "\n\nSe precisar de mais informações ou de ajuda com outro evento, é só avisar!"
        except GoogleCalendarAuthError as e:
            return f"Erro de autenticação do Google Calendar: {e}"
        except HttpError as error:
            return f"Ocorreu um erro ao listar eventos do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao listar eventos: {e}"

# --- NOVO: Ferramenta para Deletar Evento ---
class DeleteCalendarEventInput(BaseModel):
    event_id: str = Field(description="O ID único do evento a ser deletado.")

class DeleteCalendarEventTool(BaseTool):
    name: str = "Deletar Evento do Google Calendar"
    description: str = "Deleta um evento específico do Google Calendar usando seu ID. O ID do evento pode ser obtido ao listar os eventos."
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
            return f"Ocorreu um erro ao deletar o evento do Google Calendar: {error}"
        except Exception as e:
            return f"Ocorreu um erro inesperado ao deletar o evento: {e}"