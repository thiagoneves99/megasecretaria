# app/utils/db_handler.py

import psycopg2
import datetime
from config.settings import DATABASE_URL

# Verifica se a URL do banco de dados foi carregada
if not DATABASE_URL:
    print("ERRO CRÍTICO: DATABASE_URL não definida no arquivo .env! A persistência de dados não funcionará.")
    # Pode ser útil lançar um erro ou ter um fallback, dependendo da criticidade

def get_db_connection():
    """Estabelece uma conexão com o banco de dados PostgreSQL."""
    if not DATABASE_URL:
        print("Erro: DATABASE_URL não configurada.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        print("Verifique se o container do PostgreSQL está rodando e acessível, e se as credenciais estão corretas.")
        return None
    except Exception as e:
        print(f"Erro inesperado ao conectar ao banco de dados: {e}")
        return None

def initialize_database():
    """Cria a tabela de conversas se ela não existir."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                sender_number VARCHAR(30) NOT NULL,
                message_text TEXT NOT NULL,
                direction VARCHAR(10) NOT NULL, -- 'incoming' or 'outgoing'
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
            print("Banco de dados inicializado com sucesso (tabela 'conversations' verificada/criada).")
    except Exception as e:
        print(f"Erro ao inicializar o banco de dados: {e}")
        conn.rollback() # Desfaz alterações em caso de erro
    finally:
        if conn:
            conn.close()

def save_message(sender_number: str, message_text: str, direction: str):
    """Salva uma mensagem no banco de dados."""
    # Validação simples da direção
    if direction not in ["incoming", "outgoing"]:
        print(f"Erro: Direção inválida para salvar mensagem: {direction}")
        return

    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO conversations (sender_number, message_text, direction, timestamp)
            VALUES (%s, %s, %s, %s)
            """, (sender_number, message_text, direction, datetime.datetime.now(datetime.timezone.utc)))
            conn.commit()
            print(f"Mensagem {direction} de/para {sender_number} salva no banco de dados.")
    except Exception as e:
        print(f"Erro ao salvar mensagem no banco de dados: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

# Exemplo de como buscar mensagens (pode ser adicionado futuramente)
# def get_conversation_history(sender_number: str, limit: int = 10):
#     """Busca o histórico recente de conversas para um número."""
#     conn = get_db_connection()
#     if not conn:
#         return []
#     try:
#         with conn.cursor() as cur:
#             cur.execute("""
#             SELECT sender_number, message_text, direction, timestamp
#             FROM conversations
#             WHERE sender_number = %s
#             ORDER BY timestamp DESC
#             LIMIT %s
#             """, (sender_number, limit))
#             # Retorna em ordem cronológica (mais antiga primeiro)
#             history = cur.fetchall()[::-1]
#             return history
#     except Exception as e:
#         print(f"Erro ao buscar histórico de conversas: {e}")
#         return []
#     finally:
#         if conn:
#             conn.close()

# Chamada inicial para garantir que a tabela exista ao iniciar a aplicação
# Isso pode ser movido para um ponto de inicialização mais centralizado em main.py
# if __name__ != "__main__": # Evita rodar ao importar, mas roda quando o módulo é carregado
#    initialize_database()

