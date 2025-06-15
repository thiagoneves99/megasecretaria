# mega_secretaria/app/agents.py

from crewai import Agent
from app.tools.google_calendar_tools import (
    CreateCalendarEventTool,
    ListCalendarEventsTool,
    UpdateCalendarEventTool, # Importar a nova ferramenta
    DeleteCalendarEventTool, # Importar a nova ferramenta
    GetEventIdByDetailsTool # Importar a nova ferramenta
)
from app.config import settings

class MegaSecretariaAgents:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY # Assegure-se de que sua API Key está configurada.
        self.model_name = settings.OPENAI_MODEL_NAME # Assegure-se de que o modelo está configurado.

    def router_agent(self):
        return Agent(
            role='Roteador de Requisições',
            goal="Analise a mensagem do usuário e determine a intenção principal: 'gerenciamento de calendário' ou 'outra_requisição'.",
            backstory="Você é um assistente inteligente responsável por direcionar as requisições dos usuários para o agente especializado correto.",
            allow_delegation=False,
            verbose=True,
            llm=self._get_llm()
        )

    def calendar_manager_agent(self):
        return Agent(
            role='Gerente de Calendário',
            goal="Gerenciar eventos no Google Calendar (criar, listar, atualizar e deletar) com base nas solicitações do usuário.",
            backstory=(
                "Você é um especialista em gerenciamento de agenda, com acesso direto ao Google Calendar. "
                "Sua precisão é impecável, e você sempre confirma os detalhes antes de qualquer ação. "
                "Você é responsável por criar, listar, atualizar e deletar eventos, garantindo que o calendário do usuário esteja sempre organizado e preciso."
            ),
            # Adicione as novas ferramentas aqui!
            tools=[
                CreateCalendarEventTool(),
                ListCalendarEventsTool(),
                UpdateCalendarEventTool(),
                DeleteCalendarEventTool(),
                GetEventIdByDetailsTool()
            ],
            verbose=True,
            llm=self._get_llm(),
            allow_delegation=False
        )

    def _get_llm(self):
        # Aqui você pode configurar seu LLM, por exemplo, OpenAI, Anthropic, etc.
        # Certifique-se de que settings.OPENAI_API_BASE seja 'https://api.openai.com/v1' para OpenAI padrão.
        # Exemplo com OpenAI:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            openai_api_base=settings.OPENAI_API_BASE,
            openai_api_key=self.api_key,
            model_name=self.model_name,
            temperature=0.7
        )