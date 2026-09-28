# syntax=docker/dockerfile:1

# ---- base ---------------------------------------------------------------- #
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv/app

# ---- build ---------------------------------------------------------------- #
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

# ---- runtime -------------------------------------------------------------- #
FROM base AS runtime

# libpq5 for psycopg, curl for the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY --from=builder /install /usr/local
COPY --chown=appuser:appuser . /srv/app

USER appuser

ENV APP_ENV=production \
    SERVICE_NAME=users-service \
    GUNICORN_BIND=0.0.0.0:8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Init the schema, then serve. Safe to re-run: create_all is idempotent.
CMD ["sh", "-c", "flask --app app.wsgi:application init-db && exec gunicorn -c gunicorn.conf.py app.wsgi:application"]
