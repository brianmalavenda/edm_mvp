# Publicador EDM — Backend

API que parsea archivos `.docx` del periódico EDM (estilos `@1VOLA`,
`@2TITULO`, `@3COPETE`, `@4NOTA`) y publica cada nota detectada en WordPress
vía REST API, persistiendo el estado de cada documento/nota en base de datos
para que un frontend pueda hacer seguimiento del proceso.

## Estructura del proyecto

```
publicador/
├── pyproject.toml
├── Dockerfile
├── .dockerignore
├── backend/                # paquete Python real
│   ├── __init__.py         # create_app() (factory de Flask)
│   ├── __main__.py         # entrypoint (python -m backend)
│   ├── routes.py           # blueprint con los endpoints /api/*
│   ├── models.py           # modelos SQLAlchemy (Document, Note, TermCache)
│   ├── db.py                # engine + sesión
│   ├── tasks.py              # jobs async (RQ) que parsean y publican
│   ├── word_to_wp.py        # parser de .docx + cliente REST de WordPress
│   └── run_local.py         # script CLI para probar sin levantar el server
└── test/
    └── docs/                # .docx de prueba
```

## Variables de entorno

| Variable          | Descripción                                              | Ejemplo                                  |
|-------------------|-----------------------------------------------------------|-------------------------------------------|
| `WP_URL`          | URL base del WordPress destino                            | `https://ejes.sanmartinici.com.ar`        |
| `WP_USER`         | Usuario de WordPress con permisos de publicación           | `edm_publicador`                          |
| `WP_APP_PASSWORD` | Application Password generada en WordPress                | `xxxx xxxx xxxx xxxx xxxx xxxx`           |
| `DATABASE_URL`    | Cadena de conexión SQLAlchemy                              | `sqlite:///publicador.db` o `postgresql://user:pass@db:5432/publicador` |
| `REDIS_URL`       | Redis usado por la cola RQ (podés reusar el de tu WP)      | `redis://redis:6379/1`                    |
| `UPLOAD_DIR`      | Carpeta donde se guardan los .docx subidos                 | `/data/uploads`                           |
| `ALLOWED_ORIGINS` | Orígenes permitidos por CORS, separados por coma           | `http://localhost:3000,https://panel.sanmartinici.com.ar` |
| `PORT`            | Puerto donde escucha el server (Docker)                   | `5000`                                    |

Creá un `.env` en `publicador/` para desarrollo local (nunca lo commitees):

```env
WP_URL=https://ejes.sanmartinici.com.ar
WP_USER=edm_publicador
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
DATABASE_URL=sqlite:///publicador.db
REDIS_URL=redis://localhost:6379/1
UPLOAD_DIR=./uploads
ALLOWED_ORIGINS=http://localhost:3000
```

---

## Modo desarrollo local (sin Docker)

Pensado para iterar rápido sobre el parser y los endpoints.

**1. Entorno virtual e instalación**

```bash
cd publicador
python3 -m venv .venv
source .venv/bin/activate
# crear el paquete para poder correr un script. Hay rutas relativas que requieren este paso previo
pip install -e ".[dev]"
```

**2. Base de datos**

Con `DATABASE_URL=sqlite:///publicador.db` no hace falta nada más: las
tablas se crean solas al iniciar la app (`init_db()` en `db.py`).

**3. Redis para la cola de jobs**

Si no querés instalar Redis local, usá el que ya tenés corriendo en tu
homelab (`docker exec -it wordpress_redis redis-cli ping` para confirmar que
responde) y apuntá `REDIS_URL` a esa IP/puerto. También podés levantar uno
descartable:

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

**4. Levantar el servidor Flask (modo dev, con recarga automática)**

```bash
export FLASK_APP=backend
export FLASK_ENV=development
flask run --host 0.0.0.0 --port 5000
```

**5. Levantar el worker en otra terminal**

```bash
source .venv/bin/activate
rq worker publicador -u redis://localhost:6379/1
```

**6. Probar sin levantar nada de lo anterior (parser puro)**

Para iterar sobre el parseo de estilos del Word sin publicar nada:

```bash
python backend/run_local.py preview test/docs/prueba_01.docx
python backend/run_local.py publicar test/docs/prueba_01.docx
```

**7. Tests**

```bash
pytest
```

---

## Modo sandbox / prueba con Docker

Pensado para validar que la imagen final se comporta igual que en
producción, antes de integrarla al stack completo con el frontend.

**1. Build de la imagen**

```bash
cd publicador
docker build -t edm-publicador-backend .
```

**2. Correrla standalone (SQLite, sin worker) — la forma más rápida de probar**

```bash
docker run --rm -p 5000:5000 \
  -e WP_URL=https://ejes.sanmartinici.com.ar \
  -e WP_USER=edm_publicador \
  -e WP_APP_PASSWORD="xxxx xxxx xxxx xxxx xxxx xxxx" \
  -e DATABASE_URL=sqlite:////data/publicador.db \
  -v edm_uploads:/data/uploads \
  --name publicador-sandbox \
  edm-publicador-backend
```

Probá que responde:

```bash
curl http://localhost:5000/api/health
```

> Nota: para que este `curl` y el `HEALTHCHECK` del Dockerfile funcionen,
> `routes.py` necesita una ruta `GET /api/health` que devuelva `200 OK`. Si
> todavía no la agregaste, es una línea:
> ```python
> @main_bp.get('/health')
> def health():
>     return jsonify({'status': 'ok'}), 200
> ```

**3. Sandbox completo (web + worker + Redis + Postgres), integrado a tu red existente**

Este es el `docker-compose.yml` de referencia para sumar el servicio a tu
stack actual (ajustá nombres de red/volúmenes a los que ya usás en tu
Proxmox):

```yaml
services:
  publicador-web:
    build:
      context: ./publicador
      dockerfile: Dockerfile
    image: edm-publicador-backend
    restart: unless-stopped
    env_file: ./publicador/.env
    environment:
      - DATABASE_URL=postgresql://publicador:${DB_PASSWORD}@publicador-db:5432/publicador
      - REDIS_URL=redis://wordpress_redis:6379/1   # reusa tu Redis existente
    ports:
      - "5000:5000"
    volumes:
      - publicador_uploads:/data/uploads
    depends_on:
      - publicador-db
    networks:
      - dmz_network        # misma red donde ya vive tu WordPress/NPM

  publicador-worker:
    image: edm-publicador-backend     # misma imagen, distinto comando
    restart: unless-stopped
    env_file: ./publicador/.env
    environment:
      - DATABASE_URL=postgresql://publicador:${DB_PASSWORD}@publicador-db:5432/publicador
      - REDIS_URL=redis://wordpress_redis:6379/1
    command: rq worker publicador -u redis://wordpress_redis:6379/1
    volumes:
      - publicador_uploads:/data/uploads
    depends_on:
      - publicador-db
    networks:
      - dmz_network

  publicador-db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_DB=publicador
      - POSTGRES_USER=publicador
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - publicador_db_data:/var/lib/postgresql/data
    networks:
      - dmz_network

volumes:
  publicador_uploads:
  publicador_db_data:

networks:
  dmz_network:
    external: true
```

Levantalo con:

```bash
docker compose up -d --build publicador-web publicador-worker publicador-db
docker compose logs -f publicador-web publicador-worker
```

**4. Exponer al frontend vía NGINX Proxy Manager**

Igual que con tus otros servicios: creá un Proxy Host apuntando a
`publicador-web:5000`, y sumá `https://tu-panel-frontend.dominio.ar` a
`ALLOWED_ORIGINS` para que el CORS de Flask lo acepte.

> ⚠️ Recordatorio del bloqueo que ya identificaste: si NPM te está
> despojando el header `Authorization` en el camino hacia WordPress (no
> hacia este backend, sino en la llamada que `word_to_wp.py` hace a
> `WP_URL`), vas a necesitar el snippet de configuración avanzada en el
> Proxy Host de WordPress para reenviar `Authorization` (`proxy_set_header
> Authorization $http_authorization;`), no en el de este backend.

---

## Troubleshooting rápido

| Síntoma | Causa probable |
|---|---|
| `docker build` falla instalando el paquete | `pyproject.toml` mal ubicado o `packages` apuntando a un nombre que no coincide con la carpeta `backend/` |
| El worker no toma jobs | `REDIS_URL` distinto entre `publicador-web` y `publicador-worker`, o el nombre de la cola no coincide (`publicador` en ambos lados) |
| `/api/upload` devuelve 409 siempre | El hash del archivo ya existe en `documents.file_hash` — es el chequeo de idempotencia funcionando, no un bug |
| Healthcheck en `docker ps` queda `unhealthy` | Falta la ruta `/api/health` en `routes.py`, o el contenedor todavía no terminó de levantar la DB |