FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY apps ./apps
COPY packages ./packages
COPY data ./data
COPY evals ./evals
RUN pip install --no-cache-dir .[postgres,observability,local-embedding]
CMD ["python", "-m", "apps.worker.app.main"]

