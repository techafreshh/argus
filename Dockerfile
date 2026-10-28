FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY argus ./argus

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD uvicorn argus.server.app:app --host 0.0.0.0 --port ${PORT:-8000}
