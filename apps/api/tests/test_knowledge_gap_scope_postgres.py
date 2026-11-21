"""Gap ownership through the HTTP APIs and independent PostgreSQL transactions."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update

from app.authorization import get_principal
from app.database import SessionLocal, get_db
from app.models import (
    Asset, AssetType, AuditEvent, CriticalityLevel, Customer, KnowledgeAssertion,
    KnowledgeChange, KnowledgeCompletenessSummary, KnowledgeGap,
    KnowledgeRequirementDefinition, Service, ServiceType, Site,
)
from app.routes import assets, context, knowledge_completeness, services
from app.services import knowledge_completeness as evaluator
from tests.test_administration import make_principal
from tests.test_knowledge_integrity_migration import migrated_history, pytestmark


REVIEW_TIME = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


@pytest.fixture(params=["asset", "service"])
def case(request, migrated_history):
    migrated_history.migrate("upgrade", "head")
    kind = request.param
    model = Asset if kind == "asset" else Service
    permission = "knowledge_completeness.evaluate" if kind == "asset" else "service_completeness.evaluate"
    admin = make_principal(
        f"{kind}s.create", f"{kind}s.edit", f"{kind}s.view", permission,
        "knowledge_gaps.view", "knowledge_gaps.assign", "knowledge_gaps.defer",
        "knowledge_gaps.exception", "knowledge_requirements.view", "knowledge_requirements.manage",
    )
    actors = {"admin": admin}

    def grant(actor, customer_id, site_id):
        actors[actor] = replace(admin, grants=(replace(
            admin.grants[0], scope_type="site" if site_id else "customer",
            customer_id=customer_id, site_id=site_id,
        ),))

    session = migrated_history.session
    field = "hostname" if kind == "asset" else "owner_name"
    with session() as db:
        origin = db.scalars(select(Site)).one()
        customer_id, site_id = origin.customer_id, origin.id
        same_customer = Site(customer_id=customer_id, name="Second Site")
        db.add_all([admin.user, same_customer])
        # Give this case one requirement, independent of seeded Service policy.
        db.execute(update(KnowledgeRequirementDefinition).values(active=False))
        rule = KnowledgeRequirementDefinition(
            name="Required test field", key="s11_test_field", entity_type=kind,
            requirement_level="required", severity="critical",
            rule_type="field_present" if kind == "asset" else "service_field_present",
            rule_config_json={"field": field}, active=True,
        )
        db.add(rule)
        if kind == "asset":
            asset_type = db.scalar(select(AssetType).where(AssetType.key == "virtual_machine"))
            type_fields = {"asset_type": asset_type.key}
        else:
            type_fields = {
                "service_type_id": str(db.scalar(select(ServiceType.id).where(ServiceType.active))),
                "criticality_level_id": str(db.scalar(select(CriticalityLevel.id).where(CriticalityLevel.active))),
            }
        db.commit()
        requirement_id = rule.id
        destination_site_id = same_customer.id

    grant("origin", customer_id, site_id)
    grant("destination", customer_id, destination_site_id)
    grant("customer", customer_id, None)
    app = FastAPI()
    for router in (assets.router, services.router, knowledge_completeness.router, context.router):
        app.include_router(router)
    engine = migrated_history.engine

    def request_db(request: Request):
        with session() as db:
            db.connection(execution_options={"test_step": request.headers.get("x-test-step")})
            yield db

    def principal(request: Request):
        return actors[request.headers.get("x-test-actor", "admin")]

    app.dependency_overrides[get_db] = request_db
    app.dependency_overrides[get_principal] = principal
    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post(f"/{kind}s", headers={"x-test-actor": "origin"}, json={
            "name": f"Scope fixture {kind}", "customer_id": str(customer_id),
            "site_id": str(site_id), **type_fields,
        })
        assert created.status_code == 201, created.text
        entity_id = UUID(created.json()["id"])
        yield SimpleNamespace(
            client=client, session=session, engine=engine, grant=grant, model=model,
            field=field, kind=kind, id=entity_id, user_id=admin.user.id,
            customer=customer_id, site=site_id, destination=destination_site_id,
            requirement=requirement_id, path=f"/{kind}s/{entity_id}",
        )


def actor(name):
    return {"x-test-actor": name}


def gaps(case, who, **filters):
    response = case.client.get("/knowledge-gaps", headers=actor(who), params={
        "requirement_id": str(case.requirement), **filters,
    })
    assert response.status_code == 200, response.text
    return response.json()


def detail(case, who):
    response = case.client.get(case.path + "/completeness", headers=actor(who))
    assert response.status_code == 200, response.text
    return response.json()


def gap_summary(case, who, path="/knowledge-gaps/summary"):
    response = case.client.get(path, headers=actor(who))
    assert response.status_code == 200, response.text
    return response.json()


def stored(case):
    """Inspect original rows even when regular completeness reads hide them."""
    with case.session() as db:
        entity = db.get(case.model, case.id)
        gap_rows = list(db.scalars(select(KnowledgeGap).where(
            KnowledgeGap.entity_id == case.id,
        ).execution_options(include_unmatched_completeness=True)))
        summary = db.scalar(select(KnowledgeCompletenessSummary).where(
            KnowledgeCompletenessSummary.entity_id == case.id,
        ).execution_options(include_unmatched_completeness=True))
        return entity, {str(gap.id): gap for gap in gap_rows}, summary


def history(case):
    with case.session() as db:
        return tuple(
            db.execute(select(table).where(condition).order_by(table.c.id)).mappings().all()
            for table, condition in (
                (KnowledgeAssertion.__table__, KnowledgeAssertion.__table__.c.subject_id == case.id),
                (KnowledgeChange.__table__, KnowledgeChange.__table__.c.entity_id == case.id),
                (AuditEvent.__table__, AuditEvent.__table__.c.target_type == "knowledge_gap"),
            )
        )


def test_single_customer_same_scope_gap_lifecycle(case):
    with case.session() as db:
        assert db.scalar(select(func.count()).select_from(Customer)) == 1
    gap, = gaps(case, "origin")
    assert gap["status"] == "open"
    assert detail(case, "origin")["active_gaps"] == [gap]
    assert gaps(case, "destination") == []
    base = f"/knowledge-gaps/{gap['id']}"
    failed = case.client.post(base + "/resolve", headers=actor("origin"))
    assert failed.status_code == 409
    assert case.client.post(case.path + "/evaluate-completeness", headers=actor("origin")).status_code == 200
    assert gaps(case, "origin")[0]["id"] == gap["id"]

    for action, payload, status in (
        ("assign", {"user_id": str(case.user_id)}, "open"),
        ("defer", {"reason": "Planned review", "deferred_until": REVIEW_TIME}, "deferred"),
        ("exception", {"reason": "Accepted at this site"}, "exception"),
        ("reopen", {"reason": "Review done"}, "open"),
    ):
        response = case.client.post(f"{base}/{action}", headers=actor("origin"), json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    response = case.client.patch(case.path, headers=actor("origin"), json={case.field: "Known value"})
    assert response.status_code == 200, response.text
    assert gaps(case, "origin") == []
    assert detail(case, "origin")["resolved_gaps"][0]["id"] == gap["id"]
    assert case.client.post(base + "/resolve", headers=actor("origin")).status_code == 200


def test_move_replaces_active_gap_and_keeps_original_history(case):
    payload = {"site_id": str(case.destination)}
    new_customer, new_site = case.customer, case.destination
    if case.kind == "asset":
        with case.session() as db:
            customer = Customer(name="Other customer", workspace_id=db.get(Customer, case.customer).workspace_id)
            db.add(customer)
            db.flush()
            site = Site(name="Other customer's site", customer_id=customer.id)
            db.add(site)
            db.commit()
            new_customer, new_site = customer.id, site.id
        case.grant("destination", new_customer, new_site)
        payload = {"customer_id": str(new_customer), "site_id": str(new_site)}

    closed, = gaps(case, "origin")
    for value in ("Known value", None):
        edited = case.client.patch(case.path, json={case.field: value})
        assert edited.status_code == 200, edited.text
    previous_resolution = stored(case)[1][closed["id"]].resolved_at
    gap, = gaps(case, "origin")
    assert gap["id"] != closed["id"]
    base = f"/knowledge-gaps/{gap['id']}"
    assert case.client.post(base + "/assign", json={"user_id": str(case.user_id)}).status_code == 200
    assert case.client.post(base + "/exception", json={"reason": "Original site decision"}).status_code == 200
    before = history(case)
    assert any(assertion["is_accepted"] for assertion in before[0])
    assert len(before[2]) == 2

    denied = case.client.patch(case.path, headers=actor("origin"), json=payload)
    assert denied.status_code == 403, denied.text
    assert history(case) == before
    entity, gap_rows, summary = stored(case)
    assert (entity.customer_id, entity.site_id) == (case.customer, case.site)
    assert gap_rows[gap["id"]].status == "exception"
    assert summary.exception_count == 1

    moved = case.client.patch(case.path, json=payload)
    assert moved.status_code == 200, moved.text
    assert gaps(case, "origin") == gaps(case, "origin", status="superseded") == []
    assert case.client.get(case.path + "/completeness", headers=actor("origin")).status_code == 404
    current, = gaps(case, "destination")
    assert current["id"] != gap["id"]
    assert (current["customer_id"], current["site_id"]) == (str(new_customer), str(new_site))
    assert current["status"] == "open"
    assert current["assigned_to_user_id"] is current["exception_reason"] is None
    assert detail(case, "destination")["active_gaps"] == [current]
    assert detail(case, "destination")["resolved_gaps"] == []
    assert gap_summary(case, "origin")["open_knowledge_gap_count"] == 0
    assert gap_summary(case, "destination")["open_knowledge_gap_count"] == 1

    after_move = history(case)
    for old_rows, new_rows in zip(before, after_move):
        assert all(row in new_rows for row in old_rows)
    for who in ("origin", "destination", "admin"):
        for action, payload in (
            ("assign", {"user_id": None}), ("defer", {"reason": "Obsolete", "deferred_until": REVIEW_TIME}),
            ("exception", {"reason": "Obsolete"}), ("reopen", {"reason": "Obsolete"}),
            ("resolve", None),
        ):
            response = case.client.post(f"{base}/{action}", headers=actor(who), json=payload)
            assert response.status_code == 404, response.text
    assert case.client.post(
        f"/knowledge-gaps/{current['id']}/defer", headers=actor("origin"),
        json={"reason": "Wrong scope", "deferred_until": REVIEW_TIME},
    ).status_code == 404
    assert history(case) == after_move

    entity, gap_rows, summary = stored(case)
    original = gap_rows[gap["id"]]
    assert (original.customer_id, original.site_id, original.status) == (case.customer, case.site, "superseded")
    assert original.exception_reason == "Original site decision"
    assert original.assigned_to_user_id == case.user_id
    resolved = gap_rows[closed["id"]]
    assert (resolved.customer_id, resolved.site_id, resolved.status) == (case.customer, case.site, "resolved")
    assert resolved.resolved_at == previous_resolution
    assert (summary.customer_id, summary.site_id, summary.open_gap_count) == (new_customer, new_site, 1)


def test_legacy_mismatch_fails_closed_and_repairs_on_reevaluation(case):
    old, = gaps(case, "origin")
    # Bypass the new move workflow to reproduce existing persisted mismatches.
    target = case.destination if case.kind == "asset" else None
    viewer = "destination" if target else "customer"
    with case.session() as db:
        table = case.model.__table__
        db.execute(update(table).where(table.c.id == case.id).values(site_id=target))
        summary = KnowledgeCompletenessSummary.__table__
        db.execute(update(summary).where(summary.c.entity_id == case.id).values(site_id=target))
        db.commit()

    assert gaps(case, "origin") == gaps(case, viewer) == []
    assert gap_summary(case, "origin")["assets_with_critical_gaps"] == 0
    assert gap_summary(case, "origin", "/dashboard/summary")["open_knowledge_gap_count"] == 0
    hidden_summary = detail(case, viewer)["summary"]
    assert hidden_summary["completeness_status"] == "not_evaluated"
    assert hidden_summary["open_gap_count"] == 0
    response = case.client.post(f"/knowledge-gaps/{old['id']}/resolve", headers=actor("origin"))
    assert response.status_code == 404, response.text
    requirements = case.client.get("/knowledge-requirements", params={"entity_type": case.kind})
    assert requirements.status_code == 200, requirements.text
    rule = next(row for row in requirements.json() if row["id"] == str(case.requirement))
    assert rule["can_delete"] is False
    assert case.client.delete(f"/knowledge-requirements/{case.requirement}").status_code == 409

    response = case.client.post(case.path + "/evaluate-completeness", headers=actor(viewer))
    assert response.status_code == 200, response.text
    current, = gaps(case, viewer)
    assert current["id"] != old["id"]
    assert current["site_id"] == (str(target) if target else None)
    _, gap_rows, summary = stored(case)
    assert gap_rows[old["id"]].status == "superseded"
    assert summary.site_id == target

    if case.kind == "service":
        for site in (case.destination, None):
            site_id = str(site) if site else None
            response = case.client.patch(case.path, headers=actor("customer"), json={"site_id": site_id})
            assert response.status_code == 200, response.text
            replacement, = gaps(case, "customer")
            assert replacement["site_id"] == site_id
            assert replacement["id"] != current["id"]
            current = replacement
        assert gaps(case, "destination") == []


def test_evaluator_failure_preserves_transfer_boundary(case, monkeypatch):
    old, = gaps(case, "origin")

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic evaluation failure")

    with monkeypatch.context() as patch:
        patch.setattr(evaluator, f"evaluate_{case.kind}", fail)
        response = case.client.patch(case.path, json={"site_id": str(case.destination)})
        assert response.status_code == 200, response.text

    assert gaps(case, "origin") == gaps(case, "destination") == []
    entity, gap_rows, summary = stored(case)
    assert entity.site_id == summary.site_id == case.destination
    assert gap_rows[old["id"]].status == "superseded"
    assert summary.completeness_status == "not_evaluated"
    assert summary.open_gap_count == 0
    assert case.client.post(case.path + "/evaluate-completeness", headers=actor("destination")).status_code == 200
    assert len(gaps(case, "destination")) == 1


def test_failed_outer_transaction_rolls_back_entity_gap_and_audit(case):
    old, = gaps(case, "origin")
    before = history(case)

    def fail_commit(db):
        if db.connection().get_execution_options().get("test_step") == "abort" and not db.in_nested_transaction():
            db.flush()
            raise RuntimeError("synthetic outer transaction failure")

    event.listen(SessionLocal.class_, "before_commit", fail_commit)
    try:
        response = case.client.patch(case.path, headers={"x-test-step": "abort"}, json={"site_id": str(case.destination)})
    finally:
        event.remove(SessionLocal.class_, "before_commit", fail_commit)
    assert response.status_code == 500, response.text
    assert history(case) == before
    assert gaps(case, "origin") == [old]
    assert gaps(case, "destination") == []
    entity, rows, summary = stored(case)
    assert entity.site_id == summary.site_id == case.site
    assert list(rows) == [old["id"]]


@pytest.mark.parametrize("first", ["transfer", "mutation"])
def test_transfer_and_gap_mutation_serialize(case, first):
    old, = gaps(case, "origin")
    holder_ready, waiter_reached_lock, release = Event(), Event(), Event()

    def pause_before_commit(db):
        if db.connection().get_execution_options().get("test_step") == "hold" and not db.in_nested_transaction():
            db.flush()
            holder_ready.set()
            assert release.wait(10)

    def observe_entity_lock(conn, cursor, statement, parameters, ctx, many):
        if ctx.execution_options.get("test_step") == "wait" and (
            "FOR NO KEY UPDATE" in statement or "FOR UPDATE" in statement
        ):
            waiter_reached_lock.set()

    def transfer(step):
        return case.client.patch(case.path, headers={"x-test-step": step}, json={"site_id": str(case.destination)})

    def mutate(step):
        return case.client.post(f"/knowledge-gaps/{old['id']}/defer",
            headers={**actor("origin"), "x-test-step": step},
            json={"reason": "Only the original scope", "deferred_until": REVIEW_TIME})

    operations = {"transfer": transfer, "mutation": mutate}
    second = "mutation" if first == "transfer" else "transfer"
    event.listen(SessionLocal.class_, "before_commit", pause_before_commit)
    event.listen(case.engine, "before_cursor_execute", observe_entity_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            holder = workers.submit(operations[first], "hold")
            try:
                assert holder_ready.wait(10)
                waiter = workers.submit(operations[second], "wait")
                assert waiter_reached_lock.wait(10)
            finally:
                release.set()
            held_response, waited_response = holder.result(timeout=15), waiter.result(timeout=15)
    finally:
        event.remove(SessionLocal.class_, "before_commit", pause_before_commit)
        event.remove(case.engine, "before_cursor_execute", observe_entity_lock)

    assert held_response.status_code == 200, held_response.text
    assert waited_response.status_code == (404 if first == "transfer" else 200), waited_response.text
    current, = gaps(case, "destination")
    assert current["status"] == "open"
    assert current["resolution_reason"] is None
    entity, rows, summary = stored(case)
    assert entity.site_id == summary.site_id == case.destination
    assert rows[old["id"]].status == "superseded"
    assert rows[old["id"]].resolution_reason == (
        "Entity scope changed" if first == "transfer" else "Only the original scope"
    )
    _, _, audit = history(case)
    assert len(audit) == (0 if first == "transfer" else 1)
