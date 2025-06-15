# mega_secretaria/app/database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# A URL do banco de dados vem das variáveis de ambiente
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Cria o motor do banco de dados
# O pool_pre_ping é útil para conexões de longa duração, verificando se a conexão está viva.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, pool_pre_ping=True
)

# Cria uma sessão local para cada requisição
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos declarativos
Base = declarative_base()

# Função de utilidade para obter uma sessão de banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

