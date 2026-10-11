FROM python:3.12-slim-trixie

LABEL org.opencontainers.image.title="Atlas Impact" \
      org.opencontainers.image.source="https://github.com/benchristian88/atlas" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/api/requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app
COPY apps/api/scripts ./scripts
COPY apps/api/alembic.ini .
COPY apps/api/migrations ./migrations
COPY docs/architecture/integrations/contracts/connector-manifest-v1.schema.json ./contracts/connector-manifest-v1.schema.json
COPY docs/architecture/integrations/contracts/manifests ./contracts/manifests
COPY apps/runtime/ansible/baseline.json apps/runtime/ansible/requirements.lock ./runtime-baseline/

# Malformed canonical metadata fails the image build before distribution.
RUN python -c "from app.release import load_metadata; load_metadata()"

EXPOSE 8000

ARG ATLAS_BUILD_ID=unknown
ENV ATLAS_BUILD_ID=${ATLAS_BUILD_ID}
RUN useradd --system --uid 10001 atlas \
    && mkdir -p /var/lib/atlas \
    && chown atlas:atlas /var/lib/atlas \
    && chmod 0700 /var/lib/atlas
ENV ATLAS_STATE_DIR=/var/lib/atlas
USER atlas
CMD ["python", "-m", "scripts.start"]
