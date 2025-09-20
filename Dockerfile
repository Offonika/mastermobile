# filename: Dockerfile
# MasterMobile root Dockerfile
# См. также apps/mw/Dockerfile — основной образ приложения.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY httpx ./httpx
COPY openapi.yaml ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .[dev]

COPY . .

CMD ["uvicorn", "apps.mw.src.app:app", "--host", "0.0.0.0", "--port", "8000"]
