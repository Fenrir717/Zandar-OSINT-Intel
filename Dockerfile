# syntax=docker/dockerfile:1
# Image aplikasi Zandar (API + SPA + Celery) — CPU baseline (lexicon/stub default).
# GPU (IndoBERT) tetap jalur dev .venv311; image ini untuk deploy portable.
# Build: docker compose -f docker-compose.yml -f docker-compose.deploy.yml up -d --build

# ================= Stage 1: build SPA (web/dist) =================
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build   # → /web/dist (tsc -b && vite build)

# ================= Stage 2: python runtime =================
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# curl utk healthcheck. Dependensi Python andalkan wheel manylinux (asyncpg/bcrypt/lxml).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 1) metadata + paket (layer terpisah → cache pip saat source berubah)
COPY pyproject.toml README.md ./
COPY core ./core
COPY api ./api
COPY workers ./workers
COPY graphs ./graphs
RUN pip install -e .

# 2) migrasi + skrip util
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

# 3) hasil build SPA dari stage web (disajikan FastAPI di /)
COPY --from=web /web/dist ./web/dist

# 4) entrypoint (api|worker|beat)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8010
ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]
