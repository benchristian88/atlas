FROM python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

LABEL org.opencontainers.image.title="Atlas Ansible Runtime" \
      org.opencontainers.image.source="https://github.com/benchristian88/atlas" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --no-deps -r requirements.lock && pip check \
    && useradd --system --uid 10001 atlas-runtime
COPY atlas_runtime ./atlas_runtime
COPY baseline.json sbom.cdx.json ./
COPY notices ./notices
USER atlas-runtime
CMD ["python", "-m", "atlas_runtime.server"]
