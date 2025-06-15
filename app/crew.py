# mega_secretaria/app/crew.py

from crewai import Crew, Process
from app.agents import MegaSecretaryAgents
from app.tasks import MegaSecretaryTasks

class MegaSecretaryCrew:
    def __init__(self, user_message: str):
        self.user_message = user_message
        self.agents = MegaSecretaryAgents()
        self.tasks = MegaSecretaryTasks()

    def run(self):
        # Este método `run` completo da Crew não está sendo usado diretamente no main.py,
        # onde as flows específicas (routing, calendar, other) são chamadas.
        # Mantido para referência se a arquitetura da Crew mudar para uma mais unificada.
        pass

    def run_calendar_flow(self, history: str = ""): # Adicionar history como parâmetro opcional
        crew = Crew(
            agents=[self.agents.calendar_manager_agent()],
            tasks=[self.tasks.manage_calendar_task(self.user_message, history=history)], # Passar history
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        return result

    def run_other_flow(self, history: str = ""): # Adicionar history como parâmetro opcional
        # ATUALIZADO: Usar o novo agente e tarefa para chat geral
        crew = Crew(
            agents=[self.agents.general_chatter_agent()],
            tasks=[self.tasks.general_chat_task(self.user_message, history=history)], # Passar history
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        return result

    def run_routing_flow(self, history: str = ""): # Adicionar history como parâmetro opcional
        crew = Crew(
            agents=[self.agents.request_router_agent()],
            tasks=[self.tasks.route_request_task(self.user_message, history=history)], # Passar history
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        return result