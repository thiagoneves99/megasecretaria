# Mega Secretária - Projeto Inicial

Este projeto implementa a base para uma secretária virtual ("Mega Secretária") que interage via WhatsApp, utilizando a Evolution API, processamento de linguagem natural com GPT-4o-mini (OpenAI) e armazena conversas em um banco de dados PostgreSQL. A arquitetura é baseada em Docker e projetada para escalabilidade.

## Estrutura do Projeto

```
/mega_secretary
├── app/                     # Código principal da aplicação
│   ├── agents/              # Diretório para futuros agentes especializados (vazio inicialmente)
│   │   └── __init__.py
│   ├── utils/               # Módulos utilitários
│   │   ├── __init__.py
│   │   ├── ai_client.py     # Cliente para interagir com a API da OpenAI
│   │   ├── db_handler.py    # Funções para interagir com o banco de dados PostgreSQL
│   │   └── whatsapp_client.py # Cliente para interagir com a Evolution API
│   ├── __init__.py
│   ├── main.py              # Ponto de entrada da aplicação Flask (webhook)
│   └── receptionist.py      # Lógica do agente recepcionista inicial
├── config/                  # Arquivos de configuração
│   ├── .env                 # Arquivo para variáveis de ambiente (NÃO versionar)
│   └── settings.py          # Carrega e disponibiliza as variáveis do .env
├── data/                    # Diretório para dados persistentes (ex: volume do DB, se montado aqui)
├── tests/                   # Diretório para testes futuros
├── Dockerfile               # Define a imagem Docker para a aplicação Python
├── docker-compose.yml       # Orquestra os containers da aplicação e do banco de dados
├── requirements.txt         # Lista de dependências Python
├── README.md                # Este arquivo
└── todo.md                  # Checklist de desenvolvimento (concluído para esta fase)
```

## Funcionalidades Implementadas

1.  **Recepção de Mensagens:** Recebe mensagens do WhatsApp via webhook da Evolution API.
2.  **Restrição de Acesso:** Processa mensagens apenas do número de telefone configurado em `.env`.
3.  **Processamento com IA:** Utiliza o modelo GPT-4o-mini para entender a mensagem recebida e gerar uma resposta natural.
4.  **Envio de Respostas:** Envia a resposta gerada pela IA de volta ao usuário via Evolution API.
5.  **Persistência:** Salva todas as mensagens recebidas e enviadas (do número permitido) em um banco de dados PostgreSQL.
6.  **Arquitetura Dockerizada:** Aplicação e banco de dados rodam em containers Docker separados, orquestrados pelo `docker-compose.yml`.
7.  **Configuração Segura:** Chaves de API e outras informações sensíveis são gerenciadas através do arquivo `.env`.
8.  **Escalabilidade:** A estrutura modular facilita a adição de novos agentes e funcionalidades no futuro.

## Pré-requisitos

*   Docker e Docker Compose instalados.
*   Uma instância da Evolution API rodando e acessível (configurada no `.env`).
*   Uma chave de API da OpenAI (configurada no `.env`).
*   Acesso à VPS ou ambiente onde os containers serão executados.
*   Um subdomínio configurado para o webhook (ex: `webhook.neveshub.com.br`), apontando para o IP da sua VPS e porta exposta pelo Docker Compose (5001 neste exemplo).

## Configuração

1.  **Clonar/Copiar o Projeto:** Transfira os arquivos para sua VPS ou ambiente de execução.
2.  **Editar `.env`:** Preencha o arquivo `/home/ubuntu/mega_secretary/config/.env` com seus dados reais:
    *   `EVOLUTION_API_URL`: URL da sua instância Evolution API (ex: `https://evolutionapi.neveshub.com:8080`).
    *   `EVOLUTION_API_KEY`: Sua chave da Evolution API.
    *   `WEBHOOK_URL`: A URL pública que a Evolution API usará para enviar mensagens para sua aplicação (ex: `https://webhook.neveshub.com.br/webhook`). Este é o endereço que você configurará na Evolution API.
    *   `ALLOWED_PHONE_NUMBER`: O número de telefone (com código do país, sem o `+` inicial no valor, ex: `5521971189190`) autorizado a interagir.
    *   `OPENAI_API_KEY`: Sua chave da API da OpenAI.
    *   `DATABASE_URL`: String de conexão do PostgreSQL. O padrão no `docker-compose.yml` (`postgresql://user:password@db:5432/mega_secretary_db`) deve funcionar se você mantiver as credenciais no `docker-compose.yml`. **Importante:** `db` é o nome do serviço do banco de dados no `docker-compose.yml`, permitindo a comunicação interna entre os containers.
3.  **Configurar Webhook na Evolution API:** Acesse a configuração da sua instância na Evolution API e defina o Webhook Global para apontar para a `WEBHOOK_URL` que você definiu (ex: `https://webhook.neveshub.com.br/webhook`). Certifique-se de habilitar o evento `messages.upsert`.

## Execução com Docker Compose

No diretório raiz do projeto (`/home/ubuntu/mega_secretary`), execute os seguintes comandos:

1.  **Construir as imagens e iniciar os containers:**
    ```bash
    sudo docker-compose up --build -d
    ```
    *   `--build`: Reconstrói a imagem da aplicação se houver mudanças no `Dockerfile` ou código.
    *   `-d`: Executa os containers em segundo plano (detached mode).

2.  **Verificar os logs (opcional):**
    ```bash
    sudo docker-compose logs -f app # Logs da aplicação Python
    sudo docker-compose logs -f db  # Logs do PostgreSQL
    ```

3.  **Parar os containers:**
    ```bash
    sudo docker-compose down
    ```

## Próximos Passos e Escalabilidade

*   **Implementar Agentes:** Crie módulos Python dentro da pasta `app/agents/` para cada funcionalidade específica (agendamento, busca de informação, etc.).
*   **Roteamento Inteligente:** Modifique `app/receptionist.py` para usar a IA (ou lógica de regras) para identificar a intenção do usuário e chamar o agente apropriado no `AGENT_MAP`.
*   **Gerenciamento de Contexto:** Implemente a busca do histórico de conversas (`get_conversation_history` em `db_handler.py`) para fornecer contexto à IA.
*   **Tratamento de Erros:** Melhore o tratamento de erros e notificações (ex: avisar o usuário se um agente falhar).
*   **Limpeza de Mensagens:** Crie um script ou funcionalidade para limpar mensagens antigas do banco de dados, se necessário.
*   **Segurança:** Revise as configurações de segurança, especialmente se expor a porta do banco de dados ou outros serviços.
*   **Monitoramento:** Implemente ferramentas de monitoramento para acompanhar a saúde dos containers e da aplicação.
*   **Testes:** Adicione testes unitários e de integração na pasta `tests/`.

