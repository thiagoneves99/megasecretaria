# mega_secretaria/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings ):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    EVOLUTION_API_URL: str
    EVOLUTION_API_KEY: str
    WEBHOOK_URL: str
    ALLOWED_PHONE_NUMBER: str
    OPENAI_API_KEY: str
    DATABASE_URL: str
    GOOGLE_TOKEN_PATH: str = "/var/lib/megasecretaria/token.pickle"
    EVOLUTION_API_INSTANCE_NAME: str

    # Configurações do modelo LLM
    LLM_MODEL: str = "gpt-4o-mini"
    TEMPERATURE: float = 0.7
    # Removido: MAX_TOKENS
    HISTORY_MAX_CHARS: int = 1200 # NOVO: Limite de caracteres para o histórico da conversa (aprox. 300 tokens)

settings = Settings()

# Garante que o diretório do token do Google exista
# Isso é importante para o ambiente de execução onde o token.pickle será salvo
# ou lido. No EasyPanel, você pode precisar garantir que o volume esteja montado corretamente.
if not os.path.exists(os.path.dirname(settings.GOOGLE_TOKEN_PATH)):
    os.makedirs(os.path.dirname(settings.GOOGLE_TOKEN_PATH), exist_ok=True)