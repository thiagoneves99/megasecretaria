# mega_secretaria/app/tasks.py

from crewai import Task
from app.agents import MegaSecretaryAgents
from app.tools.google_calendar_tools import CreateCalendarEventTool, ListCalendarEventsTool, DeleteCalendarEventTool

# Para obter a data e hora atuais com fuso horário
from datetime import datetime
from zoneinfo import ZoneInfo

class MegaSecretaryTasks:
    def __init__(self):
        self.agents = MegaSecretaryAgents()
        # Define o fuso horário de São Paulo
        self.sao_paulo_tz = ZoneInfo("America/Sao_Paulo")

    def _get_current_time_context(self):
        """Retorna uma string com a data e hora atuais para injetar nos prompts."""
        now = datetime.now(self.sao_paulo_tz).strftime('%A, %d de %B de %Y, %H:%M:%S')
        return f"Contexto Atual: A data e hora exatas agora em São Paulo são: {now}. Use esta informação para interpretar referências relativas como 'hoje', 'amanhã' ou 'semana que vem'."

    def route_request_task(self, user_message: str, history: str = ""): # Adicionado history
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history} # Injeta o histórico aqui

            Analise a seguinte mensagem do usuário e determine a intenção principal:
            "{user_message}"

            Se a mensagem for sobre criar, listar, consultar ou gerenciar eventos/compromissos/reuniões no calendário,
            a intenção é **'gerenciamento de calendário'**.
            Se a mensagem não se encaixar claramente em gerenciamento de calendário,
            a intenção é **'outra_requisição'**.

            Sua saída DEVE ser EXATAMENTE uma das duas strings fornecidas, sem espaços extras, capitalização diferente ou caracteres adicionais:
            'gerenciamento de calendário' ou 'outra_requisição'.
            """,
            expected_output="Uma das strings: 'gerenciamento de calendário' ou 'outra_requisição'.",
            agent=self.agents.request_router_agent()
        )

    def manage_calendar_task(self, user_message: str, history: str = ""):
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history} # Injeta o histórico aqui

            Com base na mensagem do usuário e no histórico da conversa, gerencie o Google Calendar.
            A mensagem do usuário é: "{user_message}"

            Você deve ser capaz de:
            - **Criar eventos**: se o usuário pedir para criar um compromisso, reunião, lembrete, etc. Para criar um evento, você precisará de:
                - Título (summary)
                - Data e hora de início (start_datetime)
                - Data e hora de término (end_datetime) (opcional, mas tente inferir se possível)
                - Descrição (description) (opcional)
                - Local (location) (opcional)
            - **Listar eventos**: se o usuário pedir para ver os eventos futuros. Pode precisar de:
                - Data ou período (time_min, time_max) (opcional, se não informado, liste os próximos 10 eventos)
                - Termo de busca (query) (opcional, para filtrar eventos por título/descrição)
            - **Deletar eventos**: se o usuário pedir para remover um evento. Você precisará do ID do evento. Se o ID não for fornecido, primeiro liste os eventos relevantes para que o usuário possa identificar e confirmar qual evento deve ser deletado.

            Se alguma informação essencial para criar, listar ou deletar um evento estiver faltando, **peça ao usuário de forma clara e específica** os dados que faltam.
            Ao interagir com o usuário, seja sempre educado e claro em suas perguntas ou respostas. Se precisar do ID de um evento para deletar, liste-os e peça a confirmação do ID.

            Utilize as ferramentas de Google Calendar para executar a ação.

            Regras de Saída (Expected Output):
            - Se um evento for criado: Uma resposta formatada confirmando a criação e detalhes importantes. Exemplo: '✅ Evento Criado com Sucesso!\n*Nome:* Reunião...\n*Data:* 15/06/2025\n*Início:* 10:00\n*Término:* 11:00'
            - Se eventos forem listados: Retorne **EXATAMENTE** a saída completa da ferramenta `List Calendar Events` (que já virá formatada) OU a mensagem de "Nenhum compromisso agendado para o período especificado", seguida de uma frase amigável para perguntar se o usuário precisa de mais alguma coisa ou se deseja deletar um evento listado usando o ID.
            - Se um evento for deletado: Uma resposta formatada confirmando a exclusão, baseada na saída da ferramenta. Exemplo: '✅ Evento com ID 'seu_id_do_evento' deletado com sucesso.'
            - Se faltar informação: Uma pergunta clara ao usuário solicitando os dados necessários.
            """,
            # Ajustamos o expected_output para ser mais explícito
            expected_output="""Uma resposta formatada para a ação de calendário:
            - Confirmação de criação de evento com detalhes (Nome, Data, Início, Término, ID).
            - Lista de eventos encontrados OU mensagem de nenhum evento, seguida de uma pergunta sobre próxima ação.
            - Confirmação de exclusão de evento por ID.
            - Uma pergunta clara e específica ao usuário se faltar informação.""",
            agent=self.agents.calendar_manager_agent(),
            tools=[CreateCalendarEventTool(), ListCalendarEventsTool(), DeleteCalendarEventTool()]
        )

    def general_chat_task(self, user_message: str, history: str = ""): # Adicionado history
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history} # Injeta o histórico aqui

            A requisição do usuário não é sobre gerenciamento de calendário.
            Responda à pergunta do usuário de forma útil e amigável.
            Tente responder a perguntas gerais ou continuar uma conversa.
            Se não souber a resposta, peça desculpas e ofereça ajuda com outra coisa.

            Mensagem do usuário: "{user_message}"
            """,
            expected_output="Uma resposta útil e amigável à pergunta do usuário.",
            agent=self.agents.general_chatter_agent()
        )