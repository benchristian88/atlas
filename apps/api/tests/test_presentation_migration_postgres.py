"""Run against an explicitly provided EMPTY disposable database."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_PRESENTATION_MIGRATION_URL"), reason="requires empty disposable migration database")


def test_upgrade_from_0019_preserves_identity_and_backfills_once(monkeypatch):
    url = os.environ["ATLAS_TEST_PRESENTATION_MIGRATION_URL"]
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), "Refusing to alter a nonempty database"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "20260921_0019")
    with engine.begin() as db:
        for key, name in (("home_automation", "Home Automation"), ("workload", "Workload")):
            db.execute(text("INSERT INTO asset_categories (key,name) VALUES (:key,:name)"), {"key": key, "name": name})
        workspace = db.scalar(text("INSERT INTO workspaces (name,slug) VALUES ('Fixture','fixture') RETURNING id"))
        customer = db.scalar(text("INSERT INTO customers (name,workspace_id) VALUES ('Fixture',:id) RETURNING id"), {"id": workspace})
        db.execute(text("INSERT INTO networks (customer_id,name,network_type,vlan_id,cidr,gateway) VALUES (:c,'IoT','vlan',99,'10.0.99.0/24','10.0.99.1')"), {"c": customer})
        before_categories = db.execute(text("SELECT id,key,name,active,show_in_topology FROM asset_categories ORDER BY id")).all()
        before_networks = db.execute(text("SELECT id,customer_id,name,network_type,vlan_id,cidr,gateway FROM networks ORDER BY id")).all()
    command.upgrade(config, "head")
    with engine.begin() as db:
        assert db.execute(text("SELECT id,key,name,active,show_in_topology FROM asset_categories ORDER BY id")).all() == before_categories
        assert db.execute(text("SELECT id,customer_id,name,network_type,vlan_id,cidr,gateway FROM networks ORDER BY id")).all() == before_networks
        categories = {r[0]: (r[1], r[2]) for r in db.execute(text("SELECT name,icon_key,accent_key FROM asset_categories"))}
        assert categories["Compute"] == ("server", "blue")
        assert categories["Software"] == categories["Workload"] == ("cube", "green")
        assert categories["Network"] == ("network", "cyan")
        assert categories["Storage"] == ("database", "purple")
        assert categories["Backup"] == ("archive", "orange")
        assert categories["Data"] == ("database", "teal")
        assert categories["Other"] == categories["Home Automation"] == categories["Uncategorized"] == ("infrastructure", "slate")
        assert db.execute(text("SELECT icon_key,accent_key FROM networks")).one() == ("network", "blue")
        db.execute(text("UPDATE asset_categories SET name='Renamed Compute', accent_key='rose' WHERE name='Compute'"))
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.scalar(text("SELECT accent_key FROM asset_categories WHERE name='Renamed Compute'")) == "rose"
    command.downgrade(config, "20260921_0019")
    with engine.connect() as db:
        assert db.execute(text("SELECT id,customer_id,name,network_type,vlan_id,cidr,gateway FROM networks ORDER BY id")).all() == before_networks
    command.upgrade(config, "head")
    assert "accent_key" in {c["name"] for c in inspect(engine).get_columns("networks")}
    engine.dispose()
