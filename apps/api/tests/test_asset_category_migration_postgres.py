"""Run only with an explicitly supplied EMPTY disposable migration database."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_MIGRATION_DATABASE_URL"), reason="requires empty disposable migration database")


def test_legacy_category_upgrade_preserves_all_types_and_assets(monkeypatch):
    url = os.environ["ATLAS_TEST_MIGRATION_DATABASE_URL"]
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), "Refusing to alter a nonempty migration test database"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "20260912_0018")
    legacy = [None, "", "   ", "Network", "Networking", "network", "Network!", "Network ", "Uncategorized", "uncategorized", "Custom / 名"]
    with engine.begin() as db:
        for index, value in enumerate(legacy):
            db.execute(text("INSERT INTO asset_types (key,name,category) VALUES (:key,:name,:category)"), {"key": f"migration_test_{index}", "name": f"Migration {index}", "category": value})
        workspace = db.scalar(text("INSERT INTO workspaces (name,slug) VALUES ('Migration fixture','migration-fixture') RETURNING id"))
        customer = db.scalar(text("INSERT INTO customers (name,workspace_id) VALUES ('Migration fixture',:id) RETURNING id"), {"id": workspace})
        site = db.scalar(text("INSERT INTO sites (name,customer_id) VALUES ('Migration fixture',:id) RETURNING id"), {"id": customer})
        db.execute(text("INSERT INTO assets (workspace_id,customer_id,site_id,name,asset_type) VALUES (:w,:c,:s,'Preserved Asset','migration_test_4')"), {"w": workspace, "c": customer, "s": site})
        before_types = db.execute(text("SELECT id,key,name,category FROM asset_types ORDER BY key")).all()
        before_assets = db.execute(text("SELECT id,name,asset_type FROM assets ORDER BY id")).all()
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT id,key,name,category FROM asset_types ORDER BY key")).all() == before_types
        assert db.execute(text("SELECT id,name,asset_type FROM assets ORDER BY id")).all() == before_assets
        assert db.scalar(text("SELECT count(*) FROM asset_types WHERE category_id IS NULL")) == 0
        rows = db.execute(text("SELECT t.key,c.id,c.name,c.key,c.show_in_topology,c.active FROM asset_types t JOIN asset_categories c ON t.category_id=c.id WHERE t.key LIKE 'migration_test_%'")).all()
        by_key = {r[0]: r for r in rows}
        assert len({by_key[f"migration_test_{i}"][1] for i in (3,4,5,6,7,8,9,10)}) == 8
        for i, original in enumerate(legacy):
            row = by_key[f"migration_test_{i}"]
            if not original or not original.strip() or original == "Uncategorized":
                assert row[2:6] == ("Uncategorized", "uncategorized", False, True)
            else:
                assert row[2] == original and row[4] is True
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20260921_0023"
    # Downgrade remains a usable rollback path, retaining current managed names.
    command.downgrade(config, "20260912_0018")
    command.upgrade(config, "head")
    engine.dispose()
