# mega_secretaria/app/tasks.py

from crewai import Task
from app.agents import MegaSecretaryAgents
# NOVO: Importar as ferramentas do Google Calendar
from app.tools.google_calendar_tools import CreateCalendarEventTool, ListCalendarEventsTool

class MegaSecretaryTasks:
    def __init__(self):
        self.agents = MegaSecretaryAgents()

    def route_request_task(self, user_message: str):
        return Task(
            description=f"""
            Analise a seguinte mensagem do usuário e determine a intenção principal:
            "{user_message}"

            Se a mensagem for sobre criar, listar, consultar ou gerenciar eventos/compromissos/reuniões no calendário,
            a intenção é 'gerenciamento de calendário'.
            Se a mensagem não se encaixar claramente em gerenciamento de calendário,
            a intenção é 'outra_requisição'.

            Sua saída deve ser uma string simples indicando a intenção.
            Exemplos:
            - "gerenciamento de calendário"
            - "outra_requisição"
            """,
            expected_output="Uma string indicando a intenção da requisição ('gerenciamento de calendário' ou 'outra_requisição').",
            agent=self.agents.request_router_agent(),
            output_file='request_intent.txt' # Salva a intenção para ser lida por outra tarefa/processo
        )

    def manage_calendar_task(self, user_message: str):
        return Task(
            description=f"""
            Com base na seguinte mensagem do usuário, utilize as ferramentas de Google Calendar para criar ou listar eventos.
            Você deve extrair todas as informações relevantes para a ação (criar ou listar).

            Para criar um evento, você precisará de:
            - Título do evento
            - Data e hora de início (formato YYYY-MM-DDTHH:MM:SS)
            - Data e hora de término (formato YYYY-MM-DDTHH:MM:SS)
            - Descrição (opcional)
            - Local (opcional)
            - Participantes (e-mails, opcional)

            Se a mensagem for para listar eventos, use a ferramenta de listagem.
            Se precisar de mais informações do usuário para criar um evento, peça-as de forma clara.

            Mensagem do usuário: "{user_message}"
            """,
            expected_output="Confirmação da criação do evento, URL do evento, ou lista de eventos, ou uma pergunta para obter mais informações.",
            agent=self.agents.calendar_manager_agent(),
            # CORREÇÃO DO NAMERROR: As ferramentas agora estão importadas
            tools=[CreateCalendarEventTool(), ListCalendarEventsTool()]
        )

    # NOVO: Tarefa para lidar com requisições gerais
    def general_chat_task(self, user_message: str):
        return Task(
            description=f"""
            A requisição do usuário não é sobre gerenciamento de calendário.
            Responda à pergunta do usuário de forma útil e amigável.
            Tente responder a perguntas gerais ou continuar uma conversa.
            Se não souber a resposta, peça desculpas e ofereça ajuda com outra coisa.

            Mensagem do usuário: "{user_message}"
            """,
            expected_output="Uma resposta útil e amigável à pergunta do usuário, ou uma mensagem educada se não puder ajudar.",
            agent=self.agents.general_chatter_agent() # Atribuído ao novo agente geral
        )