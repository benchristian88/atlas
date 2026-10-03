"""Small deterministic consequence engine over the authorized C2 graph.

Two monotone closures avoid order-dependent unknown/degraded oscillation:
first definite unavailability, then uncertainty/degradation with unavailable
nodes fixed. No operational state is read as telemetry or written back.
"""

from collections import defaultdict, deque

from app.authorization import ActiveContext
from app.schemas import OperationalGraphEdge, OperationalGraphNode, OperationalGraphResponse
from app.schemas_dependency_analysis import (
    AnalysisEntity, AnalysisMember, AnalysisPath, AnalysisReason,
    DependencyAnalysisRequest, DependencyAnalysisResponse, ServiceAnalysisResult,
)
from app.services.operational_graph import GraphProjectionRequest, OperationalGraphBuilder

DEPENDENCY_FAMILIES = frozenset({"service_asset", "service_service"})
PRECEDENCE = {"unaffected": 0, "degraded": 1, "unknown": 2, "unavailable": 3}
GRAPH_DEPTH = 20
GRAPH_NODES = 2000
GRAPH_EDGES = 5000


def entity(node: OperationalGraphNode) -> AnalysisEntity:
    return AnalysisEntity(key=node.key, entity_id=node.entity_id, name=node.name, href=node.href)


def evaluate_set(edges: list[OperationalGraphEdge], states: dict[str, str], *, incomplete=False):
    """Return satisfaction and consequence using only explicit lean semantics."""
    values = [states.get(edge.target_key, "unaffected") for edge in edges]
    strategy = edges[0].dependency_strategy
    if strategy == "any":
        satisfaction = (
            "satisfied" if "unaffected" in values else
            "unsatisfied" if all(value == "unavailable" for value in values) else "unknown"
        )
    else:
        satisfaction = (
            "unsatisfied" if "unavailable" in values else
            "unknown" if any(value != "unaffected" for value in values) else "satisfied"
        )
    if incomplete and strategy == "any" and satisfaction == "unsatisfied":
        satisfaction = "unknown"
    consequence = (
        "unaffected" if satisfaction == "satisfied" else
        "unknown" if satisfaction == "unknown" else edges[0].failure_effect or "unknown"
    )
    return satisfaction, consequence


class DependencyAnalysisEngine:
    def __init__(self, builder: OperationalGraphBuilder):
        self.builder = builder

    def analyze(self, request: DependencyAnalysisRequest, context: ActiveContext):
        # Authorize first and pin global callers to the focus customer. Capture
        # the clock once for focus, dependencies, groups and memberships.
        analysis_time = self.builder.clock()
        builder = OperationalGraphBuilder(
            self.builder.db, self.builder.principal, clock=lambda: analysis_time
        )
        focus_graph = builder.build(GraphProjectionRequest(
            focus_type=request.focus_type, focus_id=request.focus_id,
            max_depth=0, context=context,
        ))
        projection = builder.build_dependency_projection(GraphProjectionRequest(
            focus_type=request.focus_type, focus_id=request.focus_id,
            direction="incoming", max_depth=GRAPH_DEPTH,
            node_limit=GRAPH_NODES, edge_limit=GRAPH_EDGES,
            complete_service_dependencies=True, edge_families=DEPENDENCY_FAMILIES,
            context=ActiveContext(focus_graph.nodes[0].customer_id, context.site_id),
        ))
        return self.evaluate(projection.graph, request, projection.incomplete_group_keys)

    @staticmethod
    def evaluate(
        graph: OperationalGraphResponse, request: DependencyAnalysisRequest,
        incomplete_group_keys: frozenset[str] = frozenset(),
    ) -> DependencyAnalysisResponse:
        nodes = {node.key: node for node in graph.nodes}
        response = DependencyAnalysisResponse(
            focus_key=graph.focus_key, focus=entity(nodes[graph.focus_key]),
            analysis_time=graph.generated_at,
        )
        if graph.truncated:
            # A missing alternative can invalidate ANY and uncertainty can flow
            # back around cycles. Never conclude from an incomplete input graph.
            response.truncated = True
            response.warnings = [
                "Analysis reached its graph safety limit. No conclusions were returned "
                "because dependency sets may be incomplete. Narrow the workspace scope."
            ]
            return response

        groups = defaultdict(lambda: defaultdict(list))
        for edge in sorted(graph.edges, key=lambda item: item.key):
            if edge.edge_family in DEPENDENCY_FAMILIES:
                key = f"dependency_group:{edge.dependency_group_id}" if edge.dependency_group_id else edge.key
                groups[edge.source_key][key].append(edge)
        service_keys = sorted(key for key in groups if key != graph.focus_key)
        states = {graph.focus_key: "unavailable"}

        def evaluate(group_key, edges):
            return evaluate_set(edges, states, incomplete=group_key in incomplete_group_keys)

        # Each first-phase pass adds at least one unavailable node or terminates.
        for _ in range(len(service_keys) + 1):
            additions = [key for key in service_keys if states.get(key) != "unavailable" and any(
                evaluate(group_key, edges)[1] == "unavailable" for group_key, edges in groups[key].items()
            )]
            if not additions:
                break
            states.update({key: "unavailable" for key in additions})
        fixed_unavailable = set(states)
        # Remaining nodes can only move unaffected -> degraded -> unknown.
        for _ in range(2 * len(service_keys) + 1):
            updates = {}
            for key in service_keys:
                if key in fixed_unavailable:
                    continue
                consequence = max(
                    (evaluate(group_key, edges)[1] for group_key, edges in groups[key].items()),
                    key=PRECEDENCE.__getitem__, default="unaffected",
                )
                if consequence != states.get(key, "unaffected"):
                    updates[key] = consequence
            if not updates:
                break
            states.update(updates)

        reasons_by_service = {}
        cause_edges = defaultdict(list)
        for key in service_keys:
            reasons = []
            for group_key, edges in sorted(groups[key].items()):
                triggering = [edge for edge in edges if states.get(edge.target_key, "unaffected") != "unaffected"]
                if not triggering:
                    continue
                satisfaction, consequence = evaluate(group_key, edges)
                first = edges[0]
                code = (
                    "set_satisfied" if satisfaction == "satisfied" else
                    "dependency_set_unresolved" if satisfaction == "unknown" and group_key in incomplete_group_keys else
                    "member_state_unresolved" if satisfaction == "unknown" else
                    "ungrouped_consequence_unknown" if first.dependency_group_id is None else "set_unsatisfied"
                )
                summary = {
                    "set_satisfied": "An alternative member remains available under this scenario; the dependency set is satisfied.",
                    "dependency_set_unresolved": "The available dependency knowledge does not establish whether this set is satisfied.",
                    "member_state_unresolved": "A member is degraded or unknown. The recorded semantics cannot determine whether this dependency set is satisfied.",
                    "ungrouped_consequence_unknown": "Atlas knows the dependency exists but does not know its operational consequence.",
                    "set_unsatisfied": f"The dependency set is unsatisfied. Its recorded failure effect is {first.failure_effect or 'unknown'}.",
                }[code]
                reasons.append(AnalysisReason(
                    key=group_key, dependency_group_id=first.dependency_group_id,
                    dependency_group_name=first.dependency_group_name,
                    dependency_strategy=first.dependency_strategy,
                    dependency_requirement=first.dependency_requirement,
                    failure_effect=first.failure_effect or "unknown",
                    satisfaction=satisfaction, consequence=consequence, code=code,
                    members=[AnalysisMember(entity=entity(nodes[edge.target_key]),
                        state=states.get(edge.target_key, "unaffected"), edge=edge) for edge in edges],
                    triggering_edge_keys=[edge.key for edge in triggering], summary=summary,
                ))
                # Shielded sets explain unaffected results but must not create a
                # misleading shortcut to an independently affected Service.
                if consequence != "unaffected" or states.get(key, "unaffected") == "unaffected":
                    for edge in triggering:
                        cause_edges[edge.target_key].append(edge)
            if reasons:
                reasons_by_service[key] = reasons

        # Breadth-first bounded simple paths, stable edge-key tie breaking.
        # One extra path per node detects truncation; cycles remain in reasons.
        paths = defaultdict(list)
        paths[graph.focus_key] = [AnalysisPath(nodes=[response.focus], edges=[])]
        queue = deque([(graph.focus_key, paths[graph.focus_key][0])])
        while queue:
            key, path = queue.popleft()
            if key != graph.focus_key and states.get(key, "unaffected") == "unaffected":
                continue
            for edge in sorted(cause_edges[key], key=lambda item: item.key):
                target = edge.source_key
                if target in {node.key for node in path.nodes}:
                    continue
                if len(path.edges) >= request.max_depth:
                    response.truncated = True
                    continue
                if len(paths[target]) >= request.max_paths_per_result + 1:
                    response.truncated = True
                    continue
                extended = AnalysisPath(nodes=[*path.nodes, entity(nodes[target])], edges=[*path.edges, edge])
                paths[target].append(extended)
                queue.append((target, extended))

        for key in sorted(reasons_by_service):
            if not paths[key]:
                # A bounded path can never be replaced with a dangling fragment.
                response.truncated = True
                continue
            if len(response.results) >= request.max_results:
                response.truncated = True
                break
            if len(paths[key]) > request.max_paths_per_result:
                response.truncated = True
            result_paths = paths[key][:request.max_paths_per_result]
            distance = len(result_paths[0].edges)
            response.results.append(ServiceAnalysisResult(
                service=entity(nodes[key]), state=states.get(key, "unaffected"),
                classification="direct" if distance == 1 else "downstream",
                distance=distance, reasons=reasons_by_service[key], paths=result_paths,
            ))
        if response.truncated:
            response.warnings.append(
                "Analysis explanation depth, result or path limit reached; this response is not exhaustive."
            )
        return response
