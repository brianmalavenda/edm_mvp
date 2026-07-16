from flask import Flask
from . import create_app
from .word_to_wp import WordToWordPress.

# Crear la app a nivel de módulo para que Gunicorn la encuentre
app = create_app()

def main():
    app.run(host='0.0.0.0', port=8990)  # Cambiar localhost a 0.0.0.0
    # Inicializar
    wp = WordToWordPress(WP_URL, WP_USER, WP_APP_PASSWORD)

if __name__ == '__main__':
    main()
