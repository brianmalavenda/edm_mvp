from . import create_app

# Crear la app a nivel de módulo para que Gunicorn la encuentre
app = create_app()

def main():
    app.run(host='0.0.0.0', port=8990)

if __name__ == '__main__':
    main()
