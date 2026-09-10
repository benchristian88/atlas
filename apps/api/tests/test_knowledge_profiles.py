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

from app.models import KnowledgeRequirementDefinition as Requirement
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
