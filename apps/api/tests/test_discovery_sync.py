import uuid
from datetime import datetime, timezone

from atlas_plugin_sdk import (
    DiscoveryResult,
    NormalizationResult,
    NormalizedAsset,
    NormalizedFact,
    NormalizedRelationship,
    RawDiscoveryItem,
    SyncContext,
)

from app.models import Asset, AssetFact, AssetRelationship, DiscoveryRun, Document
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
        return None

    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return [record for record in self.records if isinstance(record, entity)]

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
        integration_id=integration_id,
        discovery_run_id=run.id,
    )
    discovery = DiscoveryResult(items=(), raw_payload={"nodes": []})

    result = AtlasDiscoverySync(db).persist(
        context, discovery, NormalizationResult(assets=())
    )
    assert result.stale_marked == 1
    assert missing.status == "stale"
    assert missing in db.records
