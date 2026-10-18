"""Operator activation reuses one-version/mapping/history and I3 boundaries."""
import asyncio
from contextlib import contextmanager
import os

import pytest
from sqlalchemy import select

from app.models import AuditEvent, InstalledConnectorPackage
from app.services import connector_lifecycle as lifecycle, discovery_orchestration as orchestration
from app.services.integration_connections import installed_manifest
from app.services.connector_qualification import OperatorQualificationVerifier
from scripts import qualify_connector as cli
from tests.i3_fixtures import fixture_bundle
from tests.test_i3_discovery import db, configured
from tests.test_connector_qualification import arguments, unqualified, runtime_result

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable PostgreSQL")


@pytest.fixture
def checkpoint(db, configured, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_CONNECTOR_QUALIFICATION_ENABLED", "1")
    monkeypatch.setenv("ATLAS_BUILD_ID", "a" * 40)
    package = unqualified(fixture_bundle(tmp_path)[0])
    args = arguments(package, tmp_path)
    cli.stage(args)
    @contextmanager
    def session():
        yield db
    import app.database
    monkeypatch.setattr(app.database, "SessionLocal", session)
    from app.services.integration_runtime import runtime
    async def health(): return configured[3]
    async def verify(reference): return runtime_result(configured[2], package)
    monkeypatch.setattr(runtime, "health", health)
    monkeypatch.setattr(runtime, "verify_connector", verify)
    return package, args


def test_local_activation_retains_source_and_credentials_and_uses_normal_i3(db, configured, checkpoint):
    package, args = checkpoint
    row, _, store, _ = configured
    source_id = row.data_source_id
    from app.services.integration_secrets import AtlasEncryptedSecretProvider
    before = AtlasEncryptedSecretProvider(db).state(row)
    asyncio.run(cli.activate(args))
    record, manifest = installed_manifest(db, package.connector_id)
    assert record.version == package.version and record.bundle_digest == package.bundle_digest[7:]
    assert row.connector_version == package.version and row.data_source_id == source_id
    assert AtlasEncryptedSecretProvider(db).state(row) == before
    assert manifest["source_versions"]["qualification"] == "unqualified"
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "connector.qualification_activated"))
    run = asyncio.run(orchestration.create_run(db, row, user_id=configured[1].user.id))
    assert run.execution_provenance["connector_version"] == package.version
    assert run.execution_provenance["connector_digest"] == package.bundle_digest[7:]
    assert run.data_source_id == source_id


def test_nonmanual_connection_blocks_activation_and_preserves_previous_version(db, configured, checkpoint):
    package, args = checkpoint
    configured[0].schedule_preset = "hourly"; db.flush()
    with pytest.raises(ValueError, match="qualification_requires_generic_manual_connections"):
        asyncio.run(cli.activate(args))
    assert db.get(InstalledConnectorPackage, package.connector_id).version == "1.0.0"


def test_existing_active_run_blocks_operator_activation(db, configured, checkpoint):
    package, args = checkpoint
    asyncio.run(orchestration.create_run(db, configured[0], user_id=configured[1].user.id))
    with pytest.raises(lifecycle.ConnectorInUse): asyncio.run(cli.activate(args))
    assert db.get(InstalledConnectorPackage, package.connector_id).version == "1.0.0"


def test_explicit_scopes_enable_new_requirements_and_bad_mapping_keeps_active_version(db, configured, checkpoint, tmp_path):
    package, args = checkpoint
    configured[0].selected_scopes = []
    args.scope = ["inventory"]
    import json
    choices = tmp_path / "choices.json"
    choices.write_text(json.dumps([{"kind": "asset", "source_key": "undeclared", "target_key": "hypervisor_node"}]))
    args.mappings = choices
    with pytest.raises(ValueError, match="qualification_invalid_mappings"):
        asyncio.run(cli.activate(args))
    assert db.get(InstalledConnectorPackage, package.connector_id).version == "1.0.0"
    args.mappings = None
    asyncio.run(cli.activate(args))
    assert configured[0].selected_scopes == ["inventory"]
    assert db.get(InstalledConnectorPackage, package.connector_id).version == package.version


def test_plan_reports_requirements_without_persisting_scope_or_active_identity(db, configured, checkpoint, capsys):
    package, args = checkpoint
    configured[0].selected_scopes = []; db.commit()
    args.scope = ["inventory"]
    cli.plan(args)
    assert '"state": "qualification_plan"' in capsys.readouterr().out
    assert configured[0].selected_scopes == []
    assert db.get(InstalledConnectorPackage, package.connector_id).version == "1.0.0"
