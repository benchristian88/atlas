"""Exercise reviewed batch integrity with authenticated PostgreSQL transactions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import UUID

from fastapi import HTTPException
import pytest
from sqlalchemy import delete, func, select

from app.models import (AccessAssignment, Asset, AuditEvent, EntitySourceLink, KnowledgeAssertion,
                        KnowledgeChange, Permission, ReconciliationItem, RolePermission)
from app.routes import assets, knowledge
from tests.test_onboarding_discovery_review_postgres import (
    GRANTS, asset, batch, env, individual, observe, page, pytestmark, review_site, state_at_review,
)
from tests.test_onboarding_integrations_postgres import discovery_history, scope_headers


def canonical_snapshot(db, pair):
    def rows(model, *columns, extra=()):
        return set(db.execute(select(*columns).where(
            model.customer_id == pair.customer.id, model.site_id == pair.site.id, *extra,
        )).all())

    return {
        "assets": rows(Asset, Asset.id, Asset.name, Asset.external_id),
        "links": rows(EntitySourceLink, EntitySourceLink.id, EntitySourceLink.entity_id, EntitySourceLink.external_id),
        "assertions": rows(KnowledgeAssertion, KnowledgeAssertion.id, KnowledgeAssertion.is_accepted,
                           KnowledgeAssertion.accepted_by_user_id, KnowledgeAssertion.subject_id),
        "changes": rows(KnowledgeChange, KnowledgeChange.id, KnowledgeChange.reconciliation_item_id),
        "audits": rows(AuditEvent, AuditEvent.id, AuditEvent.target_id, AuditEvent.user_id,
                       extra=(AuditEvent.event_type.like("reconciliation.%"),)),
        "decisions": rows(ReconciliationItem, ReconciliationItem.id, ReconciliationItem.status,
                          ReconciliationItem.entity_id, ReconciliationItem.decided_by_user_id),
    }


def revoke(env, actor, permission):
    with env.sessions.begin() as db:
        role_id = db.get(AccessAssignment, actor.grant).role_id
        db.execute(delete(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == select(Permission.id).where(Permission.key == permission).scalar_subquery(),
        ))


def assert_accepted(db, pair, row, actor, *, expected_asset=None):
    item = db.get(ReconciliationItem, UUID(row["id"]))
    claim = db.get(KnowledgeAssertion, item.assertion_id)
    assert (item.status, item.decided_by_user_id) == ("accepted", actor.id)
    assert claim.is_accepted and claim.accepted_by_user_id == actor.id
    assert (item.customer_id, item.site_id) == (claim.customer_id, claim.site_id) == (pair.customer.id, pair.site.id)
    accepted = db.get(Asset, item.entity_id)
    assert (accepted.customer_id, accepted.site_id) == (pair.customer.id, pair.site.id)
    if expected_asset is not None:
        assert accepted.id == expected_asset
    link = db.scalars(select(EntitySourceLink).where(
        EntitySourceLink.data_source_id == claim.data_source_id,
        EntitySourceLink.external_id == item.candidate_external_id,
        EntitySourceLink.entity_id == accepted.id,
    )).one()
    assert (link.customer_id, link.site_id) == (pair.customer.id, pair.site.id)
    change = db.scalars(select(KnowledgeChange).where(
        KnowledgeChange.reconciliation_item_id == item.id, KnowledgeChange.change_type == "entity_accepted",
    )).one()
    audit = db.scalars(select(AuditEvent).where(
        AuditEvent.target_id == item.id, AuditEvent.event_type == "reconciliation.accepted",
    )).one()
    assert (change.customer_id, change.site_id, change.actor_user_id) == (pair.customer.id, pair.site.id, actor.id)
    assert (audit.customer_id, audit.site_id, audit.user_id) == (pair.customer.id, pair.site.id, actor.id)


def assert_open(db, row):
    item = db.get(ReconciliationItem, UUID(row["id"]))
    claim = db.get(KnowledgeAssertion, item.assertion_id)
    assert (item.status, item.entity_id, item.decided_by_user_id) == ("open", None, None)
    assert not claim.is_accepted and claim.accepted_by_user_id is None
    assert db.scalar(select(EntitySourceLink.id).where(
        EntitySourceLink.data_source_id == claim.data_source_id,
        EntitySourceLink.external_id == item.candidate_external_id,
    )) is None
    assert db.scalar(select(KnowledgeChange.id).where(
        KnowledgeChange.reconciliation_item_id == item.id, KnowledgeChange.change_type == "entity_accepted",
    )) is None
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == item.id)) is None


def wait_for_postgres_lock(env, pid, *, blocker=None):
    # Observe the actual lock wait through PostgreSQL. Events order requests;
    # this poll never relies on the scheduler to hold a request for a duration.
    deadline = monotonic() + 5
    with env.sessions() as db:
        while monotonic() < deadline:
            blockers = db.scalar(select(func.pg_blocking_pids(pid)))
            if blockers and (blocker is None or blocker in blockers):
                return
    pytest.fail(f"PostgreSQL backend {pid} did not wait on the expected lock")


@pytest.mark.parametrize(("timing", "permission", "expected_status", "applied"), [
    ("before", "reconciliation.decide", 403, 0),
    ("waiting", "reconciliation.decide", 404, 0),
    ("between", "reconciliation.decide", 404, 1),
    ("between", "reconciliation.view", 404, 1),
    ("before_commit", "reconciliation.decide", 404, 2),
    ("before_commit", "assets.view", 404, 2),
    ("before_commit", None, 200, 2),
])
def test_authority_rechecked_and_loss_rolls_back_entire_batch(
    env, review_site, monkeypatch, timing, permission, expected_status, applied,
):
    pair = review_site()
    actor = env.actor(GRANTS, "site", pair.customer.id, pair.site.id)
    witness = env.actor(GRANTS)
    state_at_review(actor, pair)
    observe(witness, pair, asset("Restricted first"), asset("Restricted second"))
    rows = page(actor, pair)["items"]
    with env.sessions() as db:
        baseline = canonical_snapshot(db, pair)
        claim = db.get(KnowledgeAssertion, UUID(rows[0]["assertion_id"]))
        source_id = claim.data_source_id

    reached, resume = Event(), Event()
    calls, backend = [], []
    apply = knowledge._apply_acceptance
    lock_sources = knowledge._lock_decision_sources

    def observe_lock(db, ids):
        backend.append(db.scalar(select(func.pg_backend_pid())))
        reached.set()
        return lock_sources(db, ids)

    def coordinate_apply(db, item, *args):
        result = apply(db, item, *args)
        calls.append(item.id)
        if (timing == "between" and len(calls) == 1) or (timing == "before_commit" and len(calls) == 2):
            assert len(canonical_snapshot(db, pair)["assets"]) == len(calls)
            reached.set()
            assert resume.wait(5)
        return result

    monkeypatch.setattr(knowledge, "_apply_acceptance", coordinate_apply)
    if timing == "before":
        revoke(env, actor, permission)
        response = batch(actor, pair, *rows)
    elif timing == "waiting":
        monkeypatch.setattr(knowledge, "_lock_decision_sources", observe_lock)
        with ThreadPoolExecutor(1) as pool:
            with env.sessions.begin() as holder:
                from app.models import DataSource
                holder.get(DataSource, source_id, with_for_update={"key_share": True})
                holder_pid = holder.scalar(select(func.pg_backend_pid()))
                pending = pool.submit(batch, actor, pair, *rows)
                assert reached.wait(5)
                wait_for_postgres_lock(env, backend[0], blocker=holder_pid)
                revoke(env, actor, permission)
            response = pending.result(timeout=8)
    else:
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(batch, actor, pair, *rows)
            try:
                assert reached.wait(5)
                with env.sessions() as observer:
                    assert canonical_snapshot(observer, pair) == baseline
                if permission:
                    revoke(env, actor, permission)
            finally:
                resume.set()
            response = pending.result(timeout=8)

    assert len(calls) == applied
    assert response.status_code == expected_status, response.text
    with env.sessions() as db:
        if permission:
            assert set(response.json()) == {"detail"}
            assert all(row["id"] not in response.text and row["entity_name"] not in response.text for row in rows)
            assert canonical_snapshot(db, pair) == baseline
        else:
            assert {row["id"] for row in response.json()["accepted"]} == {row["id"] for row in rows}
            for row in rows:
                assert_accepted(db, pair, row, actor)
    if permission == "reconciliation.view":
        recovered = page(actor, pair, decision_id=[row["id"] for row in rows])
        assert recovered["items"] == [] and recovered["decisions"] == {} and recovered["summary"]["eligible"] is None


def test_specialized_grant_revoked_after_relationship_write_rolls_back(env, review_site, monkeypatch):
    pair = review_site()
    actor = env.actor(GRANTS, "site", pair.customer.id, pair.site.id)
    state_at_review(actor, pair)
    observe(actor, pair, asset("Host"), asset("Guest", host="Host"))
    for row in page(actor, pair)["items"]:
        if row["entity_type"] == "asset":
            assert individual(actor, pair, row).status_code == 200
    [relationship] = page(actor, pair)["items"]
    from app.models import AssetRelationship
    with env.sessions() as db:
        before = canonical_snapshot(db, pair)

    apply = knowledge._apply_acceptance

    def revoke_after_write(db, item, *args):
        result = apply(db, item, *args)
        assert db.scalar(select(AssetRelationship.id).where(AssetRelationship.site_id == pair.site.id))
        revoke(env, actor, "relationships.create")
        return result

    monkeypatch.setattr(knowledge, "_apply_acceptance", revoke_after_write)
    response = batch(actor, pair, relationship)
    assert response.status_code == 403 and set(response.json()) == {"detail"}
    with env.sessions() as db:
        assert canonical_snapshot(db, pair) == before
        assert db.scalar(select(AssetRelationship.id).where(AssetRelationship.site_id == pair.site.id)) is None


def manual_asset(actor, pair, name):
    response = actor.client.post("/api/assets", headers=scope_headers(pair), json={
        "customer_id": str(pair.customer.id), "site_id": str(pair.site.id), "name": name,
        "asset_type": "virtual_machine", "status": "active",
    })
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


def test_competing_creation_invalidates_review_and_fresh_association_is_explicit(env, review_site):
    pair = review_site()
    actor, other = env.actor(GRANTS), env.actor(GRANTS)
    state_at_review(actor, pair)
    observe(actor, pair, asset("Shared name", external="review-first"))
    [reviewed] = page(actor, pair)["items"]
    assert reviewed["batch_identity"]["action"] == "create"

    observe(other, pair, asset("Shared name", external="other-decision"))
    competing = next(row for row in page(other, pair)["items"] if row["id"] != reviewed["id"])
    decided = individual(other, pair, competing)
    assert decided.status_code == 200, decided.text
    result = batch(actor, pair, reviewed).json()
    assert result["accepted"] == [] and [row["id"] for row in result["failed"]] == [reviewed["id"]]
    assert "current asset identity" in result["failed"][0]["reason"]
    with env.sessions() as db:
        assert_open(db, reviewed)
        assert_accepted(db, pair, competing, other)

    [current] = page(actor, pair)["items"]
    assert current["batch_version"] != reviewed["batch_version"]
    assert current["batch_identity"] == {"action": "associate", "asset_name": "Shared name"}
    assert batch(actor, pair, current).json()["accepted"][0]["id"] == reviewed["id"]
    assert batch(other, pair, competing).json()["already_resolved"][0]["id"] == competing["id"]
    with env.sessions() as db:
        assert_accepted(db, pair, reviewed, actor, expected_asset=UUID(decided.json()["entity_id"]))
        assert len(canonical_snapshot(db, pair)["assets"]) == 1


def test_candidate_change_ambiguity_and_unrelated_inventory(env, review_site):
    pair = review_site()
    actor = env.actor(GRANTS | {"assets.create"})
    state_at_review(actor, pair)
    observe(actor, pair, asset("Candidate"), asset("Independent creation"))
    first = manual_asset(actor, pair, "Candidate")
    def reviewed():
        return {row["entity_name"]: row for row in page(actor, pair)["items"]}

    initial = reviewed()
    manual_asset(actor, pair, "Unrelated")
    assert reviewed()["Independent creation"]["batch_version"] == initial["Independent creation"]["batch_version"]
    assert reviewed()["Candidate"]["batch_version"] == initial["Candidate"]["batch_version"]
    renamed = actor.client.patch(f"/api/assets/{first}", headers=scope_headers(pair), json={"name": "Different"})
    assert renamed.status_code == 200, renamed.text
    manual_asset(actor, pair, "Candidate")
    changed = reviewed()["Candidate"]
    assert changed["batch_identity"] == initial["Candidate"]["batch_identity"]
    assert changed["batch_version"] != initial["Candidate"]["batch_version"]
    assert batch(actor, pair, initial["Candidate"]).json()["failed"][0]["id"] == changed["id"]
    manual_asset(actor, pair, "Candidate")
    ambiguous = reviewed()["Candidate"]
    assert ambiguous["batch_version"] is None and "individual identity" in ambiguous["batch_exclusion"]
    outcome = batch(actor, pair, changed, initial["Independent creation"]).json()
    assert [row["id"] for row in outcome["blocked"]] == [changed["id"]]
    assert [row["id"] for row in outcome["accepted"]] == [initial["Independent creation"]["id"]]
    with env.sessions() as db:
        assert_open(db, changed)
        assert_accepted(db, pair, initial["Independent creation"], actor)


@pytest.mark.parametrize("fail_first", [False, True])
def test_candidate_state_follows_success_and_rollback(env, review_site, discovery_history, monkeypatch, fail_first):
    pair = review_site()
    actor = env.actor(GRANTS)
    state_at_review(actor, pair)
    for name in ("First source", "Second source"):
        connection, _ = discovery_history(pair, "completed", name=name)
        observe(actor, pair, asset("Connector match", external=name), source=connection.data_source_id)
    observe(actor, pair, asset("Independent"))
    rows = page(actor, pair)["items"]
    first, second = sorted((row for row in rows if row["entity_name"] == "Connector match"), key=lambda row: row["id"])
    independent = next(row for row in rows if row["entity_name"] == "Independent")
    assert all(row["batch_identity"]["action"] == "create" for row in rows)
    apply = knowledge._apply_acceptance

    def apply_then_fail(db, item, *args):
        result = apply(db, item, *args)
        if str(item.id) == first["id"]:
            assert db.get(Asset, item.entity_id)
            raise HTTPException(422, "Forced validation failure after canonical writes")
        return result

    if fail_first:
        monkeypatch.setattr(knowledge, "_apply_acceptance", apply_then_fail)
    response = batch(actor, pair, *rows)
    assert response.status_code == 200, response.text
    result = response.json()
    accepted, remaining = (second, first) if fail_first else (first, second)
    assert {row["id"] for row in result["accepted"]} == {accepted["id"], independent["id"]}
    if fail_first:
        assert result["blocked"] == []
        assert result["failed"][0]["reason"] == "Forced validation failure after canonical writes"
    else:
        assert result["failed"] == []
        assert [row["id"] for row in result["blocked"]] == [remaining["id"]]
        assert "individual identity decision" in result["blocked"][0]["reason"]
    [current] = page(actor, pair)["items"]
    assert current["id"] == remaining["id"] and current["batch_version"] is None
    with env.sessions() as db:
        assert_open(db, remaining)
        assert_accepted(db, pair, accepted, actor)
        assert_accepted(db, pair, independent, actor)


@pytest.mark.parametrize("writer_first", [True, False])
def test_candidate_write_and_bounded_acceptance_are_serialized(env, review_site, monkeypatch, writer_first):
    pair = review_site()
    actor, other = env.actor(GRANTS), env.actor(GRANTS | {"assets.create"})
    state_at_review(actor, pair)
    observe(actor, pair, asset("Concurrent match"))
    [row] = page(actor, pair)["items"]
    holder_ready, waiter_ready, release = Event(), Event(), Event()
    waiting_pid = []
    apply, commit = knowledge._apply_acceptance, assets.commit
    shared, exclusive = assets.lock_asset_identity_inventory, knowledge.lock_asset_identity_inventory

    def before_apply(db, *args):
        holder_ready.set()
        assert release.wait(5)
        return apply(db, *args)

    def before_commit(db, *args):
        holder_ready.set()
        assert release.wait(5)
        return commit(db, *args)

    def report_wait(lock):
        def acquire(db, *args, **kwargs):
            waiting_pid.append(db.scalar(select(func.pg_backend_pid())))
            waiter_ready.set()
            return lock(db, *args, **kwargs)
        return acquire

    if writer_first:
        monkeypatch.setattr(assets, "commit", before_commit)
        monkeypatch.setattr(knowledge, "lock_asset_identity_inventory", report_wait(exclusive))
    else:
        monkeypatch.setattr(knowledge, "_apply_acceptance", before_apply)
        monkeypatch.setattr(assets, "lock_asset_identity_inventory", report_wait(shared))

    with ThreadPoolExecutor(2) as pool:
        submit_batch = lambda: pool.submit(batch, actor, pair, row)
        submit_write = lambda: pool.submit(manual_asset, other, pair, "Concurrent match")
        holder, waiter = (submit_write, submit_batch) if writer_first else (submit_batch, submit_write)
        first = holder()
        try:
            assert holder_ready.wait(5)
            second = waiter()
            assert waiter_ready.wait(5)
            wait_for_postgres_lock(env, waiting_pid[0])
        finally:
            release.set()
        response, manual_id = ((second.result(timeout=8), first.result(timeout=8)) if writer_first
                               else (first.result(timeout=8), second.result(timeout=8)))

    assert response.status_code == 200, response.text
    with env.sessions() as db:
        assert db.get(Asset, manual_id)
        if writer_first:
            assert response.json()["failed"][0]["id"] == row["id"]
            assert_open(db, row)
        else:
            assert response.json()["accepted"][0]["id"] == row["id"]
            assert_accepted(db, pair, row, actor)
            assert len(canonical_snapshot(db, pair)["assets"]) == 2
