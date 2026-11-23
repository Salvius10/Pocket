# Build context is the repo root:  docker build -f services/core_api/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir uv==0.11.24
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/pocket_common packages/pocket_common
COPY packages/pocket_synth/pyproject.toml packages/pocket_synth/pyproject.toml
COPY services/agent/pyproject.toml services/agent/pyproject.toml
COPY services/core_api services/core_api
RUN mkdir -p packages/pocket_synth/pocket_synth services/agent/agent \
 && touch packages/pocket_synth/pocket_synth/__init__.py services/agent/agent/__init__.py \
 && uv sync --frozen --no-dev --package core-api

# Only what the app reads at runtime: reference tables, the six demo personas (their set-up in db/,
# their account statements and bank SMS in sources/, which the loader parses), layout content.
COPY data/reference data/reference
COPY data/demo/db data/demo/db
COPY data/demo/sources data/demo/sources
COPY data/content data/content

ENV PATH="/app/.venv/bin:$PATH" ENV=demo PORT=8080
EXPOSE 8080
# Postgres: apply migrations first. No DATABASE_URL: SQLite inside the container, schema created on start.
CMD ["sh", "-c", "if [ -n \"$DATABASE_URL\" ]; then (cd services/core_api && alembic upgrade head); fi; exec uvicorn core_api.main:app --host 0.0.0.0 --port ${PORT}"]
