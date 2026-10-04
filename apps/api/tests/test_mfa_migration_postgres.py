"""Explicitly empty disposable database only; protects existing account data."""
import os
from pathlib import Path
import secrets

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

from app.auth import hash_password

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_H2_MIGRATION_URL"), reason="requires empty disposable H2 migration database")


def test_h2_upgrade_preserves_identity_password_rbac_and_disables_reserved_flag(monkeypatch):
    url = os.environ["ATLAS_TEST_H2_MIGRATION_URL"]
    engine = create_engine(url, hide_parameters=True)
    assert not inspect(engine).get_table_names(), "Refusing to alter a nonempty database"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    command.upgrade(config, "20261004_0025")
    password_hash = hash_password(secrets.token_urlsafe(24))
    with engine.begin() as db:
        user_id = db.scalar(text("INSERT INTO users (email, display_name, password_hash, mfa_enabled) VALUES ('legacy@example.com', 'Legacy', :hash, true) RETURNING id"), {"hash": password_hash})
        role_id = db.scalar(text("SELECT id FROM roles WHERE name='Master Administrator'"))
        assignment_id = db.scalar(text("INSERT INTO access_assignments (user_id, role_id, scope_type) VALUES (:user_id, :role_id, 'global') RETURNING id"), {"user_id": user_id, "role_id": role_id})
    command.upgrade(config, "head")
    with engine.begin() as db:
        assert db.execute(text("SELECT id, password_hash, mfa_enabled FROM users")).one() == (user_id, password_hash, False)
        assert db.scalar(text("SELECT id FROM access_assignments")) == assignment_id
        for table in ["user_mfa", "mfa_recovery_codes", "mfa_challenges"]:
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    assert {"user_mfa", "mfa_recovery_codes", "mfa_challenges"}.issubset(inspect(engine).get_table_names())
    command.upgrade(config, "head")  # Idempotent startup does not enroll accounts.
    engine.dispose()
