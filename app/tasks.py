# mega_secretaria/app/tasks.py

from crewai import Task
from app.agents import MegaSecretaryAgents
from app.tools.google_calendar_tools import CreateCalendarEventTool, ListCalendarEventsTool, GetEventIdByDetailsTool, UpdateCalendarEventTool, DeleteCalendarEventTool # Garanta que todas as ferramentas estão importadas
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

    # NOVO: Adicionar chat_history como argumento para todas as tarefas
    def route_request_task(self, user_message: str, chat_history: str = ""):
        # NOVO: Adicionar o histórico ao prompt
        history_context = f"\n### Histórico da Conversa (para contexto):\n{chat_history}\n" if chat_history else ""
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history_context} # Injeta o histórico aqui

            Analise a seguinte mensagem do usuário e determine a intenção principal:
            "{user_message}"

            Se a mensagem for sobre criar, listar, consultar, *deletar* ou *gerenciar/alterar* eventos/compromissos/reuniões no calendário,
            a intenção é **'gerenciamento de calendário'**.
            Se a mensagem não se encaixar claramente em gerenciamento de calendário,
            a intenção é **'outra_requisição'**.

            Sua saída DEVE ser EXATAMENTE uma das duas strings fornecidas, sem espaços extras, capitalização diferente ou caracteres adicionais:
            'gerenciamento de calendário' ou 'outra_requisição'.
            """,
            expected_output="""
            Uma das strings: 'gerenciamento de calendário' ou 'outra_requisição'.
            """,
            agent=self.agents.request_router_agent()
        )

    # NOVO: Adicionar chat_history como argumento
    def manage_calendar_task(self, user_message: str, chat_history: str = ""):
        # NOVO: Adicionar o histórico ao prompt
        history_context = f"\n### Histórico da Conversa (para contexto):\n{chat_history}\n" if chat_history else ""
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history_context} # Injeta o histórico aqui

            Sua tarefa é gerenciar eventos no Google Calendar com base na mensagem do usuário.
            Mensagem do usuário: "{user_message}"

            REGRAS IMPORTANTES:
            1.  **Extração de Título:** Extraia o título do evento EXATAMENTE como o usuário informou. Se ele disser "...reunião com o nome patricia linda", o título é "patricia linda". NÃO use títulos genéricos como "Reunião".
            2.  **Duração Padrão:** Se o usuário especificar uma hora de início mas NÃO uma duração ou hora de término, você DEVE assumir uma duração padrão de 1 (UMA) hora.
            3.  **Listar Eventos em Dia Específico:** Se o usuário pedir a agenda de um dia específico (ex: "agenda de amanhã" ou "eventos do dia 16/06"), você DEVE usar a ferramenta `Listar Eventos do Google Calendar` fornecendo tanto `time_min` (o início do dia, 00:00:00) quanto `time_max` (o fim do dia, 23:59:59) para filtrar APENAS aquele dia. *Sempre inclua 'Z' para UTC no time_min e time_max ao listar.*
            4.  **Criação de Evento:** Para criar um evento, extraia todas as informações (título, data, hora de início, duração, etc.). Calcule a hora de término com base na duração (padrão de 1h se não especificada).
            5.  **Deletar Evento:** Se o usuário pedir para deletar um evento, *primeiro* use a ferramenta `GetEventIdByDetailsTool` para tentar obter o ID. Se o ID for explicitamente fornecido, use-o diretamente. Se múltiplos eventos corresponderem ou nenhum for encontrado, você DEVE listar os eventos encontrados (se houver) e **pedir ao usuário para ser mais específico**, fornecendo o título exato e/ou a data/hora, ou o ID do evento. *Depois* de obter um ID único e confirmado, use a ferramenta `DeleteCalendarEventTool`.
            6.  **Atualizar Evento:** Se o usuário pedir para alterar/atualizar um evento, *primeiro* use a ferramenta `GetEventIdByDetailsTool` se o ID não for explicitamente fornecido. Use o título e a data/hora para encontrar o ID. *Depois* de obter o ID, use a ferramenta `UpdateCalendarEventTool` com os novos detalhes fornecidos. Se vários eventos corresponderem, peça ao usuário para ser mais específico.
            7.  **Peça Informações:** Se faltarem informações CRÍTICAS para criar, deletar ou atualizar um evento (como o título, data/hora de início, ou o que exatamente precisa ser alterado), peça-as claramente ao usuário.

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
            - Se um evento for deletado/atualizado: Uma confirmação clara da ação com detalhes (ex: "✅ Evento 'Nome do Evento' deletado com sucesso!").
            - Se faltar informação ou houver ambiguidade: Uma pergunta clara ao usuário solicitando os dados necessários ou pedindo para ser mais específico.
            """,
            agent=self.agents.calendar_manager_agent(),
            tools=[CreateCalendarEventTool(), ListCalendarEventsTool(), GetEventIdByDetailsTool(), UpdateCalendarEventTool(), DeleteCalendarEventTool()]
        )

    # NOVO: Adicionar chat_history como argumento
    def general_chat_task(self, user_message: str, chat_history: str = ""):
        # NOVO: Adicionar o histórico ao prompt
        history_context = f"\n### Histórico da Conversa (para contexto):\n{chat_history}\n" if chat_history else ""
        return Task(
            description=f"""
            {self._get_current_time_context()}
            {history_context} # Injeta o histórico aqui

            A requisição do usuário não é sobre gerenciamento de calendário.
            Responda à pergunta do usuário de forma útil e amigável.
            Tente responder a perguntas gerais ou continuar uma conversa.
            Se não souber a resposta, peça desculpas e ofereça ajuda com outra coisa.

            Mensagem do usuário: "{user_message}"
            """,
            expected_output="Uma resposta útil e amigável à pergunta do usuário.",
            agent=self.agents.general_chatter_agent()
        )