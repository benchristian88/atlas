"""C2.6 end-to-end lifecycle checks. Use a disposable Alembic-migrated database."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import get_db
from app.main import app
from app.models import (
    Asset, AssetType, AuditEvent, BusinessFunction, CriticalityLevel, Customer,
    DataSource, DependencyGroup, DependencyGroupMembership, DiscoveryRun,
    EvidenceRecord, KnowledgeAssertion, KnowledgeChange, KnowledgeCompletenessSummary,
    KnowledgeGap, KnowledgeRequirementDefinition, ReconciliationItem,
    RelationshipType, RunObservedEntity, Service, ServiceAssetDependency,
    ServiceBusinessFunction, ServiceDependency, ServiceType, Site, Workspace,
)
from app.permissions import PERMISSIONS
from app.services.entity_lifecycle import deletion_eligible
from app.services.knowledge_assertions import accept_assertion, record_assertion
from tests.test_operational_graph import principal

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def env():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    actor = principal(*PERMISSIONS)
    actor.user.email = f"c26-{uuid.uuid4()}@example.test"
    with Session(engine, expire_on_commit=False) as db:
        db.add(actor.user)
        workspace = Workspace(name="C2.6", slug=f"c26-{uuid.uuid4()}")
        db.add(workspace); db.flush()
        customer = Customer(workspace_id=workspace.id, name="C2.6")
        db.add(customer); db.flush()
        site = Site(customer_id=customer.id, name="C2.6")
        service_type = ServiceType(key=f"c26_{uuid.uuid4().hex}", name=f"C2.6 {uuid.uuid4()}")
        db.add_all([site, service_type]); db.flush()
        requirement = KnowledgeRequirementDefinition(key=f"c26_{uuid.uuid4().hex}", name="Owner", entity_type="service", service_type_id=service_type.id, requirement_level="required", severity="high", rule_type="service_field_present", rule_config_json={"field": "owner_name"})
        db.add(requirement)
        level = db.scalar(select(CriticalityLevel).limit(1))
        relation = db.scalar(select(RelationshipType).where(RelationshipType.key == "depends_on"))
        asset_type = db.scalar(select(AssetType).limit(1))
        db.commit()
    current = [actor]
    def database():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_principal] = lambda: current[0]
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer.id, site.id)
    with TestClient(app) as client:
        def create(kind="services", name=None):
            payload = {"customer_id": str(customer.id), "site_id": str(site.id), "name": name or f"Mistake {uuid.uuid4()}"}
            if kind == "services": payload.update(service_type_id=str(service_type.id), criticality_level_id=str(level.id))
            response = client.post(f"/api/{kind}", json=payload)
            assert response.status_code == 201, response.text
            return response.json()
        yield SimpleNamespace(engine=engine, client=client, create=create, current=current, actor=actor, customer=customer, site=site, workspace=workspace, relation=relation, asset_type=asset_type)
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("kind,model", [("services", Service), ("business-functions", BusinessFunction)])
def test_creation_scaffolding_delete_preserves_history_and_hides_operational_results(env, kind, model):
    item = env.create(kind)
    entity_id = uuid.UUID(item["id"])
    entity_type = "service" if model is Service else "business_function"
    path = f"/api/{kind}/{entity_id}"
    assert env.client.get(path + "/deletion-eligibility").json()["eligible"] is True
    with Session(env.engine) as db:
        assertions_before = db.scalar(select(func.count()).select_from(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == entity_id))
        gaps_before = db.scalar(select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.entity_id == entity_id))
        if model is Service:
            assert assertions_before >= 5
            assert gaps_before >= 1
    response = env.client.delete(path)
    assert response.status_code == 204, response.text
    assert env.client.get(path).status_code == 404
    assert env.client.get(path + "/deletion-eligibility").status_code == 404
    assert env.client.post(path + "/restore").status_code == 404
    assert env.client.get(path + "/graph").status_code == 404
    assert env.client.get(f"/api/operational-graph?focus_type={entity_type}&focus_id={entity_id}").status_code == 404
    if model is Service:
        assert env.client.post("/api/dependency-analysis", json={"focus_type": "service", "focus_id": str(entity_id)}).status_code == 404
    assert all(row["id"] != str(entity_id) for row in env.client.get(f"/api/{kind}?search=Mistake").json())
    assert all(row["id"] != str(entity_id) for row in env.client.get(f"/api/{kind}?archived=true").json())
    assert env.create(kind, item["name"])["id"] != item["id"]  # name/slug can be reused
    with Session(env.engine) as db:
        assert db.get(model, entity_id) is None
        retained = db.scalar(select(model).where(model.id == entity_id).execution_options(include_deleted=True))
        assert retained.deleted_at is not None
        if model is Service: assert retained.archived_at is None
        else: assert retained.active is True  # Delete is not Archive
        for artifact, column, before in [(KnowledgeAssertion, KnowledgeAssertion.subject_id, assertions_before), (KnowledgeGap, KnowledgeGap.entity_id, gaps_before)]:
            assert db.scalar(select(func.count()).select_from(artifact).where(column == entity_id)) == 0
            assert db.scalar(select(func.count()).select_from(artifact).where(column == entity_id).execution_options(include_deleted=True)) == before
        events = list(db.scalars(select(AuditEvent.event_type).where(AuditEvent.target_id == entity_id)))
        assert events == [f"{entity_type}.created", f"{entity_type}.deleted"]
        assert db.scalar(select(KnowledgeChange.id).where(KnowledgeChange.entity_id == entity_id, KnowledgeChange.change_type == f"{entity_type}_deleted"))
    changes = env.client.get(f"/api/changes?entity_id={entity_id}")
    assert changes.status_code == 200
    assert path.removeprefix("/api") not in changes.text


@pytest.mark.parametrize("reference", ["provider", "function", "dependency", "dependent", "group", "membership", "ended_provider", "ended_function", "ended_dependency"])
def test_all_current_and_historical_relationships_block(env, reference):
    service = env.create()
    service_id = uuid.UUID(service["id"])
    other = env.create() if reference in {"dependency", "dependent", "ended_dependency"} else None
    function = env.create("business-functions") if "function" in reference else None
    with Session(env.engine) as db:
        context = {"customer_id": env.customer.id, "site_id": env.site.id}
        if "provider" in reference or reference == "membership":
            asset = Asset(workspace_id=env.workspace.id, **context, name="Provider", asset_type=env.asset_type.key)
            db.add(asset); db.flush()
            row = ServiceAssetDependency(**context, service_id=service_id, asset_id=asset.id, relationship_type_id=env.relation.id)
        elif "function" in reference:
            row = ServiceBusinessFunction(**context, service_id=service_id, business_function_id=uuid.UUID(function["id"]))
        elif reference == "group":
            row = DependencyGroup(**context, service_id=service_id, name="Behaviour", strategy="all", requirement="required", failure_effect="unknown")
        else:
            source, target = (uuid.UUID(other["id"]), service_id) if reference == "dependent" else (service_id, uuid.UUID(other["id"]))
            row = ServiceDependency(**context, source_service_id=source, target_service_id=target, relationship_type_id=env.relation.id)
        if reference.startswith("ended_"): row.valid_to = datetime.now(timezone.utc)
        db.add(row); db.flush()
        if reference == "membership":
            group = DependencyGroup(**context, service_id=service_id, name="Behaviour", strategy="all", requirement="required", failure_effect="unknown")
            db.add(group); db.flush()
            db.add(DependencyGroupMembership(dependency_group_id=group.id, service_asset_dependency_id=row.id))
        db.commit()
    path = f"/api/services/{service_id}"
    assert env.client.get(path + "/deletion-eligibility").json() == {"eligible": False, "reason": "This Service cannot be deleted because it has participated in the operational model. Archive it instead."}
    assert env.client.delete(path).status_code == 409
    if function: assert env.client.delete(f"/api/business-functions/{function['id']}").status_code == 409
    env.current[0] = principal("services.archive", customer_id=env.customer.id, site_id=env.site.id)
    # No permissions to view related Assets/Services/BFs: the same generic
    # response must enforce integrity without naming or counting hidden records.
    assert env.client.get(path + "/deletion-eligibility").json() == {"eligible": False, "reason": "This Service cannot be deleted because it has participated in the operational model. Archive it instead."}
    assert env.client.delete(path).status_code == 409


@pytest.mark.parametrize("kind", ["services", "business-functions"])
def test_edits_archive_restore_and_authorization(env, kind):
    item = env.create(kind)
    path = f"/api/{kind}/{item['id']}"
    permission = "services.archive" if kind == "services" else "business_functions.manage"
    env.current[0] = principal("services.view", "business_functions.view")
    assert env.client.delete(path).status_code == 403
    assert env.client.get(path + "/deletion-eligibility").status_code == 403
    env.current[0] = principal(permission, customer_id=uuid.uuid4())
    assert env.client.delete(path).status_code == 404
    env.current[0] = principal(permission, customer_id=env.customer.id, site_id=uuid.uuid4())
    assert env.client.delete(path).status_code == 404
    env.current[0] = env.actor
    assert env.client.patch(path, json={"description": "Real operational record"}).status_code == 200
    assert env.client.delete(path).status_code == 409
    response = env.client.post(path + "/archive", json={})
    assert response.status_code == 200, response.text
    assert response.json().get("archived_at") or response.json().get("active") is False
    assert env.client.get(path).status_code == 200
    assert env.client.delete(path).status_code == 409
    assert env.client.post(path + "/restore").status_code == 200
    assert env.client.delete(path).status_code == 409


@pytest.mark.parametrize("kind,reference", [(kind, reference) for kind in ["services", "business-functions"] for reference in ["manual_assertion", "observed_assertion", "reconciliation", "observation", "evidence", "gap_decision"] if (kind, reference) != ("business-functions", "gap_decision")])
def test_knowledge_and_observations_block(env, kind, reference):
    item = env.create(kind)
    entity_id = uuid.UUID(item["id"])
    entity_type = "service" if kind == "services" else "business_function"
    with Session(env.engine) as db:
        context = {"customer_id": env.customer.id, "site_id": env.site.id}
        source = DataSource(**context, name="Test evidence", source_type="manual", status="active", trust_level="declared")
        db.add(source); db.flush()
        if reference == "gap_decision":
            gap = db.scalar(select(KnowledgeGap).where(KnowledgeGap.entity_id == entity_id))
            gap.deferred_by_user_id = env.actor.user.id
        elif reference in {"observation", "evidence"}:
            run = DiscoveryRun(**context, status="completed")
            db.add(run); db.flush()
            if reference == "observation":
                db.add(RunObservedEntity(**context, discovery_run_id=run.id, data_source_id=source.id, coverage_key="test", entity_type=entity_type, entity_id=entity_id, external_id=str(entity_id), observed_at=datetime.now(timezone.utc)))
            else:
                evidence = EvidenceRecord(**context, discovery_run_id=run.id, data_source_id=source.id, external_id=str(entity_id), entity_kind=entity_type, payload_json={"observed": True}, observed_at=datetime.now(timezone.utc))
                db.add(evidence); db.flush()
                assertion, _ = record_assertion(db, **context, subject_type=entity_type, subject_id=entity_id, predicate="notes", value="Observed evidence", truth_classification="observed", data_source_id=source.id, evidence_record_id=evidence.id, discovery_run_id=run.id)

        else:
            assertion, _ = record_assertion(db, **context, subject_type=entity_type, subject_id=entity_id, predicate="notes", value="Manually verified", truth_classification="observed" if reference == "observed_assertion" else "declared", data_source_id=source.id)
            accept_assertion(db, assertion, user_id=env.actor.user.id)
            if reference == "reconciliation": db.add(ReconciliationItem(**context, category="changed", status="accepted", entity_type=entity_type, entity_id=entity_id, assertion_id=assertion.id))
        db.commit()
    assert env.client.delete(f"/api/{kind}/{entity_id}").status_code == 409


def test_deleted_entity_guard_and_counts(env):
    item = env.create()
    entity_id = uuid.UUID(item["id"])
    assert env.client.get("/api/services/summary").json()["total"] == 1
    assert env.client.delete(f"/api/services/{entity_id}").status_code == 204
    assert env.client.get("/api/services/summary").json()["total"] == 0
    dashboard = env.client.get("/api/dashboard/summary")
    assert dashboard.status_code == 200
    assert dashboard.json()["services"] == 0
    assert str(entity_id) not in env.client.get("/api/knowledge-gaps").text
    assert env.client.post(f"/api/services/{entity_id}/evaluate-completeness").status_code == 404
    with Session(env.engine) as db:
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE services SET name = 'stale edit' WHERE id = :id"), {"id": entity_id})
        db.rollback()
        with pytest.raises(IntegrityError):
            db.add(DependencyGroup(customer_id=env.customer.id, site_id=env.site.id, service_id=entity_id, name="Late", strategy="all", requirement="required", failure_effect="unknown"))
            db.commit()


@pytest.mark.parametrize("delete_first", [True, False])
def test_concurrent_reference_and_delete_are_serialized(env, delete_first):
    item = env.create()
    entity_id = uuid.UUID(item["id"])
    ready = Event()
    def wait_for_database_lock():
        deadline = monotonic() + 5
        while monotonic() < deadline:
            with env.engine.connect() as connection:
                waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock'"))
            if waiting: return
            sleep(0.02)
        pytest.fail("Concurrent write did not reach the PostgreSQL lock")
    def add_reference():
        with Session(env.engine) as db:
            ready.set()
            db.add(DependencyGroup(customer_id=env.customer.id, site_id=env.site.id, service_id=entity_id, name="Concurrent", strategy="all", requirement="required", failure_effect="unknown"))
            try: db.commit(); return "created"
            except IntegrityError: db.rollback(); return "blocked"
    if delete_first:
        # Hold the same row lock as the API, start an overlapping writer, then
        # commit the tombstone. The writer must fail after waiting for the lock.
        with ThreadPoolExecutor(max_workers=1) as pool, Session(env.engine) as db:
            row = db.scalar(select(Service).where(Service.id == entity_id).with_for_update())
            assert deletion_eligible(db, row)
            future = pool.submit(add_reference)
            assert ready.wait(5)
            wait_for_database_lock()
            row.deleted_at = datetime.now(timezone.utc)
            db.commit()
            assert future.result(timeout=10) == "blocked"
    else:
        # An uncommitted writer holds FOR SHARE; deletion must wait then observe
        # the committed reference and reject the stale client's request.
        with ThreadPoolExecutor(max_workers=1) as pool, Session(env.engine) as db:
            db.add(DependencyGroup(customer_id=env.customer.id, site_id=env.site.id, service_id=entity_id, name="Concurrent", strategy="all", requirement="required", failure_effect="unknown"))
            db.flush()
            future = pool.submit(lambda: env.client.delete(f"/api/services/{entity_id}"))
            wait_for_database_lock()
            db.commit()
            assert future.result(timeout=10).status_code == 409


def test_legacy_initial_declarations_and_repeated_automatic_evaluation_remain_eligible(env):
    item = env.create()
    entity_id = uuid.UUID(item["id"])
    with Session(env.engine) as db:
        # Pre-C2.6 creation audits did not store the initial assertion ID batch.
        event = db.scalar(select(AuditEvent).where(AuditEvent.target_id == entity_id))
        event.metadata_ = {}
        db.commit()
    assert env.client.post(f"/api/services/{entity_id}/evaluate-completeness").status_code == 200
    assert env.client.get(f"/api/services/{entity_id}/deletion-eligibility").json()["eligible"]
    assert env.client.delete(f"/api/services/{entity_id}").status_code == 204


def test_retracted_or_replaced_initial_knowledge_is_not_creation_scaffolding(env):
    item = env.create()
    entity_id = uuid.UUID(item["id"])
    with Session(env.engine) as db:
        assertion = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == entity_id))
        assertion.retracted_at = datetime.now(timezone.utc)
        db.commit()
    assert env.client.delete(f"/api/services/{entity_id}").status_code == 409


def test_downgrade_refuses_to_resurrect_tombstones(env):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migration = importlib.import_module("migrations.versions.20260910_0016_entity_tombstones")
    item = env.create()
    assert env.client.delete(f"/api/services/{item['id']}").status_code == 204
    with env.engine.connect() as connection:
        transaction = connection.begin()
        original_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        with Operations.context(MigrationContext.configure(connection)):
            from sqlalchemy.exc import DBAPIError
            with pytest.raises(DBAPIError, match="Cannot downgrade while entity tombstones exist"):
                migration.downgrade()
        transaction.rollback()
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == original_revision


def test_business_function_move_requires_destination_scope(env):
    item = env.create("business-functions")
    with Session(env.engine) as db:
        other_site = Site(customer_id=env.customer.id, name="Restricted site")
        db.add(other_site); db.commit(); other_id = other_site.id
    env.current[0] = principal("business_functions.manage", customer_id=env.customer.id, site_id=env.site.id)
    assert env.client.patch(f"/api/business-functions/{item['id']}", json={"site_id": str(other_id)}).status_code == 403
