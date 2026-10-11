"""Safe fresh/upgrade I1 migration in an explicitly empty disposable database."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_I1_MIGRATION_URL"), reason="requires empty disposable I1 migration database")


def test_i1_upgrade_preserves_knowledge_and_scoped_grants_and_single_active_identity(monkeypatch):
    url = os.environ["ATLAS_TEST_I1_MIGRATION_URL"]
    engine = create_engine(url, hide_parameters=True)
    assert not inspect(engine).get_table_names(), "Refusing to alter a nonempty database"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    command.upgrade(config, "20261004_0026")
    with engine.begin() as db:
        workspace = db.scalar(text("INSERT INTO workspaces (name,slug) VALUES ('I1 preserved','i1-preserved') RETURNING id"))
        customer = db.scalar(text("INSERT INTO customers (workspace_id,name) VALUES (:workspace,'Preserved') RETURNING id"), {"workspace": workspace})
        original_grants = db.execute(text("SELECT rp.role_id,rp.permission_id FROM role_permissions rp JOIN roles r ON r.id=rp.role_id WHERE r.name IN ('Customer Administrator','Viewer') ORDER BY rp.role_id,rp.permission_id")).all()
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert inspector.get_pk_constraint("installed_connector_packages")["constrained_columns"] == ["connector_id"]
    assert not inspector.get_foreign_keys("installed_connector_packages")
    assert {"customer_id", "site_id", "secret", "config"}.isdisjoint({col["name"] for col in inspector.get_columns("installed_connector_packages")})
    with engine.begin() as db:
        assert db.scalar(text("SELECT id FROM customers WHERE name='Preserved'")) == customer
        assert db.execute(text("SELECT rp.role_id,rp.permission_id FROM role_permissions rp JOIN roles r ON r.id=rp.role_id WHERE r.name IN ('Customer Administrator','Viewer') ORDER BY rp.role_id,rp.permission_id")).all() == original_grants
        assert db.scalar(text("SELECT count(*) FROM permissions WHERE key LIKE 'integration_runtime.%' AND system_defined")) == 2
        assert db.scalar(text("SELECT count(*) FROM role_permissions rp JOIN roles r ON r.id=rp.role_id JOIN permissions p ON p.id=rp.permission_id WHERE p.key LIKE 'integration_runtime.%' AND r.name IN ('Master Administrator','Administrator')")) == 4
        assert db.scalar(text("SELECT count(*) FROM installed_connector_packages")) == 0
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261011_0027"
    engine.dispose()
