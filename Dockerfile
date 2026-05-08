FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV APP_HOST=0.0.0.0
ENV APP_PORT=7777
ENV APP_LANG=th
ENV ENABLE_AUTH=false
ENV DATABASE_URL=sqlite:////app/data/olre.sqlite3
ENV INPUT_DIR=/app/data/input
ENV PROCESSED_DIR=/app/data/processed
ENV ERROR_DIR=/app/data/error
ENV QR_DEBUG_DIR=/app/data/debug/qr
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
    && mkdir -p /app/data/input /app/data/processed /app/data/error /app/data/debug/qr /app/data/runtime/tmp /app/data/runtime/failed-retained \
    && chmod +x /app/scripts/start-docker.sh

VOLUME ["/app/data"]

EXPOSE 7777

CMD ["/app/scripts/start-docker.sh"]

