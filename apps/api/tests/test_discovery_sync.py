import uuid
from datetime import datetime, timezone

import pytest

from atlas_plugin_sdk import (
    DiscoveryResult,
    NormalizationResult,
    NormalizedAsset,
    NormalizedFact,
    NormalizedRelationship,
    RawDiscoveryItem,
    SyncContext,
    SyncError,
)

from app.models import (
    Asset,
    AssetFact,
    AssetRelationship,
    AssetType,
    Customer,
    DiscoveryRun,
    Document,
    Integration,
    RelationshipType,
    Site,
)
from app.services.discovery_sync import AtlasDiscoverySync


class FakeSession:
    def __init__(self, run: DiscoveryRun):
        self.run = run
        self.records: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, model, record_id):
        if model is DiscoveryRun and self.run.id == record_id:
            return self.run
        return next(
            (
                record
                for record in self.records
                if isinstance(record, model) and getattr(record, "id", None) == record_id
            ),
            None,
        )

    def scalars(self, statement):
        description = statement.column_descriptions[0]
        entity = description["entity"]
        records = [record for record in self.records if isinstance(record, entity)]
        expression = description.get("expr")
        if getattr(expression, "name", None) == "key" and entity in {
            AssetType,
            RelationshipType,
        }:
            return [record.key for record in records]
        return records

    def add(self, record):
        self.records.append(record)

    def flush(self):
        for record in self.records:
            if getattr(record, "id", None) is None:
                record.id = uuid.uuid4()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def add_context_records(db: FakeSession, context: SyncContext) -> None:
    db.records.extend(
        [
            Customer(
                id=context.customer_id,
                workspace_id=context.workspace_id,
                name="Test customer",
                status="active",
            ),
            Site(
                id=context.site_id,
                customer_id=context.customer_id,
                name="Test site",
                status="active",
            ),
            Integration(
                id=context.integration_id,
                customer_id=context.customer_id,
                site_id=context.site_id,
                plugin_id="test",
                name="Test integration",
                base_url="https://example.test",
                username_or_token_id="test-user",
                secret_reference="test-secret-reference",
                verify_tls=True,
                status="active",
            ),
        ]
    )


def test_persists_raw_payload_and_idempotently_syncs_normalized_data() -> None:
    integration_id = uuid.uuid4()
    run = DiscoveryRun(
        id=uuid.uuid4(), integration_id=integration_id, status="running"
    )
    db = FakeSession(run)
    context = SyncContext(
        workspace_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        integration_id=integration_id,
        discovery_run_id=run.id,
    )
    add_context_records(db, context)
    observed_at = datetime(2026, 7, 10, 4, 0, tzinfo=timezone.utc)
    discovery = DiscoveryResult(
        items=(RawDiscoveryItem("node/pve-01", "node", {"node": "pve-01"}),),
        raw_payload={"nodes": [{"node": "pve-01", "cpu": 0.25}]},
        observed_at=observed_at,
    )
    normalized = NormalizationResult(
        assets=(
            NormalizedAsset(
                external_id="node/pve-01",
                name="pve-01",
                asset_type="hypervisor_node",
                vendor="Proxmox",
                metadata={"status": "online"},
                facts=(NormalizedFact("cpu", 0.25, "proxmox"),),
            ),
            NormalizedAsset(
                external_id="qemu/100",
                name="dc-01",
                asset_type="virtual_machine",
                vendor="Proxmox",
            ),
        ),
        relationships=(
            NormalizedRelationship("qemu/100", "node/pve-01", "runs_on"),
        ),
    )

    first = AtlasDiscoverySync(db).persist(context, discovery, normalized)
    assert first.created == 2
    assert first.facts_upserted == 1
    assert first.relationships_upserted == 1
    assert run.raw_payload == discovery.raw_payload
    assert run.raw_payload is not discovery.raw_payload
    assert run.status == "completed"
    assert run.summary["assets_seen"] == 2
    assert run.summary["documents_generated"] == 2
    assert len([record for record in db.records if isinstance(record, Asset)]) == 2
    documents = [record for record in db.records if isinstance(record, Document)]
    assert len(documents) == 2
    assert all(document.generated_from_discovery_run_id == run.id for document in documents)
    assert any("dc\\-01" in document.content_markdown for document in documents)

    second = AtlasDiscoverySync(db).persist(context, discovery, normalized)
    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == 2
    assert len([record for record in db.records if isinstance(record, Asset)]) == 2
    assert len([record for record in db.records if isinstance(record, AssetFact)]) == 1
    assert len(
        [record for record in db.records if isinstance(record, AssetRelationship)]
    ) == 1
    assert len([record for record in db.records if isinstance(record, Document)]) == 2


def test_missing_assets_are_marked_stale_not_deleted() -> None:
    integration_id = uuid.uuid4()
    run = DiscoveryRun(id=uuid.uuid4(), integration_id=integration_id, status="running")
    db = FakeSession(run)
    missing = Asset(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        source_integration_id=integration_id,
        external_id="qemu/999",
        name="old-vm",
        asset_type="virtual_machine",
        vendor="Proxmox",
        status="active",
        metadata_={},
    )
    db.records.append(missing)
    context = SyncContext(
        workspace_id=missing.workspace_id,
        customer_id=missing.customer_id,
        site_id=missing.site_id,
        integration_id=integration_id,
        discovery_run_id=run.id,
    )
    add_context_records(db, context)
    discovery = DiscoveryResult(items=(), raw_payload={"nodes": []})

    result = AtlasDiscoverySync(db).persist(
        context, discovery, NormalizationResult(assets=())
    )
    assert result.stale_marked == 1
    assert missing.status == "stale"
    assert missing in db.records


def test_sync_rejects_context_that_does_not_match_integration_ownership() -> None:
    integration_id = uuid.uuid4()
    run = DiscoveryRun(id=uuid.uuid4(), integration_id=integration_id, status="running")
    db = FakeSession(run)
    authorised = SyncContext(
        workspace_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        integration_id=integration_id,
        discovery_run_id=run.id,
    )
    add_context_records(db, authorised)
    forged = SyncContext(
        workspace_id=authorised.workspace_id,
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        integration_id=integration_id,
        discovery_run_id=run.id,
    )
    with pytest.raises(SyncError, match="ownership"):
        AtlasDiscoverySync(db).persist(
            forged,
            DiscoveryResult(items=()),
            NormalizationResult(assets=()),
        )


def test_discovery_does_not_reuse_an_inactive_type_for_a_new_asset() -> None:
    integration_id = uuid.uuid4()
    run = DiscoveryRun(id=uuid.uuid4(), integration_id=integration_id, status="running")
    db = FakeSession(run)
    context = SyncContext(
        workspace_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        integration_id=integration_id,
        discovery_run_id=run.id,
    )
    add_context_records(db, context)
    db.records.append(
        AssetType(
            id=uuid.uuid4(),
            key="retired",
            name="Retired",
            system_defined=False,
            active=False,
            sort_order=100,
        )
    )
    with pytest.raises(SyncError, match="inactive asset type"):
        AtlasDiscoverySync(db).persist(
            context,
            DiscoveryResult(items=()),
            NormalizationResult(
                assets=(
                    NormalizedAsset(
                        external_id="new/1",
                        name="new",
                        asset_type="retired",
                        vendor="Test",
                    ),
                )
            ),
        )
