FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY alembic.ini .
COPY migrations ./migrations

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
