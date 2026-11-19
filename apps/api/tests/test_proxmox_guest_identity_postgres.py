"""Proxmox 0.2.2-shaped synthetic AIP messages through real PostgreSQL and HTTP."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, or_, select, text

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import SessionLocal, get_db
from app.models import (Asset, AssetInterface, AssetRelationship, AssetType, AuditEvent, Customer,
    DataSource, DiscoveryBatchReceipt, DiscoveryRun, EntitySourceLink, EvidenceRecord, Integration,
    KnowledgeAssertion, KnowledgeChange, ReconciliationItem, RelationshipType, RunObservedEntity, Site, Workspace)
from app.routes import assets, context, integration_discovery, knowledge
from app.services import discovery_tokens
from app.services.connector_contracts import SDK_VERSION
from app.services.connector_mappings import require_resolved
from app.services.discovery_orchestration import scope_encoding
from tests.i3_fixtures import message
from tests.test_administration import make_principal
from tests.test_knowledge_integrity_migration import migrated_history, pytestmark

RELEASE = Path(__file__).parent / "fixtures/local_release"
DIGEST = "2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf"
MAC_A = "02:00:00:00:00:0a"
MAC_B = "02:00:00:00:00:0b"


@pytest.fixture
def cases(migrated_history, tmp_path, monkeypatch):
    migrated_history.migrate("upgrade", "head")
    monkeypatch.setenv("ATLAS_STATE_DIR", str(tmp_path))
    discovery_tokens.provision_signing_key()
    engine = migrated_history.engine
    manifest = json.loads((RELEASE / "manifest.json").read_text())

    def session():
        return SessionLocal(bind=engine)

    with session() as db:
        for declaration in manifest["object_classes"]:
            key = declaration.get("recommended_asset_type_key")
            if key and db.scalar(select(AssetType).where(AssetType.key == key)) is None:
                db.add(AssetType(key=key, name=key, active=True))
        for declaration in manifest["relationship_classes"]:
            key = declaration["recommended_relationship_type_key"]
            if db.scalar(select(RelationshipType).where(RelationshipType.key == key)) is None:
                db.add(RelationshipType(key=key, name=key, directional=True, active=True))
        db.flush()
        mappings = require_resolved(db, manifest, auto_map=True)
        db.commit()

    def build(kind="lxc", *, alongside=None, same_site=False):
        principal = make_principal("reconciliation.view", "reconciliation.decide", "assets.view", "assets.create", "sites.view",
            "assets.edit", "networks.view", "networks.create", "networks.edit", "relationships.view", "relationships.create",
            "assertions.retract", "assertions.delete", "discovery.simulate")
        principal.user.email = f"{uuid.uuid4().hex}@example.test"
        with session() as db:
            db.add(principal.user)
            if alongside is None:
                workspace = Workspace(name="Guest identity", slug=uuid.uuid4().hex)
                db.add(workspace)
                db.flush()
                customer = Customer(workspace_id=workspace.id, name="Guest identity")
                db.add(customer)
                db.flush()
                customer_id = customer.id
            else:
                customer_id = alongside.customer_id
            if same_site:
                site_id = alongside.site_id
            else:
                site = Site(customer_id=customer_id, name="Second site" if alongside else "Guest identity")
                db.add(site)
                db.flush()
                site_id = site.id
            source = DataSource(customer_id=customer_id, site_id=site_id, name="Proxmox test source",
                source_type="connector", status="active")
            db.add(source)
            db.flush()
            integration = Integration(customer_id=customer_id, site_id=site_id, data_source_id=source.id,
                plugin_id="proxmox", connector_id="proxmox", connector_version="0.2.2", connector_digest=DIGEST,
                name="Proxmox test integration", base_url="", username_or_token_id="", secret_reference="",
                selected_scopes=["inventory"], config_schema_version="1.0", config_json={}, creation_key=uuid.uuid4())
            db.add(integration)
            coverage, classes = scope_encoding(integration, manifest, mappings)
            provenance = dict(connector_id="proxmox", connector_version="0.2.2", connector_digest=DIGEST,
                sdk_version=SDK_VERSION, aip_version="1.0", manifest=manifest, mappings=mappings, object_classes=classes)
            db.commit()

        app = FastAPI()
        for router in (assets.router, context.router, integration_discovery.router, knowledge.router):
            app.include_router(router)

        def request_db(request: Request):
            with session() as db:
                db.connection(execution_options={"test_actor": request.headers.get("x-test-actor")})
                yield db

        app.dependency_overrides[get_db] = request_db
        app.dependency_overrides[get_principal] = lambda: principal
        app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer_id, site_id)
        return Case(TestClient(app), session, engine, integration, principal, coverage, provenance, kind)

    return build


class Case:
    def __init__(self, client, session, engine, integration, principal, coverage, provenance, kind):
        self.client, self.session, self.engine = client, session, engine
        self.integration, self.principal, self.coverage, self.provenance = integration, principal, coverage, provenance
        self.customer_id, self.site_id, self.source_id = integration.customer_id, integration.site_id, integration.data_source_id
        self.kind, self.guest = kind, f"guest/{kind}/1029"
        self.nic = self.guest + "/interface/net0"

    def stage(self, *, name=None, mac=MAC_A, bridge="vmbr0", node="node-a", extra=False,
              completeness="complete", coverage_key=None, stamp=None, observed_stamp=None,
              secondary=False, dependencies_only=False, mismatched_interface_owner=False,
              guest_relationship_only=False, relationship_target=None):
        stamp = stamp or datetime.now(timezone.utc)
        with self.session() as db:
            coverage = dict(self.coverage, key=coverage_key or self.coverage["key"])
            run = DiscoveryRun(integration_id=self.integration.id, data_source_id=self.source_id, customer_id=self.customer_id,
                site_id=self.site_id, status="pending", started_at=stamp, created_by_user_id=self.principal.user.id,
                coverage_key=coverage["key"], is_complete_snapshot=True, completeness_status="unknown",
                execution_provenance=dict(self.provenance, coverage=coverage), dispatch_state="settled",
                ingestion_generation=uuid.uuid4(), deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5))
            db.add(run)
            db.commit()
            headers = {"Authorization": "Bearer " + discovery_tokens.mint(run)}
        batch = message(run, assets=False)
        batch["observed_at"] = (observed_stamp or stamp).isoformat()
        batch["assets"] = [{"external_id": f"node/{node}", "object_class": "proxmox.node", "name": node, "facts": []}]
        if extra:
            batch["assets"].append({"external_id": "node/unrelated", "object_class": "proxmox.node",
                "name": "Unrelated node", "facts": []})
        for name_, cidr in (("vmbr0", "192.0.2.0/24"), ("vmbr1", "198.51.100.0/24")):
            batch["networks"].append({"external_id": f"network/{node}/{name_}", "object_class": "proxmox.network",
                "name": name_, "network_type": "lan", "cidr": cidr, "facts": []})
        if name:
            batch["assets"].append({"external_id": self.guest, "object_class": f"proxmox.{self.kind}", "name": name,
                "facts": [{"key": "proxmox.vmid", "value_type": "integer", "class": "identity", "cardinality": "single", "value": 1029}]})
            batch["interfaces"].append({"external_id": self.nic, "object_class": "proxmox.interface",
                "asset_external_id": self.guest, "network_external_id": f"network/{node}/{bridge}",
                "name": "eth0" if self.kind == "lxc" else "net0", "mac_address": mac,
                "ip_address": "192.0.2.24" if bridge == "vmbr0" else "198.51.100.24", "is_primary": False,
                "facts": [{"key": "proxmox.bridge_name", "value_type": "string", "class": "configuration",
                           "cardinality": "single", "value": bridge}]})
            target = relationship_target or f"node/{node}"
            endpoints = ["runs_on", self.guest, target]
            suffix = hashlib.sha256(json.dumps(endpoints, separators=(",", ":")).encode()).hexdigest()
            batch["relationships"].append({"external_id": f"relationship/{suffix}", "relationship_class": "proxmox.runs_on",
                "source": {"kind": "asset", "external_id": self.guest},
                "target": {"kind": "asset", "external_id": target}, "truth_classification": "observed", "confidence": 1.0})
        if secondary:
            batch["interfaces"].append(dict(batch["interfaces"][0], external_id=self.guest + "/interface/net1", name="eth1"))
        if dependencies_only or guest_relationship_only:
            batch["assets"] = [row for row in batch["assets"] if row["external_id"] != self.guest]
        if guest_relationship_only:
            batch["interfaces"] = []
        if mismatched_interface_owner:
            # AIP permits the owner field to disagree with a slot-shaped key.
            # This semantic edge case is synthetic; 0.2.2 emits matching owners.
            batch["interfaces"][0].update(external_id=self.guest + "/interface/net1", asset_external_id=f"node/{node}")
            batch["relationships"] = []
        reply = self.client.post(f"/integration-ingestion/{run.id}/batches", headers=headers, json=batch)
        assert reply.status_code == 200, reply.text
        completion = message(run, completion=completeness)
        completion["observed_at"] = batch["observed_at"]
        endpoint = "failure" if completeness == "failed" else "completion"
        return SimpleNamespace(id=run.id, headers=headers, body=completion, batch=batch,
                               url=f"/integration-ingestion/{run.id}/{endpoint}")

    def complete(self, staged, *, expected=200, actor="completion"):
        reply = self.client.post(staged.url, headers={**staged.headers, "x-test-actor": actor}, json=staged.body)
        assert reply.status_code == expected, reply.text
        return reply.json()

    def run(self, **options):
        staged = self.stage(**options)
        assert self.complete(staged)["replayed"] is False
        return staged

    def groups(self, **filters):
        response = self.client.get("/reconciliation-entities", params={"limit": 100, **filters})
        assert response.status_code == 200, response.text
        return response.json()["entities"]

    def proposal(self, external, predicate, **filters):
        rows = [(group, row) for group in self.groups(source_id=self.source_id, **filters) for row in
                ([group["parent"]] if group["parent"] else []) + [r for section in group["sections"] for r in section["items"]]
                if row["candidate_external_id"] == external and row["assertion_predicate"] == predicate and row["status"] == "open"]
        assert len(rows) == 1, rows
        return rows[0]

    def identity_reviews(self):
        return [row for row in self.groups(source_id=self.source_id) if row["type_label"] == "Identity review"]

    def accept(self, external, predicate, **body):
        _, row = self.proposal(external, predicate)
        reply = self.decide(row, **body)
        assert reply.status_code == 200, reply.text
        return uuid.UUID(reply.json()["entity_id"])

    def decide(self, row, action="accept", *, actor="review", **body):
        return self.client.post(f"/reconciliation-items/{row['id']}/{action}", headers={"x-test-actor": actor},
                                json={"expected_version": row["version"], **body})

    def seed(self):
        self.run(name="guest-a")
        self.accept("node/node-a", "name")
        asset = self.accept(self.guest, "name")
        network = self.accept("network/node-a/vmbr0", "configuration")
        self.accept("network/node-a/vmbr1", "configuration")
        interface = self.accept(self.nic, "configuration")
        self.accept(self.guest, "proxmox.vmid")
        self.accept(self.nic, "proxmox.bridge_name")
        relationship = self.accept(self.guest, "runs_on")
        return SimpleNamespace(asset=asset, interface=interface, network=network, relationship=relationship)

    def retire(self):
        self.run()
        return self.accept(self.guest, "observation_state", disposition="retire")

    def snapshot(self, prior):
        with self.session() as db:
            def rows(model, *conditions):
                return {row.id: {field.key: getattr(row, field.key) for field in model.__mapper__.column_attrs}
                        for row in db.scalars(select(model).where(*conditions))}
            assertions = rows(KnowledgeAssertion, KnowledgeAssertion.customer_id == self.customer_id, or_(
                KnowledgeAssertion.subject_id.in_([prior.asset, prior.interface]),
                KnowledgeAssertion.object_id == prior.asset))
            items = rows(ReconciliationItem, ReconciliationItem.assertion_id.in_(assertions))
            return {
                "asset": rows(Asset, Asset.id == prior.asset),
                "interface": rows(AssetInterface, AssetInterface.asset_id == prior.asset),
                "edges": rows(AssetRelationship, or_(AssetRelationship.source_asset_id == prior.asset,
                                                     AssetRelationship.target_asset_id == prior.asset)),
                "links": rows(EntitySourceLink, or_(EntitySourceLink.entity_id == prior.asset,
                                                    EntitySourceLink.interface_owner_id == prior.asset)),
                "assertions": assertions,
                "items": items,
                "changes": rows(KnowledgeChange, or_(KnowledgeChange.entity_id.in_([prior.asset, prior.interface, prior.relationship]),
                                                      KnowledgeChange.assertion_id.in_(assertions))),
                "audits": rows(AuditEvent, AuditEvent.target_id.in_([prior.asset, prior.interface, prior.relationship, *items])),
            }


@pytest.mark.parametrize("kind", ["lxc", "qemu"])
def test_reused_key_is_held_before_attribution(cases, kind):
    case = cases(kind)
    prior = case.seed()
    assert case.retire() == prior.asset
    before = case.snapshot(prior)
    assert before["asset"][prior.asset]["status"] == "retired"
    assert before["interface"][prior.interface]["network_id"] == prior.network
    staged = case.stage(name="guest-b", mac=MAC_B, bridge="vmbr1", extra=True)
    assert case.snapshot(prior) == before
    case.complete(staged)
    with case.session() as db:
        receipt = db.get(DiscoveryBatchReceipt, (staged.id, 1))
        assert receipt.payload_json == staged.batch
        by_kind = {(m.entity_type, m.external_id): m for m in db.scalars(select(RunObservedEntity).where(
            RunObservedEntity.discovery_run_id == staged.id))}
        keys = [("asset", case.guest), ("asset_interface", case.nic),
                ("relationship", staged.batch["relationships"][0]["external_id"])]
        assert {key: by_kind[key].entity_id for key in keys} == dict.fromkeys(keys)
        ids = [by_kind[key].evidence_record_id for key in keys]
        assert all(db.get(EvidenceRecord, evidence_id) for evidence_id in ids)
        claims = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.evidence_record_id.in_(ids))))
        assert len(claims) == 1
        assert claims[0].subject_type == "source_identity"
        assert claims[0].subject_id is None and claims[0].object_id is None
        assert set(claims[0].value_json["held_evidence_ids"]) == {str(identifier) for identifier in ids}
        run = db.get(DiscoveryRun, staged.id)
        assert run.status == "completed" and run.summary["reobserved_count"] == 0
    assert case.snapshot(prior) == before
    case.proposal("node/unrelated", "name")
    assert len(case.identity_reviews()) == 1


def _link_guest_without_accepting_source_fields(case):
    reply = case.client.post("/assets", json={"customer_id": str(case.customer_id), "site_id": str(case.site_id),
        "name": "Curated guest", "asset_type": {"lxc": "lxc_container", "qemu": "virtual_machine"}[case.kind]})
    assert reply.status_code == 201, reply.text
    asset = uuid.UUID(reply.json()["id"])
    case.run(name="Source guest")
    case.accept("node/node-a", "name")
    _, proposal = case.proposal(case.guest, "name")
    linked = case.decide(proposal, "link-asset", asset_id=str(asset))
    assert linked.status_code == 200, linked.text
    case.proposal(case.guest, "name")
    relationship = case.accept(case.guest, "runs_on")
    with case.session() as db:
        assert db.scalar(select(KnowledgeAssertion.id).join(EvidenceRecord,
            KnowledgeAssertion.evidence_record_id == EvidenceRecord.id).where(
            EvidenceRecord.data_source_id == case.source_id, EvidenceRecord.entity_kind == "asset",
            EvidenceRecord.external_id == case.guest, KnowledgeAssertion.is_accepted.is_(True))) is None
    return SimpleNamespace(asset=asset, interface=None, relationship=relationship)


@pytest.mark.parametrize("kind", ["lxc", "qemu"])
def test_relationship_only_opens_hold_after_link_without_accepted_guest_fields(cases, kind):
    case = cases(kind)
    prior = _link_guest_without_accepting_source_fields(case)
    assert case.retire() == prior.asset
    before = case.snapshot(prior)
    assert before["asset"][prior.asset]["status"] == "retired"
    assert prior.relationship in before["edges"]
    staged = case.stage(name="Omitted guest", guest_relationship_only=True, extra=True)
    assert not staged.batch["interfaces"] and all(row["external_id"] != case.guest for row in staged.batch["assets"])

    assert case.complete(staged)["replayed"] is False
    [group] = case.identity_reviews()
    review = group["parent"]
    assert review["status"] == "open"
    assert review["current"]["name"] == "Curated guest"
    assert review["proposed"]["name"] is None
    assert case.complete(staged)["replayed"] is True
    assert case.identity_reviews()[0]["parent"]["version"] == review["version"]
    with case.session() as db:
        assert db.get(DiscoveryBatchReceipt, (staged.id, 1)).payload_json == staged.batch
        observation = staged.batch["relationships"][0]
        membership = db.scalar(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == staged.id,
            RunObservedEntity.entity_type == "relationship", RunObservedEntity.external_id == observation["external_id"]))
        assert membership.entity_id is None
        evidence = db.get(EvidenceRecord, membership.evidence_record_id)
        assert evidence.payload_json == observation
        claim = db.get(KnowledgeAssertion, uuid.UUID(review["assertion_id"]))
        assert claim.evidence_record_id == evidence.id
        assert claim.subject_id is None and claim.object_id is None and not claim.is_accepted
        assert claim.value_json == {"guest_observed": False, "held_evidence_ids": [str(evidence.id)]}
        run = db.get(DiscoveryRun, staged.id)
        assert run.status == "completed" and run.summary["reobserved_count"] == 0
    assert case.snapshot(prior) == before
    case.proposal("node/unrelated", "name", run_id=str(staged.id))

    assert case.client.patch(f"/assets/{prior.asset}", json={"status": "active"}).status_code == 200
    after_edit = case.snapshot(prior)
    case.run(name="Still omitted", guest_relationship_only=True)
    [updated] = case.identity_reviews()
    assert updated["id"] == group["id"] and updated["parent"]["version"] != review["version"]
    assert case.snapshot(prior) == after_edit


@pytest.mark.parametrize("invalid", ["unbound_host", "guest_in_host_role", "active_guest_without_accepted_fields", "other_source"])
def test_relationship_only_rejects_invalid_bindings(cases, invalid):
    case = cases()
    prior = _link_guest_without_accepting_source_fields(case)
    if invalid != "active_guest_without_accepted_fields":
        assert case.retire() == prior.asset
    before = case.snapshot(prior)
    reporter = cases(alongside=case, same_site=True) if invalid == "other_source" else case
    target = {"unbound_host": "node/unbound", "guest_in_host_role": case.guest}.get(invalid)
    staged = reporter.stage(name="Omitted guest", guest_relationship_only=True, relationship_target=target, extra=True)

    assert reporter.complete(staged, expected=422)["detail"]["code"] == "invalid_relationship_binding"
    assert case.identity_reviews() == reporter.identity_reviews() == []
    assert case.snapshot(prior) == before
    with reporter.session() as db:
        run = db.get(DiscoveryRun, staged.id)
        assert run.status == "failed" and run.finalisation_hash is None
        assert db.get(DiscoveryBatchReceipt, (staged.id, 1)).payload_json == staged.batch
        assert db.scalar(select(KnowledgeAssertion.id).where(KnowledgeAssertion.discovery_run_id == staged.id)) is None


def test_relationship_only_resolves_active_guest_with_accepted_fields(cases):
    case = cases()
    prior = case.seed()
    staged = case.run(name="Omitted guest", guest_relationship_only=True, node="node-b")
    node = case.accept("node/node-b", "name")

    assert case.identity_reviews() == []
    _, proposal = case.proposal(case.guest, "runs_on", run_id=str(staged.id))
    assert proposal["can_accept"]
    relationship = case.accept(case.guest, "runs_on")
    with case.session() as db:
        edge = db.get(AssetRelationship, relationship)
        assert edge.source_asset_id == prior.asset and edge.target_asset_id == node
        assert edge.relationship_type == "runs_on"


def test_unchanged_guest_still_requires_identity_review(cases):
    case = cases()
    prior = case.seed()
    case.retire()
    before = case.snapshot(prior)
    case.run(name="guest-a")
    [group] = case.identity_reviews()
    review = group["parent"]
    assert review["current"]["name"] == review["proposed"]["name"] == "guest-a"
    assert review["current"]["interfaces"][0]["mac_address"] == review["proposed"]["interfaces"][0]["mac_address"] == MAC_A
    assert review["status"] == "open"
    assert [edge["target"] for edge in review["current"]["relationships"]] == ["node-a"]
    assert not review["can_accept"] and not group["decision_items"]
    assert case.snapshot(prior) == before


def test_active_guest_changes_follow_ordinary_review(cases):
    case = cases()
    prior = case.seed()
    case.run(name="new active name", mac=MAC_B)
    assert case.accept(case.guest, "name") == prior.asset
    assert case.accept(case.nic, "configuration") == prior.interface
    case.run(name="new active name", mac=MAC_B, node="node-b")
    case.accept("node/node-b", "name")
    _, relationship = case.proposal(case.guest, "runs_on")
    assert relationship["can_accept"]
    assert relationship["observed_value_json"]["target_external_id"] == "node/node-b"
    after = case.snapshot(prior)
    assert after["asset"][prior.asset]["status"] == "active"
    assert after["interface"][prior.interface]["mac_address"] == MAC_B
    assert after["interface"][prior.interface]["network_id"] == prior.network
    assert case.identity_reviews() == []


def test_coverage_and_review_order(cases):
    case = cases()
    prior = case.seed()
    for options in ({"completeness": "partial"}, {"completeness": "failed"}, {"coverage_key": "another-selection"}):
        case.run(**options)
        assert all(row["category"] != "no_longer_observed" for group in case.groups() for section in group["sections"]
                   for row in section["items"])
    case.retire()
    before = case.snapshot(prior)
    initial = case.run(name="observed B", mac=MAC_B, completeness="partial", dependencies_only=True)
    [group] = case.identity_reviews()
    first = group["parent"]
    assert first["proposed"]["name"] is None and first["proposed"]["asset_interface_count"] == 1
    assert first["proposed"]["relationship_count"] == 1
    assert case.complete(initial)["replayed"]
    assert case.identity_reviews()[0]["parent"]["version"] == first["version"]

    newer = case.run(name="observed C", bridge="vmbr1", completeness="partial", coverage_key="another-selection")
    [group] = case.identity_reviews()
    latest = group["parent"]
    assert latest["id"] == first["id"]
    assert latest["version"] != first["version"]
    assert latest["proposed"]["name"] == "observed C"
    assert latest["discovery_run_id"] == str(newer.id)
    stale = case.decide(first)
    assert stale.status_code == 409 and "refresh" in stale.json()["detail"]
    case.run(name="delayed B", completeness="partial",
        stamp=datetime.fromisoformat(initial.body["observed_at"]) - timedelta(seconds=1),
        observed_stamp=datetime.fromisoformat(newer.body["observed_at"]) + timedelta(seconds=1))
    case.run(name="failed evidence", completeness="failed")
    case.run()
    assert case.identity_reviews()[0]["parent"]["version"] == latest["version"]
    assert case.snapshot(prior) == before
    with case.session() as db:
        all_claims = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_type == "source_identity")))
        assert len(all_claims) == 3
        assert all(not c.is_accepted and c.subject_id is None and
                   all(db.get(EvidenceRecord, uuid.UUID(key)) for key in c.value_json["held_evidence_ids"])
                   for c in all_claims)
        assert [c.discovery_run_id for c in all_claims if c.is_source_current] == [newer.id]


def test_review_scope_and_decision_guards(cases):
    case = cases()
    prior = case.seed()
    case.run(name="previously proposed", mac=MAC_B, secondary=True)
    last_active = case.run(name="previously proposed", mac=MAC_B, node="node-b")
    case.accept("node/node-b", "name")
    old_rows = [case.proposal(key, predicate, run_id=str(last_active.id))[1]
                for key, predicate in [(case.guest, "name"), (case.nic, "configuration"), (case.guest, "runs_on")]]
    _, old_interface = case.proposal(case.guest + "/interface/net1", "configuration")
    case.retire()
    case.run(name="replacement evidence", mac=MAC_B)
    [hold] = case.identity_reviews()
    row = hold["parent"]
    for action in ("accept", "reject", "defer"):
        assert case.decide(row, action).status_code == 409
    assert case.decide(row, "link-asset", asset_id=str(prior.asset)).status_code == 409
    assert case.client.delete(f"/assertions/{row['assertion_id']}").status_code == 409
    assert case.client.post(f"/assertions/{row['assertion_id']}/retract",
        json={"reason": "Prove the retained review cannot be removed"}).status_code == 409
    initial_state = case.snapshot(prior)
    for old in old_rows:
        assert case.client.post(f"/reconciliation-items/{old['id']}/accept", json={}).status_code == 409
        assert case.decide(old).status_code == 409
    assert case.decide(old_interface, "link-technical", entity_id=str(prior.interface)).status_code == 409
    result = case.client.post(f"/reconciliation-entities/{hold['id']}/accept",
        json={"items": [{"id": row["id"], "version": row["version"]}]})
    assert result.status_code == 200, result.text
    assert len(result.json()["blocked"]) == 1
    group, refreshed = case.proposal(case.guest, "name", run_id=str(last_active.id))
    result = case.client.post(f"/reconciliation-entities/{group['id']}/accept",
        json={"items": [{"id": refreshed["id"], "version": refreshed["version"]}]})
    assert result.status_code == 200, result.text
    assert len(result.json()["blocked"]) == 1
    assert case.snapshot(prior) == initial_state

    response = case.client.patch(f"/assets/{prior.asset}", json={"status": "active", "description": "Manual edit"})
    assert response.status_code == 200, response.text
    after_manual = case.snapshot(prior)
    case.run(name="after manual edit")
    assert case.snapshot(prior) == after_manual
    assert case.identity_reviews()[0]["id"] == hold["id"]
    fresh = case.proposal(case.guest, "name", run_id=str(last_active.id))[1]
    blocked = case.decide(fresh)
    assert blocked.status_code == 409 and blocked.json()["detail"] == "This source proposal cannot be applied in its current state"
    assert case.client.post("/discovery/simulate", json={
        "customer_id": str(case.customer_id), "site_id": str(case.site_id), "data_source_id": str(case.source_id),
        "observations": [{"external_id": case.guest, "name": "Synthetic bypass", "asset_type": "lxc_container"}],
    }).status_code == 409

    for scope in ("same-site", "different-site", "different-customer"):
        other = cases(alongside=case if scope != "different-customer" else None, same_site=scope == "same-site")
        other.run(name=f"separate {scope}")
        assert other.identity_reviews() == []
        other.proposal(other.guest, "name")
        if scope != "same-site":
            assert other.groups(source_id=case.source_id) == []
            assert other.client.get(f"/reconciliation-entities/{hold['id']}").status_code == 404
            assert other.client.get(f"/assertions/{row['assertion_id']}").status_code == 404
            assert other.decide(row).status_code == 404

    view = case.client.app.dependency_overrides[get_principal]
    visible_summary = case.client.get("/reconciliation-items/summary").json()
    visible_dashboard = case.client.get("/dashboard/summary").json()
    case.client.app.dependency_overrides[get_principal] = lambda: replace(case.principal, grants=(
        replace(case.principal.grants[0], permissions=frozenset({"reconciliation.view", "sites.view"})),))
    try:
        assert case.identity_reviews() == []
        summary = case.client.get("/reconciliation-items/summary").json()
        assert summary["by_category"].get("possible_duplicate", 0) == visible_summary["by_category"]["possible_duplicate"] - 1
        dashboard = case.client.get("/dashboard/summary").json()
        assert dashboard["possible_duplicate_count"] == visible_dashboard["possible_duplicate_count"] - 1
        assert dashboard["open_reconciliation_count"] == visible_dashboard["open_reconciliation_count"] - 1
        assert case.client.get(f"/reconciliation-entities/{hold['id']}").status_code == 404
        assert case.decide(row).status_code == 403
        case.client.app.dependency_overrides[get_principal] = lambda: replace(case.principal, grants=(
            replace(case.principal.grants[0], permissions=frozenset({"reconciliation.view", "assets.view"})),))
        assert case.identity_reviews()[0]["parent"]["id"] == row["id"]
        for snapshot in (case.identity_reviews()[0]["parent"]["current"],
                         case.client.get("/reconciliation-items", params={"source_id": str(case.source_id),
                             "entity_type": "source_identity"}).json()[0]["current_value_json"]):
            assert snapshot["name"] == "guest-a"
            assert "interfaces" not in snapshot and "relationships" not in snapshot
    finally:
        case.client.app.dependency_overrides[get_principal] = view


@pytest.mark.parametrize("first", ["retire", "completion"])
def test_completion_serializes_with_retirement(cases, first):
    case = cases()
    prior = case.seed()
    case.run()
    _, absence = case.proposal(case.guest, "observation_state")
    staged = case.stage(name="racing guest", mac=MAC_B)
    held, waiting = Event(), Event()
    second = "completion" if first == "retire" else "retire"

    def before(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get("test_actor") == second and "FROM data_sources" in sql and "FOR NO KEY UPDATE" in sql:
            waiting.set()

    def after(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get("test_actor") == first and "FROM assets" in sql and "FOR UPDATE" in sql and not held.is_set():
            held.set()
            assert waiting.wait(8)

    def retire():
        return case.decide(absence, actor="retire", disposition="retire").status_code

    event.listen(case.engine, "before_cursor_execute", before)
    event.listen(case.engine, "after_cursor_execute", after)
    try:
        operations = {"retire": retire, "completion": lambda: case.complete(staged)}
        with ThreadPoolExecutor(max_workers=2) as pool:
            winner = pool.submit(operations[first])
            assert held.wait(8)
            loser = pool.submit(operations[second])
            winner_result, loser_result = winner.result(timeout=15), loser.result(timeout=15)
            retirement = winner_result if first == "retire" else loser_result
    finally:
        event.remove(case.engine, "before_cursor_execute", before)
        event.remove(case.engine, "after_cursor_execute", after)
    assert retirement == (200 if first == "retire" else 409)
    assert case.complete(staged)["replayed"]
    assert len(case.identity_reviews()) == int(first == "retire")
    with case.session() as db:
        assert db.get(Asset, prior.asset).status == ("retired" if first == "retire" else "active")
        guest = db.scalar(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == staged.id,
            RunObservedEntity.external_id == case.guest))
        assert guest.entity_id == (None if first == "retire" else prior.asset)


def test_concurrent_exact_completions_and_database_conflict(cases):
    case = cases()
    prior = case.seed()
    case.retire()
    before = case.snapshot(prior)
    staged = case.stage(name="racing guest", mac=MAC_B)

    def abort_after_seal(session, flush_context):
        if session.connection().get_execution_options().get("test_actor") == "fault":
            run = session.get(DiscoveryRun, staged.id)
            if run and run.finalisation_hash:
                session.execute(text("DO $$ BEGIN RAISE EXCEPTION 'test lock conflict' USING ERRCODE = '55P03'; END $$"))

    event.listen(SessionLocal.class_, "after_flush_postexec", abort_after_seal)
    try:
        case.complete(staged, actor="fault", expected=409)
    finally:
        event.remove(SessionLocal.class_, "after_flush_postexec", abort_after_seal)
    assert case.identity_reviews() == []
    assert case.snapshot(prior) == before
    with case.session() as db:
        assert db.get(DiscoveryRun, staged.id).finalisation_hash is None
        assert db.get(DiscoveryBatchReceipt, (staged.id, 1)).payload_json == staged.batch

    held, waiting = Event(), Event()

    def before_second(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get("test_actor") == "second" and "FROM integrations" in sql and "FOR UPDATE" in sql:
            waiting.set()

    def after_first(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get("test_actor") == "first" and "FROM integrations" in sql and "FOR UPDATE" in sql and not held.is_set():
            held.set()
            assert waiting.wait(8)

    event.listen(case.engine, "before_cursor_execute", before_second)
    event.listen(case.engine, "after_cursor_execute", after_first)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(case.complete, staged, actor="first")
            assert held.wait(8)
            second = pool.submit(case.complete, staged, actor="second")
            assert first.result(timeout=15)["replayed"] is False
            assert second.result(timeout=15)["replayed"] is True
    finally:
        event.remove(case.engine, "before_cursor_execute", before_second)
        event.remove(case.engine, "after_cursor_execute", after_first)
    assert len(case.identity_reviews()) == 1
    assert case.snapshot(prior) == before


def test_completion_prelocks_guest_named_by_unlinked_interface_slot(cases):
    case = cases()
    prior = case.seed()
    staged = case.stage(name="interface-only evidence", completeness="partial",
        dependencies_only=True, mismatched_interface_owner=True)
    locked, attempted = Event(), Event()

    def before(conn, cursor, sql, parameters, context, many):
        if (context.execution_options.get("test_actor") == "completion" and "FROM assets" in sql
                and "FOR UPDATE" in sql and prior.asset in parameters.values()):
            attempted.set()

    def after(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get("test_actor") == "manual" and "FROM assets" in sql and "FOR UPDATE" in sql and not locked.is_set():
            locked.set()
            assert attempted.wait(8)

    def manually_retire():
        return case.client.patch(f"/assets/{prior.asset}", headers={"x-test-actor": "manual"}, json={"status": "retired"})

    event.listen(case.engine, "before_cursor_execute", before)
    event.listen(case.engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            retirement = pool.submit(manually_retire)
            assert locked.wait(8)
            completion = pool.submit(case.complete, staged)
            assert retirement.result(timeout=15).status_code == 200
            assert completion.result(timeout=15)["replayed"] is False
    finally:
        event.remove(case.engine, "before_cursor_execute", before)
        event.remove(case.engine, "after_cursor_execute", after)
    [hold] = case.identity_reviews()
    assert hold["parent"]["proposed"]["interfaces"][0]["external_id"] == case.guest + "/interface/net1"
