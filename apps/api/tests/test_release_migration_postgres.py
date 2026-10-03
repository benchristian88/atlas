"""Run only against an explicitly supplied EMPTY disposable database."""
import os
from pathlib import Path
import secrets

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

from app.auth import hash_password

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_H1_MIGRATION_URL"), reason="requires empty disposable H1 migration database")


def test_legacy_backfill_preserves_users_and_setup_remains_closed(monkeypatch):
    url = os.environ["ATLAS_TEST_H1_MIGRATION_URL"]
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), "Refusing to alter a nonempty database"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    command.upgrade(config, "20261004_0024")
    with engine.begin() as db:
        original_hash = hash_password(secrets.token_urlsafe(24))
        identifier = db.scalar(text("INSERT INTO users (email, display_name, password_hash) VALUES ('existing@example.com', 'Existing', :hash) RETURNING id"), {"hash": original_hash})
    command.upgrade(config, "head")
    with engine.begin() as db:
        assert db.scalar(text("SELECT initialized_at FROM installation_state WHERE id=1")) is not None
        assert db.scalar(text("SELECT setup_code_hash FROM installation_state WHERE id=1")) is None
        assert db.execute(text("SELECT id, password_hash FROM users")).one() == (identifier, original_hash)
        assert db.scalar(text("SELECT value FROM system_settings WHERE key='auth.session_minutes'")) == 480
        db.execute(text("DELETE FROM users"))
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.scalar(text("SELECT initialized_at FROM installation_state WHERE id=1")) is not None
    engine.dispose()
