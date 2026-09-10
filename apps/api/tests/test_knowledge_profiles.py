"""Execute profile selection and copy repair against a real SQL engine."""
import importlib
import os
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models import KnowledgeGap, KnowledgeRequirementDefinition as Requirement
from app.routes import knowledge_completeness as routes
from tests.test_operational_graph import principal


@pytest.fixture
def requirement_db():
    metadata = sa.MetaData()
    table = sa.Table(Requirement.__tablename__, metadata, *(
        sa.Column(column.name, sa.JSON() if isinstance(column.type, JSONB) else column.type,
                  primary_key=column.primary_key)
        for column in Requirement.__table__.columns
    ))
    sa.Table(KnowledgeGap.__tablename__, metadata, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("requirement_definition_id", sa.Uuid()))
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        yield connection, table
    engine.dispose()


@pytest.mark.parametrize("entity", ["asset", "service"])
def test_profile_executes_entity_and_type_scope_filter(requirement_db, monkeypatch, entity):
    connection, table = requirement_db
    type_id = uuid.uuid4()
    records = []
    for kind in ("asset", "service"):
        for scope, scope_id in (("global", None), ("this", type_id), ("other", uuid.uuid4())):
            for active in (True, False):
                records.append(dict(id=uuid.uuid4(), key=f"{kind}_{scope}_{active}", name="Same name",
                    entity_type=kind, asset_type_id=scope_id if kind == "asset" else None,
                    service_type_id=scope_id if kind == "service" else None, active=active, sort_order=len(records)))
    connection.execute(table.insert(), records)
    with Session(bind=connection) as db:
        # Type existence and serialization are independent of the selection under test.
        monkeypatch.setattr(db, "get", lambda *args: SimpleNamespace(id=type_id))
        monkeypatch.setattr(routes, "_requirement_response", lambda db, item: {
            "key": item.key, "entity_type": item.entity_type, "active": item.active,
            "asset_type_id": item.asset_type_id, "service_type_id": item.service_type_id,
        })
        route = routes.list_profile_requirements if entity == "asset" else routes.list_service_profile_requirements
        result = route(type_id, principal("knowledge_requirements.view"), db)
        assert [item["key"] for item in result] == [f"{entity}_{scope}_{active}" for scope in ("global", "this") for active in (True, False)]
        assert [item[f"{entity}_type_id"] for item in result] == [None, None, type_id, type_id]
        for viewer in (principal(), principal("knowledge_requirements.view", customer_id=uuid.uuid4()), principal("knowledge_requirements.view", customer_id=uuid.uuid4(), site_id=uuid.uuid4())):
            with pytest.raises(HTTPException) as error:
                route(type_id, viewer, db)
            assert error.value.status_code == 403


def test_description_migration_repairs_only_exact_builtin_copy(requirement_db, monkeypatch):
    connection, table = requirement_db
    migration = importlib.import_module("migrations.versions.20260910_0017_knowledge_requirement_copy")
    seed = importlib.import_module("migrations.versions.20260720_0013_homelab_service_mvp")
    assert {row[0] for row in migration.DESCRIPTIONS} == {row[0] for row in seed.SERVICE_REQUIREMENTS}
    rows = [dict(id=uuid.uuid4(), key=key, description=original, entity_type="service", system_defined=True,
                 asset_type_id=None, service_type_id=None, active=False, rule_config_json={"preserve": True})
            for key, original, _ in migration.DESCRIPTIONS]
    variants = [dict(description="Our custom C1 policy."), dict(description=None), dict(system_defined=False),
                dict(entity_type="asset"), dict(service_type_id=uuid.uuid4()), dict(asset_type_id=uuid.uuid4()),
                dict(key="administrator_requirement")]
    rows += [{**rows[0], "id": uuid.uuid4(), **variant} for variant in variants]
    connection.execute(table.insert(), rows)
    before = {row.id: dict(row._mapping) for row in connection.execute(sa.select(table))}
    monkeypatch.setattr(migration, "op", SimpleNamespace(execute=connection.execute))
    migration.upgrade()
    after = {row.id: dict(row._mapping) for row in connection.execute(sa.select(table))}
    for row, (_, original, description) in zip(rows, migration.DESCRIPTIONS):
        assert original == next(f"Default C1 Service knowledge requirement: {item[1]}." for item in seed.SERVICE_REQUIREMENTS if item[0] == row["key"])
        assert "C1" not in description
        assert after[row["id"]] == {**before[row["id"]], "description": description}
    for row in rows[len(migration.DESCRIPTIONS):]:
        assert after[row["id"]] == before[row["id"]]
    migration.upgrade()
    migration.downgrade()
    assert {row.id: dict(row._mapping) for row in connection.execute(sa.select(table))} == after


@pytest.mark.parametrize("entity", ["asset", "service"])
def test_lifecycle_preserves_identity_and_requires_global_manage(monkeypatch, entity):
    item = Requirement(id=uuid.uuid4(), key="operator_policy", name="Policy", entity_type=entity,
                       active=True, rule_type="service_field_present" if entity == "service" else "field_present",
                       rule_config_json={"field": "name"}, system_defined=True)
    calls = []
    audit = []
    db = SimpleNamespace(get=lambda *args: item)
    monkeypatch.setattr(routes, "_requirement_response", lambda db, row: row)
    monkeypatch.setattr(routes, "commit", lambda *args: None)
    monkeypatch.setattr(routes, "add_audit_event", lambda db, **kwargs: audit.append(kwargs["action"]))
    monkeypatch.setattr(routes, "evaluate_assets_for_asset_type", lambda *args, **kwargs: calls.append("asset") or 0)
    monkeypatch.setattr(routes, "evaluate_services_for_service_type", lambda *args, **kwargs: calls.append("service") or 0)
    for viewer in (principal("knowledge_requirements.view"), principal("knowledge_requirements.manage", customer_id=uuid.uuid4())):
        for action in (routes.deactivate_requirement, routes.activate_requirement):
            with pytest.raises(HTTPException) as error:
                action(item.id, None, viewer, db)
            assert error.value.status_code == 403
            assert item.active is True
    manager = principal("knowledge_requirements.manage")
    assert routes.deactivate_requirement(item.id, None, manager, db) is item
    assert item.active is False
    assert routes.activate_requirement(item.id, None, manager, db) is item
    assert item.active is True
    assert item.key == "operator_policy" and item.rule_config_json == {"field": "name"}
    assert calls == [entity, entity]
    assert audit == ["knowledge_requirement.deactivated", "knowledge_requirement.activated"]


@pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
def test_copy_migration_on_postgres_fresh_and_existing_installations():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module("migrations.versions.20260910_0017_knowledge_requirement_copy")
    table = Requirement.__table__
    engine = sa.create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            keys = [key for key, _, _ in migration.DESCRIPTIONS]
            def snapshot():
                return {row.key: dict(row._mapping) for row in connection.execute(sa.select(table).where(table.c.key.in_(keys)))}
            fresh = snapshot()
            assert len(fresh) == 16
            for key, original, description in migration.DESCRIPTIONS:
                assert fresh[key]["description"] == description
                connection.execute(table.update().where(table.c.key == key).values(description=original))
            connection.execute(table.update().where(table.c.key == "service_name").values(description="Our administrator description."))
            before = snapshot()
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            after = snapshot()
            for key, _, description in migration.DESCRIPTIONS:
                expected = before[key] if key == "service_name" else {**before[key], "description": description}
                assert after[key] == expected
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.mark.parametrize("entity", ["asset", "service"])
def test_global_management_list_is_entity_scoped_and_history_safe(requirement_db, monkeypatch, entity):
    connection, table = requirement_db
    records = []
    for kind in ("asset", "service"):
        for scope in ("global", "asset_type", "service_type"):
            for variant in ("built_in", "custom", "history"):
                records.append(dict(id=uuid.uuid4(), key=f"{kind}_{scope}_{variant}", name="Same display name",
                    entity_type=kind, asset_type_id=uuid.uuid4() if scope == "asset_type" else None,
                    service_type_id=uuid.uuid4() if scope == "service_type" else None,
                    active=variant != "custom", sort_order=len(records), system_defined=variant == "built_in"))
    connection.execute(table.insert(), records)
    gaps = table.metadata.tables[KnowledgeGap.__tablename__]
    connection.execute(gaps.insert(), [dict(id=uuid.uuid4(), requirement_definition_id=row["id"]) for row in records if row["key"].endswith("history")])
    monkeypatch.setattr(routes, "_requirement_response", lambda db, item: {"key": item.key, "entity_type": item.entity_type, "asset_type_id": item.asset_type_id, "service_type_id": item.service_type_id, "active": item.active})
    with Session(bind=connection) as db:
        manager = principal("knowledge_requirements.view", "knowledge_requirements.manage")
        rows = routes.list_global_requirements(entity, manager, db)
        assert [row["key"] for row in rows] == [f"{entity}_global_{variant}" for variant in ("built_in", "custom", "history")]
        assert [row["can_delete"] for row in rows] == [False, True, False]
        assert [row["active"] for row in rows] == [True, False, True]
        assert all(row["asset_type_id"] is None and row["service_type_id"] is None for row in rows)
        for viewer in (principal(), principal("knowledge_requirements.view"), principal("knowledge_requirements.manage"), principal("knowledge_requirements.view", "knowledge_requirements.manage", customer_id=uuid.uuid4())):
            with pytest.raises(HTTPException) as error:
                routes.list_global_requirements(entity, viewer, db)
            assert error.value.status_code == 403
        connection.execute(table.delete().where(table.c.entity_type == entity))
        assert routes.list_global_requirements(entity, manager, db) == []


@pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
@pytest.mark.parametrize("entity", ["asset", "service"])
def test_global_requirement_http_management_preserves_scope_permissions_and_history(entity):
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient
    from app.authorization import get_principal
    from app.database import get_db
    from app.main import app
    from app.models import AssetType, ServiceType, Workspace, Customer

    engine = sa.create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as db:
            actor = principal("knowledge_requirements.view", "knowledge_requirements.manage")
            actor.user.email = f"global-{uuid.uuid4()}@example.test"
            db.add(actor.user)
            workspace = Workspace(name="Global profile test", slug=f"global-{uuid.uuid4()}")
            db.add(workspace); db.flush()
            customer = Customer(workspace_id=workspace.id, name="Profile history")
            db.add(customer); db.flush()
            current = [actor]
            app.dependency_overrides[get_principal] = lambda: current[0]
            app.dependency_overrides[get_db] = lambda: db
            try:
                with TestClient(app) as client:
                    path = f"/api/knowledge-requirements?entity_type={entity}"
                    for query in ("", "?entity_type=business_function"):
                        assert client.get(f"/api/knowledge-requirements{query}").status_code == 422
                    payload = dict(key=f"global_{uuid.uuid4().hex}", name="Global test policy", description="Operator policy", entity_type=entity,
                                   rule_type="field_present" if entity == "asset" else "service_field_present", rule_config_json={"field": "name"},
                                   requirement_level="recommended", severity="low")
                    response = client.post("/api/knowledge-requirements", json=payload)
                    assert response.status_code == 201, response.text
                    item = response.json(); item_path = f"/api/knowledge-requirements/{item['id']}"
                    assert item["asset_type_id"] is None and item["service_type_id"] is None
                    rows = client.get(path).json()
                    assert all(row["entity_type"] == entity and row["asset_type_id"] is None and row["service_type_id"] is None for row in rows)
                    assert next(row for row in rows if row["id"] == item["id"])["can_delete"] is True
                    assert client.patch(item_path, json={"description": "Revised operator policy"}).status_code == 200
                    for action, active in (("deactivate", False), ("activate", True)):
                        result = client.post(f"{item_path}/{action}")
                        assert result.status_code == 200 and result.json()["active"] is active
                        assert result.json()["id"] == item["id"] and result.json()["key"] == item["key"]
                    # Duplicate uses the existing global-create contract and a new key.
                    duplicate = client.post("/api/knowledge-requirements", json={**payload, "key": f"copy_{uuid.uuid4().hex}"})
                    assert duplicate.status_code == 201
                    assert client.delete(f"/api/knowledge-requirements/{duplicate.json()['id']}").status_code == 204
                    profile_type = db.scalar(sa.select(AssetType if entity == "asset" else ServiceType).limit(1))
                    profile_path = f"/api/{entity}-types/{profile_type.id}/knowledge-requirements"
                    for reader in (principal("knowledge_requirements.view"), principal("knowledge_requirements.view", "knowledge_requirements.manage", customer_id=customer.id)):
                        current[0] = reader
                        assert client.get(path).status_code == 403
                        for method, url, data in (("POST", "/api/knowledge-requirements", payload), ("PATCH", item_path, {"description": "Unauthorized"}), ("POST", f"{item_path}/deactivate", None), ("POST", f"{item_path}/activate", None), ("DELETE", item_path, None)):
                            assert client.request(method, url, json=data).status_code == 403
                    current[0] = principal("knowledge_requirements.view")
                    inherited = client.get(profile_path)
                    assert inherited.status_code == 200 and item["id"] in [row["id"] for row in inherited.json()]
                    current[0] = actor
                    now = datetime.now(timezone.utc)
                    db.add(KnowledgeGap(customer_id=customer.id, requirement_definition_id=uuid.UUID(item["id"]), entity_type=entity, entity_id=uuid.uuid4(),
                                        status="resolved", severity="low", requirement_level="recommended", summary="Retained history", first_detected_at=now,
                                        last_evaluated_at=now, last_state_changed_at=now, resolved_at=now))
                    db.flush()
                    assert next(row for row in client.get(path).json() if row["id"] == item["id"])["can_delete"] is False
                    assert client.delete(item_path).status_code == 409
                    if entity == "service":
                        built_in = next(row for row in client.get(path).json() if row["system_defined"])
                        assert built_in["can_delete"] is False
                        assert client.delete(f"/api/knowledge-requirements/{built_in['id']}").status_code == 409
            finally:
                app.dependency_overrides.clear()
        transaction.rollback()
    engine.dispose()
