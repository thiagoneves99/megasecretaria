# mega_secretaria/app/agents.py

from crewai import Agent
from langchain_openai import ChatOpenAI
from app.config import settings
from app.tools.google_calendar_tools import CreateCalendarEventTool, ListCalendarEventsTool, DeleteCalendarEventTool

class MegaSecretaryAgents:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY,
            # Removido: max_tokens=settings.MAX_TOKENS
        )

    def calendar_manager_agent(self):
        return Agent(
            role='Gerente de Calendário',
            goal='Gerenciar e organizar eventos no Google Calendar, criando, listando e atualizando compromissos.',
            backstory="""Você é um assistente especializado em organização de agenda. Sua principal responsabilidade é interagir com o Google Calendar para garantir que todos os compromissos sejam registrados e acessíveis. Você é preciso, eficiente e sempre busca a melhor forma de organizar o tempo do usuário.

            Ao listar eventos, você DEVE retornar EXATAMENTE a saída fornecida pela ferramenta 'List Calendar Events'. Se a ferramenta indicar que não há eventos, você deve usar essa mensagem. Após a saída da ferramenta de listagem de eventos (seja a lista ou a mensagem de que não há eventos), você DEVE adicionar a seguinte frase amigável: 'Se precisar de mais alguma coisa ou se deseja deletar um evento listado usando o ID, é só me avisar!'

            Para outros tipos de interações (criar, deletar), você deve retornar a confirmação em português, de forma clara e amigável, baseando-se na saída da ferramenta correspondente.""",
            verbose=True,
            allow_delegation=False, # Este agente executa as ações diretamente
            llm=self.llm,
            tools=[CreateCalendarEventTool(), ListCalendarEventsTool(), DeleteCalendarEventTool()]
        )

    def request_router_agent(self):
        return Agent(
            role='Roteador de Requisições',
            goal='Analisar a requisição do usuário e determinar qual agente é o mais adequado para lidar com ela.',
            backstory="""Você é a primeira linha de defesa da MegaSecretaria. Sua função é entender a intenção do usuário a partir da mensagem do WhatsApp e encaminhá-la para o agente especializado correto. Você deve ser capaz de identificar se a requisição é sobre calendário, tarefas, lembretes, etc., e delegar a tarefa apropriada.""",
            verbose=True,
            allow_delegation=True, # Este agente pode delegar para outros (mas aqui só roteia)
            llm=self.llm
        )

    def general_chatter_agent(self):
        return Agent(
            role='Assistente de Chat Geral',\
            goal='Responder a perguntas gerais e manter uma conversa amigável e informativa.',
            backstory="""Você é um assistente de IA prestativo e amigável, pronto para responder a uma ampla gama de perguntas e conversar sobre diversos tópicos. Você se esforça para fornecer informações precisas e ser um bom interlocutor, mesmo quando a solicitação não se encaixa nas funcionalidades específicas do sistema.""",
            verbose=True,
            allow_delegation=False, # Este agente responde diretamente
            llm=self.llm
        )