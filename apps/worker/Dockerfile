FROM python:3.12-slim

LABEL org.opencontainers.image.title="Atlas Impact" \
      org.opencontainers.image.source="https://github.com/benchristian88/atlas" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY worker ./worker

CMD ["python", "-m", "worker.main"]
