"""Configuration required before connecting to the system of record."""
import os
import re


def data_encryption_key(*, required: bool = True) -> bytes | None:
    """Independent 256-bit bootstrap material; never derive it from auth keys."""
    value = os.getenv("ATLAS_DATA_ENCRYPTION_KEY", "")
    if not value and not required and os.getenv("ATLAS_INSTALL_METHOD", "development") == "development":
        return None
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise RuntimeError("ATLAS_DATA_ENCRYPTION_KEY must be configured as 64 hexadecimal characters (32 random bytes)")
    return bytes.fromhex(value)

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
