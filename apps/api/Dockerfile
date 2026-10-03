FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY alembic.ini .
COPY migrations ./migrations

EXPOSE 8000

ARG ATLAS_BUILD_ID=unknown
ENV ATLAS_BUILD_ID=${ATLAS_BUILD_ID}
RUN useradd --system --uid 10001 atlas
USER atlas
CMD ["python", "-m", "scripts.start"]
