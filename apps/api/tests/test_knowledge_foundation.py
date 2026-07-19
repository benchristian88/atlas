import json
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from app.authorization import ActiveContext, Principal, ScopeGrant

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
    KnowledgeChange,
    Network,
    ReconciliationItem,
    RelationshipType,
    RunObservedEntity,
    Site,
)
from app.schemas import AssetKnowledgeSummaryResponse, SimulatedDiscoveryRequest
from app.routes.knowledge import (
    accept_reconciliation_item,
    simulate_discovery,
)
from app.routes.changes import get_asset_knowledge_summary
from app.services.reconciliation import (
    RelationshipResolutionError,
    accept_item,
    create_item,
    defer_item,
    link_item_to_asset,
    relationship_resolution,
    reject_item,
)
from app.services.knowledge_assertions import accept_assertion, record_assertion
from app.services.knowledge_summary import asset_knowledge_summary
from app.services.manual_knowledge import declare_asset_changes
from app.services.predicate_definitions import predicate_cardinality
from app.services.simulated_discovery import run_simulation
from app.services.discovery_observations import reconcile_complete_snapshot
from app.utils.json_values import to_json_value


class KnowledgeSession:
    """Small identity-map fake for deterministic service-level pipeline tests."""

    def __init__(self, *records):
        self.records = list(records)
        self.commits = 0
        self.rollbacks = 0

    def add(self, record):
        self.records.append(record)

    def flush(self):
        now = datetime.now(timezone.utc)
        for record in self.records:
            if getattr(record, "id", None) is None:
                record.id = uuid.uuid4()
            for field in ("created_at", "updated_at"):
                if hasattr(record, field) and getattr(record, field) is None:
                    setattr(record, field, now)
            for field in (
                "raw_payload",
                "summary",
                "payload_json",
                "value_json",
                "current_value_json",
                "observed_value_json",
                "previous_value_json",
                "new_value_json",
                "metadata_json",
                "metadata_",
                "value",
                "value_",
            ):
                if hasattr(record, field):
                    value = getattr(record, field)
                    if value is not None:
                        json.dumps(value)

    def commit(self):
        self.flush()
        self.commits += 1

    def refresh(self, record):
        pass

    def rollback(self):
        self.rollbacks += 1

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
            "discovery_run_id": "discovery_run_id",
            "coverage_key": "coverage_key",
            "completeness_status": "completeness_status",
            "source_type": "source_type",
        }
        statement_sql = str(statement)
        for prefix, attribute in field_map.items():
            expected = value(prefix)
            if expected is not None:
                if (
                    entity is KnowledgeAssertion
                    and attribute == "data_source_id"
                    and (
                        "knowledge_assertions.data_source_id !=" in statement_sql
                        or "knowledge_assertions.data_source_id <>" in statement_sql
                    )
                ):
                    rows = [
                        row
                        for row in rows
                        if getattr(row, attribute, None) != expected
                    ]
                    continue
                if entity is ReconciliationItem and attribute == "data_source_id":
                    rows = [
                        row for row in rows
                        if getattr(self.get(KnowledgeAssertion, row.assertion_id), attribute, None)
                        == expected
                    ]
                elif rows and hasattr(rows[0], attribute):
                    rows = [row for row in rows if getattr(row, attribute, None) == expected]
        sql = statement_sql
        if entity is KnowledgeAssertion:
            if "knowledge_assertions.is_source_current IS true" in sql:
                rows = [row for row in rows if bool(row.is_source_current)]
            if "knowledge_assertions.is_accepted IS true" in sql:
                rows = [row for row in rows if bool(row.is_accepted)]
            if "knowledge_assertions.retracted_at IS NULL" in sql:
                rows = [row for row in rows if row.retracted_at is None]
            if "knowledge_assertions.id !=" in sql or "knowledge_assertions.id <>" in sql:
                excluded = value("id")
                if excluded is not None:
                    rows = [row for row in rows if row.id != excluded]
        return rows

    def scalar(self, statement):
        sql = str(statement)
        if self._entity(statement) is DiscoveryRun and "discovery_runs.id !=" in sql:
            params = self._params(statement)
            excluded = next(value for key, value in params.items() if key.startswith("id_"))
            rows = [row for row in self._matching(statement) if row.id != excluded]
            rows.sort(key=lambda row: row.finished_at or row.started_at, reverse=True)
            return rows[0] if rows else None
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
    observations = [row for row in db.records if isinstance(row, RunObservedEntity)]
    assert len(observations) == 1
    assert isinstance(observations[0].id, uuid.UUID)
    assert observations[0].external_id == "manual:docker01"
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
    assert len([row for row in db.records if isinstance(row, RunObservedEntity)]) == 2


def test_run_observed_entity_flush_populates_uuid_without_explicit_id():
    customer, site = context_records()
    source = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Test source", source_type="simulated_discovery", status="active",
    )
    run = DiscoveryRun(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        data_source_id=source.id, status="running", coverage_key="test",
        is_complete_snapshot=False, completeness_status="unknown",
    )
    row = RunObservedEntity(
        discovery_run_id=run.id,
        data_source_id=source.id,
        customer_id=customer.id,
        site_id=site.id,
        coverage_key="test",
        entity_type="asset",
        external_id="manual:docker01",
        observed_at=datetime.now(timezone.utc),
    )
    assert row.id is None
    db = KnowledgeSession(customer, site, source, run, row)

    db.flush()

    assert isinstance(row.id, uuid.UUID)


def complete_payload(customer, site, names):
    return SimulatedDiscoveryRequest.model_validate({
        "customer_id": customer.id,
        "site_id": site.id,
        "coverage_key": "homelab-assets",
        "is_complete_snapshot": True,
        "observations": [{
            "external_id": f"manual:{name}",
            "entity_kind": "asset",
            "asset_type": "hypervisor_node" if name == "pve1" else "virtual_machine",
            "name": name,
            "facts": {"hostname": name, "status": "active"},
        } for name in names],
    })


def test_complete_snapshot_detects_missing_once_without_mutating_asset():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, pve, docker)

    first, _, _, first_items = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    second, _, _, second_items = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1"]), user_id=uuid.uuid4()
    )
    missing = [item for item in second_items if item.category == "no_longer_observed"]

    assert first.completeness_status == "complete"
    assert first.snapshot_reconciliation.baseline_run_id is None
    assert not [item for item in first_items if item.category == "no_longer_observed"]
    assert second.snapshot_reconciliation.baseline_run_id == first.id
    assert len(missing) == 1
    assert missing[0].entity_id == docker.id
    assert docker.status == "active"
    assert any(
        isinstance(row, KnowledgeChange)
        and row.change_type == "entity_no_longer_observed"
        for row in db.records
    )

    third, _, _, third_items = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1"]), user_id=uuid.uuid4()
    )
    assert third.snapshot_reconciliation.no_longer_observed_count == 0
    assert not [item for item in third_items if item.category == "no_longer_observed"]


def test_partial_snapshot_never_creates_missing_items():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, pve, docker)
    run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    payload = complete_payload(customer, site, ["pve1"])
    payload.is_complete_snapshot = False
    run, _, _, items = run_simulation(db, payload=payload, user_id=uuid.uuid4())
    assert run.completeness_status == "partial"
    assert not [item for item in items if item.category == "no_longer_observed"]


def test_different_coverage_key_does_not_compare_snapshots():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, pve, docker)
    run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    payload = complete_payload(customer, site, ["pve1"])
    payload.coverage_key = "different-coverage"
    run, _, _, items = run_simulation(db, payload=payload, user_id=uuid.uuid4())
    assert run.snapshot_reconciliation.baseline_run_id is None
    assert not [item for item in items if item.category == "no_longer_observed"]


def test_failed_complete_run_cannot_process_absence():
    customer, site = context_records()
    source = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Test source", source_type="simulated_discovery", status="active",
    )
    run = DiscoveryRun(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        data_source_id=source.id, status="failed", coverage_key="homelab-assets",
        is_complete_snapshot=True, completeness_status="complete",
    )
    db = KnowledgeSession(customer, site, source, run)
    result = reconcile_complete_snapshot(db, run=run, user_id=uuid.uuid4())
    assert result.no_longer_observed_count == 0
    assert result.items == []


def test_reobserved_entity_resolves_missing_episode():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, pve, docker)
    run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    _, _, _, missing_items = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1"]), user_id=uuid.uuid4()
    )
    missing = next(item for item in missing_items if item.category == "no_longer_observed")
    run, _, _, _ = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    assert run.snapshot_reconciliation.reobserved_count == 1
    assert missing.status == "accepted"
    assert missing.decision_reason.startswith("Automatically resolved")
    assert any(
        isinstance(row, KnowledgeChange) and row.change_type == "entity_reobserved"
        for row in db.records
    )


def test_absence_decision_changes_status_but_never_deletes_asset():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, pve, docker)
    run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    _, _, _, items = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1"]), user_id=uuid.uuid4()
    )
    item = next(row for row in items if row.category == "no_longer_observed")
    user = SimpleNamespace(id=uuid.uuid4())

    result = accept_item(
        db,
        item,
        user,
        disposition="mark_inactive",
        reason="Removed from service",
    )

    assert result is docker
    assert docker in db.records
    assert docker.status == "inactive"
    assert item.status == "accepted"
    assert item.decision_reason == "Removed from service"
    with pytest.raises(HTTPException, match="already been decided"):
        accept_item(db, item, user, disposition="retire")


def test_retired_asset_is_not_silently_reactivated_when_reobserved():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, pve, docker)
    run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    _, _, _, items = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1"]), user_id=uuid.uuid4()
    )
    missing = next(row for row in items if row.category == "no_longer_observed")
    accept_item(
        db,
        missing,
        SimpleNamespace(id=uuid.uuid4()),
        disposition="mark_retired",
    )
    run, _, _, items = run_simulation(
        db, payload=complete_payload(customer, site, ["pve1", "docker01"]), user_id=uuid.uuid4()
    )
    assert run.snapshot_reconciliation.reobserved_count == 1
    assert docker.status == "retired"
    assert not [
        item for item in items
        if item.category == "changed" and item.entity_id == docker.id
    ]

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
    assert {row.change_type for row in db.records if isinstance(row, KnowledgeChange)} >= {
        "entity_discovered",
        "entity_accepted",
        "relationship_added",
    }


def test_accepting_changed_fact_records_one_meaningful_change():
    customer, site = context_records()
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    asset.hostname = "docker01"
    assertion = KnowledgeAssertion(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        subject_type="asset", subject_id=asset.id, subject_external_id="manual:docker01",
        predicate="hostname", value_json="docker-prod-01", truth_classification="observed",
        confirmation_status="unreviewed", confidence=1,
        first_observed_at=site.created_at, last_observed_at=site.created_at,
        is_current=True,
    )
    item = ReconciliationItem(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        category="changed", status="open", entity_type="asset", entity_id=asset.id,
        assertion_id=assertion.id,
        current_value_json={"field": "hostname", "value": "docker01"},
        observed_value_json={"field": "hostname", "value": "docker-prod-01"},
    )
    db = KnowledgeSession(customer, site, asset, assertion, item)

    accept_item(db, item, SimpleNamespace(id=uuid.uuid4()))

    assert asset.hostname == "docker-prod-01"
    assert assertion.is_accepted is True
    changes = [row for row in db.records if isinstance(row, KnowledgeChange)]
    assert [row.change_type for row in changes] == ["fact_changed"]
    assert changes[0].previous_value_json["value"] == "docker01"


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
    assert assertion.confirmation_status == "conflicted"
    assert assertion.is_source_current is True
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
    assert resolution["resolved_source_asset_id"] == str(docker.id)
    assert resolution["resolved_target_asset_id"] == str(pve.id)
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
    assert item.current_value_json["relationship_id"] == str(edge.id)
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
    assert resolution["resolved_source_asset_id"] == str(existing_docker.id)
    assert resolution["resolved_target_asset_id"] == str(pve.id)
    assert resolution["blocked_reason"] is None
    accept_item(db, relationship_item, user)
    assert relationship_item.status == "accepted"
    assert len([row for row in db.records if isinstance(row, Asset)]) == 2
    assert any(
        isinstance(row, KnowledgeChange) and row.change_type == "source_linked"
        for row in db.records
    )


def assertion_record(customer, site):
    return KnowledgeAssertion(
        id=uuid.uuid4(),
        customer_id=customer.id,
        site_id=site.id,
        subject_type="asset",
        predicate="test",
        truth_classification="observed",
        confirmation_status="unreviewed",
        confidence=1,
        first_observed_at=datetime.now(timezone.utc),
        last_observed_at=datetime.now(timezone.utc),
        is_current=True,
    )


def test_create_item_normalizes_nested_uuids_in_current_json():
    customer, site = context_records()
    assertion = assertion_record(customer, site)
    db = KnowledgeSession(customer, site, assertion)
    first_id, second_id = uuid.uuid4(), uuid.uuid4()

    item, created = create_item(
        db,
        assertion=assertion,
        category="contradiction",
        entity_type="asset_relationship",
        entity_id=None,
        current_value={"relationship_id": first_id, "nested": [{"asset_id": second_id}]},
        observed_value=None,
        recommended_action="Review",
    )

    assert created is True
    assert item.current_value_json == {
        "relationship_id": str(first_id),
        "nested": [{"asset_id": str(second_id)}],
    }
    json.dumps(item.current_value_json)


def test_create_item_normalizes_nested_uuids_in_observed_json():
    customer, site = context_records()
    assertion = assertion_record(customer, site)
    db = KnowledgeSession(customer, site, assertion)
    source_id, target_id = uuid.uuid4(), uuid.uuid4()

    item, _ = create_item(
        db,
        assertion=assertion,
        category="inferred_relationship",
        entity_type="asset_relationship",
        entity_id=None,
        current_value="No current relationship",
        observed_value={
            "resolved_source_asset_id": source_id,
            "nested": {"targets": [target_id, {"source": source_id}]},
        },
        recommended_action="Create relationship",
    )

    assert item.observed_value_json["resolved_source_asset_id"] == str(source_id)
    assert item.observed_value_json["nested"]["targets"] == [
        str(target_id),
        {"source": str(source_id)},
    ]
    json.dumps(item.observed_value_json)


class JsonState(Enum):
    READY = "ready"


class JsonPayload(BaseModel):
    identity: uuid.UUID
    state: JsonState


def test_json_normalizer_handles_datetime_date_enum_and_pydantic_models():
    identity = uuid.uuid4()
    timestamp = datetime(2026, 7, 19, 12, 30, tzinfo=timezone.utc)
    day = date(2026, 7, 19)
    result = to_json_value({
        "timestamp": timestamp,
        "day": day,
        "state": JsonState.READY,
        "model": JsonPayload(identity=identity, state=JsonState.READY),
    })

    assert result == {
        "timestamp": timestamp.isoformat(),
        "day": day.isoformat(),
        "state": "ready",
        "model": {"identity": str(identity), "state": "ready"},
    }
    json.dumps(result)


def test_assertion_value_is_normalized_before_flush():
    customer, site = context_records()
    db = KnowledgeSession(customer, site)
    identity = uuid.uuid4()

    assertion, created = record_assertion(
        db,
        customer_id=customer.id,
        site_id=site.id,
        subject_type="asset",
        predicate="nested",
        value={"identity": identity, "seen": datetime.now(timezone.utc)},
    )

    assert created is True
    assert assertion.value_json["identity"] == str(identity)
    json.dumps(assertion.value_json)


def test_simulated_relationship_route_returns_json_safe_resolution_ids():
    customer, site = context_records()
    pve = manual_asset(customer, site, "pve1", "hypervisor_node")
    docker = manual_asset(customer, site, "docker01", "virtual_machine")
    relationship_type = RelationshipType(
        key="runs_on", name="Runs on", source_label="runs on", target_label="hosts",
        directional=True, active=True,
    )
    db = KnowledgeSession(customer, site, pve, docker, relationship_type)
    principal = Principal(
        user=SimpleNamespace(
            id=uuid.uuid4(), email="test@example.com", display_name="Test User"
        ),
        grants=(ScopeGrant(
            assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Test",
            scope_type="global", customer_id=None, site_id=None,
            permissions=frozenset({"integrations.manage"}),
        ),),
    )
    request = Request({
        "type": "http", "method": "POST", "path": "/api/discovery/simulate",
        "headers": [], "scheme": "http", "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    })

    response = simulate_discovery(
        matched_assets_payload(customer, site),
        request,
        ActiveContext(customer.id, site.id),
        principal,
        db,
    )

    relationship = next(
        item for item in response["reconciliation_items"]
        if item["entity_type"] == "asset_relationship"
    )
    assert relationship["resolved_source_asset_id"] == str(docker.id)
    assert relationship["resolved_target_asset_id"] == str(pve.id)
    assert relationship["observed_value_json"]["resolved_source_asset_id"] == str(docker.id)
    observations = [row for row in db.records if isinstance(row, RunObservedEntity)]
    assert len(observations) == 2
    assert {row.external_id for row in observations} == {
        "manual:pve1",
        "manual:docker01",
    }
    assert all(isinstance(row.id, uuid.UUID) for row in observations)
    assert db.commits == 1
    json.dumps(to_json_value(response))


def test_simulation_route_rolls_back_an_unexpected_failure(monkeypatch):
    customer, site = context_records()
    db = KnowledgeSession(customer, site)
    principal = Principal(
        user=SimpleNamespace(
            id=uuid.uuid4(), email="test@example.com", display_name="Test User"
        ),
        grants=(ScopeGrant(
            assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Test",
            scope_type="global", customer_id=None, site_id=None,
            permissions=frozenset({"integrations.manage"}),
        ),),
    )
    request = Request({
        "type": "http", "method": "POST", "path": "/api/discovery/simulate",
        "headers": [], "scheme": "http", "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    })

    def fail(*args, **kwargs):
        raise RuntimeError("unexpected persistence failure")

    monkeypatch.setattr("app.routes.knowledge.run_simulation", fail)
    with pytest.raises(RuntimeError, match="unexpected persistence failure"):
        simulate_discovery(
            simulation_payload(customer, site),
            request,
            ActiveContext(customer.id, site.id),
            principal,
            db,
        )
    assert db.rollbacks == 1
    assert db.commits == 0


def test_predicate_cardinality_distinguishes_scalar_and_multi_valued_knowledge():
    assert predicate_cardinality("asset_type") == "single"
    assert predicate_cardinality("interface") == "multi"
    assert predicate_cardinality("owner") == "multi"
    assert predicate_cardinality("service_owner") == "single"
    assert predicate_cardinality("runs_on", object_type="asset") == "multi"


def test_new_discovery_value_is_source_current_but_not_automatically_accepted():
    customer, site = context_records()
    source = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Discovery", source_type="simulated_discovery", status="active",
    )
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, source, asset)

    first, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="hostname", value="docker01",
        data_source_id=source.id,
    )
    second, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="hostname", value="docker-new",
        data_source_id=source.id,
    )

    assert first.is_source_current is False
    assert first.is_current is False
    assert second.is_source_current is True
    assert second.is_accepted is False


def test_multi_valued_relationship_assertions_remain_current_from_one_source():
    customer, site = context_records()
    source = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Discovery", source_type="simulated_discovery", status="active",
    )
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    db = KnowledgeSession(customer, site, source, asset)
    first, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="depends_on", object_type="asset",
        object_id=uuid.uuid4(), data_source_id=source.id,
    )
    second, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="depends_on", object_type="asset",
        object_id=uuid.uuid4(), data_source_id=source.id,
    )
    assert first.is_source_current is True
    assert second.is_source_current is True
    accept_assertion(db, first, user_id=uuid.uuid4())
    accept_assertion(db, second, user_id=uuid.uuid4())
    assert first.is_accepted is True
    assert second.is_accepted is True


def test_manual_asset_edit_creates_one_accepted_declaration_and_conflict():
    customer, site = context_records()
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    observed_source = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Proxmox", source_type="proxmox", status="active",
    )
    observed = KnowledgeAssertion(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        subject_type="asset", subject_id=asset.id, predicate="hostname",
        value_json="docker-discovered", truth_classification="observed",
        confirmation_status="conflicted", data_source_id=observed_source.id,
        confidence=1, first_observed_at=datetime.now(timezone.utc),
        last_observed_at=datetime.now(timezone.utc), is_current=True,
        is_source_current=True, is_accepted=False,
    )
    db = KnowledgeSession(customer, site, asset, observed_source, observed)
    previous = asset.hostname
    asset.hostname = "docker-manual"

    created = declare_asset_changes(
        db, asset=asset, previous_values={"hostname": previous},
        actor_user_id=uuid.uuid4(),
    )
    repeated = declare_asset_changes(
        db, asset=asset, previous_values={"hostname": asset.hostname},
        actor_user_id=uuid.uuid4(),
    )

    assert len(created) == 1
    assert repeated == []
    assert created[0].truth_classification == "declared"
    assert created[0].is_accepted is True
    assert observed.is_source_current is True
    assert any(
        isinstance(row, ReconciliationItem)
        and row.category == "contradiction"
        for row in db.records
    )
    changes = [row for row in db.records if isinstance(row, KnowledgeChange)]
    assert len(changes) == 1
    assert changes[0].change_type == "fact_changed"


def test_accepting_single_value_clears_previous_accepted_assertion():
    customer, site = context_records()
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    source_a = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Manual", source_type="manual", status="active",
    )
    source_b = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Discovery", source_type="proxmox", status="active",
    )
    db = KnowledgeSession(customer, site, asset, source_a, source_b)
    declared, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="asset_type", value="virtual_machine",
        truth_classification="declared", data_source_id=source_a.id,
    )
    accept_assertion(db, declared, user_id=uuid.uuid4())
    observed, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="asset_type", value="container",
        data_source_id=source_b.id,
    )
    accept_assertion(db, observed, user_id=uuid.uuid4())
    assert declared.is_accepted is False
    assert observed.is_accepted is True


def test_knowledge_summary_rolls_up_accepted_value_and_conflicting_sources():
    customer, site = context_records()
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    manual = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Atlas Manual Inventory", source_type="manual", status="active",
    )
    proxmox = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Proxmox", source_type="proxmox", status="active",
    )
    db = KnowledgeSession(customer, site, asset, manual, proxmox)
    declared, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="hostname", value="docker01",
        truth_classification="declared", data_source_id=manual.id,
    )
    accept_assertion(db, declared, user_id=None)
    record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="hostname", value="docker01-new",
        data_source_id=proxmox.id,
    )

    result = asset_knowledge_summary(db, asset)
    AssetKnowledgeSummaryResponse.model_validate(result)
    hostname = next(item for item in result["groups"] if item["predicate"] == "hostname")
    assert hostname["accepted"]["value"] == "docker01"
    assert hostname["latest_observations"][0]["value"] == "docker01-new"
    assert hostname["conflict"] is True
    assert hostname["assertion_count"] == 2
    assert hostname["source_count"] == 2
    assert hostname["latest_observations"][0]["conflicts_with_accepted"] is True
    assert result["conflict_count"] == 1


def test_historical_rejected_and_retracted_values_do_not_create_active_conflict():
    customer, site = context_records()
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    manual = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Manual", source_type="manual", status="active",
    )
    discovery = DataSource(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        name="Discovery", source_type="proxmox", status="active",
    )
    db = KnowledgeSession(customer, site, asset, manual, discovery)
    declared, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="status", value="active",
        truth_classification="declared", data_source_id=manual.id,
    )
    accept_assertion(db, declared)
    historical, _ = record_assertion(
        db, customer_id=customer.id, site_id=site.id, subject_type="asset",
        subject_id=asset.id, predicate="status", value="inactive",
        data_source_id=discovery.id,
    )
    historical.is_source_current = False
    historical.is_current = False
    historical.confirmation_status = "superseded"

    result = asset_knowledge_summary(db, asset)
    status = next(item for item in result["groups"] if item["predicate"] == "status")
    assert status["conflict"] is False
    assert status["historical_count"] == 1


def test_multiple_unaccepted_source_values_are_reported_as_unresolved():
    customer, site = context_records()
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    sources = [
        DataSource(
            id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
            name=f"Source {index}", source_type="proxmox", status="active",
        )
        for index in (1, 2)
    ]
    db = KnowledgeSession(customer, site, asset, *sources)
    for source, value in zip(sources, ("virtual_machine", "lxc_container")):
        record_assertion(
            db, customer_id=customer.id, site_id=site.id,
            subject_type="asset", subject_id=asset.id,
            predicate="asset_type", value=value, data_source_id=source.id,
        )
    result = asset_knowledge_summary(db, asset)
    asset_type = next(
        item for item in result["groups"] if item["predicate"] == "asset_type"
    )
    assert asset_type["accepted"] is None
    assert asset_type["accepted_values"] == []
    assert asset_type["unresolved"] is True


def test_asset_knowledge_summary_tolerates_missing_optional_provenance():
    customer, site = context_records()
    asset = manual_asset(customer, site, "docker01", "virtual_machine")
    assertion = KnowledgeAssertion(
        id=uuid.uuid4(), customer_id=customer.id, site_id=site.id,
        subject_type="asset", subject_id=asset.id, predicate="asset_type",
        value_json="virtual_machine", truth_classification="declared",
        confirmation_status="confirmed", data_source_id=uuid.uuid4(),
        confidence=1, first_observed_at=datetime.now(timezone.utc),
        last_observed_at=datetime.now(timezone.utc), is_current=True,
        is_source_current=True, is_accepted=True,
        accepted_at=datetime.now(timezone.utc),
        accepted_by_user_id=uuid.uuid4(),
    )
    db = KnowledgeSession(customer, site, asset, assertion)
    principal = Principal(
        user=SimpleNamespace(id=uuid.uuid4()),
        grants=(ScopeGrant(
            assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Test",
            scope_type="global", customer_id=None, site_id=None,
            permissions=frozenset({"assets.view"}),
        ),),
    )

    response = get_asset_knowledge_summary(asset.id, principal, db)

    group = response["groups"][0]
    assert group["accepted"]["source_name"] is None
    assert group["accepted"]["actor_name"] is None
