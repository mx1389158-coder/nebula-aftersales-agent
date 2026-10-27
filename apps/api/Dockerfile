# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10

WORKDIR /app
COPY pyproject.toml ./
COPY alembic.ini ./
COPY infra ./infra
COPY apps ./apps
COPY packages ./packages
COPY data ./data
RUN --mount=type=cache,id=aftersales-pip,target=/root/.cache/pip,sharing=locked \
    pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2,<3"
RUN --mount=type=cache,id=aftersales-pip,target=/root/.cache/pip,sharing=locked \
    pip install .[postgres,observability,local-embedding]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000"]

