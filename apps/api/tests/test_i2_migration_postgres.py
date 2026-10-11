"""Fresh and additive I1 upgrade preserve legacy fields and scoped FK invariants."""
import os
import secrets

from alembic import command
import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from pathlib import Path

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_I2_MIGRATION_URL"), reason="requires empty disposable I2 migration database")


def test_i1_to_i2_upgrade_preserves_legacy_records_and_single_head(monkeypatch):
    engine = create_engine(os.environ["ATLAS_TEST_I2_MIGRATION_URL"], hide_parameters=True)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%"))
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    command.upgrade(config, "20261011_0027")
    with engine.begin() as db:
        workspace = db.scalar(text("INSERT INTO workspaces (name,slug) VALUES ('I2 migration','i2-migration') RETURNING id"))
        customer = db.scalar(text("INSERT INTO customers (name,workspace_id) VALUES ('I2 migration',:workspace) RETURNING id"), {"workspace": workspace})
        site = db.scalar(text("INSERT INTO sites (name,customer_id) VALUES ('I2 migration',:customer) RETURNING id"), {"customer": customer})
        identifier = db.scalar(text("INSERT INTO integrations (customer_id,site_id,plugin_id,name,base_url,username_or_token_id,secret_reference) VALUES (:customer,:site,'legacy','Legacy','https://example.test','legacy-identity','legacy-reference') RETURNING id"), {"customer": customer, "site": site})
    command.upgrade(config, "20261012_0028")
    with engine.begin() as db:
        row = db.execute(text("SELECT connector_id,data_source_id,base_url,username_or_token_id,secret_reference,config_json FROM integrations WHERE id=:id"), {"id": identifier}).one()
        assert row == (None, None, "https://example.test", "legacy-identity", "legacy-reference", {})
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261012_0028"
        assert db.scalar(text("SELECT count(*) FROM integration_secrets")) == 0
    engine.dispose()
