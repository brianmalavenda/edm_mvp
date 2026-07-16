from flask import Flask
from flask_cors import CORS
import os

def create_app():
    # load_dotenv()
    app = Flask(__name__)
    
    # Configuración
    ALLOWED_ORIGINS = ['http://localhost:5000', 'http://localhost']
    CORS(app, origins=ALLOWED_ORIGINS)
    
    app.config['WP_URL'] = os.getenv('WP_URL', 'https://tudominio.com')
    app.config['WP_USER'] = os.getenv('WP_USER', 'tu_usuario')
    app.config['WP_APP_PASSWORD'] = os.getenv('WP_APP_PASSWORD', 'xxxx xxxx xxxx xxxx')

    # Inicializacion de la base de datos y creación de sesiones por request. Cada sesion se cierra automáticamente al final del request.
    from .db import init_db, init_app
    init_db()
    init_app(app)

    # Registrar blueprints de rutas.
    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app
    