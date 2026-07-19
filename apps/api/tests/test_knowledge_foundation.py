import json
import uuid
from types import SimpleNamespace

from starlette.requests import Request

from app.authorization import Principal, ScopeGrant

from app.models import (
    Asset,
    AssetInterface,
    AssetRelationship,
    AssetType,
    Customer,
    DataSource,
    DiscoveryRun,
    EntitySourceLink,
    EvidenceRecord,
    KnowledgeAssertion,
    Network,
    ReconciliationItem,
    RelationshipType,
    Site,
)
from app.schemas import SimulatedDiscoveryRequest
from app.routes.knowledge import accept_reconciliation_item
from app.services.reconciliation import (
    RelationshipResolutionError,
    accept_item,
    defer_item,
    link_item_to_asset,
    relationship_resolution,
    reject_item,
)
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

    def rollback(self):
        pass

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
            "entity_type": "entity_type",
            "entity_id": "entity_id",
            "subject_id": "subject_id",
            "assertion_id": "assertion_id",
            "candidate_external_id": "candidate_external_id",
            "object_id": "object_id",
            "object_external_id": "object_external_id",
            "relationship_type": "relationship_type",
            "source_asset_id": "source_asset_id",
            "target_asset_id": "target_asset_id",
        }
        for prefix, attribute in field_map.items():
            expected = value(prefix)
            if expected is not None:
                if entity is ReconciliationItem and attribute == "data_source_id":
                    rows = [
                        row for row in rows
                        if getattr(self.get(KnowledgeAssertion, row.assertion_id), attribute, None)
                        == expected
                    ]
                elif rows and hasattr(rows[0], attribute):
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


def matched_assets_payload(customer, site, target_external_id="manual:pve1"):
    return SimulatedDiscoveryRequest.model_validate({
        "customer_id": customer.id,
        "site_id": site.id,
        "observations": [
            {
                "external_id": "manual:pve1",
                "entity_kind": "asset",
                "asset_type": "hypervisor_node",
                "name": "  PVE1  ",
                "facts": {"hostname": "pve1", "status": "active"},
            },
            {
                "external_id": "manual:docker01",
                "entity_kind": "asset",
                "asset_type": "virtual_machine",
                "name": "Docker01",
                "facts": {"hostname": "docker01", "status": "active"},
                "relationships": [{
                    "relationship_type": "runs_on",
                    "target_external_id": target_external_id,
                }],
            },
        ],
    })


def manual_asset(customer, site, name, asset_type):
    return Asset(
        id=uuid.uuid4(),
        workspace_id=customer.workspace_id,
        customer_id=customer.id,
        site_id=site.id,
        name=name,
        asset_type=asset_type,
        hostname=name.casefold(),
        status="active",
        source="manual",
        metadata_={},
    )


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


def test_manual_assets_are_strong_matched_and_relationship_accepts_without_duplicates():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    relationship_type = RelationshipType(
        key="runs_on", name="Runs on", source_label="runs on", target_label="hosts",
        directional=True, active=True,
    )
    db = KnowledgeSession(customer, site, pve, docker, relationship_type)

    _, _, _, items = run_simulation(
        db, payload=matched_assets_payload(customer, site), user_id=uuid.uuid4()
    )

    assert not [item for item in items if item.entity_type == "asset" and item.category == "newly_discovered"]
    links = [row for row in db.records if isinstance(row, EntitySourceLink)]
    assert {(link.external_id, link.entity_id) for link in links} == {
        ("manual:pve1", pve.id),
        ("manual:docker01", docker.id),
    }
    relationship_item = next(item for item in items if item.entity_type == "asset_relationship")
    resolution = relationship_resolution(db, relationship_item)
    assert resolution["resolved_source_asset_id"] == docker.id
    assert resolution["resolved_target_asset_id"] == pve.id
    assert resolution["blocked_reason"] is None
    edge = accept_item(db, relationship_item, SimpleNamespace(id=uuid.uuid4()))
    assert edge.source_asset_id == docker.id
    assert edge.target_asset_id == pve.id
    assert len([row for row in db.records if isinstance(row, Asset)]) == 2


def test_existing_relationship_is_corroborated_without_open_relationship_item():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    edge = AssetRelationship(
        id=uuid.uuid4(), source_asset_id=docker.id, target_asset_id=pve.id,
        customer_id=customer.id, site_id=site.id, relationship_type="runs_on",
        legacy_cross_context=False, metadata_={},
    )
    db = KnowledgeSession(customer, site, pve, docker, edge)

    _, evidence_count, _, items = run_simulation(
        db, payload=matched_assets_payload(customer, site), user_id=uuid.uuid4()
    )

    assert evidence_count == 2
    assert not [item for item in items if item.entity_type == "asset_relationship"]
    relationship_assertions = [
        row for row in db.records
        if isinstance(row, KnowledgeAssertion) and row.predicate == "runs_on"
    ]
    assert {row.truth_classification for row in relationship_assertions} == {
        "observed",
        "declared",
    }
    assert all(row.confirmation_status == "confirmed" for row in relationship_assertions)


def test_competing_relationship_populates_current_value_and_can_be_reconciled():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    edge = AssetRelationship(
        id=uuid.uuid4(), source_asset_id=docker.id, target_asset_id=pve.id,
        customer_id=customer.id, site_id=site.id, relationship_type="depends_on",
        legacy_cross_context=False, metadata_={},
    )
    relationship_type = RelationshipType(
        key="runs_on", name="Runs on", source_label="runs on", target_label="hosts",
        directional=True, active=True,
    )
    db = KnowledgeSession(customer, site, pve, docker, edge, relationship_type)

    _, _, _, items = run_simulation(
        db, payload=matched_assets_payload(customer, site), user_id=uuid.uuid4()
    )
    item = next(item for item in items if item.entity_type == "asset_relationship")

    assert item.category == "contradiction"
    assert item.current_value_json["relationship_id"] == edge.id
    assert item.current_value_json["relationship_type"] == "depends_on"
    accept_item(db, item, SimpleNamespace(id=uuid.uuid4()))
    assert edge.relationship_type == "runs_on"
    assert item.status == "accepted"


def test_ambiguous_match_requires_explicit_link_and_does_not_duplicate_asset():
    customer, site = context_records()
    first = manual_asset(customer, site, "docker01", "virtual_machine")
    second = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, first, second)
    payload = SimulatedDiscoveryRequest.model_validate({
        "customer_id": customer.id,
        "site_id": site.id,
        "observations": [{
            "external_id": "manual:docker01",
            "entity_kind": "asset",
            "asset_type": "virtual_machine",
            "name": "docker01",
            "facts": {"hostname": "docker01", "status": "active"},
        }],
    })

    _, _, _, items = run_simulation(db, payload=payload, user_id=uuid.uuid4())

    duplicate = next(item for item in items if item.category == "possible_duplicate")
    assert len(duplicate.current_value_json["possible_matches"]) == 2
    assert not [row for row in db.records if isinstance(row, EntitySourceLink)]
    assert len([row for row in db.records if isinstance(row, Asset)]) == 2


def test_unresolved_relationship_has_detailed_block_and_remains_open():
    customer, site = context_records()
    db = KnowledgeSession(customer, site)
    payload = simulation_payload(customer, site)
    payload.observations[0].relationships[0].target_external_id = "manual:missing-host"
    _, _, _, items = run_simulation(db, payload=payload, user_id=uuid.uuid4())
    relationship_item = next(item for item in items if item.entity_type == "asset_relationship")

    try:
        accept_item(db, relationship_item, SimpleNamespace(id=uuid.uuid4()))
        raise AssertionError("Expected relationship resolution to fail")
    except RelationshipResolutionError as exc:
        assert exc.payload["detail"] == "Relationship endpoints are unresolved"
        assert exc.payload["source_status"] == "pending_asset_acceptance"
        assert exc.payload["target_status"] == "unresolved"
        assert exc.payload["target_external_id"] == "manual:missing-host"
    assert relationship_item.status == "open"

    principal = Principal(
        user=SimpleNamespace(id=uuid.uuid4()),
        grants=(ScopeGrant(
            assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Test",
            scope_type="global", customer_id=None, site_id=None,
            permissions=frozenset({"assets.edit", "relationships.create"}),
        ),),
    )
    request = Request({
        "type": "http", "method": "POST", "path": "/test", "headers": [],
        "scheme": "http", "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    })
    response = accept_reconciliation_item(
        relationship_item.id, request, None, principal, db
    )
    body = json.loads(response.body)
    assert response.status_code == 409
    assert body["detail"] == "Relationship endpoints are unresolved"
    assert body["target_status"] == "unresolved"


def test_linking_asset_identity_unblocks_same_run_relationship():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    relationship_type = RelationshipType(
        key="runs_on", name="Runs on", source_label="runs on", target_label="hosts",
        directional=True, active=True,
    )
    db = KnowledgeSession(customer, site, pve, relationship_type)
    _, _, _, items = run_simulation(
        db, payload=simulation_payload(customer, site), user_id=uuid.uuid4()
    )
    asset_item = next(item for item in items if item.entity_type == "asset")
    relationship_item = next(item for item in items if item.entity_type == "asset_relationship")
    existing_docker = manual_asset(customer, site, "existing-docker", "virtual_machine")
    db.add(existing_docker)
    user = SimpleNamespace(id=uuid.uuid4())

    link_item_to_asset(
        db, item=asset_item, asset=existing_docker, user=user, reason="Same device"
    )
    resolution = relationship_resolution(db, relationship_item)
    assert resolution["resolved_source_asset_id"] == existing_docker.id
    assert resolution["resolved_target_asset_id"] == pve.id
    assert resolution["blocked_reason"] is None
    accept_item(db, relationship_item, user)
    assert relationship_item.status == "accepted"
    assert len([row for row in db.records if isinstance(row, Asset)]) == 2
