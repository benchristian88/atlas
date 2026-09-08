from datetime import timedelta
import uuid

import pytest
from fastapi.testclient import TestClient

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import get_db
from app.main import app
from app.models import AssetRelationship, DependencyGroup, DependencyGroupMembership, ServiceAssetDependency, ServiceBusinessFunction, ServiceDependency
from app.schemas_dependency_analysis import DependencyAnalysisRequest
from app.services.dependency_analysis import DependencyAnalysisEngine, evaluate_set
from app.services.operational_graph import GraphFocusNotFound, OperationalGraphBuilder
from tests.test_operational_graph import NOW, GraphDatabase, asset, service, function, principal, reference_records

PERMISSIONS = ("assets.view", "services.view", "service_dependencies.view", "relationships.view", "business_functions.view")


class Topology:
    def __init__(self):
        self.customer, self.site = uuid.uuid4(), uuid.uuid4()
        self.refs = reference_records()
        self.records = list(self.refs)
        self.focus = self.asset("AdGuard")

    def asset(self, name):
        item = asset(name, self.customer, self.site)
        self.records.append(item)
        return item

    def service(self, name):
        item = service(name, self.customer, *self.refs[:2], site_id=self.site)
        self.records.append(item)
        return item

    def dependency(self, subject, target, *, strategy="all", effect="unavailable", requirement="required", group=None):
        is_asset = hasattr(target, "asset_type")
        model = ServiceAssetDependency if is_asset else ServiceDependency
        endpoints = dict(service_id=subject.id, asset_id=target.id) if is_asset else dict(source_service_id=subject.id, target_service_id=target.id)
        edge = model(id=uuid.uuid4(), customer_id=subject.customer_id, site_id=subject.site_id,
            relationship_type_id=self.refs[3].id, required_for_operation=requirement == "required",
            valid_from=NOW - timedelta(days=1), valid_to=None, **endpoints)
        self.records.append(edge)
        if strategy is not None:
            if group is None:
                group = DependencyGroup(id=uuid.uuid4(), customer_id=subject.customer_id, site_id=subject.site_id,
                    service_id=subject.id, name="Core Operation", strategy=strategy,
                    requirement=requirement, failure_effect=effect, valid_from=NOW - timedelta(days=1), valid_to=None)
                self.records.append(group)
            self.records.append(DependencyGroupMembership(id=uuid.uuid4(), dependency_group_id=group.id,
                service_asset_dependency_id=edge.id if is_asset else None,
                service_dependency_id=None if is_asset else edge.id,
                valid_from=NOW - timedelta(days=1), valid_to=None))
        return edge, group

    def analyze(self, *, focus=None, viewer=None, context=None, **limits):
        focus = focus or self.focus
        db = GraphDatabase(*self.records)
        engine = DependencyAnalysisEngine(OperationalGraphBuilder(db, viewer or principal(*PERMISSIONS), clock=lambda: NOW))
        result = engine.analyze(DependencyAnalysisRequest(focus_type="asset" if hasattr(focus, "asset_type") else "service", focus_id=focus.id, **limits), context or ActiveContext(None, None))
        return result


def by_name(result):
    return {row.service.name: row for row in result.results}


def assert_paths(result):
    for row in result.results:
        assert row.paths
        for path in row.paths:
            assert path.nodes[0].key == result.focus_key
            assert path.nodes[-1].key == row.service.key
            assert len(path.nodes) == len(path.edges) + 1
            assert len({node.key for node in path.nodes}) == len(path.nodes)
            for index, edge in enumerate(path.edges):
                assert edge.target_key == path.nodes[index].key
                assert edge.source_key == path.nodes[index + 1].key


@pytest.mark.parametrize("effect", ["unavailable", "degraded", "unknown"])
@pytest.mark.parametrize("requirement", ["required", "optional"])
def test_asset_direct_effect_is_explicit_not_required_flag(effect, requirement):
    t = Topology()
    dns = t.service("DNS")
    t.dependency(dns, t.focus, effect=effect, requirement=requirement)
    result = t.analyze()
    row = by_name(result)["DNS"]
    assert row.state == effect
    assert row.classification == "direct" and row.distance == 1
    assert row.reasons[0].dependency_requirement == requirement
    assert row.reasons[0].satisfaction == "unsatisfied"
    assert result.analysis_time == NOW
    assert_paths(result)


def test_service_focus_multihop_and_no_mutation():
    t = Topology()
    dns, proxy = t.service("DNS"), t.service("Proxy")
    t.dependency(dns, t.focus)
    t.dependency(proxy, dns)
    before = [dict(record.__dict__) for record in t.records]
    result = t.analyze()
    assert by_name(result)["DNS"].state == "unavailable"
    assert by_name(result)["Proxy"].classification == "downstream"
    assert by_name(result)["Proxy"].distance == 2
    direct = t.analyze(focus=dns)
    assert list(by_name(direct)) == ["Proxy"]
    assert direct.results[0].classification == "direct"
    assert before == [dict(record.__dict__) for record in t.records]
    assert_paths(result)


@pytest.mark.parametrize("required", ["required", "optional"])
def test_ungrouped_unknown_and_downstream_uncertainty(required):
    t = Topology()
    dns, proxy = t.service("DNS"), t.service("Proxy")
    t.dependency(dns, t.focus, strategy=None, requirement=required)
    t.dependency(proxy, dns)
    rows = by_name(t.analyze())
    assert rows["DNS"].state == rows["Proxy"].state == "unknown"
    assert rows["DNS"].reasons[0].code == "ungrouped_consequence_unknown"
    assert rows["DNS"].reasons[0].dependency_strategy is None
    assert rows["Proxy"].reasons[0].code == "member_state_unresolved"


@pytest.mark.parametrize("strategy,expected", [("all", "unavailable"), ("any", "unaffected")])
def test_complete_group_includes_alternative_outside_incoming_path(strategy, expected):
    t = Topology()
    dns, alternate = t.service("DNS"), t.asset("Alternate")
    _, group = t.dependency(dns, t.focus, strategy=strategy)
    t.dependency(dns, alternate, group=group)
    row = t.analyze().results[0]
    assert row.state == expected
    assert len(row.reasons[0].members) == 2
    assert sorted(member.state for member in row.reasons[0].members) == ["unaffected", "unavailable"]


def test_any_all_members_unavailable_via_diamond():
    t = Topology()
    left, right, consumer = [t.service(name) for name in ("Left", "Right", "Consumer")]
    t.dependency(left, t.focus)
    t.dependency(right, t.focus)
    _, group = t.dependency(consumer, left, strategy="any")
    t.dependency(consumer, right, group=group)
    result = t.analyze()
    row = by_name(result)["Consumer"]
    assert row.state == "unavailable" and row.distance == 2
    assert len(row.paths) == 2
    assert all(member.state == "unavailable" for member in row.reasons[0].members)
    assert_paths(result)


@pytest.mark.parametrize("effects,expected", [
    (["degraded", "unknown"], "unknown"),
    (["degraded", "unavailable"], "unavailable"),
    (["unknown", "unavailable"], "unavailable"),
    (["degraded", "degraded"], "degraded"),
])
def test_independent_groups_conservative_aggregation(effects, expected):
    t = Topology()
    left, right, consumer = [t.service(name) for name in ("Left", "Right", "Consumer")]
    t.dependency(left, t.focus)
    t.dependency(right, t.focus)
    t.dependency(consumer, left, effect=effects[0])
    t.dependency(consumer, right, effect=effects[1])
    row = by_name(t.analyze())["Consumer"]
    assert row.state == expected
    assert len(row.reasons) == 2


def test_degraded_is_not_unavailable_and_any_can_shield_uncertainty():
    t = Topology()
    dns, proxy, shield = [t.service(name) for name in ("DNS", "Proxy", "Shield")]
    t.dependency(dns, t.focus, effect="degraded")
    t.dependency(proxy, dns)
    _, group = t.dependency(shield, dns, strategy="any")
    t.dependency(shield, t.asset("Alternate"), group=group)
    rows = by_name(t.analyze())
    assert rows["DNS"].state == "degraded"
    assert rows["Proxy"].state == "unknown"
    assert rows["Shield"].state == "unaffected"


def test_cycles_terminate_and_keep_explanation_edges_deterministically():
    t = Topology()
    a, b = t.service("A"), t.service("B")
    t.dependency(a, t.focus, effect="degraded")
    t.dependency(b, a)
    back, _ = t.dependency(a, b)
    first = t.analyze()
    assert all(row.state == "unknown" for row in first.results)
    assert any(member.edge.edge_id == back.id for reason in by_name(first)["A"].reasons for member in reason.members)
    t.records.reverse()
    assert first == t.analyze()
    assert_paths(first)


def test_any_cycle_has_least_scenario_consequence_not_self_invented_outage():
    t = Topology()
    a, b = t.service("A"), t.service("B")
    _, group = t.dependency(a, t.focus, strategy="any")
    t.dependency(a, b, group=group)
    t.dependency(b, a)
    rows = by_name(t.analyze())
    assert list(rows) == ["A"] and rows["A"].state == "unaffected"


@pytest.mark.parametrize("ended", ["dependency", "membership", "group", "future_dependency", "future_membership"])
def test_current_time_temporal_filtering(ended):
    t = Topology()
    dns = t.service("DNS")
    edge, group = t.dependency(dns, t.focus)
    item = edge if "dependency" in ended else group if ended == "group" else t.records[-1]
    if ended.startswith("future"):
        item.valid_from = NOW + timedelta(seconds=1)
    else:
        item.valid_to = NOW
    result = t.analyze()
    if "dependency" in ended:
        assert result.results == []
    else:
        assert result.results[0].state == "unknown"
        assert result.results[0].reasons[0].dependency_group_id is None


def test_structural_assets_and_business_functions_do_not_propagate():
    t = Topology()
    host, dns = t.asset("PVE1"), t.service("DNS")
    bf = function("Business", t.customer, t.refs[1], site_id=t.site)
    t.records.extend([bf, AssetRelationship(id=uuid.uuid4(), source_asset_id=t.focus.id,
        target_asset_id=host.id, relationship_type="runs_on"),
        ServiceBusinessFunction(id=uuid.uuid4(), customer_id=t.customer, site_id=t.site,
            service_id=dns.id, business_function_id=bf.id, valid_from=NOW, valid_to=None)])
    t.dependency(dns, t.focus)
    assert t.analyze(focus=host).results == []
    result = t.analyze()
    assert list(by_name(result)) == ["DNS"]
    assert "business_function:" not in result.model_dump_json()


@pytest.mark.parametrize("hidden", ["focus", "intermediary", "downstream"])
def test_site_authorization_and_non_disclosure(hidden):
    t = Topology()
    dns, proxy = t.service("DNS"), t.service("Proxy")
    target = {"focus": t.focus, "intermediary": dns, "downstream": proxy}[hidden]
    target.site_id = uuid.uuid4()
    t.dependency(dns, t.focus)
    t.dependency(proxy, dns)
    viewer = principal(*PERMISSIONS, customer_id=t.customer, site_id=t.site)
    if hidden == "focus":
        with pytest.raises(GraphFocusNotFound):
            t.analyze(viewer=viewer)
    else:
        result = t.analyze(viewer=viewer)
        assert str(target.id) not in result.model_dump_json()
        assert target.name not in result.model_dump_json()
        assert list(by_name(result)) == ([] if hidden == "intermediary" else ["DNS"])


def test_global_caller_cannot_cross_customer_and_context_narrows_sites():
    t = Topology()
    dns, hidden = t.service("DNS"), t.service("Hidden")
    hidden.customer_id = uuid.uuid4()
    t.dependency(dns, t.focus)
    t.dependency(hidden, dns)
    assert list(by_name(t.analyze())) == ["DNS"]
    dns.site_id = uuid.uuid4()
    assert t.analyze(context=ActiveContext(t.customer, t.site)).results == []
    with pytest.raises(GraphFocusNotFound):
        t.analyze(viewer=principal(*PERMISSIONS, customer_id=uuid.uuid4()))


def test_hidden_group_member_does_not_disclose_ids_names_or_counts():
    t = Topology()
    dns, hidden = t.service("DNS"), t.asset("Hidden Alternate")
    hidden.site_id = uuid.uuid4()
    _, group = t.dependency(dns, t.focus, strategy="any")
    edge, _ = t.dependency(dns, hidden, group=group)
    result = t.analyze(viewer=principal(*PERMISSIONS, customer_id=t.customer, site_id=t.site))
    assert str(hidden.id) not in result.model_dump_json()
    assert str(edge.id) not in result.model_dump_json()
    assert hidden.name not in result.model_dump_json()
    assert not result.truncated
    assert result.results[0].state == "unknown"
    assert result.results[0].reasons[0].code == "dependency_set_unresolved"


@pytest.mark.parametrize("permissions", [("assets.view",), ("assets.view", "services.view")])
def test_mixed_permissions_exclude_inaccessible_dependencies(permissions):
    t = Topology()
    t.dependency(t.service("DNS"), t.focus)
    assert t.analyze(viewer=principal(*permissions)).results == []


def test_bounds_keep_complete_paths_even_when_intermediate_result_omitted():
    t = Topology()
    a, b, c = [t.service(name) for name in ("A", "B", "C")]
    t.dependency(a, t.focus)
    t.dependency(b, a)
    t.dependency(c, b)
    for limits in ({"max_depth": 1}, {"max_results": 1}):
        result = t.analyze(**limits)
        assert result.truncated and result.warnings and len(result.results) == 1
        assert_paths(result)


def test_path_limit_and_graph_limit_are_safe(monkeypatch):
    t = Topology()
    a, b, c = [t.service(name) for name in ("A", "B", "C")]
    t.dependency(a, t.focus)
    t.dependency(b, t.focus)
    t.dependency(c, a)
    t.dependency(c, b)
    result = t.analyze(max_paths_per_result=1)
    assert result.truncated
    assert_paths(result)
    monkeypatch.setattr("app.services.dependency_analysis.GRAPH_NODES", 2)
    result = t.analyze()
    assert result.truncated and result.results == []
    assert "sets may be incomplete" in result.warnings[0]


def test_graph_depth_safety_limit_detects_incomplete_closure(monkeypatch):
    t = Topology()
    a, b = t.service("A"), t.service("B")
    t.dependency(a, t.focus)
    t.dependency(b, a)
    monkeypatch.setattr("app.services.dependency_analysis.GRAPH_DEPTH", 1)
    result = t.analyze()
    assert result.truncated and not result.results


def test_all_satisfied_without_scenario_member():
    t = Topology()
    t.dependency(t.service("Unrelated"), t.asset("Unrelated provider"))
    assert t.analyze().results == []
    from app.schemas import OperationalGraphEdge
    edge = OperationalGraphEdge(key="edge", edge_id=uuid.uuid4(), edge_family="service_asset",
        source_key="service", target_key="asset", label="Depends on", dependency_strategy="all", failure_effect="unavailable")
    assert evaluate_set([edge], {}) == ("satisfied", "unaffected")


def test_endpoint_viewer_read_only_validation_and_non_disclosing_substitution():
    t = Topology()
    t.dependency(t.service("DNS"), t.focus)
    app.dependency_overrides[get_db] = lambda: GraphDatabase(*t.records)
    app.dependency_overrides[get_principal] = lambda: principal(*PERMISSIONS)
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(None, None)
    try:
        with TestClient(app) as client:
            payload = {"focus_type": "asset", "focus_id": str(t.focus.id), "state": "unavailable"}
            response = client.post("/api/dependency-analysis", json=payload)
            assert response.status_code == 200, response.text
            assert response.json()["results"][0]["state"] == "unavailable"
            assert response.json()["engine_version"] == "c2.3-v1"
            for override in ({"state": "degraded"}, {"focus_type": "business_function"}, {"max_depth": 21}, {"max_results": 0}, {"max_paths_per_result": 21}, {"as_of": "2026-01-01"}):
                assert client.post("/api/dependency-analysis", json={**payload, **override}).status_code == 422
            missing = client.post("/api/dependency-analysis", json={**payload, "focus_id": str(uuid.uuid4())})
            app.dependency_overrides[get_principal] = lambda: principal(*PERMISSIONS, customer_id=uuid.uuid4())
            hidden = client.post("/api/dependency-analysis", json=payload)
            assert missing.status_code == hidden.status_code == 404
            assert missing.json() == hidden.json() == {"detail": "Record not found"}
    finally:
        app.dependency_overrides.clear()


def test_later_unavailability_resolves_temporary_unknown_to_explicit_degraded():
    t = Topology()
    early, middle, late, consumer = [t.service(name) for name in ("Early", "Middle", "Late", "Consumer")]
    t.dependency(early, t.focus, effect="unknown")
    t.dependency(middle, t.focus)
    t.dependency(late, middle)
    _, group = t.dependency(consumer, early, effect="degraded")
    t.dependency(consumer, late, group=group)
    rows = by_name(t.analyze())
    assert rows["Early"].state == "unknown"
    assert rows["Late"].state == "unavailable"
    assert rows["Consumer"].state == "degraded"


def test_all_unsatisfied_unavailable_dominates_unknown_member():
    t = Topology()
    uncertain, consumer = t.service("Uncertain"), t.service("Consumer")
    t.dependency(uncertain, t.focus, effect="unknown")
    _, group = t.dependency(consumer, uncertain)
    t.dependency(consumer, t.focus, group=group)
    assert by_name(t.analyze())["Consumer"].state == "unavailable"


def test_satisfied_direct_set_does_not_shortcut_downstream_consequence():
    t = Topology()
    dns, proxy = t.service("DNS"), t.service("Proxy")
    t.dependency(dns, t.focus)
    _, group = t.dependency(proxy, t.focus, strategy="any")
    t.dependency(proxy, t.asset("Alternate"), group=group)
    t.dependency(proxy, dns)
    row = by_name(t.analyze())["Proxy"]
    assert row.state == "unavailable" and row.classification == "downstream"
    assert row.distance == 2
    assert {reason.consequence for reason in row.reasons} == {"unaffected", "unavailable"}


def test_completion_edge_safety_limit_and_hidden_edges_do_not_trigger_it(monkeypatch):
    t = Topology()
    dns, alternate = t.service("DNS"), t.asset("Alternate")
    _, group = t.dependency(dns, t.focus, strategy="any")
    t.dependency(dns, alternate, group=group)
    monkeypatch.setattr("app.services.dependency_analysis.GRAPH_EDGES", 1)
    assert t.analyze().truncated
    alternate.site_id = uuid.uuid4()
    result = t.analyze(viewer=principal(*PERMISSIONS, customer_id=t.customer, site_id=t.site))
    assert not result.truncated


@pytest.mark.parametrize("strategy,expected", [("all", "unavailable"), ("any", "unknown")])
def test_partial_groups_preserve_only_defensible_conclusions(strategy, expected):
    t = Topology()
    dns, proxy, hidden = t.service("DNS"), t.service("Proxy"), t.asset("Private provider")
    hidden.site_id = uuid.uuid4()
    _, group = t.dependency(dns, t.focus, strategy=strategy)
    t.dependency(dns, hidden, group=group)
    t.dependency(proxy, dns)
    result = t.analyze(context=ActiveContext(t.customer, t.site))
    rows = by_name(result)
    assert rows["DNS"].state == rows["Proxy"].state == expected
    assert "incomplete_group_keys" not in result.model_dump_json()
    assert str(hidden.id) not in result.model_dump_json()
    assert_paths(result)
