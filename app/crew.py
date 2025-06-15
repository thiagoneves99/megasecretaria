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
        # Agentes
        router_agent = self.agents.request_router_agent()
        calendar_agent = self.agents.calendar_manager_agent()

        # Tarefas
        route_task = self.tasks.route_request_task(self.user_message)
        manage_calendar_task = self.tasks.manage_calendar_task(self.user_message)
        handle_other_task = self.tasks.handle_other_request_task(self.user_message)

        # Crew
        crew = Crew(
            agents=[router_agent, calendar_agent],
            tasks=[route_task, manage_calendar_task, handle_other_task],
            process=Process.sequential, # Ou hierarchical, dependendo da complexidade futura
            verbose=True
        )

        # Inicia o processo da Crew
        # A lógica de roteamento será feita fora da Crew por enquanto,
        # baseada na saída da route_request_task.
        # No futuro, podemos usar um processo mais complexo dentro da Crew.
        
        # Para este primeiro MVP, vamos rodar a tarefa de roteamento e depois decidir.
        # A CrewAI não tem um mecanismo nativo de "if/else" para tarefas baseadas em output de outras tarefas
        # dentro de um único `crew.kickoff()` de forma trivial para o Process.sequential.
        # A abordagem mais simples para o roteamento inicial é fazer a decisão no `main.py`
        # após a execução de uma tarefa de roteamento ou de forma mais direta.

        # Para simplificar o uso do CrewAI aqui, vamos fazer o roteamento no main.py
        # e chamar a Crew com a tarefa específica.
        # A Crew será instanciada com a tarefa já definida.
        pass # A lógica de execução será no main.py

    def run_calendar_flow(self):
        crew = Crew(
            agents=[self.agents.calendar_manager_agent()],
            tasks=[self.tasks.manage_calendar_task(self.user_message)],
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        return result

    def run_other_flow(self):
        crew = Crew(
            agents=[self.agents.request_router_agent()], # O agente roteador pode responder a outras requisições
            tasks=[self.tasks.handle_other_request_task(self.user_message)],
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        return result

    def run_routing_flow(self):
        crew = Crew(
            agents=[self.agents.request_router_agent()],
            tasks=[self.tasks.route_request_task(self.user_message)],
            process=Process.sequential,
            verbose=True
        )
        result = crew.kickoff()
        return result

