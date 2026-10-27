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
    for attempt in 1 2 3; do \
        pip install --no-deps --index-url https://download.pytorch.org/whl/cpu "torch>=2,<3" && exit 0; \
    done; exit 1
RUN --mount=type=cache,id=aftersales-pip,target=/root/.cache/pip,sharing=locked \
    for attempt in 1 2 3; do \
        pip install \
            "filelock>=3.10" "typing-extensions>=4.10" "sympy>=1.13.3" \
            "networkx>=2.5.1" jinja2 "fsspec>=2023.5.0" \
            .[postgres,observability,local-embedding] \
            && pip check \
            && exit 0; \
    done; exit 1
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000"]

