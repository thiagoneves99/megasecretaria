# mega_secretaria/app/tasks.py

from crewai import Task
from app.agents import MegaSecretaryAgents
from app.tools.google_calendar_tools import (
    CreateCalendarEventTool,
    ListCalendarEventsTool,
    UpdateCalendarEventTool,  # Nova importação
    DeleteCalendarEventTool,  # Nova importação
    GetEventIdByDetailsTool   # Nova importação
)

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

    def route_request_task(self, user_message: str):
        return Task(
            description=f"""
            {self._get_current_time_context()}

            Analise a seguinte mensagem do usuário e determine a intenção principal:
            "{user_message}"

            Se a mensagem for sobre criar, listar, consultar, *deletar* ou *gerenciar/alterar* eventos/compromissos/reuniões no calendário,
            a intenção é **'gerenciamento de calendário'**.
            Se a mensagem não se encaixar claramente em gerenciamento de calendário,
            a intenção é **'outra_requisição'**.

            Sua saída DEVE ser EXATAMENTE uma das duas strings fornecidas, sem espaços extras, capitalização diferente ou caracteres adicionais:
            'gerenciamento de calendário' ou 'outra_requisição'.
            """,
            expected_output="Uma string EXATA indicando a intenção ('gerenciamento de calendário' ou 'outra_requisição').",
            agent=self.agents.request_router_agent(),
            output_file='request_intent.txt'
        )

    def manage_calendar_task(self, user_message: str):
        return Task(
            description=f"""
            {self._get_current_time_context()}

            Sua tarefa é gerenciar eventos no Google Calendar com base na mensagem do usuário.
            Mensagem do usuário: "{user_message}"

            REGRAS IMPORTANTES:
            1.  **Extração de Título:** Extraia o título do evento EXATAMENTE como o usuário informou. Se ele disser "...reunião com o nome patricia linda", o título é "patricia linda". NÃO use títulos genéricos como "Reunião".
            2.  **Duração Padrão:** Se o usuário especificar uma hora de início mas NÃO uma duração ou hora de término, você DEVE assumir uma duração padrão de 1 (UMA) hora.
            3.  **Listar Eventos em Dia Específico:** Se o usuário pedir a agenda de um dia específico (ex: "agenda de amanhã" ou "eventos do dia 16/06"), você DEVE usar a ferramenta `Listar Eventos do Google Calendar` fornecendo tanto `time_min` (o início do dia, 00:00:00) quanto `time_max` (o fim do dia, 23:59:59) para filtrar APENAS aquele dia. *Sempre inclua 'Z' para UTC no time_min e time_max ao listar.*
            4.  **Criação de Evento:** Para criar um evento, extraia todas as informações (título, data, hora de início, duração, etc.). Calcule a hora de término com base na duração (padrão de 1h se não especificada).
            5.  **Deletar Evento:** Se o usuário pedir para deletar um evento, *primeiro* use a ferramenta `Obter ID de Evento por Detalhes` se o ID não for explicitamente fornecido. Use o título e a data/hora para encontrar o ID. *Depois* de obter o ID, use a ferramenta `Deletar Evento no Google Calendar`. Se vários eventos corresponderem, peça ao usuário para ser mais específico.
            6.  **Atualizar Evento:** Se o usuário pedir para alterar/atualizar um evento, *primeiro* use a ferramenta `Obter ID de Evento por Detalhes` se o ID não for explicitamente fornecido. Use o título e a data/hora para encontrar o ID. *Depois* de obter o ID, use a ferramenta `Atualizar Evento no Google Calendar` com os novos detalhes fornecidos. Se vários eventos corresponderem, peça ao usuário para ser mais específico.
            7.  **Peça Informações:** Se faltarem informações CRÍTICAS para criar, deletar ou atualizar um evento (como o título, data/hora de início, ou o que exatamente precisa ser alterado), peça-as claramente ao usuário.

            Utilize as ferramentas de Google Calendar para executar a ação. Sempre retorne a confirmação da ação realizada ao usuário.
            """,
            expected_output="""
            - Se um evento for criado: Uma resposta formatada confirmando a criação, baseada na saída da ferramenta. Exemplo:
              '✅ Evento Criado com Sucesso!

              *Nome:* Nome do Evento
              *Data:* DD/MM/YYYY
              *Início:* HH:MM
              *Término:* HH:MM'
            - Se eventos forem listados: A lista de eventos fornecida pela ferramenta.
            - Se um evento for atualizado: Uma resposta formatada confirmando a atualização, baseada na saída da ferramenta.
            - Se um evento for deletado: Uma resposta confirmando a exclusão do evento.
            - Se faltar informação: Uma pergunta clara ao usuário solicitando os dados necessários.
            """,
            agent=self.agents.calendar_manager_agent(),
            tools=[
                CreateCalendarEventTool(),
                ListCalendarEventsTool(),
                UpdateCalendarEventTool(),  # Adicionada
                DeleteCalendarEventTool(),  # Adicionada
                GetEventIdByDetailsTool()   # Adicionada
            ]
        )

    def general_chat_task(self, user_message: str):
        return Task(
            description=f"""
            {self._get_current_time_context()}

            A requisição do usuário não é sobre gerenciamento de calendário.
            Responda à pergunta do usuário de forma útil e amigável.
            Tente responder a perguntas gerais ou continuar uma conversa.
            Se não souber a resposta, peça desculpas e ofereça ajuda com outra coisa.

            Mensagem do usuário: "{user_message}"
            """,
            expected_output="Uma resposta útil e amigável à pergunta do usuário.",
            agent=self.agents.general_chatter_agent()
        )