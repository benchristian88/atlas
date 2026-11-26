"""Verify the create-only contract through authenticated HTTP and real PostgreSQL."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import UUID, uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import delete, event, func, insert, select, text, update

from app.models import (
    AccessAssignment, AuditEvent, BusinessFunction, CriticalityLevel, DataSource, KnowledgeAssertion,
    KnowledgeChange, KnowledgeCompletenessSummary, KnowledgeGap, KnowledgeRequirementDefinition,
    OnboardingCapabilitySubmission,
    Permission, RolePermission, Service, ServiceAssetDependency, ServiceBusinessFunction, ServiceDependency,
    ServiceType, SiteOnboarding,
)
from app.routes import service_reference_data as reference_routes
from app.routes import services as service_routes
from app.services import onboarding, onboarding_capabilities
from app.services.homelab_catalogue import load_catalogue
from tests.test_onboarding_postgres import ENTRY, confirm, env, pytestmark


CREATE = {"services.create", "business_functions.manage", "business_functions.view"}
READ = {"services.view", "business_functions.view"}
REFERENCE_READ = {"service_types.view", "criticality_levels.view"}
ALL = ENTRY | CREATE | READ | REFERENCE_READ
FUNCTION = "bf.home-connectivity"
SERVICE = "svc.internet-access"
LINK = "assoc.home-connectivity.internet-access"


def open_capabilities(client, pair, profile="homelab"):
    assert client.post(f"{pair.path}/start").status_code == 200
    result = confirm(client, pair.path, profile=profile)
    assert result.status_code == 200, result.text
    return pair.path + "/capabilities"


def subset(*, suffix="", link=True):
    return {
        **load_catalogue().versions,
        "functions": [{"id": FUNCTION, "name": f"Home Connectivity{suffix}"}],
        "services": [{"id": SERVICE, "name": f"Internet Access{suffix}"}],
        "associations": [LINK] if link else [],
    }


def put(client, path, selection, version=2, **flags):
    return client.put(path + "/draft", json={"version": version, "selection": selection, **flags})


def apply(client, path, version, key=None):
    return client.post(path + "/apply", json={"version": version, "submission_id": str(key or uuid4())})


def counts(env, pair):
    scopes = (BusinessFunction, Service, ServiceBusinessFunction, DataSource, KnowledgeAssertion, KnowledgeChange,
              KnowledgeGap, KnowledgeCompletenessSummary, AuditEvent)
    with env.sessions() as db:
        result = [db.scalar(select(func.count()).select_from(model).where(model.customer_id == pair.customer.id))
                  for model in scopes]
        result.append(db.scalar(select(func.count()).select_from(OnboardingCapabilitySubmission).join(
            SiteOnboarding, SiteOnboarding.id == OnboardingCapabilitySubmission.onboarding_id,
        ).where(SiteOnboarding.customer_id == pair.customer.id)))
    return result


def test_defaults_preview_shared_draft_and_stale_version(env, monkeypatch):
    pair = env.pair()
    author = env.actor(ALL).client
    peer = env.actor(ALL, "customer", pair.customer.id).client
    viewer = env.actor(ENTRY - {"sites.manage"}).client
    assert author.get(pair.path + "/capabilities").status_code == 404
    path = open_capabilities(author, pair)
    status = author.get(path).json()
    defaults = status["defaults"]
    assert status["version"] == 2 and status["draft"] is None and status["profile"] == "homelab"
    assert [len(defaults[key]) for key in ("functions", "services", "associations")] == [8, 24, 24]
    assert len(status["catalogue"]["associations"]) == 42
    assert defaults["services"][0] == {"id": SERVICE}
    baseline = counts(env, pair)
    assert author.post(path + "/preview", json={"version": 2, "selection": defaults}).json() == {"warnings": []}
    assert counts(env, pair) == baseline

    chosen = subset()
    chosen["functions"][0]["description"] = None
    chosen["services"][0].update(name="  WAN link  ", description="Local notes",
                                 service_type_key="shared_service", criticality_key="high")
    saved = put(author, path, chosen, save_and_exit=True)
    assert saved.status_code == 200, saved.text
    assert (saved.json()["status"], saved.json()["version"]) == ("saved", 3)
    assert peer.get(path).json()["draft"] == chosen
    assert viewer.get(path).json()["draft"] is None
    assert put(peer, path, defaults).status_code == 409
    assert apply(peer, path, 3).status_code == 409
    assert peer.post(pair.path + "/resume", json={"version": 3}).json()["version"] == 4
    assert peer.get(path).json()["draft"] == chosen
    assert counts(env, pair)[:-2] == baseline[:-2]

    original = load_catalogue()
    monkeypatch.setattr("app.services.onboarding_capabilities.load_catalogue",
                        lambda: original.model_copy(update={"content_version": "1.1.0"}))
    stale = peer.get(path).json()
    assert stale["draft_stale"] and stale["draft"] == chosen
    assert apply(peer, path, 4).status_code == 409
    assert put(peer, path, stale["defaults"], version=4).status_code == 409
    assert put(peer, path, chosen, version=4, replace_stale_draft=True).status_code == 409
    chosen["content_version"] = "1.1.0"
    assert put(peer, path, chosen, version=4, replace_stale_draft=True).status_code == 200
    assert not peer.get(path).json()["draft_stale"]


@pytest.mark.parametrize("profile", ["homelab", "blank"])
def test_skip_and_blank_never_create_domain_records(env, profile):
    pair = env.pair()
    client = env.actor(ENTRY, "site", pair.customer.id, pair.site.id).client
    path = open_capabilities(client, pair, profile)
    if profile == "blank":
        blank = client.get(path).json()
        assert blank["catalogue"] is None and blank["defaults"] is None
        assert put(client, path, subset()).status_code == 409
        assert apply(client, path, 2).status_code == 409
        version = 2
    else:
        empty = {**subset(), "functions": [], "services": [], "associations": []}
        assert put(client, path, empty).status_code == 200
        assert apply(client, path, 3).status_code == 422
        version = 3
    skipped = client.post(path + "/skip", json={"version": version})
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["current_stage"] == "integrations"
    assert skipped.json()["stage_decisions"]["capabilities"] == "skipped"
    assert client.get(path).json()["draft"] is None
    assert client.post(path + "/skip", json={"version": version + 1}).status_code == 409
    assert counts(env, pair)[:8] == [0] * 8


@pytest.mark.parametrize("selection", [
    lambda s: s["services"][0].update(name="  "),
    lambda s: s["services"][0].update(name="x\x00y"),
    lambda s: s["services"][0].update(service_type_key="unknown_type"),
    lambda s: s["services"][0].update(criticality_key="unknown_rank"),
    lambda s: s["services"][0].update(operational_status="healthy"),
    lambda s: s["services"][0].update(id="svc.not-in-catalogue"),
    lambda s: s["functions"].append(s["functions"][0]),
    lambda s: s["functions"].clear(),
    lambda s: s["associations"].append(LINK),
    lambda s: s["associations"].__setitem__(0, "assoc.home-connectivity.other"),
])
def test_invalid_selection_is_rejected_by_preview_and_draft(env, selection):
    pair = env.pair()
    client = env.actor(ALL).client
    path = open_capabilities(client, pair)
    candidate = subset()
    selection(candidate)
    assert client.post(path + "/preview", json={"version": 2, "selection": candidate}).status_code == 422
    assert put(client, path, candidate).status_code == 422
    assert client.get(path).json()["version"] == 2


def test_active_reference_keys_rechecked_on_apply(env):
    pair = env.pair()
    client = env.actor(ALL).client
    path = open_capabilities(client, pair)
    assert put(client, path, subset()).status_code == 200
    with env.sessions.begin() as db:
        category = db.scalar(select(ServiceType).where(ServiceType.key == "external_service"))
        original_active, original_name = category.active, category.name
        category.active = False
    try:
        result = apply(client, path, 3)
        assert result.status_code == 422 and result.json()["detail"]["definition_id"] == SERVICE
        assert client.get(path).json()["draft"] == subset()
        with env.sessions.begin() as db:
            db.execute(update(ServiceType).where(ServiceType.key == "external_service").values(
                active=True, name="Renamed external classification",
            ))
        assert apply(client, path, 3).status_code == 200
    finally:
        with env.sessions.begin() as db:
            db.execute(update(ServiceType).where(ServiceType.key == "external_service").values(
                active=original_active, name=original_name,
            ))


@pytest.mark.parametrize("model,reference_key,endpoint,field,new_value,requirement_key", [
    (ServiceType, "external_service", "service-types", "requires_asset_dependency", True,
     "service_asset_dependency"),
    (CriticalityLevel, "medium", "criticality-levels", "rank", 75, "critical_service_rto"),
])
@pytest.mark.parametrize("creation,first", [
    ("apply", "creator"), ("apply", "reference"), ("apply", "rollback"),
    ("customer", "creator"), ("customer", "reference"), ("site", "creator"),
])
def test_reference_edits_and_service_creation_commit_current_completeness(
    env, monkeypatch, model, reference_key, endpoint, field, new_value, requirement_key, creation, first,
):
    pair = env.pair()
    admin = env.actor({"service_types.manage", "criticality_levels.manage"}).client
    creator = env.actor(ALL).client
    submission_id = uuid4()
    with env.sessions() as db:
        reference = db.scalar(select(model).where(model.key == reference_key))
        reference_id, original_value = reference.id, getattr(reference, field)
        service_type_id = db.scalar(select(ServiceType.id).where(ServiceType.key == "external_service"))
        level_id = db.scalar(select(CriticalityLevel.id).where(CriticalityLevel.key == "medium"))
        requirement_id = db.scalar(select(KnowledgeRequirementDefinition.id).where(
            KnowledgeRequirementDefinition.key == requirement_key,
        ))
    assert original_value != new_value and requirement_id is not None

    if creation == "apply" and first == "creator" and model is ServiceType:
        # Rows newer than the import must not crowd it out of the reference edit's scan.
        with env.sessions.begin() as db:
            db.execute(insert(Service).values(updated_at=func.now() + text("interval '1 day'")), [
                {"customer_id": pair.customer.id, "name": f"Existing Service {index}",
                 "slug": f"existing-service-{index}", "service_type_id": service_type_id,
                 "criticality_level_id": level_id}
                for index in range(100)
            ])

    ordinary_payload = {"customer_id": str(pair.customer.id), "name": "Manual Internet Access",
                        "service_type_id": str(service_type_id), "criticality_level_id": str(level_id)}
    existing_id = None
    if first == "rollback":
        existing = creator.post("/api/services", json={**ordinary_payload, "name": "Existing Service"})
        assert existing.status_code == 201, existing.text
        existing_id = UUID(existing.json()["id"])

    if creation == "apply":
        path = open_capabilities(creator, pair)
        assert put(creator, path, subset()).status_code == 200
        created_name = "Internet Access"

        def create():
            return apply(creator, path, 3, submission_id)
    else:
        created_name = ordinary_payload["name"]
        if creation == "site":
            ordinary_payload["site_id"] = str(pair.site.id)

        def create():
            return creator.post("/api/services", json=ordinary_payload)

    def edit():
        return admin.patch(f"/api/{endpoint}/{reference_id}", json={field: new_value})

    holder_ready, waiter_ready, release_holder = Event(), Event(), Event()
    pids, database_errors = {}, []

    def pause(db):
        pids["holder"] = db.connection().connection.driver_connection.info.backend_pid
        holder_ready.set()
        assert release_holder.wait(12)

    if first == "creator":
        # Creation has evaluated the original reference but has yet to commit.
        module = onboarding_capabilities if creation == "apply" else service_routes
        add_service = module.add_service

        def pause_after_create(db, *args):
            service = add_service(db, *args)
            pause(db)
            return service

        monkeypatch.setattr(module, "add_service", pause_after_create)
    else:
        commit = reference_routes.commit

        def pause_after_edit(db, resource):
            db.flush()
            pause(db)
            if first == "rollback":
                raise HTTPException(409, "Injected reference transaction failure")
            return commit(db, resource)

        monkeypatch.setattr(reference_routes, "commit", pause_after_edit)

    table = model.__tablename__

    def observe_waiter(conn, cursor, statement, parameters, context, executemany):
        lock_mode = "FOR NO KEY UPDATE" if first == "creator" else "FOR SHARE"
        if (holder_ready.is_set() and not waiter_ready.is_set() and (
            (f"FROM {table}" in statement and lock_mode in statement)
            or (first == "creator" and statement.startswith(f"UPDATE {table} "))
        )):
            pids["waiter"] = conn.connection.driver_connection.info.backend_pid
            waiter_ready.set()

    def observe_database_error(context):
        database_errors.append(getattr(context.original_exception, "sqlstate", None))

    engine = env.sessions.kw["bind"]
    event.listen(engine, "before_cursor_execute", observe_waiter)
    event.listen(engine, "handle_error", observe_database_error)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            holder, waiter = (create, edit) if first == "creator" else (edit, create)
            pending_holder = pool.submit(holder)
            try:
                assert holder_ready.wait(5)
                pending_waiter = pool.submit(waiter)
                assert waiter_ready.wait(5)
                with engine.connect() as connection:
                    deadline = monotonic() + 4
                    while pids["holder"] not in connection.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["waiter"]},
                    ):
                        assert monotonic() < deadline, "Reference edit and creation did not serialize"
                        sleep(0.01)
            finally:
                release_holder.set()
            a, b = pending_holder.result(timeout=12), pending_waiter.result(timeout=12)
        created, edited = (a, b) if first == "creator" else (b, a)
        assert not database_errors
        assert created.status_code == (200 if creation == "apply" else 201), created.text
        assert edited.status_code == (409 if first == "rollback" else 200), edited.text
        with env.sessions() as db:
            service = db.scalars(select(Service).where(Service.customer_id == pair.customer.id,
                                                       Service.name == created_name)).one()
            assert service.site_id == (pair.site.id if creation == "site" else None)
            assert service.service_type_id == service_type_id and service.criticality_level_id == level_id
            gap = db.scalar(select(KnowledgeGap).where(
                KnowledgeGap.entity_id == service.id, KnowledgeGap.requirement_definition_id == requirement_id,
            ))
            if first == "rollback":
                assert getattr(db.get(model, reference_id), field) == original_value and gap is None
                assert db.scalar(select(KnowledgeGap.id).where(
                    KnowledgeGap.entity_id == existing_id, KnowledgeGap.requirement_definition_id == requirement_id,
                )) is None
            else:
                assert getattr(db.get(model, reference_id), field) == new_value
                assert gap is not None and gap.status == "open"
            if creation == "apply":
                receipt = db.get(OnboardingCapabilitySubmission, submission_id)
                assert receipt.requested_version == 3 and receipt.outcome == created.json()
    finally:
        event.remove(engine, "before_cursor_execute", observe_waiter)
        event.remove(engine, "handle_error", observe_database_error)
        with env.sessions.begin() as db:
            db.execute(update(model).where(model.id == reference_id).values({field: original_value}))


@pytest.mark.parametrize("full", [False, True])
def test_creation_canonical_side_effects_and_replay(env, full, monkeypatch):
    pair = env.pair()
    sibling = env.pair(customer=pair.customer)
    actor = env.actor(ALL)
    client = actor.client
    path = open_capabilities(client, pair)
    sibling_path = open_capabilities(client, sibling)
    other_progress = client.get(sibling.path).json()
    catalogue = load_catalogue()
    custom_function_name = "Réseau domestique — 家庭"
    chosen = subset()
    if full:
        chosen = {
            **catalogue.versions,
            "functions": [{"id": group.id} for group in catalogue.functions],
            "services": [{"id": item.id} for group in catalogue.functions for item in group.services],
            "associations": [item.id for item in catalogue.associations],
        }
    else:
        chosen["functions"][0].update(name=custom_function_name, description="My Function")
        chosen["services"][0].update(name="Uplink", description="My Service",
                                     service_type_key="shared_service", criticality_key="high")
    assert put(client, path, chosen).status_code == 200
    key = uuid4()
    first = apply(client, path, 3, key)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result == {
        "submission_id": str(key), "version": 4, "current_stage": "integrations",
        "created": {field: len(chosen[field]) for field in ("functions", "services", "associations")},
    }
    saved_counts = counts(env, pair)
    assert apply(client, path, 3, key).json() == result
    assert apply(client, path, 4, key).status_code == 409
    assert apply(client, sibling_path, 2, key).json() == {"detail": "Record not found"}
    assert counts(env, pair) == saved_counts
    assert client.get(sibling.path).json() == other_progress
    status = client.get(path).json()
    assert status["draft"] is None
    assert all(not status["defaults"][field] for field in ("functions", "services", "associations"))
    assert client.get(pair.path).json()["progress"]["stage_decisions"]["capabilities"] == "completed"

    with env.sessions() as db:
        customer = pair.customer.id
        functions = list(db.scalars(select(BusinessFunction).where(BusinessFunction.customer_id == customer)))
        services = list(db.scalars(select(Service).where(Service.customer_id == customer)))
        links = list(db.scalars(select(ServiceBusinessFunction).where(ServiceBusinessFunction.customer_id == customer)))
        assert [len(rows) for rows in (functions, services, links)] == [len(chosen[field]) for field in (
            "functions", "services", "associations",
        )]
        assert all(item.site_id is None and item.created_by_user_id == actor.id for item in [*functions, *services, *links])
        expected = {item.name: (item.description, item.service_type_name) for group in catalogue.functions for item in group.services}
        actual = {item.name: (item.description, db.get(ServiceType, item.service_type_id).key) for item in services}
        if full:
            assert actual == {name: (description, status["default_service_type_keys"][label])
                              for name, (description, label) in expected.items()}
            assert {item.name: item.description for item in functions} == {
                group.name: group.description for group in catalogue.functions
            }
        else:
            assert actual == {"Uplink": ("My Service", "shared_service")}
            assert (functions[0].name, functions[0].description) == (custom_function_name, "My Function")
        expected_level = "medium" if full else "high"
        assert {db.get(CriticalityLevel, item.criticality_level_id).key for item in services} == {expected_level}
        assert all((item.source, item.operational_status, item.owner_name, item.rto_minutes, item.rpo_minutes)
                   == ("manual", "unknown", None, None, None) for item in services)
        service_names = {item.id: item.name for item in services}
        function_names = {item.id: item.name for item in functions}
        assert {(function_names[link.business_function_id], service_names[link.service_id]) for link in links} == (
            {(group.name, item.name) for group in catalogue.functions for item in group.services}
            if full else {(custom_function_name, "Uplink")}
        )
        assert all(link.relationship_type_id is None and link.valid_to is None for link in links)
        assert db.scalar(select(func.count()).select_from(ServiceAssetDependency).where(
            ServiceAssetDependency.customer_id == customer,
        )) == 0
        assert db.scalar(select(func.count()).select_from(ServiceDependency).where(
            ServiceDependency.customer_id == customer,
        )) == 0
        event_counts = Counter(db.scalars(select(AuditEvent.event_type).where(
            AuditEvent.customer_id == customer, AuditEvent.user_id == actor.id,
        )))
        assert event_counts["business_function.created"] == len(functions)
        assert event_counts["service.created"] == len(services)
        assert event_counts["service_business_function.created"] == len(links)
        assert event_counts["onboarding.capabilities_applied"] == 1
        assert db.scalar(select(func.count()).select_from(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == customer, KnowledgeAssertion.predicate == "supports",
            KnowledgeAssertion.truth_classification == "declared",
        )) == len(links)
        assert db.scalar(select(func.count()).select_from(KnowledgeCompletenessSummary).where(
            KnowledgeCompletenessSummary.customer_id == customer,
        )) == len(services)
        receipt = db.get(OnboardingCapabilitySubmission, key)
        assert receipt.outcome == result
    # A committed replay remains available across content upgrades.
    monkeypatch.setattr("app.services.onboarding_capabilities.load_catalogue",
                        lambda: catalogue.model_copy(update={"content_version": "1.1.0"}))
    assert apply(client, path, 3, key).json() == result


def test_warnings_match_customer_wide_constraints_without_reuse(env):
    pair = env.pair()
    other = env.pair()
    operator = env.actor(ALL).client
    path = open_capabilities(operator, pair)
    selection = subset()
    selection["services"].append({"id": "svc.dns", "name": "Local DNS"})
    with env.sessions.begin() as db:
        pair_type = db.scalar(select(ServiceType.id).where(ServiceType.key == "external_service"))
        level = db.scalar(select(CriticalityLevel.id).where(CriticalityLevel.key == "medium"))
        existing = Service(customer_id=pair.customer.id, name="INTERNET ACCESS", slug="internet-access",
                           service_type_id=pair_type, criticality_level_id=level, description="Accepted")
        db.add_all([
            existing,
            BusinessFunction(customer_id=other.customer.id, name="Home Connectivity"),
            BusinessFunction(customer_id=pair.customer.id, site_id=pair.site.id, name="Home Connectivity"),
            Service(customer_id=pair.customer.id, site_id=pair.site.id, name="Local DNS", slug="local-dns",
                    service_type_id=pair_type, criticality_level_id=level),
        ])
    preview = {"version": 2, "selection": selection}
    assert operator.post(path + "/preview", json=preview).json()["warnings"] == [
        {"code": "existing_name", "definition_id": SERVICE},
    ]
    site_only = env.actor(ALL, "site", pair.customer.id, pair.site.id).client
    assert site_only.post(path + "/preview", json=preview).json() == {"warnings": []}
    assert put(operator, path, selection).status_code == 200
    before = counts(env, pair)
    conflict = apply(operator, path, 3)
    assert conflict.status_code == 409 and "Edit the selected names" in conflict.json()["detail"]
    assert counts(env, pair) == before
    assert operator.get(path).json()["draft"] == selection
    with env.sessions() as db:
        assert db.get(Service, existing.id).description == "Accepted"
    # The generated canonical slug can still collide when display names differ.
    selection["services"][0]["name"] = "Internet / Access"
    assert put(operator, path, selection, version=3).status_code == 200
    assert apply(operator, path, 4).status_code == 409
    selection["services"][0]["name"] = "Internet Access (lab)"
    assert put(operator, path, selection, version=4).status_code == 200
    assert apply(operator, path, 5).status_code == 200

    with env.sessions.begin() as db:
        state = onboarding.progress(db, pair.site, lock=True)
        state.current_stage = "discovery_review"
        state.stage_decisions = {**state.stage_decisions, "integrations": "completed"}
    assert put(operator, path, subset(suffix=" Second import"), version=6).status_code == 200
    repeated = apply(operator, path, 7)
    assert repeated.status_code == 200, repeated.text
    progress = operator.get(pair.path).json()["progress"]
    assert progress["current_stage"] == "discovery_review"
    assert progress["stage_decisions"] == {
        "environment": "completed", "capabilities": "completed", "integrations": "completed",
    }
    with env.sessions() as db:
        assert db.get(Service, existing.id).description == "Accepted"
        assert db.scalar(select(func.count()).select_from(ServiceBusinessFunction).where(
            ServiceBusinessFunction.service_id == existing.id,
        )) == 0


def test_unicode_business_function_names_use_canonical_uniqueness_during_apply(env):
    pair = env.pair()
    client = env.actor(ALL).client
    created = client.post("/api/business-functions", json={
        "customer_id": str(pair.customer.id), "name": "  İletişim — 家庭\t",
    })
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "İletişim — 家庭"
    function_path = f"/api/business-functions/{created.json()['id']}"
    edited = client.patch(function_path, json={"name": "  Maison — 家庭\t"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "Maison — 家庭"

    path = open_capabilities(client, pair)
    selection = subset()
    conflicting_id = load_catalogue().functions[1].id
    selection["functions"].append({"id": conflicting_id, "name": "  mAISON — 家庭\t"})
    preview = client.post(path + "/preview", json={"version": 2, "selection": selection})
    assert preview.status_code == 200, preview.text
    assert preview.json() == {"warnings": [{"definition_id": conflicting_id, "code": "existing_name"}]}
    assert put(client, path, selection).status_code == 200
    before = counts(env, pair)
    progress = client.get(pair.path).json()["progress"]
    submission_id = uuid4()

    conflict = apply(client, path, 3, submission_id)
    assert conflict.status_code == 409 and "Edit the selected names" in conflict.json()["detail"]
    assert counts(env, pair) == before
    assert client.get(path).json()["draft"] == selection
    assert client.get(pair.path).json()["progress"] == progress
    assert client.get(function_path).json()["name"] == "Maison — 家庭"
    with env.sessions() as db:
        assert db.get(OnboardingCapabilitySubmission, submission_id) is None


def test_rollback_after_associations_audit_and_receipt_are_written(env):
    pair = env.pair()
    client = env.actor(ALL).client
    path = open_capabilities(client, pair)
    assert put(client, path, subset()).status_code == 200
    before = counts(env, pair)
    key = uuid4()
    trigger = "e1b_deferred_" + key.hex
    with env.sessions.begin() as db:
        db.execute(text(f"""
            CREATE FUNCTION {trigger}() RETURNS trigger LANGUAGE plpgsql AS $fail$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM service_business_functions AS link
                    JOIN site_onboarding AS progress ON progress.customer_id = link.customer_id
                    WHERE progress.id = NEW.onboarding_id
                    AND progress.current_stage = 'integrations'
                ) THEN
                    RAISE EXCEPTION 'test ordering: link and workflow must already be written';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM audit_events AS audit JOIN site_onboarding AS progress
                    ON progress.site_id = audit.site_id AND progress.customer_id = audit.customer_id
                    WHERE progress.id = NEW.onboarding_id AND audit.event_type = 'onboarding.capabilities_applied'
                ) THEN
                    RAISE EXCEPTION 'test ordering: onboarding audit must already be written';
                END IF;
                RAISE check_violation USING MESSAGE = 'disposable E1-B commit failure';
            END $fail$
        """))
        db.execute(text(f"""
            CREATE CONSTRAINT TRIGGER {trigger} AFTER INSERT ON onboarding_capability_submissions
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.id = '{key}')
            EXECUTE FUNCTION {trigger}()
        """))
    try:
        response = apply(client, path, 3, key)
        assert response.status_code == 409, response.text
        assert counts(env, pair) == before
        assert client.get(path).json()["draft"] == subset()
        assert client.get(pair.path).json()["progress"]["version"] == 3
    finally:
        with env.sessions.begin() as db:
            db.execute(text(f"DROP TRIGGER {trigger} ON onboarding_capability_submissions"))
            db.execute(text(f"DROP FUNCTION {trigger}()"))
    assert apply(client, path, 3, key).status_code == 200


@pytest.mark.parametrize("scenario", ["same_key", "same_site", "cross_site", "cross_site_conflict", "cross_site_same_key"])
def test_concurrent_submissions_obey_versions_scope_and_constraints(env, scenario):
    left = env.pair()
    a, b = env.actor(ALL).client, env.actor(ALL).client
    left_path = open_capabilities(a, left)
    left_key = uuid4()
    assert put(a, left_path, subset()).status_code == 200
    if scenario.startswith("cross_site"):
        right = env.pair(customer=left.customer)
        right_path = open_capabilities(b, right)
        suffix = "" if scenario == "cross_site_conflict" else " Form B"
        assert put(b, right_path, subset(suffix=suffix)).status_code == 200
    else:
        right_path = left_path
    right_key = left_key if scenario in {"same_key", "cross_site_same_key"} else uuid4()
    barrier = Barrier(2, timeout=5)

    def submit(client, path, key):
        barrier.wait()
        return apply(client, path, 3, key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, client, path, key) for client, path, key in (
            (a, left_path, left_key), (b, right_path, right_key),
        )]
        results = [future.result(timeout=15) for future in futures]
    statuses = [result.status_code for result in results]
    expected = [200, 200] if scenario in {"same_key", "cross_site"} else [
        200, 404 if scenario == "cross_site_same_key" else 409,
    ]
    assert sorted(statuses) == expected, [response.text for response in results]
    if scenario == "same_key":
        assert results[0].json() == results[1].json()
    created = 2 if scenario == "cross_site" else 1
    assert counts(env, left)[:4] == [created, created, created, 1]
    assert counts(env, left)[-1] == created


@pytest.mark.parametrize("apply_first,promote", [(True, False), (False, False), (True, True)])
def test_multiservice_apply_and_canonical_service_write_use_the_same_lock_order(env, monkeypatch, apply_first, promote):
    pair = env.pair()
    importer = env.actor(ALL).client
    operator = env.actor(ALL | {"services.edit"}).client
    path = open_capabilities(importer, pair)
    chosen = subset()
    chosen["services"].append({"id": "svc.dns"})
    assert put(importer, path, chosen).status_code == 200
    with env.sessions() as db:
        service_type = db.scalar(select(ServiceType.id).where(ServiceType.key == "external_service"))
        criticality = db.scalar(select(CriticalityLevel.id).where(CriticalityLevel.key == "medium"))
    payload = {"customer_id": str(pair.customer.id), "name": "DNS", "service_type_id": str(service_type),
               "criticality_level_id": str(criticality)}
    if promote:
        local = operator.post("/api/services", json={**payload, "name": "Site DNS", "site_id": str(pair.site.id)})
        assert local.status_code == 201, local.text
        local_id = UUID(local.json()["id"])

    key = uuid4()

    def submit():
        return apply(importer, path, 3, key)

    def write_service():
        if promote:
            return operator.patch(f"/api/services/{local_id}", json={"name": "DNS", "site_id": None})
        return operator.post("/api/services", json=payload)

    holder_ready, waiter_ready, release_holder = Event(), Event(), Event()
    pids, database_errors = {}, []
    declare = service_routes.declare_service_changes

    def pause_after_first_declaration(db, *, service, **kwargs):
        assertions = declare(db, service=service, **kwargs)
        if not holder_ready.is_set():
            assert service.name == ("Internet Access" if apply_first else "DNS")
            pids["holder"] = db.connection().connection.driver_connection.info.backend_pid
            holder_ready.set()
            assert release_holder.wait(12)
        return assertions

    def observe_waiter(conn, cursor, statement, parameters, context, executemany):
        if (holder_ready.is_set() and "pg_advisory_xact_lock" in statement
                and f"atlas-manual-customer-source:{pair.customer.id}" in parameters.values()):
            pids["waiter"] = conn.connection.driver_connection.info.backend_pid
            waiter_ready.set()

    def observe_database_error(context):
        database_errors.append(getattr(context.original_exception, "sqlstate", None))

    monkeypatch.setattr(service_routes, "declare_service_changes", pause_after_first_declaration)
    engine = env.sessions.kw["bind"]
    event.listen(engine, "before_cursor_execute", observe_waiter)
    event.listen(engine, "handle_error", observe_database_error)
    first, second = (submit, write_service) if apply_first else (write_service, submit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            holder = pool.submit(first)
            try:
                assert holder_ready.wait(5)
                waiter = pool.submit(second)
                assert waiter_ready.wait(5)
                with engine.connect() as connection:
                    deadline = monotonic() + 4
                    while pids["holder"] not in connection.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["waiter"]},
                    ):
                        assert monotonic() < deadline, "Second request never waited for the first transaction"
                        sleep(0.01)
            finally:
                release_holder.set()
            winner, loser = holder.result(timeout=12), waiter.result(timeout=12)
    finally:
        event.remove(engine, "before_cursor_execute", observe_waiter)
        event.remove(engine, "handle_error", observe_database_error)

    assert "40P01" not in database_errors
    assert winner.status_code == (200 if apply_first else 201), winner.text
    assert loser.status_code == 409, loser.text
    conflict = "conflicts with an existing record" if apply_first else "Edit the selected names"
    assert conflict in loser.json()["detail"]
    with env.sessions() as db:
        source_scope = (DataSource.customer_id == pair.customer.id, DataSource.site_id.is_(None),
                        DataSource.source_type == "manual", DataSource.name == "Atlas Manual Inventory")
        assert db.scalar(select(func.count()).select_from(DataSource).where(*source_scope)) == 1
        service_names = set(db.scalars(select(Service.name).where(Service.customer_id == pair.customer.id,
                                                                  Service.site_id.is_(None))))
        assert service_names == ({"Internet Access", "DNS"} if apply_first else {"DNS"})
        applied_audits = db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.customer_id == pair.customer.id, AuditEvent.event_type == "onboarding.capabilities_applied",
        ))
        assert applied_audits == int(apply_first)
        if promote:
            assert db.get(Service, local_id).site_id == pair.site.id
        receipt = db.get(OnboardingCapabilitySubmission, key)
        if apply_first:
            assert receipt.requested_version == 3 and receipt.outcome == winner.json()
        else:
            assert receipt is None
    assert counts(env, pair)[:3] == ([1, 2 + int(promote), 1] if apply_first else [0, 1, 0])
    assert counts(env, pair)[-1] == int(apply_first)
    progress = importer.get(pair.path).json()["progress"]
    if apply_first:
        assert (progress["version"], progress["current_stage"]) == (4, "integrations")
        assert importer.get(path).json()["draft"] is None
        assert apply(importer, path, 3, key).json() == winner.json()
    else:
        assert (progress["version"], progress["current_stage"], progress["stage_decisions"]) == (
            3, "capabilities", {"environment": "completed"},
        )
        assert importer.get(path).json()["draft"] == chosen

    assert operator.post("/api/services", json={**payload, "name": "Additional manual Service"}).status_code == 201
    assert put(importer, path, subset(suffix=" Later"), version=progress["version"]).status_code == 200
    assert apply(importer, path, progress["version"] + 1).status_code == 200
    with env.sessions() as db:
        assert db.scalar(select(func.count()).select_from(DataSource).where(*source_scope)) == 1


def test_canonical_create_rechecks_grants_after_customer_inventory_lock(env, monkeypatch):
    pair = env.pair()
    operator = env.actor(ALL, "customer", pair.customer.id)
    waiting = Event()
    lock_inventory = service_routes.lock_customer_manual_inventory

    def notify_lock(db, customer_id):
        waiting.set()
        return lock_inventory(db, customer_id)

    monkeypatch.setattr(service_routes, "lock_customer_manual_inventory", notify_lock)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with env.sessions.begin() as db:
            lock_inventory(db, pair.customer.id)
            service_type = db.scalar(select(ServiceType.id).where(ServiceType.key == "external_service"))
            criticality = db.scalar(select(CriticalityLevel.id).where(CriticalityLevel.key == "medium"))
            pending = pool.submit(operator.client.post, "/api/services", json={
                "customer_id": str(pair.customer.id), "name": "Customer DNS",
                "service_type_id": str(service_type), "criticality_level_id": str(criticality),
            })
            assert waiting.wait(5)
            role_id = db.scalar(select(AccessAssignment.role_id).where(AccessAssignment.id == operator.grant))
            permission_id = db.scalar(select(Permission.id).where(Permission.key == "services.create"))
            db.execute(delete(RolePermission).where(
                RolePermission.role_id == role_id, RolePermission.permission_id == permission_id,
            ))
        assert pending.result(timeout=8).status_code == 403
    assert counts(env, pair) == [0] * 10


def test_permissions_scope_receipt_and_disabled_routes(env, monkeypatch):
    pair = env.pair()
    other = env.pair()
    administrator = env.actor(ALL).client
    path = open_capabilities(administrator, pair)
    forged_context = {"X-Atlas-Customer-ID": str(pair.customer.id), "X-Atlas-Site-ID": str(pair.site.id)}
    verify_only = env.actor(ENTRY - {"sites.manage"}).client
    scoped = env.actor(ALL, "site", pair.customer.id, pair.site.id).client
    manager_no_link_view = env.actor(ALL - {"business_functions.view"}, "customer", pair.customer.id).client
    assert scoped.get(path).json()["permissions"] == {
        "can_manage": True, "can_view_service_types": True, "can_view_criticality_levels": True,
        "can_create_functions": False, "can_create_services": False,
        "can_create_associations": False,
    }
    assert verify_only.get(path).json()["permissions"]["can_manage"] is False
    wrong = f"/api/onboarding/{pair.customer.id}/{other.site.id}/capabilities"
    assert scoped.get(wrong, headers=forged_context).json() == {"detail": "Record not found"}
    assert put(verify_only, path, subset()).status_code == 404
    assert put(scoped, path, subset()).status_code == 200
    command = {"version": 3, "submission_id": str(uuid4())}
    assert scoped.post(path + "/apply", headers=forged_context, json=command).status_code == 403
    assert manager_no_link_view.post(path + "/apply", json=command).status_code == 404
    assert manager_no_link_view.post(path + "/apply", json={**command, "actor_id": str(uuid4())}).status_code == 422
    assert manager_no_link_view.post(path + "/skip", json={"version": True}).status_code == 422
    assert administrator.post(path + "/apply", json=command).status_code == 200
    assert verify_only.post(path + "/apply", json=command).status_code == 404
    assert scoped.post(path + "/apply", json=command).status_code == 403
    assert manager_no_link_view.post(path + "/apply", json=command).status_code == 404
    monkeypatch.delenv("ATLAS_ONBOARDING_PREVIEW")
    for method, suffix, data in [
        ("GET", "", None), ("POST", "/preview", {"version": 4, "selection": subset()}),
        ("PUT", "/draft", {"version": 4, "selection": subset()}),
        ("POST", "/apply", command), ("POST", "/skip", {"version": 4}),
    ]:
        result = administrator.request(method, path + suffix, json=data)
        assert result.status_code == 404, result.text
    malformed = administrator.post(path + "/apply", content=b"{", headers={"Content-Type": "application/json"})
    assert malformed.status_code == 404


def test_apply_rechecks_customer_grants_after_real_progress_lock(env, monkeypatch):
    pair = env.pair()
    actor = env.actor(ALL)
    administrator = env.actor(ALL).client
    path = open_capabilities(administrator, pair)
    assert put(administrator, path, subset()).status_code == 200
    before = counts(env, pair)
    attempting_lock = Event()
    lock_state = onboarding.progress

    def notify_progress(db, site, *, lock=False):
        if lock:
            attempting_lock.set()
        return lock_state(db, site, lock=lock)

    monkeypatch.setattr(onboarding, "progress", notify_progress)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with env.sessions.begin() as db:
            lock_state(db, pair.site, lock=True)
            pending = pool.submit(apply, actor.client, path, 3)
            assert attempting_lock.wait(timeout=5)
            role_id = db.scalar(select(AccessAssignment.role_id).where(AccessAssignment.id == actor.grant))
            permission_id = db.scalar(select(Permission.id).where(Permission.key == "services.create"))
            db.execute(delete(RolePermission).where(
                RolePermission.role_id == role_id, RolePermission.permission_id == permission_id,
            ))
        assert pending.result(timeout=5).status_code == 403
    assert counts(env, pair) == before
    assert administrator.get(path).json()["draft"] == subset()


def test_request_body_is_bounded(env):
    pair = env.pair()
    client = env.actor(ALL).client
    path = open_capabilities(client, pair)
    response = client.post(path + "/preview", content=b" " * (12 * 1024 * 1024 + 1),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_alternate_taxonomy_keys_require_normal_reference_visibility(env):
    pair = env.pair()
    manager = env.actor(ALL - REFERENCE_READ).client
    path = open_capabilities(manager, pair)
    for key in ("shared_service", "nonexistent_service"):
        chosen = subset()
        chosen["services"][0]["service_type_key"] = key
        response = manager.post(path + "/preview", json={"version": 2, "selection": chosen})
        assert response.status_code == 403
        assert put(manager, path, chosen).status_code == 403
    assert put(manager, path, subset()).status_code == 200
    assert apply(manager, path, 3).status_code == 200
