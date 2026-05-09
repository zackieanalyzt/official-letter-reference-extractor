FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=docker
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV APP_LANG=th
ENV ENABLE_AUTH=false
ENV DATABASE_URL=sqlite:////app/data/olre.sqlite3
ENV INPUT_DIR=/app/data/input
ENV PROCESSED_DIR=/app/data/processed
ENV ERROR_DIR=/app/data/error
ENV QR_DEBUG_DIR=/app/data/qr-debug
ENV RUNTIME_TMP_DIR=/app/data/runtime/tmp
ENV FAILED_RETAINED_DIR=/app/data/runtime/failed-retained

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./

RUN pip install --upgrade pip \
    && pip install --no-cache-dir . \
    && mkdir -p /app/data/input /app/data/processed /app/data/error /app/data/qr-debug /app/data/runtime/tmp /app/data/runtime/failed-retained \
    && chmod +x /app/scripts/start-docker.sh

VOLUME ["/app/data"]

EXPOSE 8000

CMD ["/app/scripts/start-docker.sh"]
