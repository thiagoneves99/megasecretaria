# mega_secretaria/app/agents.py

from crewai import Agent
from langchain_openai import ChatOpenAI
from app.config import settings
# CORREÇÃO: Usar ListCalendarEventsTool (plural) em vez de ListCalendarEventTool
from app.tools.google_calendar_tools import CreateCalendarEventTool, ListCalendarEventsTool 

class MegaSecretaryAgents:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY
        )

    def calendar_manager_agent(self):
        return Agent(
            role='Gerente de Calendário',
            goal='Gerenciar e organizar eventos no Google Calendar, criando, listando e atualizando compromissos, mantendo o contexto da conversa com base no histórico fornecido.',
            backstory="""Você é um assistente especializado em organização de agenda. Sua principal responsabilidade é interagir com o Google Calendar para garantir que todos os compromissos sejam registrados e acessíveis. Você é preciso, eficiente e sempre busca a melhor forma de organizar o tempo do usuário. Você utiliza o histórico de conversa para entender melhor as preferências e informações já fornecidas pelo usuário.""",
            verbose=True,
            allow_delegation=False, # Este agente executa as ações diretamente
            llm=self.llm,
            # CORREÇÃO: Usar ListCalendarEventsTool (plural) na lista de ferramentas
            tools=[CreateCalendarEventTool(), ListCalendarEventsTool()] 
        )

    def request_router_agent(self):
        return Agent(
            role='Roteador de Requisições',
            goal='Analisar a requisição do usuário e determinar qual agente é o mais adequado para lidar com ela, levando em consideração o histórico da conversa para contextualização.',
            backstory="""Você é a primeira linha de defesa da MegaSecretaria. Sua função é entender a intenção do usuário a partir da mensagem do WhatsApp e encaminhá-la para o agente especializado correto. Você deve ser capaz de identificar se a requisição é sobre calendário, tarefas, lembretes, etc., e delegar a tarefa apropriada. Sua análise é aprimorada pelo contexto fornecido pelo histórico de mensagens anteriores.""",
            verbose=True,
            allow_delegation=True, # Este agente pode delegar para outros (mas aqui só roteia)
            llm=self.llm
        )
    
    def general_chatter_agent(self):
        return Agent(
            role='Assistente de Chat Geral',
            goal='Responder a perguntas gerais e manter uma conversa amigável e informativa, utilizando o histórico para manter a coerência e lembrar de informações cruciais, como o nome do usuário.',
            backstory="""Você é um assistente de IA prestativo e amigável, pronto para responder a uma ampla gama de perguntas e conversar sobre diversos tópicos. Você se esforça para fornecer informações precisas e ser um bom interlocutor, mesmo quando a solicitação não se encaixa nas funcionalidades específicas do sistema. Você tem a capacidade de recordar e utilizar informações de conversas anteriores para oferecer uma experiência mais personalizada e contínua.""",
            verbose=True,
            allow_delegation=False, # Este agente responde diretamente
            llm=self.llm
        )