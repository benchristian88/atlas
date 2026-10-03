"""Configuration required before connecting to the system of record."""
import os

from sqlalchemy import URL


def database_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    production = os.getenv("ATLAS_INSTALL_METHOD", "development") != "development"
    password = os.getenv("POSTGRES_PASSWORD")
    if production and not password:
        raise RuntimeError("POSTGRES_PASSWORD or DATABASE_URL is required")
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "atlas"),
        password=password or "atlas_dev",
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "atlas"),
    ).render_as_string(hide_password=False)
