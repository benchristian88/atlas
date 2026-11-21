"""Real scoped HTTP decisions with independent PostgreSQL transaction checks."""

from concurrent.futures import ThreadPoolExecutor
from copy import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
    return next(row["parent"] for row in case.identity_reviews()
        if row["parent"]["status"] == "open" and row["parent"]["candidate_external_id"] == case.guest)


def decide(case, row, outcome="reactivate", reason="Verified against the guest inventory", **options):
    version_key = "replacement_expected_version" if outcome == "replace" else "expected_version"
    return case.decide(row, "identity-decision", outcome=outcome, reason=reason,
        expected_version=options.pop("expected_version", row["identity_review"][version_key]), **options)


def current_link(db, case, key, kind="asset"):
    return db.scalar(select(EntitySourceLink).where(EntitySourceLink.data_source_id == case.source_id,
        EntitySourceLink.entity_type == kind, EntitySourceLink.external_id == key, EntitySourceLink.ended_epoch.is_(None)))


def effects(case, row, run):
    """Independent read of committed source, asset, proposal and run state."""
    with case.session() as db:
        keys = ("assets", "asset_interfaces", "asset_relationships", "networks", "knowledge_assertions",
                "entity_source_links", "reconciliation_items", "data_sources",
                "discovery_batch_receipts", "run_observed_entities", "discovery_runs", "proxmox_guest_identity_decisions",
                "evidence_records", "knowledge_changes", "audit_events")
        snapshot = {table: db.execute(text(f"SELECT to_jsonb(r) FROM {table} r ORDER BY to_jsonb(r)")).scalars().all()
                    for table in keys}
        assert db.get(ReconciliationItem, uuid.UUID(row["id"])) is not None
        assert db.get(DiscoveryRun, run.id).status == "completed"
        return snapshot


def test_committed_complete_omission_blocks_replacement_until_fresh_positive_review(cases, monkeypatch):
    case = cases()
    prior = case.seed()
    case.retire()
    positive = case.run(name="Replacement guest")
    opened = review(case)
    assert opened["identity_review"]["actions"]["replace"] is None
    omission = case.run()
    fresh = review(case)
    assert (fresh["id"], fresh["assertion_id"], fresh["status"]) == (opened["id"], opened["assertion_id"], "open")
    assert fresh["identity_review"]["actions"]["replace"] == identity.GUEST_OMITTED
    assert fresh["identity_review"]["replacement_expected_version"] != opened["identity_review"]["replacement_expected_version"]
    before = effects(case, opened, omission)
    for row, reason in ((opened, identity.CHANGED), (fresh, identity.GUEST_OMITTED)):
        refused = decide(case, row, "replace")
        assert (refused.status_code, refused.json()["detail"]) == (409, reason)
    grant = case.principal.grants[0]
    with monkeypatch.context() as patch:
        patch.setitem(case.client.app.dependency_overrides, get_principal, lambda: replace(case.principal,
            grants=(replace(grant, permissions=grant.permissions - {"assets.create"}),)))
        restricted = review(case)["identity_review"]
        assert restricted["actions"]["replace"] == "You do not have the required permissions in this Customer and Site."
        assert restricted["replacement_expected_version"] == opened["identity_review"]["replacement_expected_version"]
        assert decide(case, fresh, "replace").status_code == 403
    assert effects(case, opened, omission) == before

    newest_omission = case.run()
    assert review(case)["identity_review"]["replacement_expected_version"] != fresh["identity_review"]["replacement_expected_version"]
    returned = case.run(name="Replacement guest")
    returned_review = review(case)
    assert returned_review["discovery_run_id"] == str(returned.id)
    assert returned_review["identity_review"]["actions"]["replace"] is None
    assert decide(case, opened, "replace").status_code == 409
    with case.session() as db:
        for observed in (positive, returned):
            member = db.scalar(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == observed.id,
                RunObservedEntity.entity_type == "asset", RunObservedEntity.external_id == case.guest))
            assert member.entity_id is None
        assert db.get(DiscoveryRun, newest_omission.id).summary["no_longer_observed_count"] == 0
        assert current_link(db, case, case.guest).entity_id == prior.asset
    assert decide(case, returned_review, "replace").status_code == 200


@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
@pytest.mark.parametrize("positive_first", [True, False], ids=["positive-first", "omission-first"])
@pytest.mark.parametrize("unrelated_advances", [0, 1, 2])
def test_tied_complete_run_start_blocks_identity_decisions(cases, outcome, positive_first, unrelated_advances):
    case = cases()
    original = case.seed()
    case.retire()
    others = []
    for vmid in range(1030, 1030 + unrelated_advances):
        other = copy(case)
        other.guest = f"guest/lxc/{vmid}"
        other.nic = f"{other.guest}/interface/net0"
        other.run(name=f"Unrelated guest {vmid}", completeness="partial")
        asset = other.accept(other.guest, "name")
        assert other.client.patch(f"/assets/{asset}", json={"status": "retired"}).status_code == 200
        others.append(other)
    with case.session() as db:
        original_binding = current_link(db, case, case.guest).id

    stamp = datetime.now(timezone.utc)
    if positive_first:
        positive = case.run(name="Guest evidence", stamp=stamp)
        opened = review(case)
        assert opened["identity_review"]["actions"][outcome] is None
    else:
        # A complete run can omit 1029 while providing positive evidence for 1030.
        omission = others[0].run(name="Unrelated guest 1030", stamp=stamp) if others else case.run(stamp=stamp)
        assert all(group["parent"]["candidate_external_id"] != case.guest for group in case.identity_reviews())
    for index, other in enumerate(others):
        if positive_first or index:
            other.run(name=f"Unrelated guest {1030 + index}", completeness="partial")
        assert decide(other, review(other), "reactivate").status_code == 200
    if positive_first:
        assert review(case)["identity_review"] == opened["identity_review"]
        omission = case.run(stamp=stamp)
    else:
        positive = case.run(name="Guest evidence", stamp=stamp)

    fresh = review(case)
    assert fresh == review(case)
    assert fresh["discovery_run_id"] == str(positive.id)
    assert fresh["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS, identity.AMBIGUOUS_DISCOVERY_START)
    first, second = (positive, omission) if positive_first else (omission, positive)
    with case.session() as db:
        earlier, later = (db.get(DiscoveryRun, run.id) for run in (first, second))
        assert earlier.started_at == later.started_at == stamp
        assert earlier.completed_at < later.completed_at
        assert earlier.finalisation_hash and later.finalisation_hash
        assert (earlier.completeness_status, later.completeness_status) == ("complete", "complete")
        assert (earlier.identity_epoch, later.identity_epoch) == (0, unrelated_advances)
        binding = current_link(db, case, case.guest)
        assert (binding.id, binding.entity_id, binding.opened_epoch) == (original_binding, original.asset, 0)
        member = db.scalar(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == positive.id,
            RunObservedEntity.entity_type == "asset", RunObservedEntity.external_id == case.guest))
        assert member.entity_id is None and member.evidence_record_id is not None

    before = effects(case, fresh, second)
    if positive_first:
        key = "expected_version" if outcome == "reactivate" else "replacement_expected_version"
        assert opened["identity_review"][key] != fresh["identity_review"][key]
        stale = decide(case, opened, outcome)
        assert (stale.status_code, stale.json()["detail"]) == (409, identity.CHANGED)
    refused = decide(case, fresh, outcome)
    assert (refused.status_code, refused.json()["detail"]) == (409, identity.AMBIGUOUS_DISCOVERY_START)
    assert effects(case, fresh, second) == before

    returned = case.run(name="Fresh guest evidence", stamp=stamp + timedelta(seconds=1))
    renewed = review(case)
    assert renewed["discovery_run_id"] == str(returned.id)
    assert renewed["identity_review"]["actions"][outcome] is None
    assert decide(case, fresh, outcome).status_code == 409
    assert decide(case, renewed, outcome).status_code == 200


@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
@pytest.mark.parametrize("completions", [("complete", "partial"), ("partial", "complete"), ("partial", "partial")],
    ids=["complete-first", "partial-first", "two-partial"])
@pytest.mark.parametrize("advance_other", [False, True], ids=["same-epoch", "cross-epoch"])
def test_tied_positive_runs_keep_preview_and_invalidate_both_confirmation_tokens(cases, outcome, completions, advance_other):
    case = cases()
    case.seed()
    case.retire()
    if advance_other:
        other = copy(case)
        other.guest, other.nic = "guest/lxc/1030", "guest/lxc/1030/interface/net0"
        other.run(name="Unrelated guest", completeness="partial")
        other_asset = other.accept(other.guest, "name")
        assert other.client.patch(f"/assets/{other_asset}", json={"status": "retired"}).status_code == 200
    stamp = datetime.now(timezone.utc)
    low = uuid.UUID("00000000-0000-4000-8000-000000000001")
    high = uuid.UUID("ffffffff-ffff-4fff-bfff-ffffffffffff")
    first_id, second_id = (low, high) if outcome == "reactivate" else (high, low)
    first = case.run(name="First positive", stamp=stamp, run_id=first_id, completeness=completions[0])
    original = review(case)
    assert original["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS)
    if advance_other:
        other.run(name="Unrelated guest evidence", completeness="partial", coverage_key="unrelated-review")
        assert decide(other, review(other)).status_code == 200
    second = case.run(name="Conflicting positive", mac=MAC_B, stamp=stamp, run_id=second_id, completeness=completions[1])
    blocked = review(case)
    assert blocked["assertion_id"] == original["assertion_id"] and blocked["discovery_run_id"] == str(first.id)
    assert blocked["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS, identity.AMBIGUOUS_DISCOVERY_START)
    flat = case.client.get("/reconciliation-items", params={"entity_type": "source_identity", "source_id": str(case.source_id)})
    assert flat.status_code == 200
    assert next(row for row in flat.json() if row["id"] == blocked["id"])["identity_review"] == blocked["identity_review"]
    for version_key in ("expected_version", "replacement_expected_version"):
        assert blocked["identity_review"][version_key] != original["identity_review"][version_key]
    with case.session() as db:
        first_run, second_run = (db.get(DiscoveryRun, staged.id) for staged in (first, second))
        assert first_run.started_at == second_run.started_at == stamp and first_run.completed_at < second_run.completed_at
        assert (first_run.identity_epoch, second_run.identity_epoch) == (0, int(advance_other))
        members = list(db.scalars(select(RunObservedEntity).where(
            RunObservedEntity.discovery_run_id.in_([first.id, second.id]),
            RunObservedEntity.entity_type == "asset", RunObservedEntity.external_id == case.guest)))
        assert len(members) == 2 and all(row.entity_id is None and row.evidence_record_id for row in members)
        retained = db.scalar(select(KnowledgeAssertion).where(
            KnowledgeAssertion.discovery_run_id == second.id, KnowledgeAssertion.subject_type == "source_identity"))
        assert retained.superseded_by_id == uuid.UUID(original["assertion_id"])
    before = effects(case, blocked, second)
    for row, reason in ((original, identity.CHANGED), (blocked, identity.AMBIGUOUS_DISCOVERY_START)):
        reply = decide(case, row, outcome)
        assert (reply.status_code, reply.json()["detail"]) == (409, reason)
    assert effects(case, blocked, second) == before
    newer = case.run(name="Distinct evidence", completeness="partial", stamp=stamp + timedelta(seconds=1))
    renewed = review(case)
    assert renewed["discovery_run_id"] == str(newer.id)
    assert renewed["identity_review"]["actions"][outcome] is None
    assert decide(case, blocked, outcome).status_code == 409
    assert decide(case, renewed, outcome).status_code == 200


@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
@pytest.mark.parametrize("omission_offset", [-1, 0, 1], ids=["older-omission", "tied", "newer-omission"])
@pytest.mark.parametrize("positive_first", [True, False], ids=["positive-first", "omission-first"])
def test_partial_positive_and_complete_omission_follow_server_start(cases, outcome, omission_offset, positive_first):
    case = cases()
    case.seed()
    case.retire()
    stamp = datetime.now(timezone.utc) + timedelta(seconds=2)
    positive_options = {"name": "Partial guest evidence", "stamp": stamp, "completeness": "partial"}
    omission_options = {"stamp": stamp + timedelta(seconds=omission_offset)}
    if positive_first:
        case.run(**positive_options)
        original = review(case)
        last = case.run(**omission_options)
    else:
        case.run(**omission_options)
        last = case.run(**positive_options)
    row = review(case)
    if omission_offset < 0:
        assert row["identity_review"]["actions"][outcome] is None
        assert decide(case, original if positive_first else row, outcome).status_code == 200
        return
    reason = identity.AMBIGUOUS_DISCOVERY_START if omission_offset == 0 else {
        "reactivate": identity.REACTIVATION_GUEST_OMITTED, "replace": identity.GUEST_OMITTED,
    }[outcome]
    assert row["identity_review"]["actions"][outcome] == reason
    before = effects(case, row, last)
    if positive_first:
        stale = decide(case, original, outcome)
        assert (stale.status_code, stale.json()["detail"]) == (409, identity.CHANGED)
    blocked = decide(case, row, outcome)
    assert (blocked.status_code, blocked.json()["detail"]) == (409, reason)
    assert effects(case, row, last) == before


@pytest.mark.parametrize("relationship_first", [True, False])
def test_partial_relationship_only_hold_participates_in_equal_start_ambiguity(cases, relationship_first):
    case = cases()
    case.seed()
    case.retire()
    stamp = datetime.now(timezone.utc)
    first = case.run(name="First evidence", guest_relationship_only=relationship_first, completeness="partial", stamp=stamp)
    original = review(case)
    assert original["identity_review"]["actions"]["reactivate"] is None
    second = case.run(name="Same-start evidence", guest_relationship_only=not relationship_first,
                      completeness="partial", stamp=stamp)
    blocked = review(case)
    assert blocked["discovery_run_id"] == str(first.id)
    assert blocked["identity_review"]["actions"]["reactivate"] == identity.AMBIGUOUS_DISCOVERY_START
    before = effects(case, blocked, second)
    for row, reason in ((original, identity.CHANGED), (blocked, identity.AMBIGUOUS_DISCOVERY_START)):
        response = decide(case, row)
        assert (response.status_code, response.json()["detail"]) == (409, reason)
    assert effects(case, blocked, second) == before
    case.run(name="Fresh relationship-only evidence", guest_relationship_only=True,
             completeness="partial", stamp=stamp + timedelta(seconds=1))
    assert decide(case, review(case)).status_code == 200


def tied_relationship_review(case):
    case.seed()
    case.run(node="node-b", completeness="partial")
    host = case.accept("node/node-b", "name")
    case.retire()
    stamp = datetime.now(timezone.utc)
    first = case.run(name="Reviewed on node-a", stamp=stamp)
    original = review(case)
    assert original["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS)
    competing = case.run(name="Guest on node-b", stamp=stamp, guest_relationship_only=True,
                         relationship_target="node/node-b", completeness="partial")
    tied = review(case)
    assert tied["discovery_run_id"] == str(first.id)
    assert tied["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS, identity.AMBIGUOUS_DISCOVERY_START)
    with case.session() as db:
        proofs = db.scalars(select(KnowledgeAssertion.id).join(EvidenceRecord,
            EvidenceRecord.id == KnowledgeAssertion.evidence_record_id).where(
            KnowledgeAssertion.subject_id == host, KnowledgeAssertion.is_accepted.is_(True),
            KnowledgeAssertion.retracted_at.is_(None), EvidenceRecord.external_id == "node/node-b")
            .order_by(KnowledgeAssertion.id)).all()
    assert proofs
    return stamp, original, competing, tied, proofs


def retract_host_proof(case, claim_id, *, actor="retraction"):
    return case.client.post(f"/assertions/{claim_id}/retract", headers={"x-test-actor": actor},
        json={"reason": "Retract host corroboration", "confirm_provenance_gap": True})


@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
@pytest.mark.parametrize("legacy", [False, True], ids=["sealed-marker", "legacy-hold"])
def test_retraction_cannot_forget_a_tied_relationship_hold(cases, outcome, legacy):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    case = cases()
    stamp, original, competing, tied, proofs = tied_relationship_review(case)
    with case.session() as db, db.begin():
        claim = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == competing.id,
            KnowledgeAssertion.subject_type == "source_identity"))
        assert claim.value_json["identity_positive"] is True
        if legacy:
            claim.value_json = {key: value for key, value in claim.value_json.items() if key != "identity_positive"}
        competing_claim_id = claim.id
    assert review(case)["identity_review"] == tied["identity_review"]
    for claim_id in proofs:
        response = retract_host_proof(case, claim_id)
        assert response.status_code == 200, response.text
        assert review(case)["identity_review"] == tied["identity_review"]
    assert retract_host_proof(case, proofs[-1]).status_code == 409

    # Recreate the HTTP service and discard its pooled database connections.
    case.engine.dispose()
    app = FastAPI()
    app.include_router(case.client.app.router)
    app.dependency_overrides.update(case.client.app.dependency_overrides)
    case.client = TestClient(app)
    refreshed = review(case)
    assert refreshed["identity_review"] == tied["identity_review"]
    with case.session() as db:
        claim = db.get(KnowledgeAssertion, competing_claim_id)
        assert claim.retracted_at is None and claim.superseded_by_id == uuid.UUID(original["assertion_id"])
        assert db.get(DiscoveryBatchReceipt, (competing.id, 1)).payload_json == competing.batch
    before = effects(case, refreshed, competing)
    for comparison, reason in ((original, identity.CHANGED), (refreshed, identity.AMBIGUOUS_DISCOVERY_START)):
        reply = decide(case, comparison, outcome)
        assert (reply.status_code, reply.json()["detail"]) == (409, reason)
    assert effects(case, refreshed, competing) == before

    case.run(name="Later distinct positive", stamp=stamp + timedelta(seconds=1), completeness="partial")
    renewed = review(case)
    assert renewed["identity_review"]["actions"][outcome] is None
    assert decide(case, original, outcome).status_code == 409
    assert decide(case, refreshed, outcome).status_code == 409
    assert decide(case, renewed, outcome).status_code == 200


def test_selected_host_corroboration_cannot_return_to_an_earlier_token(cases):
    case = cases()
    case.seed()
    case.run(node="node-b", completeness="partial")
    host = case.accept("node/node-b", "name")
    case.retire()
    run = case.run(name="Relationship-only guest", guest_relationship_only=True,
                   relationship_target="node/node-b", completeness="partial")
    original = review(case)
    assert original["identity_review"]["actions"]["reactivate"] is None
    with case.session() as db, db.begin():
        proof = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == host,
            KnowledgeAssertion.predicate == "name", KnowledgeAssertion.is_accepted.is_(True)))
        # Two accepted predicates can corroborate the same endpoint record.
        # Seed a distinct preferred proof without modifying the canonical Asset.
        supplemental = KnowledgeAssertion(id=uuid.UUID(int=1), customer_id=case.customer_id,
            site_id=case.site_id, data_source_id=case.source_id, subject_type="asset", subject_id=host,
            subject_external_id="node/node-b", predicate="fixture.host_proof", value_json=True,
            discovery_run_id=proof.discovery_run_id, evidence_record_id=proof.evidence_record_id,
            first_observed_at=proof.first_observed_at, last_observed_at=proof.last_observed_at,
            truth_classification="observed", confirmation_status="confirmed", is_accepted=True)
        db.add(supplemental)
    changed = review(case)
    version = "expected_version"
    assert changed["identity_review"][version] != original["identity_review"][version]
    assert changed["identity_review"]["actions"]["reactivate"] is None
    response = retract_host_proof(case, uuid.UUID(int=1))
    assert response.status_code == 200, response.text
    fallback = review(case)
    assert fallback["assertion_id"] == original["assertion_id"]
    assert fallback["identity_review"]["actions"]["reactivate"] is None
    assert fallback["identity_review"][version] not in {
        original["identity_review"][version], changed["identity_review"][version],
    }
    before = effects(case, fallback, run)
    for old in (original, changed):
        assert decide(case, old).status_code == 409
    assert effects(case, fallback, run) == before
    assert decide(case, fallback).status_code == 200


def test_discovery_refresh_of_host_proof_cannot_restore_an_older_token(cases):
    case = cases()
    case.seed()
    stamp = datetime.now(timezone.utc)
    case.run(node="node-b", completeness="partial", observed_stamp=stamp)
    host = case.accept("node/node-b", "name")
    retained_run = case.run(node="node-b", completeness="partial", observed_stamp=stamp + timedelta(seconds=1))
    with case.session() as db, db.begin():
        retained_record = db.scalar(select(EvidenceRecord).where(EvidenceRecord.discovery_run_id == retained_run.id,
            EvidenceRecord.entity_kind == "asset", EvidenceRecord.external_id == "node/node-b"))
        db.add(KnowledgeAssertion(customer_id=case.customer_id, site_id=case.site_id, data_source_id=case.source_id,
            subject_type="asset", subject_id=host, subject_external_id="node/node-b", predicate="fixture.retained_fact",
            value_json=True, discovery_run_id=retained_run.id, evidence_record_id=retained_record.id,
            first_observed_at=retained_record.observed_at, last_observed_at=retained_record.observed_at,
            truth_classification="observed", confirmation_status="confirmed", is_accepted=True))
    case.run(node="node-b", completeness="partial", observed_stamp=stamp)
    case.retire()
    run = case.run(name="Relationship-only guest", guest_relationship_only=True,
                   relationship_target="node/node-b", completeness="partial")
    original = review(case)
    assert original["identity_review"]["actions"]["reactivate"] is None
    case.run(node="node-b", completeness="partial", observed_stamp=stamp + timedelta(seconds=2))
    changed = review(case)
    assert changed["identity_review"]["expected_version"] != original["identity_review"]["expected_version"]
    assert decide(case, original).status_code == 409

    # The connector can report a clock correction on a later server-admitted
    # run. The originally selected retained fact is preferred again.
    case.run(node="node-b", completeness="partial", observed_stamp=stamp)
    fallback = review(case)
    assert fallback["discovery_run_id"] == original["discovery_run_id"]
    assert fallback["identity_review"]["actions"]["reactivate"] is None
    before = effects(case, fallback, run)
    for old in (original, changed):
        assert decide(case, old).status_code == 409
    assert effects(case, fallback, run) == before
    assert decide(case, fallback).status_code == 200


@pytest.mark.parametrize("winner", ["retraction", "decision"])
@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
def test_tied_hold_retraction_and_identity_post_serialize_on_source(cases, winner, outcome):
    case = cases()
    _, original, competing, blocked, proofs = tied_relationship_review(case)
    for claim_id in proofs[:-1]:
        assert retract_host_proof(case, claim_id).status_code == 200
    before = effects(case, blocked, competing)
    locked, attempted, release = Event(), Event(), Event()
    pids = {}

    def before_sql(conn, cursor, sql, parameters, execution, many):
        if (execution.execution_options.get("test_actor") == "racer"
                and "FROM data_sources" in sql and "FOR NO KEY UPDATE" in sql):
            pids["racer"] = conn.connection.driver_connection.info.backend_pid
            attempted.set()

    def after_sql(conn, cursor, sql, parameters, execution, many):
        if (execution.execution_options.get("test_actor") == "holder"
                and "FROM data_sources" in sql and "FOR NO KEY UPDATE" in sql and not locked.is_set()):
            pids["holder"] = conn.connection.driver_connection.info.backend_pid
            locked.set()
            assert release.wait(10)

    def retraction(actor):
        return retract_host_proof(case, proofs[-1], actor=actor)

    def decision(actor):
        return decide(case, original, outcome, actor=actor)

    event.listen(case.engine, "before_cursor_execute", before_sql)
    event.listen(case.engine, "after_cursor_execute", after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = (retraction, decision) if winner == "retraction" else (decision, retraction)
            holding = pool.submit(first, "holder")
            try:
                assert locked.wait(7)
                waiting = pool.submit(second, "racer")
                assert attempted.wait(7)
                deadline = monotonic() + 5
                with case.session() as db:
                    while pids["holder"] not in db.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["racer"]}):
                        assert monotonic() < deadline
                        sleep(0.02)
            finally:
                release.set()
            results = (holding.result(timeout=15), waiting.result(timeout=15))
    finally:
        event.remove(case.engine, "before_cursor_execute", before_sql)
        event.remove(case.engine, "after_cursor_execute", after_sql)
    retracted, refused = results if winner == "retraction" else results[::-1]
    assert retracted.status_code == 200, retracted.text
    assert (refused.status_code, refused.json()["detail"]) == (409, identity.CHANGED)
    refreshed = review(case)
    assert refreshed["identity_review"] == blocked["identity_review"]
    after = effects(case, blocked, competing)
    for table in before.keys() - {"knowledge_assertions", "knowledge_changes", "audit_events"}:
        assert after[table] == before[table], table
    for table in ("knowledge_changes", "audit_events"):
        assert len(after[table]) == len(before[table]) + 1
    old_assertions = {row["id"]: row for row in before["knowledge_assertions"]}
    current_assertions = {row["id"]: row for row in after["knowledge_assertions"]}
    assert old_assertions.keys() == current_assertions.keys()
    assert [key for key in old_assertions if old_assertions[key] != current_assertions[key]] == [str(proofs[-1])]
    response = decide(case, refreshed, outcome)
    assert (response.status_code, response.json()["detail"]) == (409, identity.AMBIGUOUS_DISCOVERY_START)
    assert effects(case, blocked, competing) == after


@pytest.mark.parametrize("invalid_first", [True, False])
@pytest.mark.parametrize("invalid_id_first", [True, False])
def test_only_positive_observation_owns_preview_at_same_start(cases, invalid_first, invalid_id_first):
    case = cases()
    case.seed()
    case.retire()
    stamp = datetime.now(timezone.utc)
    low = uuid.UUID("00000000-0000-4000-8000-000000000001")
    high = uuid.UUID("ffffffff-ffff-4fff-bfff-ffffffffffff")
    invalid_id, valid_id = (low, high) if invalid_id_first else (high, low)
    invalid = {"run_id": invalid_id, "name": "Unverified Interface only",
               "dependencies_only": True, "mismatched_interface_owner": True}
    valid = {"run_id": valid_id, "name": "Verified guest"}
    first, second = (invalid, valid) if invalid_first else (valid, invalid)
    run = case.run(**first, stamp=stamp, completeness="partial")
    prior = review(case)
    assert (prior["identity_review"]["actions"]["reactivate"] is None) == (not invalid_first)
    case.run(**second, stamp=stamp, completeness="partial")
    current = review(case)
    assert current["discovery_run_id"] == str(valid_id)
    assert current["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS)
    with case.session() as db:
        diagnostics = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == invalid_id,
            KnowledgeAssertion.subject_type == "source_identity"))
        assert diagnostics.value_json["identity_positive"] is False and diagnostics.value_json["held_evidence_ids"]
        assert diagnostics.superseded_by_id == uuid.UUID(current["assertion_id"])
    if invalid_first:
        before = effects(case, current, run)
        for outcome in identity.DECISION_GRANTS:
            assert decide(case, prior, outcome).status_code == 409
        assert effects(case, current, run) == before
    else:
        assert current["identity_review"] == prior["identity_review"]
    assert decide(case, current, "replace").status_code == 200


@pytest.mark.parametrize("relative_start", [-1, 1], ids=["older", "newer"])
def test_earlier_source_epoch_omission_uses_start_time_for_unchanged_binding(cases, relative_start):
    case = cases()
    case.seed()
    case.retire()
    other = copy(case)
    other.guest, other.nic = "guest/lxc/1030", "guest/lxc/1030/interface/net0"
    other.run(name="Other guest", completeness="partial")
    other_asset = other.accept(other.guest, "name")
    assert other.client.patch(f"/assets/{other_asset}", json={"status": "retired"}).status_code == 200
    stamp = datetime.now(timezone.utc) + timedelta(seconds=2)
    omission = other.run(name="Other guest", stamp=stamp + timedelta(seconds=relative_start))
    advanced = decide(other, review(other))
    assert advanced.status_code == 200, advanced.text
    selected = case.run(name="Reviewed guest", stamp=stamp)
    row = review(case)
    with case.session() as db:
        older_epoch = db.get(DiscoveryRun, omission.id)
        newer_epoch = db.get(DiscoveryRun, selected.id)
        assert (older_epoch.identity_epoch, newer_epoch.identity_epoch) == (0, 1)
        assert (older_epoch.started_at - newer_epoch.started_at).total_seconds() == relative_start
    if relative_start == 1:
        assert row["identity_review"]["actions"] == {
            "reactivate": identity.REACTIVATION_GUEST_OMITTED, "replace": identity.GUEST_OMITTED,
        }
        before = effects(case, row, selected)
        for outcome, reason in row["identity_review"]["actions"].items():
            reply = decide(case, row, outcome)
            assert (reply.status_code, reply.json()["detail"]) == (409, reason)
        assert effects(case, row, selected) == before
    else:
        assert row["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS)
        assert decide(case, row, "replace").status_code == 200


@pytest.mark.parametrize("cutover", ["reactivate", "replace"])
@pytest.mark.parametrize("relative_start, advance_other", [(0, False), (1, False), (1, True)],
    ids=["tied", "newer", "newer-with-in-window-tie"])
def test_prior_guest_evidence_window_ends_at_its_own_decision(cases, cutover, relative_start, advance_other):
    case = cases()
    original = case.seed()
    case.retire()
    stamp = datetime.now(timezone.utc)
    historic = case.run(stamp=stamp + timedelta(seconds=relative_start))
    # Make the first decision using different coverage so the historic omission
    # can challenge the next review's boundary independently of the first.
    case.run(name="First decision evidence", coverage_key="first-decision-scope")
    previous = review(case)
    with case.session() as db:
        old_binding_id = current_link(db, case, case.guest).id
    assert decide(case, previous, cutover).status_code == 200
    with case.session() as db:
        binding = current_link(db, case, case.guest)
        asset_id = binding.entity_id
        if cutover == "replace":
            assert asset_id != original.asset and binding.id != old_binding_id and binding.opened_epoch == 1
            old = db.get(EntitySourceLink, old_binding_id)
            assert (old.entity_id, old.ended_epoch, old.external_id) == (original.asset, 1, case.guest)
        else:
            assert (asset_id, binding.id, binding.opened_epoch) == (original.asset, old_binding_id, 0)
    assert case.client.patch(f"/assets/{asset_id}", json={"status": "retired"}).status_code == 200
    if advance_other:
        omission = case.run(stamp=stamp)
        other = copy(case)
        other.guest, other.nic = "guest/lxc/1030", "guest/lxc/1030/interface/net0"
        other.run(name="Other guest", completeness="partial")
        other_asset = other.accept(other.guest, "name")
        assert other.client.patch(f"/assets/{other_asset}", json={"status": "retired"}).status_code == 200
        other.run(name="Other guest", completeness="partial", coverage_key="unrelated-decision-scope")
        assert decide(other, review(other)).status_code == 200
    selected = case.run(name="Guest now using this slot", stamp=stamp)
    current = review(case)
    assert current["id"] != previous["id"] and current["entity_id"] == str(asset_id)
    assert current["discovery_run_id"] == str(selected.id)
    reason = identity.AMBIGUOUS_DISCOVERY_START if advance_other else None
    assert current["identity_review"]["actions"] == dict.fromkeys(identity.DECISION_GRANTS, reason)
    with case.session() as db:
        old_run, new_run = db.get(DiscoveryRun, historic.id), db.get(DiscoveryRun, selected.id)
        assert (old_run.identity_epoch, new_run.identity_epoch) == (0, 2 if advance_other else 1)
        assert old_run.coverage_key == new_run.coverage_key
        assert (old_run.started_at - new_run.started_at).total_seconds() == relative_start
        if advance_other:
            tied_run = db.get(DiscoveryRun, omission.id)
            assert tied_run.identity_epoch == 1 and tied_run.started_at == new_run.started_at
    before = effects(case, current, selected)
    prior_token = previous["identity_review"]["expected_version"]
    stale = decide(case, current, expected_version=prior_token)
    assert (stale.status_code, stale.json()["detail"]) == (409, identity.CHANGED)
    if advance_other:
        for outcome in identity.DECISION_GRANTS:
            blocked = decide(case, current, outcome)
            assert (blocked.status_code, blocked.json()["detail"]) == (409, reason)
    assert effects(case, current, selected) == before
    if advance_other:
        case.run(name="Fresh guest evidence", stamp=stamp + timedelta(seconds=2))
        current = review(case)
    assert decide(case, current, "reactivate").status_code == 200


def test_tied_newest_comparable_starts_are_ambiguous_even_after_a_strictly_older_review(cases):
    case = cases()
    case.seed()
    case.retire()
    stamp = datetime.now(timezone.utc)
    case.run(name="Guest evidence", stamp=stamp)
    later = stamp + timedelta(seconds=1)
    case.run(stamp=later)
    opened = review(case)
    assert opened["identity_review"]["actions"]["replace"] == identity.GUEST_OMITTED
    case.run(stamp=later)
    latest = review(case)
    assert latest["identity_review"]["actions"]["replace"] == identity.AMBIGUOUS_DISCOVERY_START
    assert latest["identity_review"]["replacement_expected_version"] != opened["identity_review"]["replacement_expected_version"]
    assert decide(case, opened, "replace").status_code == 409
    assert decide(case, latest, "replace").status_code == 409


@pytest.mark.parametrize("path,params", [
    ("/reconciliation-entities", {}),
    ("/reconciliation-items", {"entity_type": "source_identity"}),
])
def test_review_get_during_relationship_only_completion_requires_refresh(cases, path, params):
    case = cases()
    case.seed()
    case.retire()
    case.run(name="Original guest evidence")
    opened = review(case)
    staged = case.stage(name="Guest with fresh relationship evidence", guest_relationship_only=True)
    reached, resume = Event(), Event()

    def before_sql(conn, cursor, sql, parameters, execution, many):
        if (execution.execution_options.get("test_actor") == "review-reader"
                and "ORDER BY discovery_runs.started_at DESC" in sql
                and "run_observed_entities.coverage_key" in sql and not reached.is_set()):
            reached.set()
            assert resume.wait(10)

    event.listen(case.engine, "before_cursor_execute", before_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading = pool.submit(case.client.get, path, params={"source_id": str(case.source_id), **params},
                headers={"x-test-actor": "review-reader"})
            try:
                assert reached.wait(7), "review did not reach the newest-run query"
                assert case.complete(staged)["status"] == "completed"
                before = effects(case, opened, staged)
            finally:
                resume.set()
            conflicted = reading.result(timeout=12)
    finally:
        event.remove(case.engine, "before_cursor_execute", before_sql)

    assert (conflicted.status_code, conflicted.json()["detail"]) == (409, identity.CHANGED)
    fresh = review(case)
    assert fresh["discovery_run_id"] == str(staged.id)
    assert fresh["identity_review"]["actions"] == {"reactivate": None, "replace": identity.MISSING_GUEST}
    assert decide(case, opened, "reactivate").status_code == 409
    assert effects(case, opened, staged) == before
    assert decide(case, fresh, "reactivate").status_code == 200


def test_incomparable_omissions_leave_replacement_action_and_version_available(cases, monkeypatch):
    case = cases("qemu")
    case.seed()
    case.retire()
    positive = case.run(name="Replacement guest", completeness="partial")
    opened = review(case)
    for options in ({"completeness": "partial"}, {"completeness": "failed"},
                    {"coverage_key": "different-inventory"}):
        case.run(**options)
        assert review(case)["identity_review"] == opened["identity_review"]

    for other in (cases(alongside=case, same_site=True), cases(alongside=case), cases()):
        assert other.coverage["key"] == case.coverage["key"]
        other.run()
        assert review(case)["identity_review"] == opened["identity_review"]

    simulated = case.client.post("/discovery/simulate", json={"customer_id": str(case.customer_id),
        "site_id": str(case.site_id), "data_source_id": str(case.source_id), "coverage_key": case.coverage["key"],
        "is_complete_snapshot": True, "observations": [
            {"external_id": "node/node-a", "name": "node-a", "asset_type": "hypervisor_node"}]})
    assert simulated.status_code == 200, simulated.text
    assert review(case)["identity_review"] == opened["identity_review"]

    with monkeypatch.context() as patch:
        patch.setattr(case, "provenance", {**case.provenance,
            "object_classes": [cls for cls in case.provenance["object_classes"] if cls != "proxmox.qemu"]})
        case.run()
    assert review(case)["identity_review"] == opened["identity_review"]

    positive_start = datetime.fromisoformat(positive.batch["observed_at"])
    delayed = case.run(stamp=positive_start - timedelta(seconds=1), observed_stamp=positive_start + timedelta(seconds=1))
    with case.session() as db:
        earlier, reviewed = (db.get(DiscoveryRun, run.id) for run in (delayed, positive))
        assert earlier.started_at < reviewed.started_at and earlier.finished_at > reviewed.finished_at
    assert review(case)["identity_review"] == opened["identity_review"]
    assert decide(case, opened, "replace").status_code == 200


def test_omission_after_unrelated_slot_decision_still_covers_the_original_binding(cases):
    case = cases()
    original = case.seed()
    case.retire()
    other = copy(case)
    other.guest, other.nic = "guest/lxc/1030", "guest/lxc/1030/interface/net0"
    other.run(name="Other guest", completeness="partial")
    other_asset = other.accept(other.guest, "name")
    assert other.client.patch(f"/assets/{other_asset}", json={"status": "retired"}).status_code == 200
    other.run(name="Other replacement", completeness="partial")
    other_review = review(other)
    positive = case.run(name="Original slot replacement", completeness="partial")
    opened = next(group["parent"] for group in case.identity_reviews() if group["parent"]["candidate_external_id"] == case.guest)
    accepted = decide(other, other_review, "replace")
    assert accepted.status_code == 200, accepted.text
    assert review(case)["identity_review"] == opened["identity_review"]

    omission = case.run()
    fresh = review(case)
    assert fresh["identity_review"]["actions"]["replace"] == identity.GUEST_OMITTED
    assert fresh["identity_review"]["actions"]["reactivate"] == identity.REACTIVATION_GUEST_OMITTED
    assert decide(case, opened, "replace").status_code == 409
    assert decide(case, opened, "reactivate").status_code == 409
    with case.session() as db:
        assert db.get(DiscoveryRun, positive.id).identity_epoch == 0
        assert db.get(DiscoveryRun, omission.id).identity_epoch == 1
        binding = current_link(db, case, case.guest)
        assert (binding.entity_id, binding.opened_epoch) == (original.asset, 0)


@pytest.mark.parametrize("status", ["retired", "active"])
def test_complete_omission_blocks_reactivation_until_fresh_positive_review(cases, status):
    case = cases()
    original = case.seed()
    case.retire()
    if status == "active":
        assert case.client.patch(f"/assets/{original.asset}", json={"status": "active"}).status_code == 200
    case.run(name="Same guest")
    opened = review(case)
    assert opened["identity_review"]["actions"]["reactivate"] is None

    omission = case.run()
    fresh = review(case)
    assert (fresh["id"], fresh["assertion_id"], fresh["status"]) == (opened["id"], opened["assertion_id"], "open")
    assert fresh["identity_review"]["actions"]["reactivate"] == identity.REACTIVATION_GUEST_OMITTED
    assert fresh["identity_review"]["expected_version"] != opened["identity_review"]["expected_version"]
    if status == "active":
        assert fresh["identity_review"]["actions"]["replace"] == identity.ACTIVE_ASSET
        assert fresh["identity_review"]["replacement_expected_version"] == opened["identity_review"]["replacement_expected_version"]
    before = effects(case, opened, omission)
    for row, reason in ((opened, identity.CHANGED), (fresh, identity.REACTIVATION_GUEST_OMITTED)):
        refused = decide(case, row, "reactivate")
        assert (refused.status_code, refused.json()["detail"]) == (409, reason)
    assert effects(case, opened, omission) == before

    positive = case.run(name="Same guest", completeness="partial")
    returned = review(case)
    assert returned["discovery_run_id"] == str(positive.id)
    assert returned["identity_review"]["actions"]["reactivate"] is None
    assert decide(case, opened, "reactivate").status_code == 409
    assert decide(case, fresh, "reactivate").status_code == 409
    assert decide(case, returned, "reactivate").status_code == 200
    with case.session() as db:
        assert db.get(Asset, original.asset).status == "active"
        assert current_link(db, case, case.guest).entity_id == original.asset
        change = db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == uuid.UUID(opened["id"])))
        assert change.change_type == ("lifecycle_changed" if status == "retired" else "identity_confirmed")


@pytest.mark.parametrize("completeness", ["complete", "partial"])
def test_verified_relationship_only_run_supplies_positive_reactivation_evidence(cases, completeness):
    case = cases()
    original = case.seed()
    case.retire()
    relationship = case.run(name="Same guest", guest_relationship_only=True)
    opened = review(case)
    assert opened["discovery_run_id"] == str(relationship.id)
    assert opened["identity_review"]["actions"] == {"reactivate": None, "replace": identity.MISSING_GUEST}

    case.run(completeness="partial")
    assert review(case)["identity_review"] == opened["identity_review"]
    omission = case.run()
    fresh = review(case)
    assert fresh["identity_review"]["actions"]["reactivate"] == identity.REACTIVATION_GUEST_OMITTED
    assert fresh["identity_review"]["replacement_expected_version"] == opened["identity_review"]["replacement_expected_version"]
    assert decide(case, opened, "reactivate").status_code == 409
    assert decide(case, fresh, "reactivate").json()["detail"] == identity.REACTIVATION_GUEST_OMITTED

    # Manual lifecycle editing remains independently authorized. Activating the
    # Asset manually does not acknowledge the held retirement revision.
    assert case.client.patch(f"/assets/{original.asset}", json={"status": "active"}).status_code == 200
    assert review(case)["identity_review"]["actions"]["reactivate"] == identity.REACTIVATION_GUEST_OMITTED
    later_relationship = case.run(name="Same guest", guest_relationship_only=True, completeness=completeness)
    returned = review(case)
    assert returned["discovery_run_id"] == str(later_relationship.id)
    assert not returned["proposed"]["guest_observed"]
    assert returned["identity_review"]["actions"] == {"reactivate": None, "replace": identity.ACTIVE_ASSET}
    assert decide(case, fresh, "reactivate").status_code == 409
    assert decide(case, returned, "reactivate").status_code == 200
    with case.session() as db:
        for run in (relationship, omission, later_relationship):
            assert db.scalar(select(RunObservedEntity.id).where(RunObservedEntity.discovery_run_id == run.id,
                RunObservedEntity.entity_type == "asset", RunObservedEntity.external_id == case.guest)) is None
        decision = db.get(ProxmoxGuestIdentityDecision, uuid.UUID(opened["id"]))
        assert decision.replacement_binding_id is None and current_link(db, case, case.guest).id == decision.old_binding_id


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
    unrelated = copy(case)
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
    assert decide(unrelated, review(unrelated), "replace").status_code == 200
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


@pytest.mark.parametrize("first", ["decision", "omission decision", "completion", "omission completion", "two reviewers",
    "reactivate omission decision", "reactivate omission completion", "partial tie decision", "partial tie completion",
    "reactivate partial tie decision", "reactivate partial tie completion"])
def test_identity_decision_serializes_with_reviewers_and_completion(cases, first):
    case = cases()
    prior = case.seed()
    case.retire()
    stamp = datetime.now(timezone.utc)
    sealed = case.run(name="First evidence", stamp=stamp)
    held = review(case)
    omission = "omission" in first
    tied_partial = "partial tie" in first
    outcome = "reactivate" if first.startswith("reactivate") else "replace"
    staged = case.stage(name=None if omission else "Later evidence", stamp=stamp if tied_partial else None,
        completeness="partial" if tied_partial else "complete") if first != "two reviewers" else None
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
            holder = pool.submit(completion, "holder") if first.endswith("completion") else pool.submit(decision, "holder", outcome)
            try:
                assert locked.wait(6)
                if first.endswith("decision"):
                    racer = pool.submit(completion, "racer")
                else:
                    racer = pool.submit(decision, "racer", outcome if first.endswith("completion") else "reactivate")
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
    if first.endswith("completion"):
        assert loser.json()["detail"] == identity.CHANGED
        with case.session() as db:
            assert db.get(DataSource, case.source_id).identity_epoch == 0
            assert db.get(ReconciliationItem, uuid.UUID(held["id"])).status == "open"
            assert db.get(ProxmoxGuestIdentityDecision, uuid.UUID(held["id"])) is None
            assert current_link(db, case, case.guest).entity_id == prior.asset
        refreshed = review(case)
        version_key = "expected_version" if outcome == "reactivate" else "replacement_expected_version"
        assert refreshed["identity_review"][version_key] != held["identity_review"][version_key]
        if omission or tied_partial:
            expected = identity.AMBIGUOUS_DISCOVERY_START if tied_partial else {
                "reactivate": identity.REACTIVATION_GUEST_OMITTED, "replace": identity.GUEST_OMITTED,
            }[outcome]
            assert refreshed["identity_review"]["actions"][outcome] == expected
            snapshot = effects(case, held, staged)
            refused = decide(case, refreshed, outcome)
            assert (refused.status_code, refused.json()["detail"]) == (409, expected)
            assert effects(case, held, staged) == snapshot
            after = snapshot
            for table in ("assets", "proxmox_guest_identity_decisions", "audit_events"):
                assert before[table] == after[table], table
            for snapshot in (before, after):
                snapshot["entity_source_links"] = [link for link in snapshot["entity_source_links"]
                    if link["external_id"] in {case.guest, case.nic}]
            assert before["entity_source_links"] == after["entity_source_links"]
            return
        assert decide(case, review(case), "replace").status_code == 200
    elif first.endswith("decision"):
        assert winner.json()["outcome"] == outcome
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
            attributed = db.scalar(select(RunObservedEntity.entity_id).where(RunObservedEntity.discovery_run_id == next_run.id,
                RunObservedEntity.external_id == case.guest))
            assert attributed == current_link(db, case, case.guest).entity_id
            assert (attributed == prior.asset) == (outcome == "reactivate")
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
