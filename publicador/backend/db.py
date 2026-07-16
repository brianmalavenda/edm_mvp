import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import Base

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///publicador.db')
# Para arrancar rápido: SQLite alcanza de sobra para el volumen de un
# periódico semanal. Si más adelante escalás a publicación diaria con
# varios operadores concurrentes, migrás la misma DATABASE_URL a
# postgresql://usuario:pass@host/db sin tocar el resto del código.

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if 'sqlite' in DATABASE_URL else {})
SessionLocal = scoped_session(sessionmaker(bind=engine))


def init_db():
    Base.metadata.create_all(bind=engine)