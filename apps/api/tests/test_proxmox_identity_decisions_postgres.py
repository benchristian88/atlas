"""Real scoped HTTP decisions with independent PostgreSQL transaction checks."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from time import monotonic, sleep
import os
from threading import Event
import uuid

import pytest
from sqlalchemy import event, select, text

from app.authorization import get_principal
from app.database import SessionLocal, get_db
from app.models import (Asset, AssetInterface, AssetType, AuditEvent, DataSource, Integration, DiscoveryBatchReceipt, DiscoveryRun,
    EntitySourceLink, EvidenceRecord, KnowledgeAssertion, KnowledgeChange, ProxmoxGuestIdentityDecision,
    ReconciliationItem, RunObservedEntity)
from app.routes import knowledge
from app.services import discovery_tokens, proxmox_identity_decisions as identity
from app.services.discovery_orchestration import IDENTITY_RETRY_MESSAGE
from tests.test_knowledge_integrity_migration import migrated_history, pytestmark
from tests.test_backup_postgres import installations, portable_backup, restore
from tests.test_proxmox_guest_identity_postgres import case_factory, cases, MAC_B


def review(case):
    return next(row["parent"] for row in case.identity_reviews() if row["parent"]["status"] == "open")


def decide(case, row, outcome="reactivate", reason="Verified against the guest inventory", **options):
    return case.decide(row, "identity-decision", outcome=outcome, reason=reason,
        expected_version=options.pop("expected_version", row["identity_review"]["expected_version"]), **options)


def current_link(db, case, key, kind="asset"):
    return db.scalar(select(EntitySourceLink).where(EntitySourceLink.data_source_id == case.source_id,
        EntitySourceLink.entity_type == kind, EntitySourceLink.external_id == key, EntitySourceLink.ended_epoch.is_(None)))


def effects(case, row, run):
    """Independent read of committed source, asset, proposal and run state."""
    with case.session() as db:
        keys = ("assets", "knowledge_assertions", "entity_source_links", "reconciliation_items", "data_sources",
                "discovery_batch_receipts", "run_observed_entities", "discovery_runs", "proxmox_guest_identity_decisions",
                "evidence_records", "knowledge_changes", "audit_events")
        snapshot = {table: db.execute(text(f"SELECT to_jsonb(r) FROM {table} r ORDER BY to_jsonb(r)")).scalars().all()
                    for table in keys}
        assert db.get(ReconciliationItem, uuid.UUID(row["id"])) is not None
        assert db.get(DiscoveryRun, run.id).status == "completed"
        return snapshot


def test_reactivate_keeps_identity_leaves_released_facts_pending_and_reopens_after_retirement(cases):
    case = cases()
    prior = case.seed()
    assert case.retire() == prior.asset
    run = case.run(name="Reviewed source name", mac=MAC_B, bridge="vmbr1")
    row = review(case)
    assert row["identity_review"]["actions"] == {"reactivate": None, "replace": None}
    before = effects(case, row, run)
    assert review(case) == row
    assert effects(case, row, run) == before  # Leaving via GET is a non-action.
    assert decide(case, row, reason="  ").status_code == 422
    assert decide(case, row, reason="invalid\x00reason").status_code == 422
    assert decide(case, row, asset_id=str(prior.asset)).status_code == 422
    response = decide(case, row)
    assert response.status_code == 200, response.text
    assert response.json() == {"id": row["id"], "status": "accepted", "outcome": "reactivate"}
    with case.session() as db:
        decision = db.get(ProxmoxGuestIdentityDecision, uuid.UUID(row["id"]))
        asset = db.get(Asset, prior.asset)
        assert (asset.name, asset.status, asset.identity_retirement_revision) == ("guest-a", "active", 1)
        assert current_link(db, case, case.guest).id == decision.old_binding_id
        assert db.get(AssetInterface, prior.interface).network_id == prior.network
        assert current_link(db, case, case.nic, "asset_interface").interface_id == prior.interface
        assert db.get(KnowledgeAssertion, decision.reviewed_assertion_id).is_accepted is False
        released = list(db.execute(select(KnowledgeAssertion, ReconciliationItem).join(ReconciliationItem,
            ReconciliationItem.assertion_id == KnowledgeAssertion.id).where(KnowledgeAssertion.identity_epoch == 1)))
        assert {claim.predicate for claim, _ in released} == {"name", "asset_type", "proxmox.vmid", "runs_on", "configuration", "proxmox.bridge_name"}
        assert all(not claim.is_accepted and proposal.status == "open" for claim, proposal in released)
        assert all(claim.discovery_run_id == run.id for claim, _ in released)
        lifecycle = db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == decision.reconciliation_item_id,
            KnowledgeChange.change_type == "lifecycle_changed"))
        assert lifecycle.entity_id == asset.id and lifecycle.new_value_json == "active"
        assert set(lifecycle.metadata_json["released_evidence_ids"]) == {str(claim.evidence_record_id) for claim, _ in released}
        assert db.get(KnowledgeAssertion, lifecycle.assertion_id).is_accepted
        assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "reconciliation.identity_reactivate")))) == 1
    after = effects(case, row, run)
    for table in ("discovery_batch_receipts", "discovery_runs", "evidence_records", "run_observed_entities"):
        assert after[table] == before[table], table
    assert decide(case, row).status_code == 409
    name = case.proposal(case.guest, "name", run_id=run.id)[1]
    assert case.decide(name).status_code == 200
    latest = case.run(name="Reviewed source name")
    with case.session() as db:
        assert db.scalar(select(RunObservedEntity.entity_id).where(RunObservedEntity.discovery_run_id == latest.id,
            RunObservedEntity.external_id == case.guest)) == prior.asset
    assert case.client.patch(f"/assets/{prior.asset}", json={"status": "retired"}).status_code == 200
    case.run(name="Another return")
    assert review(case)["id"] != row["id"]


def test_replacement_ends_only_exact_guest_and_same_source_interface_bindings(cases):
    case = cases()
    prior = case.seed()
    other = cases(alongside=case, same_site=True)
    original_key, original_nic = case.guest, case.nic
    case.guest, case.nic = "guest/lxc/1030", "guest/lxc/1030/interface/net0"
    case.run(name="Unrelated guest")
    other_asset = case.accept(case.guest, "name")
    case.accept(case.nic, "configuration")
    with case.session() as db:
        other_link = current_link(db, case, case.guest).id
        other_nic = current_link(db, case, case.nic, "asset_interface").id
    assert case.client.patch(f"/assets/{other_asset}", json={"status": "retired"}).status_code == 200
    case.run(name="Unrelated replacement")
    case.guest, case.nic = original_key, original_nic
    with case.session() as db, db.begin():
        old = current_link(db, case, case.guest).id
        old_nic = current_link(db, case, case.nic, "asset_interface").id
        old_other = EntitySourceLink(data_source_id=other.source_id, customer_id=case.customer_id, site_id=case.site_id,
            entity_type="asset", entity_id=prior.asset, external_id=case.guest,
            first_observed_at=datetime.now(timezone.utc), last_observed_at=datetime.now(timezone.utc))
        other_interface = EntitySourceLink(data_source_id=other.source_id, customer_id=case.customer_id, site_id=case.site_id,
            entity_type="asset_interface", interface_id=prior.interface, interface_owner_id=prior.asset, external_id=case.nic,
            first_observed_at=old_other.first_observed_at, last_observed_at=old_other.last_observed_at)
        db.add_all([old_other, other_interface])
        db.flush()
        old_other_id, other_interface_id = old_other.id, other_interface.id
    assert decide(case, review(case), "replace").status_code == 200
    with case.session() as db:
        assert db.get(EntitySourceLink, old).ended_epoch is None
        assert db.get(EntitySourceLink, old_nic).ended_epoch is None
        assert db.get(EntitySourceLink, other_link).ended_epoch == db.get(EntitySourceLink, other_nic).ended_epoch == 1
    assert case.client.patch(f"/assets/{prior.asset}", json={"status": "retired", "description": "Retained context"}).status_code == 200
    run = case.run(name="guest-a", mac=MAC_B, bridge="vmbr1", omit_network=True)
    row = review(case)
    before = case.snapshot(prior)
    response = decide(case, row, "replace")
    assert response.status_code == 200, response.text
    after = case.snapshot(prior)
    for key in ("asset", "interface", "edges", "assertions", "items", "audits"):
        assert after[key] == before[key], key
    with case.session() as db:
        outcome = db.get(ProxmoxGuestIdentityDecision, uuid.UUID(row["id"]))
        binding = current_link(db, case, case.guest)
        assert binding.id == outcome.replacement_binding_id and binding.opened_epoch == 2
        new_id = binding.entity_id
        new = db.get(Asset, new_id)
        assert new_id != prior.asset and new.status == "active" and new.name == "guest-a"
        assert new.description is None and new.hostname is None and new.source_integration_id is None
        assert db.get(EntitySourceLink, old).ended_epoch == db.get(EntitySourceLink, old_nic).ended_epoch == 2
        assert db.get(EntitySourceLink, old_other_id).ended_epoch is None
        assert db.get(EntitySourceLink, other_interface_id).ended_epoch is None
        assert current_link(db, case, case.nic, "asset_interface") is None
        assert not list(db.scalars(select(AssetInterface).where(AssetInterface.asset_id == new_id)))
        audit = db.scalar(select(AuditEvent).where(AuditEvent.target_id == outcome.reconciliation_item_id))
        assert set(audit.metadata_["ended_binding_ids"]) == {str(old), str(old_nic)}
    proposal = case.proposal(case.nic, "configuration", run_id=run.id)[1]
    assert proposal["status"] == "open" and proposal["entity_id"] is None
    accepted = case.decide(proposal)
    assert accepted.status_code == 200, accepted.text
    interface_id = uuid.UUID(accepted.json()["entity_id"])
    assert case.accept(case.nic, "proxmox.vlan_tag") == interface_id
    with case.session() as db:
        assert interface_id != prior.interface
        assert db.get(AssetInterface, interface_id).asset_id == new_id
        assert db.get(AssetInterface, interface_id).network_id is None
    next_run = case.run(name="guest renamed again", bridge="vmbr1")
    reply = case.decide(case.proposal(case.nic, "configuration", run_id=next_run.id)[1])
    assert reply.status_code == 200, reply.text
    with case.session() as db:
        assert db.scalar(select(RunObservedEntity.entity_id).where(RunObservedEntity.discovery_run_id == next_run.id,
            RunObservedEntity.external_id == case.guest)) == new_id
        assert db.get(AssetInterface, prior.interface).network_id == prior.network
        assert db.get(AssetInterface, interface_id).network_id == current_link(db, case, "network/node-a/vmbr1", "network").network_id


def test_relationship_only_already_active_confirmation_and_scope(cases):
    case = cases()
    case.run(name="Source-only guest")
    case.accept("node/node-a", "name")
    proposal = case.proposal(case.guest, "name")[1]
    response = case.client.post("/assets", json={"customer_id": str(case.customer_id), "site_id": str(case.site_id),
        "asset_type": "lxc_container", "name": "Pre-existing inventory"})
    assert response.status_code == 201, response.text
    asset_id = uuid.UUID(response.json()["id"])
    assert case.decide(proposal, "link-asset", asset_id=str(asset_id)).status_code == 200
    assert case.client.patch(f"/assets/{asset_id}", json={"status": "retired"}).status_code == 200
    run = case.run(name="unused", dependencies_only=True, guest_relationship_only=True)
    row = review(case)
    assert row["identity_review"]["actions"]["replace"] == identity.MISSING_GUEST
    assert decide(case, row, "replace").status_code == 409
    original = case.client.app.dependency_overrides[get_principal]
    for permission, status in (("assets.view", 404), ("reconciliation.view", 404), ("assets.edit", 403), ("reconciliation.decide", 403)):
        case.client.app.dependency_overrides[get_principal] = lambda: replace(case.principal, grants=(replace(case.principal.grants[0],
            permissions=case.principal.grants[0].permissions - {permission}),))
        assert decide(case, row).status_code == status
    case.client.app.dependency_overrides[get_principal] = original
    for foreign in (cases(alongside=case), cases()):
        assert decide(foreign, row).status_code == 404
    assert case.client.patch(f"/assets/{asset_id}", json={"status": "active"}).status_code == 200
    assert decide(case, row).status_code == 409
    fresh = review(case)
    assert fresh["identity_review"]["current_asset_status"] == "active"
    assert fresh["identity_review"]["actions"]["replace"] == identity.ACTIVE_ASSET
    with case.session() as db:
        status_id = db.scalar(select(KnowledgeAssertion.id).where(KnowledgeAssertion.subject_id == asset_id,
            KnowledgeAssertion.predicate == "status", KnowledgeAssertion.is_accepted.is_(True)))
    response = decide(case, fresh)
    assert response.status_code == 200, response.text
    with case.session() as db:
        claims = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == run.id,
            KnowledgeAssertion.identity_epoch == 1)))
        assert len(claims) == 1 and claims[0].predicate == "runs_on" and not claims[0].is_accepted
        assert db.get(KnowledgeAssertion, status_id).is_accepted
        assert db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == uuid.UUID(fresh["id"]),
            KnowledgeChange.change_type == "identity_confirmed")) is not None


@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
@pytest.mark.parametrize("point", ["before proposals", "after proposals", "after success audit"])
def test_injected_failure_rolls_back_decision_and_allows_deliberate_retry(cases, monkeypatch, outcome, point):
    case = cases()
    prior = case.seed()
    case.retire()
    run = case.run(name="Rollback fixture")
    row = review(case)
    before = effects(case, row, run)
    release = identity.release_proposals
    apply = knowledge.decide_review

    def rollback_after_audit(*args):
        apply(*args)
        raise ValueError("test fault injection")

    def fail(*args):
        if point == "after proposals":
            release(*args)
        raise ValueError("test fault injection")

    with monkeypatch.context() as patch:
        if point == "after success audit":
            patch.setattr(knowledge, "decide_review", rollback_after_audit)
        else:
            patch.setattr(identity, "release_proposals", fail)
        with pytest.raises(ValueError, match="test fault injection"):
            decide(case, row, outcome)
    assert effects(case, row, run) == before
    response = decide(case, row, outcome)
    assert response.status_code == 200, response.text
    assert decide(case, row, outcome).status_code == 409
    with case.session() as db:
        assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.target_id == uuid.UUID(row["id"]))))) == 1
        assert db.get(DataSource, case.source_id).identity_epoch == 1
        assert db.get(Asset, prior.asset).status == ("active" if outcome == "reactivate" else "retired")


@pytest.mark.parametrize("first", ["decision", "completion", "two reviewers"])
def test_identity_decision_serializes_with_reviewers_and_completion(cases, first):
    case = cases()
    prior = case.seed()
    case.retire()
    sealed = case.run(name="First evidence")
    held = review(case)
    staged = case.stage(name="Later evidence") if first != "two reviewers" else None
    before = effects(case, held, sealed)
    locked, attempted, release = Event(), Event(), Event()
    pids = {}

    def before_sql(conn, cursor, sql, parameters, execution, many):
        if execution.execution_options.get("test_actor") == "racer" and "FROM integrations" in sql and "FOR UPDATE" in sql:
            pids["racer"] = conn.connection.driver_connection.info.backend_pid
            attempted.set()

    def after_sql(conn, cursor, sql, parameters, execution, many):
        if (execution.execution_options.get("test_actor") == "holder" and "FROM integrations" in sql
                and "FOR UPDATE" in sql and not locked.is_set()):
            pids["holder"] = conn.connection.driver_connection.info.backend_pid
            locked.set()
            assert release.wait(8)

    def decision(actor, outcome):
        return decide(case, held, outcome, actor=actor)

    def completion(actor):
        return case.client.post(staged.url, headers={**staged.headers, "x-test-actor": actor}, json=staged.body)

    event.listen(case.engine, "before_cursor_execute", before_sql)
    event.listen(case.engine, "after_cursor_execute", after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            holder = pool.submit(completion, "holder") if first == "completion" else pool.submit(decision, "holder", "replace")
            try:
                assert locked.wait(6)
                racer = pool.submit(completion, "racer") if first == "decision" else pool.submit(decision, "racer", "reactivate")
                assert attempted.wait(6)
                assert pids["racer"] != pids["holder"]
                deadline = monotonic() + 5
                with case.session() as db:
                    while pids["holder"] not in db.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["racer"]}):
                        assert monotonic() < deadline, "expected PostgreSQL writer to wait on Integration"
                        sleep(0.02)
            finally:
                release.set()
            winner, loser = holder.result(timeout=12), racer.result(timeout=12)
    finally:
        event.remove(case.engine, "before_cursor_execute", before_sql)
        event.remove(case.engine, "after_cursor_execute", after_sql)
    assert (winner.status_code, loser.status_code) == (200, 409), (winner.text, loser.text)
    if first == "completion":
        assert loser.json()["detail"] == identity.CHANGED
        with case.session() as db:
            assert db.get(DataSource, case.source_id).identity_epoch == 0
            assert db.get(ReconciliationItem, uuid.UUID(held["id"])).status == "open"
            assert db.get(ProxmoxGuestIdentityDecision, uuid.UUID(held["id"])) is None
            assert current_link(db, case, case.guest).entity_id == prior.asset
        assert review(case)["identity_review"]["expected_version"] != held["identity_review"]["expected_version"]
        assert decide(case, review(case), "replace").status_code == 200
    elif first == "decision":
        assert loser.json()["detail"]["code"] == "identity_epoch_changed"
        assert case.complete(sealed)["replayed"]
        with case.session() as db:
            stale = db.get(DiscoveryRun, staged.id)
            assert stale.status == "failed" and stale.error_message == IDENTITY_RETRY_MESSAGE
            assert db.get(DiscoveryBatchReceipt, (staged.id, 1)).payload_json == staged.batch
            assert list(db.scalars(select(EvidenceRecord.id).where(EvidenceRecord.discovery_run_id == staged.id)))
            assert len(list(db.scalars(select(KnowledgeAssertion.id).where(KnowledgeAssertion.discovery_run_id == staged.id)))) == 0
            assert all(row.entity_id is None for row in db.scalars(select(RunObservedEntity).where(
                RunObservedEntity.discovery_run_id == staged.id)))
        assert effects(case, held, sealed)["discovery_batch_receipts"] == before["discovery_batch_receipts"]
        next_run = case.run(name="Fresh discovery after stale run")
        with case.session() as db:
            assert db.scalar(select(RunObservedEntity.entity_id).where(RunObservedEntity.discovery_run_id == next_run.id,
                RunObservedEntity.external_id == case.guest)) == current_link(db, case, case.guest).entity_id != prior.asset
    else:
        assert loser.json()["detail"] == identity.CHANGED
    with case.session() as db:
        assert db.get(DataSource, case.source_id).identity_epoch == 1
        assert len(list(db.scalars(select(ProxmoxGuestIdentityDecision)))) == 1
        assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.target_id == uuid.UUID(held["id"]))))) == 1


def test_replace_requires_both_network_grants_even_without_interface_bindings(cases):
    case = cases()
    case.run(name="Guest without an Interface binding")
    case.accept("node/node-a", "name")
    asset = case.accept(case.guest, "name")
    assert case.client.patch(f"/assets/{asset}", json={"status": "retired"}).status_code == 200
    case.run(name="Replacement with observed Interface")
    row = review(case)
    assert row["identity_review"]["actions"]["replace"] is None
    with case.session() as db:
        assert current_link(db, case, case.nic, "asset_interface") is None
    original = case.client.app.dependency_overrides[get_principal]
    for permission in ("networks.view", "networks.edit", "assets.create", "relationships.view"):
        case.client.app.dependency_overrides[get_principal] = lambda: replace(case.principal, grants=(replace(case.principal.grants[0],
            permissions=case.principal.grants[0].permissions - {permission}),))
        scoped = review(case)
        assert scoped["identity_review"]["actions"]["reactivate"] is None
        flat = case.client.get("/reconciliation-items", params={"entity_type": "source_identity"}).json()[0]
        if permission == "networks.view":
            assert "interfaces" not in scoped["proposed"] and "asset_interface_count" not in flat["observed_value_json"]
        if permission == "relationships.view":
            assert "relationships" not in scoped["proposed"] and "relationship_count" not in flat["observed_value_json"]
            assert scoped["identity_review"]["actions"]["replace"] is None
        else:
            assert scoped["identity_review"]["actions"]["replace"]
            assert decide(case, scoped, "replace").status_code == 403
    case.client.app.dependency_overrides[get_principal] = original
    assert decide(case, row, "replace").status_code == 200


def test_replace_conflicting_interface_owner_fails_without_ending_any_links(cases):
    case = cases()
    prior = case.seed()
    case.retire()
    with case.session() as db, db.begin():
        host = current_link(db, case, "node/node-a").entity_id
        interface = AssetInterface(asset_id=host, name="Conflicting Interface")
        db.add(interface)
        db.flush()
        link = current_link(db, case, case.nic, "asset_interface")
        # A legacy alias with a conflicting canonical owner. Retain the valid FK pair.
        link.interface_id = interface.id
        link.interface_owner_id = host
    run = case.run(name="New guest held with conflicting Interface")
    row = review(case)
    assert row["identity_review"]["actions"]["replace"] == identity.OWNERSHIP_CONFLICT
    assert row["identity_review"]["actions"]["reactivate"] is None
    before = effects(case, row, run)
    assert decide(case, row, "replace").status_code == 409
    assert effects(case, row, run) == before
    same = decide(case, row)
    assert same.status_code == 200, same.text
    with case.session() as db:
        assert current_link(db, case, case.guest).entity_id == prior.asset
        assert current_link(db, case, case.nic, "asset_interface").interface_owner_id == host
        change = db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == uuid.UUID(row["id"])))
        assert [entry["reason"] for entry in change.metadata_json["withheld_evidence"]] == ["interface_owner_conflict"]


def test_changed_mapping_invalidates_review(cases):
    case = cases()
    prior = case.seed()
    case.retire()
    case.run(name="Reviewed guest type")
    row = review(case)
    with case.session() as db, db.begin():
        asset = db.get(Asset, prior.asset)
        db.scalar(select(AssetType).where(AssetType.key == asset.asset_type)).active = False
    stale = decide(case, row, "replace")
    assert stale.status_code == 409 and stale.json()["detail"] == identity.CHANGED
    fresh = review(case)
    assert fresh["identity_review"]["actions"]["replace"] == identity.MAPPING_REQUIRED
    assert fresh["identity_review"]["actions"]["reactivate"] is None


def test_relationship_release_waits_for_unlinked_host(cases):
    case = cases()
    prior = case.seed()
    case.retire()
    run = case.run(name="unused", dependencies_only=True, guest_relationship_only=True, node="unlinked-host")
    response = decide(case, review(case))
    assert response.status_code == 200, response.text
    relation = case.proposal(case.guest, "runs_on", run_id=run.id)[1]
    assert relation["can_accept"] is False
    assert case.decide(relation).status_code == 409
    case.accept("node/unlinked-host", "name")
    relation = case.proposal(case.guest, "runs_on", run_id=run.id)[1]
    reply = case.decide(relation)
    assert reply.status_code == 200, reply.text
    with case.session() as db:
        assertion = db.get(KnowledgeAssertion, uuid.UUID(relation["assertion_id"]))
        assert assertion.subject_id == prior.asset and assertion.is_accepted


def test_relationship_release_uses_accepted_evidence_for_an_omitted_host(cases):
    case = cases()
    case.run(name="Guest with known host", node="accepted-host")
    host = case.accept("node/accepted-host", "name")
    guest = case.accept(case.guest, "name")
    assert case.client.patch(f"/assets/{guest}", json={"status": "retired"}).status_code == 200
    run = case.run(name="unused", dependencies_only=True, guest_relationship_only=True,
        relationship_target="node/accepted-host")
    assert all(row["external_id"] != "node/accepted-host" for row in run.batch["assets"])
    response = decide(case, review(case))
    assert response.status_code == 200, response.text
    relation = case.proposal(case.guest, "runs_on", run_id=run.id)[1]
    assert relation["can_accept"] and relation["proposed"]["resolved_target_asset_id"] == str(host)


def test_populated_0032_upgrade_resolves_retained_case_and_keeps_unsupported_evidence_pending(cases, migrated_history):
    supported, unsupported = cases(), cases()
    expected = []
    for case in (supported, unsupported):
        prior = case.seed()
        case.retire()
        run = case.run(name="unused", guest_relationship_only=True, dependencies_only=True)
        row = review(case)
        expected.append((prior, run, uuid.UUID(row["id"]), uuid.UUID(row["assertion_id"])))
    # Materialize the same Pass 1 receipt, membership, claim and item records
    # without 0033 storage, then carry them through the populated migration.
    migrated_history.migrate("downgrade", "20261101_0032")
    with migrated_history.engine.begin() as db:
        db.execute(text("UPDATE evidence_records SET payload_hash = NULL WHERE discovery_run_id = :run"), {"run": expected[1][1].id})
    migrated_history.migrate("upgrade", "20261119_0033")
    for index, case in enumerate((supported, unsupported)):
        prior, run, item_id, claim_id = expected[index]
        row = review(case)
        assert (row["id"], row["assertion_id"]) == (str(item_id), str(claim_id))
        reply = decide(case, row)
        with case.session() as db:
            if case is supported:
                assert reply.status_code == 200, reply.text
                assert db.get(ProxmoxGuestIdentityDecision, item_id).reviewed_assertion_id == claim_id
                assert db.get(Asset, prior.asset).status == "active"
            else:
                assert reply.status_code == 409 and reply.json()["detail"] == identity.UNAVAILABLE_EVIDENCE
                assert db.get(ReconciliationItem, item_id).status == "open"
                assert db.get(Asset, prior.asset).status == "retired"
                assert db.get(DiscoveryBatchReceipt, (run.id, 1)) is not None
        if case is unsupported:
            case.run(name="Fresh supported evidence")
            assert review(case)["id"] == str(item_id)
            assert decide(case, review(case), "replace").status_code == 200


@pytest.mark.skipif(not (os.getenv("ATLAS_TEST_H3_SOURCE_URL") and os.getenv("ATLAS_TEST_H3_TARGET_URL")),
                    reason="requires two disposable PostgreSQL databases for encrypted restore")
def test_matching_build_encrypted_restore_of_real_replacement(installations):
    source, target = installations["source"], installations["target"]
    discovery_tokens.provision_signing_key()
    case = case_factory(source)()
    prior = case.seed()
    case.retire()
    case.run(name="Real decision to back up", mac=MAC_B)
    row = review(case)
    response = decide(case, row, "replace")
    assert response.status_code == 200, response.text
    identifier = uuid.UUID(row["id"])
    with case.session() as db:
        decision = db.get(ProxmoxGuestIdentityDecision, identifier)
        old_id, new_id = decision.old_binding_id, decision.replacement_binding_id
        new_asset = db.get(EntitySourceLink, new_id).entity_id
        audit_id = db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == identifier))
        ended = db.get(AuditEvent, audit_id).metadata_["ended_binding_ids"]
    archive = portable_backup(installations)
    restore(installations, archive)
    case.engine = target
    case.session = lambda: SessionLocal(bind=target)

    def target_db():
        with case.session() as db:
            yield db

    case.client.app.dependency_overrides[get_db] = target_db
    with case.session() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261119_0033"
        assert db.get(EntitySourceLink, old_id).ended_epoch == db.get(EntitySourceLink, new_id).opened_epoch == 1
        assert db.get(EntitySourceLink, old_id).entity_id == prior.asset
        assert current_link(db, case, case.guest).entity_id == new_asset
        assert db.get(AuditEvent, audit_id).metadata_["ended_binding_ids"] == ended
        assert db.get(ReconciliationItem, identifier).status == "accepted"
        restored = db.get(Integration, case.integration.id)
        assert restored is not None
    restored_review = case.client.get(f"/reconciliation-entities/{identifier}")
    assert restored_review.status_code == 200, restored_review.text
    assert restored_review.json()["parent"]["identity_review"]["outcome"] == "replace"
    assert not any(item["parent"]["status"] == "open" for item in case.identity_reviews())
    first = case.run(name="Fresh observation on restored installation")
    with case.session() as db:
        assert db.scalar(select(RunObservedEntity.entity_id).where(RunObservedEntity.discovery_run_id == first.id,
            RunObservedEntity.external_id == case.guest)) == new_asset
        assert db.get(AssetInterface, prior.interface).network_id == prior.network
        assert not list(db.scalars(select(AssetInterface).where(AssetInterface.asset_id == new_asset)))


def test_mutation_grant_revoked_while_identity_decision_waits(cases, monkeypatch):
    from fastapi import Depends
    from app.authorization import _load_principal
    from app.models import AccessAssignment, Permission, Role, RolePermission, User

    case = cases()
    case.seed()
    case.retire()
    run = case.run(name="Pending while a grant is revoked")
    row = review(case)
    grant_keys = set(identity.READ_GRANTS) | set(identity.DECISION_GRANTS["replace"])
    with case.session() as db, db.begin():
        role = Role(name="Synthetic reviewer")
        db.add(role)
        db.flush()
        db.add(AccessAssignment(user_id=case.principal.user.id, role_id=role.id, scope_type="site",
            customer_id=case.customer_id, site_id=case.site_id))
        permission_ids = {}
        for key in grant_keys:
            permission = db.scalar(select(Permission).where(Permission.key == key))
            if permission is None:
                permission = Permission(key=key, name=key)
                db.add(permission)
                db.flush()
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            permission_ids[key] = permission.id
        role_id = role.id

    def scoped_principal(db=Depends(get_db)):
        return _load_principal(db.get(User, case.principal.user.id), db)

    monkeypatch.setitem(case.client.app.dependency_overrides, get_principal, scoped_principal)
    locked, released = Event(), Event()
    lock = identity.IdentityReview.lock_references

    def wait_for_revocation(review):
        lock(review)
        locked.set()
        assert released.wait(8)

    monkeypatch.setattr(identity.IdentityReview, "lock_references", wait_for_revocation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(decide, case, row, "replace")
        try:
            assert locked.wait(6)
            with case.session() as db, db.begin():
                db.delete(db.get(RolePermission, (role_id, permission_ids["networks.edit"])))
        finally:
            released.set()
        reply = future.result(timeout=12)
    assert reply.status_code == 403, reply.text
    with case.session() as db:
        assert db.get(ProxmoxGuestIdentityDecision, uuid.UUID(row["id"])) is None
        assert db.get(DiscoveryRun, run.id).status == "completed"
        assert db.get(DataSource, case.source_id).identity_epoch == 0
