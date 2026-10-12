FROM python:3.12-slim-trixie

LABEL org.opencontainers.image.title="Atlas Impact" \
      org.opencontainers.image.source="https://github.com/benchristian88/atlas" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY vendor/sdk /vendor/sdk
RUN pip install --no-index --no-deps --require-hashes --find-links /vendor/sdk -r /vendor/sdk/requirements.txt
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api/app ./app
COPY apps/worker/worker ./worker
COPY apps/runtime/ansible/baseline.json apps/runtime/ansible/requirements.lock ./runtime-baseline/
RUN useradd --system --uid 10001 atlas
USER atlas

CMD ["python", "-m", "worker.main"]
