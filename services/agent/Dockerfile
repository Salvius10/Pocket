# Build context is the repo root:  docker build -f services/agent/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir uv==0.11.24
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/pocket_common packages/pocket_common
COPY packages/pocket_synth/pyproject.toml packages/pocket_synth/pyproject.toml
COPY services/core_api/pyproject.toml services/core_api/pyproject.toml
COPY services/agent services/agent
RUN mkdir -p packages/pocket_synth/pocket_synth services/core_api/core_api \
 && touch packages/pocket_synth/pocket_synth/__init__.py services/core_api/core_api/__init__.py \
 && uv sync --frozen --no-dev --package agent --extra gemini

ENV PATH="/app/.venv/bin:$PATH" ENV=demo PORT=8080
EXPOSE 8080
# GEMINI_API_KEY arrives as a Cloud Run environment variable. It is never baked into the image.
CMD ["sh", "-c", "exec uvicorn agent.main:app --host 0.0.0.0 --port ${PORT} --ws-ping-interval 20 --ws-ping-timeout 30"]
