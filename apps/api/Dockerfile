FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY alembic.ini ./
COPY infra ./infra
COPY apps ./apps
COPY packages ./packages
COPY data ./data
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2,<3" \
    && pip install --no-cache-dir .[postgres,observability,local-embedding]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000"]

