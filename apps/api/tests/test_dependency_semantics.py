from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.authorization import get_principal
from app.database import get_db
from app.main import app
from app.models import (
    Base,
    DependencyGroup,
    DependencyGroupMembership,
    ServiceAssetDependency,
    ServiceDependency,
)
from app.routes.services import _asset_dependency_response, _validated_group_members
from app.schemas import DependencyGroupCreate, DependencyGroupUpdate, OperationalGraphEdge
from app.services.operational_graph import GraphProjectionRequest
from tests.test_operational_graph import (
    NOW,
    asset,
    builder,
    principal,
    reference_records,
    service,
)


def test_dependency_group_schema_is_small_explicit_and_requires_members():
    member_id = uuid.uuid4()
    payload = DependencyGroupCreate.model_validate({
        "name": " DNS providers ",
        "strategy": "any",
        "requirement": "required",
        "failure_effect": "unavailable",
        "asset_dependency_ids": [str(member_id)],
    })
    assert payload.name == "DNS providers"
    assert payload.strategy == "any"
    with pytest.raises(ValidationError):
        DependencyGroupCreate.model_validate({"name": "Empty"})
    with pytest.raises(ValidationError):
        DependencyGroupCreate.model_validate({
            "name": "Quorum", "strategy": "minimum", "asset_dependency_ids": [member_id]
        })
    with pytest.raises(ValidationError):
        DependencyGroupCreate.model_validate({
            "name": "Invented certainty", "failure_effect": "failed", "asset_dependency_ids": [member_id]
        })
    with pytest.raises(ValidationError):
        DependencyGroupUpdate.model_validate({})
    with pytest.raises(ValidationError):
        DependencyGroupUpdate.model_validate({"strategy": None})


def test_persistence_constraints_keep_groups_scoped_temporal_and_members_typed():
    groups = Base.metadata.tables["dependency_groups"]
    memberships = Base.metadata.tables["dependency_group_memberships"]
    group_checks = " ".join(
        str(constraint.sqltext)
        for constraint in groups.constraints
        if hasattr(constraint, "sqltext")
    )
    membership_checks = " ".join(
        str(constraint.sqltext)
        for constraint in memberships.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "strategy IN ('all', 'any')" in group_checks
    assert "requirement IN ('required', 'optional')" in group_checks
    assert "failure_effect IN ('unavailable', 'degraded', 'unknown')" in group_checks
    assert "service_asset_dependency_id IS NOT NULL" in membership_checks
    assert groups.c.valid_to.nullable
    assert memberships.c.valid_to.nullable
    assert memberships.c.service_asset_dependency_id.foreign_keys
    assert memberships.c.service_dependency_id.foreign_keys


def test_ungrouped_dependencies_preserve_required_flag_and_explicit_unknown():
    required = OperationalGraphEdge(
        key=f"service_asset:{uuid.uuid4()}",
        edge_family="service_asset",
        edge_id=uuid.uuid4(),
        source_key=f"service:{uuid.uuid4()}",
        target_key=f"asset:{uuid.uuid4()}",
        label="Runs on",
        required_for_operation=True,
        dependency_requirement="required",
        failure_effect="unknown",
    )
    optional = required.model_copy(update={
        "required_for_operation": False,
        "dependency_requirement": "optional",
    })
    assert required.dependency_requirement == "required"
    assert required.failure_effect == "unknown"
    assert optional.dependency_requirement == "optional"
    assert optional.failure_effect == "unknown"


class DependencyResponseDatabase:
    def __init__(self, membership, *records):
        self.membership = membership
        self.records = {(type(record), record.id): record for record in records}

    def get(self, model, record_id):
        return self.records.get((model, record_id))

    def scalar(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        return self.membership if entity is DependencyGroupMembership else None


def test_dependency_response_adds_group_semantics_without_removing_legacy_flag():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, _, _, runs_on, _ = reference_records()
    subject = service("DNS", customer_id, service_type, criticality, site_id=site_id)
    host = asset("AdGuard", customer_id, site_id)
    dependency = ServiceAssetDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=subject.id, asset_id=host.id, relationship_type_id=runs_on.id,
        required_for_operation=False, source="manual",
        valid_from=NOW, valid_to=None, created_at=NOW, updated_at=NOW,
    )
    group = DependencyGroup(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=subject.id, name="Optional monitoring", strategy="all",
        requirement="optional", failure_effect="degraded",
        valid_from=NOW, valid_to=None,
    )
    membership = DependencyGroupMembership(
        id=uuid.uuid4(), dependency_group_id=group.id,
        service_asset_dependency_id=dependency.id,
        valid_from=NOW, valid_to=None,
    )
    db = DependencyResponseDatabase(
        membership, subject, host, runs_on, group, dependency,
    )
    response = _asset_dependency_response(db, dependency)
    assert response["required_for_operation"] is False
    assert response["dependency_group_id"] == group.id
    assert response["dependency_strategy"] == "all"
    assert response["dependency_requirement"] == "optional"
    assert response["failure_effect"] == "degraded"


def test_operational_graph_projects_all_any_and_mixed_group_membership():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    subject = service("DNS", customer_id, service_type, criticality, site_id=site_id)
    upstream = service("Resolver", customer_id, service_type, criticality, site_id=site_id)
    host = asset("AdGuard", customer_id, site_id)
    asset_dependency = ServiceAssetDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=subject.id, asset_id=host.id, relationship_type_id=runs_on.id,
        required_for_operation=True, source="manual",
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    service_dependency = ServiceDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        source_service_id=subject.id, target_service_id=upstream.id,
        relationship_type_id=depends_on.id, required_for_operation=True,
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    group = DependencyGroup(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=subject.id, name="Resolvers", strategy="any",
        requirement="required", failure_effect="unavailable",
        valid_from=NOW - timedelta(hours=1), valid_to=None,
    )
    memberships = [
        DependencyGroupMembership(
            id=uuid.uuid4(), dependency_group_id=group.id,
            service_asset_dependency_id=asset_dependency.id,
            valid_from=NOW - timedelta(hours=1), valid_to=None,
        ),
        DependencyGroupMembership(
            id=uuid.uuid4(), dependency_group_id=group.id,
            service_dependency_id=service_dependency.id,
            valid_from=NOW - timedelta(hours=1), valid_to=None,
        ),
    ]
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        subject, upstream, host, asset_dependency, service_dependency, group, *memberships,
    )
    graph = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=subject.id,
        edge_families=frozenset({"service_asset", "service_service"}),
    ))
    assert len(graph.edges) == 2
    for edge in graph.edges:
        assert edge.dependency_group_id == group.id
        assert edge.dependency_group_name == "Resolvers"
        assert edge.dependency_strategy == "any"
        assert edge.dependency_requirement == "required"
        assert edge.failure_effect == "unavailable"


def test_ended_membership_is_not_projected_and_ungrouped_effect_is_unknown():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    subject = service("Monitoring", customer_id, service_type, criticality, site_id=site_id)
    host = asset("Grafana", customer_id, site_id)
    dependency = ServiceAssetDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=subject.id, asset_id=host.id, relationship_type_id=runs_on.id,
        required_for_operation=False, source="manual",
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    group = DependencyGroup(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=subject.id, name="Observability", strategy="all",
        requirement="optional", failure_effect="degraded",
        valid_from=NOW - timedelta(days=1), valid_to=NOW - timedelta(hours=1),
    )
    membership = DependencyGroupMembership(
        id=uuid.uuid4(), dependency_group_id=group.id,
        service_asset_dependency_id=dependency.id,
        valid_from=NOW - timedelta(days=1), valid_to=NOW - timedelta(hours=1),
    )
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        subject, host, dependency, group, membership,
    )
    edge = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=subject.id,
        edge_families=frozenset({"service_asset"}),
    )).edges[0]
    assert edge.dependency_group_id is None
    assert edge.dependency_requirement == "optional"
    assert edge.failure_effect == "unknown"


def test_operational_graph_omits_mismatched_group_metadata():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    subject = service("DNS", customer_id, service_type, criticality, site_id=site_id)
    host = asset("AdGuard", customer_id, site_id)
    dependency = ServiceAssetDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=subject.id, asset_id=host.id, relationship_type_id=runs_on.id,
        required_for_operation=True, source="manual",
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    mismatched_group = DependencyGroup(
        id=uuid.uuid4(), customer_id=uuid.uuid4(), site_id=site_id,
        service_id=subject.id, name="Hidden tenant semantics", strategy="any",
        requirement="optional", failure_effect="degraded",
        valid_from=NOW - timedelta(hours=1), valid_to=None,
    )
    membership = DependencyGroupMembership(
        id=uuid.uuid4(), dependency_group_id=mismatched_group.id,
        service_asset_dependency_id=dependency.id,
        valid_from=NOW - timedelta(hours=1), valid_to=None,
    )
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        subject, host, dependency, mismatched_group, membership,
    )
    edge = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=subject.id,
        edge_families=frozenset({"service_asset"}),
    )).edges[0]
    assert edge.dependency_group_id is None
    assert edge.dependency_group_name is None
    assert edge.dependency_requirement == "required"
    assert edge.failure_effect == "unknown"


class MembershipValidationDatabase:
    def __init__(self, *records):
        self.records = {(type(record), record.id): record for record in records}

    def get(self, model, record_id):
        return self.records.get((model, record_id))

    def scalars(self, statement):
        return []


def test_membership_rejects_dependency_owned_by_another_service_without_disclosure():
    customer_id = uuid.uuid4()
    service_type, criticality, _, depends_on, _, _ = reference_records()
    subject = service("Subject", customer_id, service_type, criticality)
    other = service("Other", customer_id, service_type, criticality)
    target = service("Target", customer_id, service_type, criticality)
    dependency = ServiceDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=None,
        source_service_id=other.id, target_service_id=target.id,
        relationship_type_id=depends_on.id, required_for_operation=True,
        valid_from=NOW, valid_to=None,
    )
    db = MembershipValidationDatabase(subject, other, target, dependency)
    with pytest.raises(Exception) as error:
        _validated_group_members(
            db,
            principal("service_dependencies.manage"),
            subject,
            [],
            [dependency.id],
        )
    assert getattr(error.value, "status_code", None) == 404
    assert str(dependency.id) not in str(getattr(error.value, "detail", ""))


@pytest.mark.parametrize("scope_mismatch", ["customer", "site"])
def test_membership_rejects_cross_scope_dependency(scope_mismatch):
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, _, depends_on, _, _ = reference_records()
    subject = service("Subject", customer_id, service_type, criticality, site_id=site_id)
    target = service("Target", customer_id, service_type, criticality, site_id=site_id)
    dependency = ServiceDependency(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4() if scope_mismatch == "customer" else customer_id,
        site_id=uuid.uuid4() if scope_mismatch == "site" else site_id,
        source_service_id=subject.id,
        target_service_id=target.id,
        relationship_type_id=depends_on.id,
        required_for_operation=True,
        valid_from=NOW,
        valid_to=None,
    )
    db = MembershipValidationDatabase(subject, target, dependency)
    with pytest.raises(Exception) as error:
        _validated_group_members(
            db,
            principal("service_dependencies.manage"),
            subject,
            [],
            [dependency.id],
        )
    assert getattr(error.value, "status_code", None) == 404


def test_routes_are_additive_and_reuse_existing_dependency_permissions():
    expected = {
        "/api/services/{service_id}/dependency-groups": {"GET", "POST"},
        "/api/dependency-groups/{group_id}": {"PATCH", "DELETE"},
    }
    for path, methods in expected.items():
        matches = [route.methods for route in app.routes if getattr(route, "path", None) == path]
        assert matches, path
        assert methods.issubset(set().union(*matches))


def test_group_routes_enforce_view_manage_and_non_disclosing_service_scope():
    customer_a, customer_b = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, _, _, _, _ = reference_records()
    visible = service("Visible", customer_a, service_type, criticality)
    hidden = service("Hidden", customer_b, service_type, criticality)
    hidden_group = DependencyGroup(
        id=uuid.uuid4(), customer_id=customer_b, site_id=None,
        service_id=hidden.id, name="Private providers", strategy="any",
        requirement="required", failure_effect="unknown",
        valid_from=NOW, valid_to=None, created_at=NOW, updated_at=NOW,
    )
    db = MembershipValidationDatabase(visible, hidden, hidden_group)
    scoped_viewer = principal(
        "services.view", "service_dependencies.view", customer_id=customer_a
    )
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: scoped_viewer
    try:
        with TestClient(app) as client:
            assert client.get(f"/api/services/{visible.id}/dependency-groups").json() == []
            hidden_response = client.get(f"/api/services/{hidden.id}/dependency-groups")
            assert hidden_response.status_code == 404
            assert "Hidden" not in hidden_response.text
            write_response = client.post(
                f"/api/services/{visible.id}/dependency-groups",
                json={
                    "name": "Denied",
                    "asset_dependency_ids": [str(uuid.uuid4())],
                },
            )
            assert write_response.status_code == 403
            app.dependency_overrides[get_principal] = lambda: principal(
                "service_dependencies.manage", customer_id=customer_a
            )
            substituted = client.patch(
                f"/api/dependency-groups/{hidden_group.id}",
                json={"failure_effect": "degraded"},
            )
            assert substituted.status_code == 404
            assert "Private providers" not in substituted.text
    finally:
        app.dependency_overrides.clear()


def test_migration_is_additive_and_does_not_rewrite_existing_dependencies():
    migration = Path(__file__).parents[1] / "migrations/versions/20260908_0014_lean_dependency_semantics.py"
    source = migration.read_text()
    assert 'down_revision: str | None = "20260720_0013"' in source
    assert '"dependency_groups"' in source
    assert '"dependency_group_memberships"' in source
    assert "op.add_column(\"service_dependencies\"" not in source
    assert "op.add_column(\"service_asset_dependencies\"" not in source
    assert "UPDATE SERVICE_" not in source.upper()
    assert "DELETE FROM SERVICE_" not in source.upper()
