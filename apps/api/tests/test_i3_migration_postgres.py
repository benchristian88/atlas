"""I2 -> I3 and fresh PostgreSQL migration with legacy history preserved."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_I3_MIGRATION_URL"), reason="requires empty disposable I3 migration database")


def test_additive_upgrade_legacy_history_receipts_and_single_head(monkeypatch):
    engine = create_engine(os.environ["ATLAS_TEST_I3_MIGRATION_URL"], hide_parameters=True)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    assert ScriptDirectory.from_config(config).get_heads() == ["20261018_0030"]
    command.upgrade(config, "20261012_0028")
    with engine.begin() as db:
        workspace = db.scalar(text("INSERT INTO workspaces(name,slug) VALUES ('I3 migration','i3-migration') RETURNING id"))
        customer = db.scalar(text("INSERT INTO customers(name,workspace_id) VALUES ('I3',:workspace) RETURNING id"), {"workspace": workspace})
        site = db.scalar(text("INSERT INTO sites(name,customer_id) VALUES ('I3',:customer) RETURNING id"), {"customer": customer})
        identifier = db.scalar(text("INSERT INTO integrations(customer_id,site_id,plugin_id,name,base_url,username_or_token_id,secret_reference) VALUES (:customer,:site,'legacy','Legacy','https://example.test','','') RETURNING id"), {"customer": customer, "site": site})
        run = db.scalar(text("INSERT INTO discovery_runs(integration_id,customer_id,site_id,status,started_at,coverage_key) VALUES (:integration,:customer,:site,'completed',now(),'legacy') RETURNING id"), {"integration": identifier, "customer": customer, "site": site})
    command.upgrade(config, "20261012_0029")
    command.upgrade(config, "head")
    with engine.begin() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261018_0030"
        assert db.execute(text("SELECT status,coverage_key,execution_provenance FROM discovery_runs WHERE id=:id"), {"id": run}).one() == ("completed", "legacy", None)
        assert db.scalar(text("SELECT schedule_preset FROM integrations WHERE id=:id"), {"id": identifier}) == "manual"
        assert db.scalar(text("SELECT debug_next_run FROM integrations WHERE id=:id"), {"id": identifier}) is False
        assert db.execute(text("SELECT debug_enabled,debug_expires_at,diagnostics_summary FROM discovery_runs WHERE id=:id"), {"id": run}).one() == (False, None, None)
        db.execute(text("INSERT INTO discovery_batch_receipts(discovery_run_id,sequence,body_hash,payload_json) VALUES (:id,1,:hash,'{}')"), {"id": run, "hash": "a"*64})
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("DELETE FROM discovery_batch_receipts WHERE discovery_run_id=:id"), {"id": run})
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("INSERT INTO discovery_batch_receipts(discovery_run_id,sequence,body_hash,payload_json) VALUES (:id,1,:hash,'{}')"), {"id": run, "hash": "a"*64})
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("INSERT INTO discovery_runs(integration_id,customer_id,site_id,status,started_at,execution_provenance) VALUES (:integration,:customer,:site,'pending',now(),'{}')"), {"integration": identifier, "customer": customer, "site": site})
    engine.dispose()
