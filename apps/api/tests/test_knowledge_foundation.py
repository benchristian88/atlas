import uuid
from types import SimpleNamespace

from app.models import (
    Asset,
    AssetInterface,
    AssetRelationship,
    AssetType,
    Customer,
    DataSource,
    DiscoveryRun,
    EvidenceRecord,
    KnowledgeAssertion,
    Network,
    ReconciliationItem,
    RelationshipType,
    Site,
)
from app.schemas import SimulatedDiscoveryRequest
from app.services.reconciliation import accept_item, defer_item, reject_item
from app.services.simulated_discovery import run_simulation


class KnowledgeSession:
    """Small identity-map fake for deterministic service-level pipeline tests."""

    def __init__(self, *records):
        self.records = list(records)

    def add(self, record):
        self.records.append(record)

    def flush(self):
        for record in self.records:
            if getattr(record, "id", None) is None:
                record.id = uuid.uuid4()

    def get(self, model, record_id):
        return next(
            (
                record
                for record in self.records
                if isinstance(record, model) and getattr(record, "id", None) == record_id
            ),
            None,
        )

    @staticmethod
    def _entity(statement):
        return statement.column_descriptions[0]["entity"]

    @staticmethod
    def _params(statement):
        return statement.compile().params

    def _matching(self, statement):
        entity = self._entity(statement)
        params = self._params(statement)
        rows = [record for record in self.records if isinstance(record, entity)]

        def value(prefix):
            return next((item for key, item in params.items() if key.startswith(prefix)), None)

        field_map = {
            "customer_id": "customer_id",
            "site_id": "site_id",
            "external_id": "external_id",
            "name": "name",
            "asset_type": "asset_type",
            "subject_external_id": "subject_external_id",
            "predicate": "predicate",
            "data_source_id": "data_source_id",
            "assertion_id": "assertion_id",
            "candidate_external_id": "candidate_external_id",
            "relationship_type": "relationship_type",
            "source_asset_id": "source_asset_id",
            "target_asset_id": "target_asset_id",
        }
        for prefix, attribute in field_map.items():
            expected = value(prefix)
            if expected is not None:
                rows = [row for row in rows if getattr(row, attribute, None) == expected]
        return rows

    def scalar(self, statement):
        sql = str(statement)
        if self._entity(statement) is KnowledgeAssertion and (
            "data_source_id !=" in sql or "data_source_id <>" in sql
        ):
            return None
        rows = self._matching(statement)
        return rows[0] if rows else None

    def scalars(self, statement):
        return self._matching(statement)


def context_records():
    customer = Customer(id=uuid.uuid4(), workspace_id=uuid.uuid4(), name="Home Lab", status="active")
    site = Site(id=uuid.uuid4(), customer_id=customer.id, name="Home", status="active")
    return customer, site


def simulation_payload(customer, site):
    return SimulatedDiscoveryRequest.model_validate({
        "customer_id": customer.id,
        "site_id": site.id,
        "observations": [{
            "external_id": "manual:docker01",
            "entity_kind": "asset",
            "asset_type": "virtual_machine",
            "name": "docker01",
            "facts": {"hostname": "docker01", "status": "running"},
            "interfaces": [{
                "name": "eth0",
                "ip_address": "192.168.5.8",
                "network_name": "Apps VLAN",
                "is_primary": True,
            }],
            "relationships": [{
                "relationship_type": "runs_on",
                "target_external_id": "manual:pve1",
            }],
        }],
    })


def test_simulation_creates_run_evidence_assertions_and_new_asset_item():
    customer, site = context_records()
    pve = Asset(
        id=uuid.uuid4(), workspace_id=customer.workspace_id, customer_id=customer.id,
        site_id=site.id, name="pve1", asset_type="hypervisor_node", source="manual",
        metadata_={},
    )
    db = KnowledgeSession(customer, site, pve)

    run, evidence_count, assertion_count, items = run_simulation(
        db, payload=simulation_payload(customer, site), user_id=uuid.uuid4()
    )

    assert run.status == "completed"
    assert evidence_count == 1
    assert assertion_count == 6
    assert len([row for row in db.records if isinstance(row, DataSource)]) == 1
    assert len([row for row in db.records if isinstance(row, DiscoveryRun)]) == 1
    assert len([row for row in db.records if isinstance(row, EvidenceRecord)]) == 1
    assert len([row for row in db.records if isinstance(row, KnowledgeAssertion)]) == 6
    assert any(item.category == "newly_discovered" for item in items)
    assert any(item.entity_type == "asset_relationship" for item in items)
    assert run.summary["reconciliation_items_created"] == 2

    repeated_run, repeated_evidence, repeated_assertions, repeated_items = run_simulation(
        db, payload=simulation_payload(customer, site), user_id=uuid.uuid4()
    )
    assert repeated_run.status == "completed"
    assert repeated_evidence == 1
    assert repeated_assertions == 0
    assert repeated_items == []
    assert len([row for row in db.records if isinstance(row, DataSource)]) == 1
    assert len([row for row in db.records if isinstance(row, KnowledgeAssertion)]) == 6
    assert len([row for row in db.records if isinstance(row, ReconciliationItem)]) == 2


def test_accepting_new_asset_and_relationship_updates_operational_view():
    customer, site = context_records()
    asset_type = AssetType(key="virtual_machine", name="Virtual Machine", active=True)
    relationship_type = RelationshipType(
        key="runs_on", name="Runs on", source_label="runs on", target_label="hosts",
        directional=True, active=True,
    )
    network = Network(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Apps VLAN", network_type="vlan",
    )
    pve = Asset(
        id=uuid.uuid4(), workspace_id=customer.workspace_id, customer_id=customer.id,
        site_id=site.id, external_id="manual:pve1", name="pve1",
        asset_type="hypervisor_node", source="manual", metadata_={},
    )
    db = KnowledgeSession(customer, site, asset_type, relationship_type, network, pve)
    _, _, _, items = run_simulation(
        db, payload=simulation_payload(customer, site), user_id=uuid.uuid4()
    )
    user = SimpleNamespace(id=uuid.uuid4())

    asset_item = next(item for item in items if item.entity_type == "asset")
    docker = accept_item(db, asset_item, user)
    relationship_item = next(item for item in items if item.entity_type == "asset_relationship")
    edge = accept_item(db, relationship_item, user)

    assert docker.name == "docker01"
    assert docker.source == "discovery"
    assert asset_item.status == "accepted"
    interface = next(row for row in db.records if isinstance(row, AssetInterface))
    assert interface.asset_id == docker.id
    assert interface.network_id == network.id
    assert edge.source_asset_id == docker.id
    assert edge.target_asset_id == pve.id
    assert edge.relationship_type == "runs_on"
    assert relationship_item.status == "accepted"


def test_reject_and_defer_never_mutate_operational_asset():
    customer, site = context_records()
    asset = Asset(
        id=uuid.uuid4(), workspace_id=customer.workspace_id, customer_id=customer.id,
        site_id=site.id, name="pve1", hostname="old-name",
        asset_type="hypervisor_node", source="manual", metadata_={},
    )
    assertion = KnowledgeAssertion(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        subject_type="asset", subject_id=asset.id, predicate="hostname",
        value_json="new-name", truth_classification="observed",
        confirmation_status="unreviewed", confidence=1,
        first_observed_at=site.created_at, last_observed_at=site.created_at,
        is_current=True,
    )
    rejected = ReconciliationItem(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        category="contradiction", status="open", entity_type="asset",
        entity_id=asset.id, assertion_id=assertion.id,
        current_value_json={"field": "hostname", "value": "old-name"},
        observed_value_json={"field": "hostname", "value": "new-name"},
    )
    deferred = ReconciliationItem(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        category="changed", status="open", entity_type="asset",
        entity_id=asset.id, assertion_id=assertion.id,
        observed_value_json={"field": "hostname", "value": "later-name"},
    )
    db = KnowledgeSession(customer, site, asset, assertion, rejected, deferred)
    user = SimpleNamespace(id=uuid.uuid4())

    reject_item(db, rejected, user, "Keep the declared value")
    defer_item(db, deferred, user, "Review later")

    assert asset.hostname == "old-name"
    assert rejected.status == "rejected"
    assert deferred.status == "deferred"
    assert not [row for row in db.records if isinstance(row, AssetRelationship)]
