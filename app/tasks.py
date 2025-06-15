# mega_secretaria/app/tasks.py

from crewai import Task
from app.agents import MegaSecretaryAgents
from app.tools.google_calendar_tools import CreateCalendarEventTool, ListCalendarEventsTool

# NOVO: Para obter a data e hora atuais com fuso horário
from datetime import datetime
from zoneinfo import ZoneInfo

class MegaSecretaryTasks:
    def __init__(self):
        self.agents = MegaSecretaryAgents()
        # NOVO: Define o fuso horário de São Paulo
        self.sao_paulo_tz = ZoneInfo("America/Sao_Paulo")

    def _get_current_time_context(self):
        """Retorna uma string com a data e hora atuais para injetar nos prompts."""
        now = datetime.now(self.sao_paulo_tz).strftime('%A, %d de %B de %Y, %H:%M:%S')
        return f"Contexto Atual: A data e hora exatas agora em São Paulo são: {now}. Use esta informação para interpretar referências relativas como 'hoje', 'amanhã' ou 'semana que vem'."

    # Modificar para aceitar o histórico
    def route_request_task(self, user_message: str, history: str = ""):
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history} # <--- INJETA O HISTÓRICO AQUI

            Analise a seguinte mensagem do usuário e determine a intenção principal:
            "{user_message}"

            Se a mensagem for sobre criar, listar, consultar, *deletar* ou *gerenciar/alterar* eventos/compromissos/reuniões no calendário,
            a intenção é **'gerenciamento de calendário'**.
            Se a mensagem não se encaixar claramente em gerenciamento de calendário,
            a intenção é **'outra_requisição'**.

            Sua saída DEVE ser EXATAMENTE uma das duas strings fornecidas, sem espaços extras, capitalização diferente ou caracteres adicionais:
            'gerenciamento de calendário' ou 'outra_requisição'.
            """,
            expected_output="Uma string indicando a intenção: 'gerenciamento de calendário' ou 'outra_requisição'.",
            agent=self.agents.request_router_agent()
        )

    # Modificar para aceitar o histórico
    def manage_calendar_task(self, user_message: str, history: str = ""):
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history} # <--- INJETA O HISTÓRICO AQUI

            Com base na mensagem do usuário e no histórico da conversa, gerencie o Google Calendar.
            A mensagem do usuário é: \"{user_message}\"

            Você deve ser capaz de:
            - **Criar eventos**: se o usuário pedir para criar um compromisso, reunião, lembrete, etc. Para criar um evento, você precisará de:
                - Título (summary)
                - Data e hora de início (start_datetime)
                - Data e hora de término (end_datetime) (opcional, mas tente inferir se possível)
                - Descrição (description) (opcional)
                - Local (location) (opcional)
            - **Listar eventos**: se o usuário pedir para ver os eventos futuros. Pode precisar de:
                - Data ou período (time_min, time_max) (opcional, se não informado, liste os próximos 10 eventos)

            Se alguma informação essencial para criar um evento estiver faltando, **peça ao usuário de forma clara e específica** os dados que faltam.
            Ao interagir com o usuário, seja sempre educado e claro em suas perguntas ou respostas.

            Utilize as ferramentas de Google Calendar para executar a ação.
            """,
            expected_output="""
            - Se um evento for criado: Uma resposta formatada confirmando a criação, baseada na saída da ferramenta. Exemplo:
              '✅ Evento Criado com Sucesso!

              *Nome:* Nome do Evento
              *Data:* DD/MM/YYYY
              *Início:* HH:MM
              *Término:* HH:MM'
            - Se eventos forem listados: A lista de eventos fornecida pela ferramenta.
            - Se faltar informação: Uma pergunta clara ao usuário solicitando os dados necessários.
            """,
            agent=self.agents.calendar_manager_agent(),
            tools=[CreateCalendarEventTool(), ListCalendarEventsTool()]
        )

    # Modificar para aceitar o histórico
    def general_chat_task(self, user_message: str, history: str = ""):
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history} # <--- INJETA O HISTÓRICO AQUI

            A requisição do usuário não é sobre gerenciamento de calendário.
            Responda à pergunta do usuário de forma útil e amigável, **utilizando o histórico da conversa para manter o contexto e a coerência**.
            Tente responder a perguntas gerais ou continuar uma conversa.
            Se não souber a resposta, peça desculpas e ofereça ajuda com outra coisa.
            Lembre-se de informações fornecidas anteriormente pelo usuário, como o nome dele.

            Mensagem do usuário: "{user_message}"
            """,
            expected_output="Uma resposta útil e amigável à pergunta do usuário.",
            agent=self.agents.general_chatter_agent()
        )