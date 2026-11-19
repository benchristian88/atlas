"""Operational cutover through PostgreSQL and HTTP with storage-only decisions."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from dataclasses import replace
from datetime import datetime, timezone
import os
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select

from app.authorization import get_principal
from app.models import (Asset, AssetInterface, AuditEvent, DataSource, DiscoveryBatchReceipt, DiscoveryRun,
    EntitySourceLink, EvidenceRecord, Integration, KnowledgeAssertion, KnowledgeChange, ProxmoxGuestIdentityDecision,
    ReconciliationItem, RunObservedEntity)
from app.services import discovery_orchestration as orchestration
from app.services.knowledge_lifecycle import can_delete_assertion
from app.services.knowledge_summary import SummaryValues
from tests.test_proxmox_guest_identity_postgres import MAC_B, cases, migrated_history, pytestmark


def slot(case, vmid):
    result = copy(case)
    result.guest = f"guest/{result.kind}/{vmid}"
    result.nic = result.guest + "/interface/net0"
    return result


def decision_fixture(db, case, prior, hold, outcome):
    """Represent a committed decision and intervals without a decision endpoint."""
    db.get(Integration, case.integration.id, with_for_update=True)
    source = db.get(DataSource, case.source_id, with_for_update={"key_share": True})
    asset = db.get(Asset, prior.asset, with_for_update=True)
    links = list(db.scalars(select(EntitySourceLink).where(
        EntitySourceLink.data_source_id == source.id, EntitySourceLink.ended_epoch.is_(None),
        (EntitySourceLink.entity_id == asset.id) | (EntitySourceLink.interface_owner_id == asset.id))))
    old = next(link for link in links if link.entity_type == "asset" and link.external_id == case.guest)
    source.identity_epoch += 1
    new = None
    if outcome == "replace":
        assert asset.status == "retired"
        for link in links:
            link.ended_epoch = source.identity_epoch
        db.flush()
        new = Asset(customer_id=asset.customer_id, site_id=asset.site_id, workspace_id=asset.workspace_id,
                    asset_type=asset.asset_type, name="Successor guest")
        db.add(new)
        db.flush()
        binding = EntitySourceLink(data_source_id=source.id, customer_id=case.customer_id, site_id=case.site_id,
            entity_type="asset", entity_id=new.id, external_id=case.guest, opened_epoch=source.identity_epoch,
            first_observed_at=datetime.now(timezone.utc), last_observed_at=datetime.now(timezone.utc))
        db.add(binding)
        db.flush()
    item = db.get(ReconciliationItem, UUID(hold["id"]), with_for_update=True)
    db.add(ProxmoxGuestIdentityDecision(reconciliation_item_id=item.id, data_source_id=source.id,
        identity_epoch=source.identity_epoch, old_binding_id=old.id, replacement_binding_id=binding.id if new else None,
        reviewed_assertion_id=item.assertion_id, retirement_revision=asset.identity_retirement_revision, outcome=outcome))
    item.status, item.decision_reason, item.decided_at = "accepted", "Storage fixture", datetime.now(timezone.utc)
    db.flush()
    return new.id if new else asset.id


def snapshot_counts(case):
    with case.session() as db:
        return {model.__name__: db.scalar(select(func.count()).select_from(model)) for model in (
            Asset, DiscoveryBatchReceipt, EntitySourceLink, EvidenceRecord, KnowledgeAssertion, KnowledgeChange,
            ReconciliationItem, RunObservedEntity)}


def hold_after_retirement(case, prior):
    assert case.client.patch(f"/assets/{prior.asset}", json={"status": "retired"}).status_code == 200
    case.run(name="Held", completeness="partial")
    [group] = case.identity_reviews()
    return group["parent"]


def test_replacement_fences_mixed_run_and_old_proposals(cases, monkeypatch):
    case = slot(cases(), 811)
    unrelated = slot(case, 812)
    prior = case.seed()
    old_run = case.run(name="Changed before cutover", node="node-b", mac=MAC_B, bridge="vmbr1", secondary=True)
    case.accept("node/node-b", "name")
    historical = [case.proposal(key, predicate, run_id=str(old_run.id)) for key, predicate in (
        (case.guest, "name"), (case.nic, "configuration"), (case.guest, "runs_on"),
        (case.guest + "/interface/net1", "configuration"), (case.nic, "proxmox.bridge_name"))]
    case.run(node="node-b")
    historical.append(case.proposal(case.guest, "observation_state"))
    hold = hold_after_retirement(case, prior)
    unrelated.run(name="Unaffected proposal", completeness="partial")
    _, unaffected = unrelated.proposal(unrelated.guest, "name")
    _, unaffected_interface = unrelated.proposal(unrelated.nic, "configuration")
    staged = case.stage(name="Obsolete mixed run", extra=True, dispatch_state="running")

    waiting = Event()

    def before(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get("test_actor") == "completion" and "FROM integrations" in sql and "FOR UPDATE" in sql:
            waiting.set()

    event.listen(case.engine, "before_cursor_execute", before)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with case.session() as db, db.begin():
                successor = decision_fixture(db, case, prior, hold, "replace")
                completion = pool.submit(case.complete, staged, expected=409)
                assert waiting.wait(8)
                assert not completion.done()
            assert completion.result(timeout=12)["detail"] == {
                "code": orchestration.IDENTITY_EPOCH_CHANGED, "message": orchestration.IDENTITY_RETRY_MESSAGE}
    finally:
        event.remove(case.engine, "before_cursor_execute", before)

    with case.session() as db:
        run = db.get(DiscoveryRun, staged.id)
        assert (run.status, run.completeness_status, run.identity_epoch) == ("failed", "failed", 0)
        assert run.error_message == orchestration.IDENTITY_RETRY_MESSAGE
        assert run.ingestion_generation is None and run.finalisation_hash is None and run.completed_at
        assert db.get(DiscoveryBatchReceipt, (run.id, 1)).payload_json == staged.batch
        assert not db.scalar(select(KnowledgeAssertion.id).where(KnowledgeAssertion.discovery_run_id == run.id).limit(1))
        assert not db.scalar(select(KnowledgeChange.id).where(KnowledgeChange.discovery_run_id == run.id).limit(1))
        members = list(db.scalars(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == run.id)))
        assert {case.guest, "node/unrelated"} <= {member.external_id for member in members}
        assert all(member.entity_id is None and member.evidence_record_id for member in members)
        assert db.get(Asset, successor).name == "Successor guest"

    async def terminal(*args):
        return {"state": "succeeded"}

    monkeypatch.setattr(orchestration.runtime, "get_job", terminal)
    monkeypatch.setattr(orchestration.runtime, "cancel_job", terminal)
    with case.session() as db:
        asyncio.run(orchestration.reconcile(db, staged.id))
    with case.session() as db:
        assert db.get(DiscoveryRun, staged.id).dispatch_state == "settled"
        assert orchestration.active_run(db, case.integration.id) is None

    counts = snapshot_counts(case)
    old_snapshot = case.snapshot(prior)
    replay_writes = []

    def capture_replay(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get("test_actor") == "replay" and sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE")):
            replay_writes.append(sql)

    event.listen(case.engine, "before_cursor_execute", capture_replay)
    try:
        assert case.complete(old_run, actor="replay")["replayed"]
    finally:
        event.remove(case.engine, "before_cursor_execute", capture_replay)
    assert replay_writes == []
    assert snapshot_counts(case) == counts
    assert case.snapshot(prior) == old_snapshot

    queue = case.client.get("/reconciliation-items/page").json()["items"]
    assert not {row["id"] for row in queue} & {row["id"] for _, row in historical}
    history_rows = case.client.get("/reconciliation-items", params={"run_id": str(old_run.id)}).json()
    old_relationship = next(row for row in history_rows if row["id"] == historical[2][1]["id"])
    assert old_relationship["resolved_source_asset_id"] == str(prior.asset)
    assert "predates" in old_relationship["blocked_reason"]
    for group, row in historical:
        reply = case.client.post(f"/reconciliation-items/{row['id']}/accept", json={})
        assert reply.status_code == 409, reply.text
        bulk = case.client.post(f"/reconciliation-entities/{group['id']}/accept",
            json={"items": [{"id": row["id"], "version": row["version"]}]})
        assert bulk.status_code == 200, bulk.text
        assert not bulk.json()["accepted"] and (bulk.json()["blocked"] or bulk.json()["failed"])
    _, technical = historical[3]
    assert case.decide(technical, "link-technical", entity_id=str(prior.interface)).status_code == 409
    assert case.decide(historical[0][1], "link-asset", asset_id=str(successor)).status_code == 409
    assert case.snapshot(prior) == old_snapshot

    _, still_actionable = unrelated.proposal(unrelated.guest, "name")
    assert still_actionable["can_accept"] and still_actionable["version"] == unaffected["version"]
    repeated = unrelated.run(name="Unaffected proposal", completeness="partial")
    _, unaffected_again = unrelated.proposal(unrelated.guest, "name", run_id=str(repeated.id))
    assert unaffected_again["id"] == unaffected["id"]
    assert unaffected_again["assertion_id"] == unaffected["assertion_id"]
    assert unrelated.decide(unaffected_again).status_code == 200
    _, interface_again = unrelated.proposal(unrelated.nic, "configuration")
    assert interface_again["id"] == unaffected_interface["id"]
    assert unrelated.decide(interface_again).status_code == 200

    omitted_guest = case.stage(name="An omitted guest cannot use the old accepted proof",
                               node="node-b", guest_relationship_only=True)
    assert case.complete(omitted_guest, expected=422)["detail"]["code"] == "invalid_relationship_binding"
    fresh = case.run(name="Changed before cutover", node="node-b", mac=MAC_B, bridge="vmbr1", secondary=True)
    _, new_interface = case.proposal(case.guest + "/interface/net1", "configuration", run_id=str(fresh.id))
    assert new_interface["assertion_id"] != technical["assertion_id"]
    _, network = case.proposal("network/node-b/vmbr1", "configuration")
    assert case.decide(network, "link-technical", entity_id=str(prior.network)).status_code == 200
    new_nic = case.accept(case.nic, "configuration")
    with case.session() as db:
        assert db.get(DiscoveryRun, fresh.id).identity_epoch == 1
        row = db.scalar(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == fresh.id,
            RunObservedEntity.external_id == case.guest))
        assert row.entity_id == successor
        new_link = db.scalar(select(EntitySourceLink).where(EntitySourceLink.interface_id == new_nic))
        assert (new_link.opened_epoch, new_link.interface_owner_id) == (1, successor)
        old_claim = db.get(KnowledgeAssertion, UUID(historical[2][1]["assertion_id"]))
        assert (old_claim.subject_id, old_claim.identity_epoch) == (prior.asset, 0)
        new_claim = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == fresh.id,
            KnowledgeAssertion.predicate == "runs_on"))
        assert (new_claim.subject_id, new_claim.identity_epoch, new_claim.object_id) == (successor, 1, old_claim.object_id)
        historical_target = SimpleNamespace(object_id=None, value_json={}, object_external_id=case.guest,
            data_source_id=case.source_id, identity_epoch=0, customer_id=case.customer_id, site_id=case.site_id,
            discovery_run_id=old_run.id, object_type="asset", predicate="runs_on", accepted_by_user_id=None)
        history = SummaryValues(db, db.get(Asset, old_claim.object_id), [historical_target], None)
        assert history.identifier(historical_target) == prior.asset
        historical_target.identity_epoch, historical_target.discovery_run_id = None, None
        assert history.identifier(historical_target) is None
        linked_claim = db.get(KnowledgeAssertion, UUID(historical[0][1]["assertion_id"]))
        assert can_delete_assertion(db, linked_claim).counts["linked_entities"] == 1
    assert case.client.delete(f"/assets/{prior.asset}").status_code == 409
    assert case.snapshot(prior) == old_snapshot

    for other in (slot(cases(alongside=case, same_site=True), 811), slot(cases(alongside=case), 811), slot(cases(), 811)):
        if other.site_id == case.site_id:
            with other.session() as db, db.begin():
                asset = Asset(customer_id=other.customer_id, site_id=other.site_id,
                    workspace_id=db.get(Asset, successor).workspace_id, name="Separate canonical guest", asset_type="lxc_container")
                db.add(asset)
                db.flush()
                now = datetime.now(timezone.utc)
                db.add(EntitySourceLink(customer_id=other.customer_id, site_id=other.site_id,
                    data_source_id=other.source_id, entity_type="asset", entity_id=asset.id,
                    external_id=other.guest, first_observed_at=now, last_observed_at=now))
                other_asset = asset.id
            run = other.run(name="Same key, separate source")
            with other.session() as db:
                membership = db.scalar(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == run.id,
                    RunObservedEntity.external_id == other.guest))
                assert membership.entity_id == other_asset
        else:
            other.run(name="Same key, separate source")
            other_asset = other.accept(other.guest, "name")
            restricted = replace(other.principal, grants=(replace(other.principal.grants[0], scope_type="site",
                customer_id=other.customer_id, site_id=other.site_id),))
            other.client.app.dependency_overrides[get_principal] = lambda: restricted
            assert other.groups(source_id=case.source_id) == []
            assert other.client.get(f"/assertions/{historical[2][1]['assertion_id']}").status_code == 404
        assert other_asset not in {prior.asset, successor}


@pytest.mark.parametrize("endpoint", ["pinned", "epoch-fallback", "unreadable", "unproven"])
def test_historical_relationship_read_during_cutover(cases, endpoint):
    case = slot(cases(), 851)
    prior = case.seed()
    old_run = case.run(name="Old relationship", node="node-b")
    case.accept("node/node-b", "name")
    _, row = case.proposal(case.guest, "runs_on", run_id=str(old_run.id))
    hold = hold_after_retirement(case, prior)
    other_site = cases(alongside=case) if endpoint == "unreadable" else None
    with case.session() as db, db.begin():
        original = db.get(Asset, prior.asset)
        original_name = original.name
        claim = db.get(KnowledgeAssertion, UUID(row["assertion_id"]))
        item = db.get(ReconciliationItem, UUID(row["id"]))
        assert claim.subject_id == original.id
        if endpoint in {"epoch-fallback", "unproven"}:
            claim.subject_id = claim.identity_epoch = None
            item.observed_value_json = {**item.observed_value_json, "resolved_source_asset_id": None}
        if endpoint == "unproven":
            db.get(DiscoveryRun, old_run.id).finalisation_hash = None
        if other_site:
            hidden = Asset(customer_id=original.customer_id, site_id=other_site.site_id,
                workspace_id=original.workspace_id, name="Hidden recorded endpoint", asset_type=original.asset_type)
            db.add(hidden)
            db.flush()
            claim.subject_id = hidden.id

    params = {"run_id": str(old_run.id), "entity_type": "asset_relationship"}
    selected, proceed = Event(), Event()

    def pause_after_source_read(conn, cursor, sql, parameters, context, many):
        if (not selected.is_set() and context.execution_options.get("test_actor") == "history"
                and "FROM data_sources" in sql):
            selected.set()
            assert proceed.wait(12)

    def historical_response():
        response = case.client.get("/reconciliation-items", params=params, headers={"x-test-actor": "history"})
        assert response.status_code == 200, response.text
        return response.json()

    event.listen(case.engine, "after_cursor_execute", pause_after_source_read)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(historical_response)
            try:
                assert selected.wait(8)
                with case.session() as db, db.begin():
                    successor = decision_fixture(db, case, prior, hold, "replace")
            finally:
                proceed.set()
            [during] = pending.result(timeout=12)
    finally:
        event.remove(case.engine, "after_cursor_execute", pause_after_source_read)

    visible = endpoint in {"pinned", "epoch-fallback"}
    expected = (str(prior.asset), original_name) if visible else (None, None)
    [after] = historical_response()
    _, grouped = case.proposal(case.guest, "runs_on", run_id=str(old_run.id))
    for historical in (during, after, grouped["observed_value_json"]):
        assert (historical["resolved_source_asset_id"], historical["resolved_source_name"]) == expected
        assert str(successor) not in str(historical) and "Successor guest" not in str(historical)

    fresh = case.run(name="New live evidence", node="node-b")
    live = case.client.get("/reconciliation-items", params={**params, "run_id": str(fresh.id)})
    assert live.status_code == 200, live.text
    [relationship] = live.json()
    assert (relationship["resolved_source_asset_id"], relationship["resolved_source_name"]) == (
        str(successor), "Successor guest")
    with case.session() as db:
        membership = db.scalar(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == fresh.id,
            RunObservedEntity.entity_type == "asset", RunObservedEntity.external_id == case.guest))
        assert membership.entity_id == successor


@pytest.mark.parametrize("binding_action,bulk", [("accept", False), ("link-technical", True)])
def test_opaque_interface_fact_stays_at_its_observed_owner(cases, monkeypatch, binding_action, bulk):
    case = slot(cases(), 856)
    other = slot(case, 857)
    prior = case.seed()
    original_post = case.client.post
    alias = "legacy-interface/slot-a"

    def with_opaque_key(path, **kwargs):
        if path.endswith("/batches"):
            for row in kwargs["json"]["interfaces"]:
                if row["external_id"].endswith("/net1"):
                    row["external_id"] = alias
        return original_post(path, **kwargs)

    monkeypatch.setattr(case.client, "post", with_opaque_key)
    old = other.run(name="Original Interface owner", completeness="partial", secondary=True, bridge="vmbr1")
    other.accept(other.guest, "name")
    _, stale = case.proposal(alias, "proxmox.bridge_name", run_id=str(old.id))
    assertion_id, item_id = UUID(stale["assertion_id"]), UUID(stale["id"])

    def retained_fact():
        with case.session() as db:
            claim = db.get(KnowledgeAssertion, assertion_id)
            evidence = db.get(EvidenceRecord, claim.evidence_record_id)
            item = db.get(ReconciliationItem, item_id)
            assert claim.subject_id is None and not claim.is_accepted
            assert (claim.identity_epoch, claim.discovery_run_id) == (0, old.id)
            assert evidence.payload_json["asset_external_id"] == other.guest
            assert item.status == "open" and item.entity_id is None
            assert db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == item_id)) is None
            return [{field.key: getattr(row, field.key) for field in row.__mapper__.column_attrs}
                    for row in (claim, evidence, item)]

    retained = retained_fact()
    hold = hold_after_retirement(case, prior)
    with case.session() as db, db.begin():
        successor = decision_fixture(db, case, prior, hold, "replace")
    fresh = case.run(name="Replacement Interface owner", completeness="partial", secondary=True)
    _, config = case.proposal(alias, "configuration", run_id=str(fresh.id))
    target = {}
    if binding_action == "link-technical":
        with case.session() as db, db.begin():
            interface = AssetInterface(asset_id=successor, name="Manually configured Interface")
            db.add(interface)
            db.flush()
            target["entity_id"] = str(interface.id)
    bound = case.decide(config, binding_action, **target)
    assert bound.status_code == 200, bound.text
    interface_id = UUID(bound.json()["entity_id"])
    with case.session() as db:
        link = db.scalar(select(EntitySourceLink).where(EntitySourceLink.interface_id == interface_id))
        assert (link.opened_epoch, link.interface_owner_id) == (1, successor)
    assert retained_fact() == retained
    assert not any(row["id"] == stale["id"] for row in case.client.get("/reconciliation-items/page").json()["items"])

    group, historical = case.proposal(alias, "proxmox.bridge_name", run_id=str(old.id))
    assert historical["id"] == stale["id"] and not historical["can_accept"]
    assert "predates" in historical["blocked_reason"]
    counts = snapshot_counts(case)
    if bulk:
        response = case.client.post(f"/reconciliation-entities/{group['id']}/accept",
            json={"items": [{"id": historical["id"], "version": historical["version"]}]})
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] == []
        assert "predates" in response.json()["blocked"][0]["reason"]
    else:
        response = case.client.post(f"/reconciliation-items/{item_id}/accept", json={})
        assert response.status_code == 409 and "predates" in response.json()["detail"], response.text
    assert retained_fact() == retained
    assert snapshot_counts(case) == counts
    with case.session() as db:
        assert db.scalar(select(KnowledgeChange.id).where(
            KnowledgeChange.entity_id == interface_id, KnowledgeChange.assertion_id == assertion_id)) is None


def test_first_interface_binding_remains_eligible_after_unrelated_decision(cases):
    case = slot(cases(), 858)
    other = slot(case, 859)
    prior = case.seed()
    old = other.run(name="Unaffected owner", completeness="partial")
    owner_id = other.accept(other.guest, "name")
    _, fact = other.proposal(other.nic, "proxmox.bridge_name", run_id=str(old.id))
    hold = hold_after_retirement(case, prior)
    with case.session() as db, db.begin():
        decision_fixture(db, case, prior, hold, "replace")
    _, config = other.proposal(other.nic, "configuration", run_id=str(old.id))
    assert config["can_accept"]
    interface_id = other.accept(other.nic, "configuration")
    _, attached = other.proposal(other.nic, "proxmox.bridge_name", run_id=str(old.id))
    assert attached["id"] == fact["id"] and attached["can_accept"]
    assert other.decide(attached).status_code == 200
    with case.session() as db:
        claim = db.get(KnowledgeAssertion, UUID(fact["assertion_id"]))
        link = db.scalar(select(EntitySourceLink).where(EntitySourceLink.interface_id == interface_id))
        assert db.get(DataSource, case.source_id).identity_epoch == 1
        assert (link.opened_epoch, link.interface_owner_id) == (0, owner_id)
        assert (claim.identity_epoch, claim.discovery_run_id, claim.subject_id, claim.is_accepted) == (
            0, old.id, interface_id, True)


def test_reactivation_storage_acknowledges_only_that_retirement_revision(cases):
    case = slot(cases(), 821)
    prior = case.seed()
    for status in ("retired", "active"):
        assert case.client.patch(f"/assets/{prior.asset}", json={"status": status}).status_code == 200
    before = case.run(name="guest-a")
    [first] = case.identity_reviews()
    with case.session() as db, db.begin():
        decision_fixture(db, case, prior, first["parent"], "reactivate")
    fresh = case.run(name="guest-a")
    assert case.identity_reviews() == []
    with case.session() as db:
        claims = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == prior.asset,
            KnowledgeAssertion.subject_external_id == case.guest, KnowledgeAssertion.predicate == "name")))
        assert {claim.identity_epoch for claim in claims} == {0, 1}
        assert len(claims) == 2 and all(claim.superseded_by_id is None for claim in claims)
        assert db.get(DiscoveryRun, before.id).identity_epoch == 0
        assert db.get(DiscoveryRun, fresh.id).identity_epoch == 1
    for status in ("retired", "active"):
        assert case.client.patch(f"/assets/{prior.asset}", json={"status": status}).status_code == 200
    case.run(name="guest returns after a later retirement")
    [second] = case.identity_reviews()
    assert second["parent"]["id"] != first["parent"]["id"]


def test_replacement_absence_requires_real_attributed_complete_baseline(cases):
    case = slot(cases(), 831)
    prior = case.seed()
    hold = hold_after_retirement(case, prior)
    case.run(name="Held complete membership")
    hold = case.identity_reviews()[0]["parent"]
    with case.session() as db, db.begin():
        successor = decision_fixture(db, case, prior, hold, "replace")
    first_omission = case.run()
    partial = case.run(name="Partial successor", completeness="partial")
    after_partial = case.run()
    payload = {"customer_id": str(case.customer_id), "site_id": str(case.site_id), "data_source_id": str(case.source_id),
        "coverage_key": case.coverage["key"], "is_complete_snapshot": True,
        "observations": [{"external_id": case.guest, "name": "Simulation", "asset_type": "lxc_container"}]}
    assert case.client.post("/discovery/simulate", json=payload).status_code == 409
    baseline = case.run(name="First eligible successor baseline")
    payload["observations"][0].update(external_id="node/node-a", name="node-a", asset_type="hypervisor_node")
    simulated = case.client.post("/discovery/simulate", json=payload)
    assert simulated.status_code == 200, simulated.text
    final = case.run()
    with case.session() as db:
        absence = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == successor,
            KnowledgeAssertion.predicate == "observation_state"))
        assert absence.identity_epoch == 1 and absence.discovery_run_id == final.id
        assert absence.value_json["baseline_run_id"] == str(baseline.id)
        for run in (first_omission, partial, after_partial, baseline):
            assert not db.get(DiscoveryRun, run.id).summary.get("no_longer_observed_count")


@pytest.mark.skipif(not os.getenv("ATLAS_TEST_CP2_REDIS_URL"), reason="requires an isolated disposable Redis instance")
def test_queued_admission_and_retry_keep_the_admitted_epoch(cases, monkeypatch):
    case = slot(cases(), 841)
    prior = case.seed()
    hold = hold_after_retirement(case, prior)
    monkeypatch.setenv("REDIS_URL", os.environ["ATLAS_TEST_CP2_REDIS_URL"])
    record = SimpleNamespace(connector_id="proxmox", version=case.integration.connector_version,
        bundle_digest=case.integration.connector_digest, verification_evidence={})

    async def eligibility(db, row):
        return (record, case.provenance["manifest"], case.provenance["mappings"],
                case.coverage, case.provenance["object_classes"], {})

    requests = []

    async def run_discovery(request):
        requests.append(set(request))
        return {"diagnostic_code": "runtime_capacity"} if len(requests) == 1 else {"job_id": str(uuid4())}

    monkeypatch.setattr(orchestration, "eligibility", eligibility)
    monkeypatch.setattr(orchestration.runtime, "run_discovery", run_discovery)

    def admit(expected):
        with case.session() as db, db.begin():
            row = db.get(Integration, case.integration.id, with_for_update=True)
            run = asyncio.run(orchestration.create_run(db, row))
            assert run.identity_epoch == expected
            return run.id

    pending = admit(0)
    assert orchestration.enqueue(pending)
    with case.session() as db, db.begin():
        decision_fixture(db, case, prior, hold, "replace")
    with orchestration.redis_client() as redis:
        assert redis.lpop(orchestration.QUEUE) == str(pending)
    with case.session() as db:
        asyncio.run(orchestration.dispatch(db, pending))
    with case.session() as db:
        failed = db.get(DiscoveryRun, pending)
        assert (failed.status, failed.dispatch_state, failed.dispatch_attempts, failed.identity_epoch) == ("failed", "settled", 0, 0)
        assert failed.error_message == orchestration.IDENTITY_RETRY_MESSAGE
        assert requests == []

    fresh = admit(1)
    with case.session() as db:
        asyncio.run(orchestration.dispatch(db, fresh))
    with case.session() as db, db.begin():
        retry = db.get(DiscoveryRun, fresh)
        assert (retry.dispatch_state, retry.identity_epoch) == ("pending", 1)
        retry.dispatch_after = orchestration.utcnow()
    with case.session() as db:
        asyncio.run(orchestration.dispatch(db, fresh))
    with case.session() as db:
        running = db.get(DiscoveryRun, fresh)
        assert (running.status, running.dispatch_attempts, running.identity_epoch) == ("running", 2, 1)
    assert len(requests) == 2 and all("identity_epoch" not in request for request in requests)
