# ==========================================================================
# Dockerfile - Backend "publicador" (EDM: Word -> WordPress)
#
# Build context esperado: la carpeta `publicador/` (contiene pyproject.toml,
# backend/ y test/). Ejemplo de build:
#
#   docker build -t edm-publicador-backend -f publicador/Dockerfile publicador/
#
# Esta misma imagen sirve para DOS roles, según el CMD/entrypoint que se
# le pase en docker-compose:
#   - "web"    -> gunicorn sirviendo la API Flask (CMD por defecto de abajo)
#   - "worker" -> proceso RQ que consume la cola de Redis y publica en WP
# ==========================================================================

# ---------- Etapa de build ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# build-essential solo por si alguna dependencia transitiva necesita compilar
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend ./backend

RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /build/wheels .

# ---------- Etapa final ----------
FROM python:3.11-slim

LABEL org.opencontainers.image.title="edm-publicador-backend" \
      org.opencontainers.image.description="API de publicación de notas EDM (Word -> WordPress)" \
      org.opencontainers.image.authors="Brian Malavenda"

# Usuario no-root
RUN groupadd -r publicador && useradd -r -g publicador -d /app publicador

WORKDIR /app

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

# Carpeta de uploads persistente (montar como volumen en docker-compose)
RUN mkdir -p /data/uploads && chown -R publicador:publicador /data/uploads /app

ENV PYTHONUNBUFFERED=1 \
    UPLOAD_DIR=/data/uploads \
    FLASK_ENV=production \
    PORT=5000

USER publicador

EXPOSE 5000

# Requiere una ruta GET /api/health en routes.py que devuelva 200 OK.
# Si todavía no la agregaste, hacelo antes de depender de este healthcheck.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0) if urllib.request.urlopen('http://localhost:8990/api/health').status==200 else sys.exit(1)" \
        || exit 1

# CMD por defecto: rol "web". El rol "worker" se define pisando el comando
# en docker-compose.yml con: rq worker publicador -u redis://redis:6379/1
CMD ["gunicorn", "--bind", "0.0.0.0:8990", "--workers", "2", "--timeout", "120", "backend:create_app()"]