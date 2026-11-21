"""Detail relationship reads must authorize endpoints before serialization."""
import uuid

import pytest
from fastapi import HTTPException

from app.models import Asset, BusinessFunction, Service, ServiceAssetDependency, ServiceBusinessFunction, ServiceDependency
from app.routes import business_functions, services
from tests.test_operational_graph import GraphDatabase, principal


@pytest.mark.parametrize("kind", ["service", "business_function"])
def test_inaccessible_detail_focus_is_not_found(kind):
    record = (Service if kind == "service" else BusinessFunction)(id=uuid.uuid4(), customer_id=uuid.uuid4(), site_id=uuid.uuid4())
    viewer = principal("services.view", "business_functions.view", customer_id=uuid.uuid4())
    lookup = services._service if kind == "service" else business_functions._function
    with pytest.raises(HTTPException) as error:
        lookup(GraphDatabase(record), viewer, record.id, "services.view" if kind == "service" else "business_functions.view")
    assert error.value.status_code == 404


def test_partially_visible_groups_do_not_expose_member_ids(monkeypatch):
    from app.models import DependencyGroup
    focus = Service(id=uuid.uuid4(), customer_id=uuid.uuid4(), site_id=None)
    group = DependencyGroup(id=uuid.uuid4(), customer_id=focus.customer_id, service_id=focus.id)
    visible, hidden = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(services, "_dependency_group_response", lambda db, row: {"asset_dependency_ids": [visible, hidden], "service_dependency_ids": []})
    monkeypatch.setattr(services, "list_service_asset_dependencies", lambda *args: [{"id": visible}])
    monkeypatch.setattr(services, "list_service_dependencies", lambda *args: [])
    assert services.list_dependency_groups(focus.id, principal("service_dependencies.view"), False, GraphDatabase(focus, group)) == []


@pytest.mark.parametrize("can_read_gaps", [False, True])
def test_function_summary_counts_only_authorized_services_and_gaps(can_read_gaps):
    from tests.test_operational_graph import NOW
    customer, site = uuid.uuid4(), uuid.uuid4()
    visible = Service(id=uuid.uuid4(), customer_id=customer, site_id=site)
    hidden = Service(id=uuid.uuid4(), customer_id=customer, site_id=uuid.uuid4())
    function = BusinessFunction(id=uuid.uuid4(), customer_id=customer, site_id=site, name="Purpose", active=True, created_at=NOW, updated_at=NOW)

    class SummaryDatabase(GraphDatabase):
        gap_queries = 0

        def scalars(self, statement):
            if statement.column_descriptions[0]["name"] == "service_id":
                return [visible.id]
            return super().scalars(statement)

        def scalar(self, statement):
            self.gap_queries += 1
            params = statement.compile().params
            # The gap aggregate must not include the inaccessible Service ID.
            assert any(isinstance(value, (set, list)) and set(value) == {visible.id} for value in params.values())
            return 2

    viewer = principal("business_functions.view", "services.view", *(["knowledge_gaps.view"] if can_read_gaps else []), customer_id=customer, site_id=site)
    db = SummaryDatabase(function, visible, hidden)
    response = business_functions.function_response(db, function, viewer)
    assert response["service_count"] == 1
    assert response["open_gap_count"] == (2 if can_read_gaps else 0)
    assert db.gap_queries == int(can_read_gaps)


@pytest.mark.parametrize("scope", ["global", "site", "no_relationship_permissions"])
def test_service_summary_executes_scoped_relationship_counts(scope):
    """Execute the actual aggregate SQL against minimal in-memory relation tables."""
    from sqlalchemy import Column, MetaData, Table, create_engine
    from tests.test_operational_graph import NOW
    from tests.test_services import service_records

    service_type, criticality, focus = service_records()
    focus.site_id = uuid.uuid4()
    focus.created_at = focus.updated_at = NOW
    fields = {
        Asset: ["id", "customer_id", "site_id"],
        Service: ["id", "customer_id", "site_id", "deleted_at"],
        BusinessFunction: ["id", "customer_id", "site_id", "deleted_at"],
        ServiceAssetDependency: ["service_id", "asset_id", "customer_id", "site_id", "valid_to"],
        ServiceDependency: ["source_service_id", "target_service_id", "customer_id", "site_id", "valid_to"],
        ServiceBusinessFunction: ["service_id", "business_function_id", "customer_id", "site_id", "valid_to"],
    }
    metadata = MetaData()
    tables = {model: Table(model.__tablename__, metadata, *(Column(name, model.__table__.c[name].type) for name in names)) for model, names in fields.items()}
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(tables[Service].insert(), {"id": focus.id, "customer_id": focus.customer_id, "site_id": focus.site_id})
        for model in [Asset, Service, BusinessFunction]:
            for customer, site in [(focus.customer_id, focus.site_id), (focus.customer_id, uuid.uuid4()), (uuid.uuid4(), uuid.uuid4())]:
                related_id = uuid.uuid4()
                connection.execute(tables[model].insert(), {"id": related_id, "customer_id": customer, "site_id": site})
                relation = {Asset: ServiceAssetDependency, Service: ServiceDependency, BusinessFunction: ServiceBusinessFunction}[model]
                values = ({"source_service_id": focus.id, "target_service_id": related_id} if model is Service else {"service_id": focus.id, "asset_id" if model is Asset else "business_function_id": related_id})
                values.update(customer_id=focus.customer_id, site_id=focus.site_id)
                connection.execute(tables[relation].insert(), {**values, "valid_to": None})
                # Ended links never increase the current count.
                connection.execute(tables[relation].insert(), {**values, "valid_to": NOW})

        class CountDatabase(GraphDatabase):
            def scalar(self, statement):
                return connection.scalar(statement)

        permissions = ["services.view"] if scope == "no_relationship_permissions" else ["services.view", "assets.view", "business_functions.view", "service_dependencies.view"]
        viewer = principal(*permissions, **({} if scope == "global" else {"customer_id": focus.customer_id, "site_id": focus.site_id}))
        response = services.service_response(CountDatabase(service_type, criticality), focus, viewer)
        expected = {"global": 1, "site": 1, "no_relationship_permissions": 0}[scope]
        for name in ["asset_dependency_count", "service_dependency_count", "business_function_count"]:
            assert response[name] == expected
        assert response["open_gap_count"] == response["required_gap_count"] == response["recommended_gap_count"] == 0
        assert response["completeness_status"] == "not_evaluated"
    engine.dispose()
