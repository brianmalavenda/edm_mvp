from flask import Flask
from flask_cors import CORS
import os

def create_app():
    # load_dotenv()
    app = Flask(__name__)
    
    # Configuración
    ALLOWED_ORIGINS = ['http://localhost:3000', 'http://localhost']
    CORS(app, origins=ALLOWED_ORIGINS)
    
    app.config['WP_URL'] = os.getenv('WP_URL', 'https://tudominio.com')
    app.config['WP_USER'] = os.getenv('WP_USER', 'tu_usuario')
    app.config['WP_APP_PASSWORD'] = os.getenv('WP_APP_PASSWORD', 'xxxx xxxx xxxx xxxx')

    # Registrar blueprints de rutas
    from .routes import main_bp
    app.register_blueprint(main_bp)

    # Registrar blueprint de Telegram
    # from .services import telegram_bp
    # app.register_blueprint(telegram_bp)

    return app

# Para backwards compatibility (si alguien hace "from api_backend import app")
# app = create_app()
    