"""Run generations cannot survive a portable restore as active authority."""
import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSource, DiscoveryRun, Integration, Site
from tests.test_backup_postgres import installations, portable_backup, restore

pytestmark = pytest.mark.skipif(not (os.getenv("ATLAS_TEST_H3_SOURCE_URL") and os.getenv("ATLAS_TEST_H3_TARGET_URL")), reason="requires disposable source and restore PostgreSQL databases")


def test_restore_fails_active_source_run_and_revokes_generation(installations):
    inst = installations
    with Session(inst["source"]) as db:
        site = db.scalar(select(Site))
        source = DataSource(customer_id=site.customer_id, site_id=site.id, name="I3 portable source", source_type="connector", status="active")
        db.add(source); db.flush()
        row = Integration(customer_id=site.customer_id, site_id=site.id, name="I3 portable", plugin_id="i3-fixture",
            connector_id="i3-fixture", connector_version="1.0.0", connector_digest="a"*64, config_schema_version="1.0",
            base_url="", username_or_token_id="", secret_reference="", data_source_id=source.id)
        db.add(row); db.flush()
        from datetime import datetime, timezone
        run = DiscoveryRun(integration_id=row.id, data_source_id=source.id, customer_id=site.customer_id, site_id=site.id,
            status="pending", dispatch_state="pending", started_at=datetime.now(timezone.utc), execution_provenance={"connector_id": "i3-fixture"}, ingestion_generation=uuid.uuid4())
        db.add(run); db.flush(); identity = run.id; db.commit()
    archive = portable_backup(inst)
    restore(inst, archive)
    with Session(inst["target"]) as db:
        restored = db.get(DiscoveryRun, identity)
        assert restored.status == "failed" and restored.error_message == "restore_interrupted"
        assert restored.ingestion_generation is None and restored.dispatch_state == "settled"
        assert restored.execution_provenance == {"connector_id": "i3-fixture"}


def test_restore_refuses_unsettled_destination_execution_before_replacement(installations):
    from app.services.backup_archive import BackupError
    from app.services import backup_runtime
    from datetime import datetime, timezone
    inst = installations
    archive = portable_backup(inst)
    with Session(inst["target"]) as db:
        site = db.scalar(select(Site))
        # Target may be uninitialized: use the preserved source scope identifiers
        # only after creating its own independent local context.
        if site is None:
            from app.models import Workspace, Customer
            workspace = Workspace(name="Destination", slug=uuid.uuid4().hex); db.add(workspace); db.flush()
            customer = Customer(name="Destination", workspace_id=workspace.id); db.add(customer); db.flush()
            site = Site(name="Destination", customer_id=customer.id); db.add(site); db.flush()
        source = DataSource(customer_id=site.customer_id, site_id=site.id, name="Active destination", source_type="connector")
        db.add(source); db.flush()
        row = Integration(customer_id=site.customer_id, site_id=site.id, name="Active destination", plugin_id="i3-fixture", base_url="", username_or_token_id="", secret_reference="", data_source_id=source.id)
        db.add(row); db.flush()
        run = DiscoveryRun(integration_id=row.id, data_source_id=source.id, customer_id=site.customer_id, site_id=site.id,
            status="running", dispatch_state="running", started_at=datetime.now(timezone.utc), execution_provenance={"connector_id": "i3-fixture"})
        db.add(run); db.flush(); identifier = run.id; db.commit()
    with pytest.raises(BackupError, match="Cancel active discovery runs"):
        restore(inst, archive)
    assert backup_runtime.maintenance() is None
    with Session(inst["target"]) as db:
        assert db.get(DiscoveryRun, identifier).status == "running"
