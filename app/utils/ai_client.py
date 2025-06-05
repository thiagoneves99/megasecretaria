# app/utils/ai_client.py

import openai
from config.settings import OPENAI_API_KEY, AI_MODEL_NAME

# Configure the OpenAI client
if not OPENAI_API_KEY:
    print("AVISO: OPENAI_API_KEY não definida no arquivo .env. A funcionalidade de IA não funcionará.")
    # Poderia lançar um erro ou desabilitar a funcionalidade
    client = None
else:
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Erro ao inicializar o cliente OpenAI: {e}")
        client = None

def get_ai_response(messages: list[dict]) -> str | None:
    """Obtém uma resposta do modelo de IA configurado."""
    if not client:
        print("Erro: Cliente OpenAI não inicializado.")
        return "Desculpe, estou com problemas para acessar minha inteligência artificial no momento."

    try:
        completion = client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=messages
        )
        # Acessa o conteúdo da mensagem da resposta
        if completion.choices and completion.choices[0].message:
            response_content = completion.choices[0].message.content
            return response_content.strip() if response_content else None
        else:
            print("Resposta inesperada da API OpenAI:", completion)
            return "Não consegui processar sua solicitação neste momento."

    except openai.APIError as e:
        # Handle API error here, e.g. retry or log
        print(f"Erro na API OpenAI: {e}")
        return f"Ocorreu um erro ao comunicar com a IA: {e}"
    except openai.AuthenticationError as e:
        print(f"Erro de autenticação OpenAI: {e}")
        return "Erro de autenticação com o serviço de IA. Verifique a chave da API."
    except openai.RateLimitError as e:
        print(f"Erro de limite de taxa OpenAI: {e}")
        return "O serviço de IA está sobrecarregado no momento. Tente novamente mais tarde."
    except Exception as e:
        print(f"Erro inesperado ao chamar a API OpenAI: {e}")
        return "Ocorreu um erro inesperado ao processar sua solicitação com a IA."

# Exemplo de uso (pode ser removido ou comentado)
# if __name__ == '__main__':
#     test_prompt = "Olá, como você está hoje?"
#     response = get_ai_response(test_prompt)
#     print(f"Prompt: {test_prompt}")
#     print(f"Resposta da IA: {response}")

