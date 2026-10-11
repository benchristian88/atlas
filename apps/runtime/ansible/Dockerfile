FROM python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

LABEL org.opencontainers.image.title="Atlas Ansible Runtime" \
      org.opencontainers.image.source="https://github.com/benchristian88/atlas" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY vendor/sdk /vendor/sdk
RUN pip install --no-index --no-deps --require-hashes --find-links /vendor/sdk -r /vendor/sdk/requirements.txt
COPY apps/runtime/ansible/requirements.lock .
RUN pip install --no-cache-dir --no-deps -r requirements.lock && pip check \
    && useradd --system --uid 10001 atlas-runtime
COPY apps/runtime/ansible/atlas_runtime ./atlas_runtime
COPY apps/runtime/ansible/baseline.json apps/runtime/ansible/sbom.cdx.json ./
COPY apps/runtime/ansible/notices ./notices
USER atlas-runtime
CMD ["python", "-m", "atlas_runtime.server"]
