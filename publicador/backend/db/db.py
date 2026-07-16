import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import Base
from flask import Flask

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///publicador.db')
# Para escalar migrar la misma DATABASE_URL a postgresql://usuario:pass@host/db sin tocar el resto del código.

engine = create_engine(DATABASE_URL, 
            connect_args={'check_same_thread': False} if 'sqlite' in DATABASE_URL else {},
            pool_size=5,          # máximo 5 conexiones simultáneas en el pool
            pool_pre_ping=True,   # testea la conexión antes de entregarla; descarta las muertas
            pool_recycle=1800,    # recicla conexiones de más de 30min (evita que el DB server las mate primero)
            pool_timeout=10,      # cuánto espera un thread por una conexión libre del pool antes de tirar error
            echo=False,            # True para debug SQL
            future=False          # usa la nueva API de SQLAlchemy 2.0
        )

SessionLocal = scoped_session(sessionmaker(bind=engine))


def init_db():
    Base.metadata.create_all(bind=engine)


def init_app(app: Flask):
    """ En Flask, cada request se procesa (por default con el servidor de desarrollo o con gunicorn sync workers) en threads que se reciclan y reutilizan entre requests. 
        El SessionLocal lo que hace es crear una sesión de base de datos por cada request. Olvidarse de cerrar una session implicaría un apilamiento de sesiones en threas locales, y eventualmente un memory leak. 
        Cada thread de conexion queda asociado a un pool de conexiones, y si no se cierra la session, el thread queda con una conexion abierta que nunca se libera.
        
        Esto podría convertirse en un problema de concurrencia si varios requests intentan usar la misma session, o si se agotan las conexiones del pool.
        Podría ser utilizado como un ataque de hacking para agotar recursos o robar identidad de threads que contienen sesiones de request anteriores si logran forzas concurrencia.
        Por eso usamos scoped_session, que crea una sesión por request y la cierra automáticamente al final del request.        
    """
    @app.teardown_appcontext
    def remove_session(exception=None):
        SessionLocal.remove()