# Imagem única para os dois processos (Plano, Seção 12.2):
#   api:    uvicorn brikta_ia.main:app --host 0.0.0.0 --port 8000
#   worker: (IA-31) processo da fila
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# ffmpeg/ffprobe: normalização e validação de áudio (IA-11)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev
# Prompts versionados (ADR-08), lidos em tempo de execução.
COPY prompts ./prompts

RUN useradd --create-home --uid 1000 brikta
USER brikta

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Um worker só: as conversas do Assistente ficam em memória até a IA-61 (com dois, cada
# processo teria um histórico). --proxy-headers: IP real do cliente atrás do Caddy.
CMD ["uvicorn", "brikta_ia.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
