"""Authorized, read-time projection of accepted Atlas operational knowledge."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.authorization import ActiveContext, Principal
from app.models import (
    Asset,
    AssetRelationship,
    AssetType,
    BusinessFunction,
    CriticalityLevel,
    DependencyGroup,
    DependencyGroupMembership,
    KnowledgeCompletenessSummary,
    KnowledgeGap,
    RelationshipType,
    Service,
    ServiceAssetDependency,
    ServiceBusinessFunction,
    ServiceDependency,
    ServiceType,
)
from app.schemas import (
    OperationalGraphEdge,
    OperationalGraphNode,
    OperationalGraphResponse,
    ServiceGraphResponse,
)

EntityType = Literal["asset", "service", "business_function"]
Direction = Literal["both", "outgoing", "incoming"]
EdgeFamily = Literal[
    "asset_relationship",
    "service_asset",
    "service_service",
    "service_business_function",
]

EDGE_FAMILIES: frozenset[str] = frozenset(
    {
        "asset_relationship",
        "service_asset",
        "service_service",
        "service_business_function",
    }
)
NODE_PERMISSIONS = {
    "asset": "assets.view",
    "service": "services.view",
    "business_function": "business_functions.view",
}
MODEL_BY_ENTITY_TYPE = {
    "asset": Asset,
    "service": Service,
    "business_function": BusinessFunction,
}
ACTIVE_GAP_STATUSES = frozenset({"open", "deferred"})
NODE_LIMIT_WARNING = "The graph reached the node limit and was truncated."


def graph_node_key(entity_type: EntityType, entity_id: uuid.UUID) -> str:
    return f"{entity_type}:{entity_id}"


def graph_edge_key(edge_family: EdgeFamily, edge_id: uuid.UUID) -> str:
    return f"{edge_family}:{edge_id}"


@dataclass(frozen=True, slots=True)
class GraphProjectionRequest:
    focus_type: EntityType
    focus_id: uuid.UUID
    max_depth: int = 1
    direction: Direction = "both"
    node_limit: int = 250
    edge_families: frozenset[str] = EDGE_FAMILIES
    context: ActiveContext | None = None
    include_inactive_focus: bool = False
    # Compatibility routes can retain their C1 expansion shape while using the
    # same authorization, temporal, identity, and metadata implementation.
    edge_families_by_depth: tuple[frozenset[str], ...] | None = None
    # Internal analysis profile: probe the depth boundary, then complete the
    # outgoing dependency sets of reached Services using the same loaders.
    complete_service_dependencies: bool = False
    edge_limit: int | None = None


class GraphFocusNotFound(LookupError):
    """The focus is missing, inactive, archived, or unavailable to the caller."""


@dataclass(frozen=True, slots=True)
class DependencyGraphProjection:
    graph: OperationalGraphResponse
    # Internal only: no hidden endpoint identifiers, labels or counts reach
    # the analysis contract. A partially visible ANY set cannot prove failure.
    incomplete_group_keys: frozenset[str]


class OperationalGraphBuilder:
    """Build a deterministic, bounded graph without depending on HTTP objects."""

    def __init__(
        self,
        db: Session,
        principal: Principal,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.principal = principal
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def build(self, request: GraphProjectionRequest) -> OperationalGraphResponse:
        return self._build(request).graph

    def build_dependency_projection(self, request: GraphProjectionRequest) -> DependencyGraphProjection:
        return self._build(request)

    def _build(self, request: GraphProjectionRequest) -> DependencyGraphProjection:
        generated_at = self.clock()
        incomplete_group_keys: set[str] = set()
        focus = self.db.get(MODEL_BY_ENTITY_TYPE[request.focus_type], request.focus_id)
        if focus is None or not self._node_is_viewable(
            request.focus_type,
            focus,
            request.context,
            allow_inactive=request.include_inactive_focus,
        ):
            raise GraphFocusNotFound

        focus_key = graph_node_key(request.focus_type, request.focus_id)
        objects: dict[str, object] = {focus_key: focus}
        object_types: dict[str, EntityType] = {focus_key: request.focus_type}
        member_keys = {focus_key}
        edges: dict[str, OperationalGraphEdge] = {}
        relationship_types = list(self.db.scalars(select(RelationshipType)))
        relationship_types_by_id = {item.id: item for item in relationship_types}
        relationship_types_by_key = {item.key: item for item in relationship_types}

        frontier: list[tuple[EntityType, uuid.UUID]] = [
            (request.focus_type, request.focus_id)
        ]
        expanded: set[str] = set()
        truncated = False

        for depth in range(request.max_depth + (2 if request.complete_service_dependencies else 0)):
            completing = request.complete_service_dependencies and depth == request.max_depth + 1
            probing = request.complete_service_dependencies and depth == request.max_depth
            if completing:
                frontier = [
                    (object_types[key], objects[key].id)
                    for key in sorted(member_keys) if object_types[key] == "service"
                ]
            frontier = sorted(
                (
                    (entity_type, entity_id)
                    for entity_type, entity_id in frontier
                    if completing or graph_node_key(entity_type, entity_id) not in expanded
                ),
                key=lambda item: graph_node_key(item[0], item[1]),
            )
            if not frontier:
                if request.complete_service_dependencies:
                    continue
                break
            expanded.update(graph_node_key(*item) for item in frontier)
            families = self._families_for_depth(request, depth)
            candidates = self._load_edge_candidates(
                frontier, families, "outgoing" if completing else request.direction, generated_at
            )
            dependency_groups = self._load_dependency_groups(candidates, generated_at)
            endpoint_refs = {
                endpoint
                for _, row in candidates
                for endpoint in self._edge_endpoints(row)
            }
            self._batch_load_objects(endpoint_refs, objects, object_types)
            next_frontier: set[tuple[EntityType, uuid.UUID]] = set()

            for family, row in candidates:
                edge_key = graph_edge_key(family, row.id)
                if edge_key in edges:
                    continue
                source_ref, target_ref = self._edge_endpoints(row)
                source_key = graph_node_key(*source_ref)
                target_key = graph_node_key(*target_ref)
                source = objects.get(source_key)
                target = objects.get(target_key)
                if (
                    source is None
                    or target is None
                    or not self._node_is_viewable(
                        source_ref[0],
                        source,
                        request.context,
                        allow_inactive=(
                            request.include_inactive_focus and source_key == focus_key
                        ),
                    )
                    or not self._node_is_viewable(
                        target_ref[0],
                        target,
                        request.context,
                        allow_inactive=(
                            request.include_inactive_focus and target_key == focus_key
                        ),
                    )
                    or not self._edge_is_viewable(family, row, source, target)
                ):
                    group = dependency_groups.get((family, row.id))
                    if group is not None:
                        incomplete_group_keys.add(f"dependency_group:{group.id}")
                    continue

                # Objects loaded for authorization are not graph members until
                # their edge is accepted, so membership is tracked separately
                # from the object cache.
                new_refs = [
                    ref
                    for ref in (source_ref, target_ref)
                    if graph_node_key(*ref) not in member_keys
                ]
                if probing and new_refs:
                    truncated = True
                    continue
                if request.edge_limit is not None and len(edges) >= request.edge_limit:
                    truncated = True
                    continue
                if len(member_keys) + len(set(new_refs)) > request.node_limit:
                    truncated = True
                    # Continue through this frontier so legitimate edges whose
                    # endpoints are already present are not lost at the limit.
                    continue

                for ref in (source_ref, target_ref):
                    key = graph_node_key(*ref)
                    if key != focus_key and key not in member_keys:
                        next_frontier.add(ref)
                    member_keys.add(key)
                edges[edge_key] = self._edge_schema(
                    family,
                    row,
                    relationship_types_by_id,
                    relationship_types_by_key,
                    dependency_groups.get((family, row.id)),
                )

            if truncated:
                break
            frontier = sorted(next_frontier, key=lambda item: graph_node_key(*item))

        members = {key: objects[key] for key in member_keys}
        member_types = {key: object_types[key] for key in member_keys}
        nodes = self._node_schemas(members, member_types)
        result_edges = [
            edge
            for edge in edges.values()
            if edge.source_key in member_keys and edge.target_key in member_keys
        ]
        graph = OperationalGraphResponse(
            focus_key=focus_key,
            generated_at=generated_at,
            requested_depth=request.max_depth,
            truncated=truncated,
            warnings=[NODE_LIMIT_WARNING] if truncated else [],
            nodes=sorted(nodes, key=lambda node: node.key),
            edges=sorted(result_edges, key=lambda edge: edge.key),
        )
        return DependencyGraphProjection(graph, frozenset(incomplete_group_keys))

    @staticmethod
    def _families_for_depth(
        request: GraphProjectionRequest, depth: int
    ) -> frozenset[str]:
        if request.edge_families_by_depth is None:
            return request.edge_families
        if depth >= len(request.edge_families_by_depth):
            return frozenset()
        return request.edge_families.intersection(
            request.edge_families_by_depth[depth]
        )

    def _node_is_viewable(
        self,
        entity_type: EntityType,
        item,
        context: ActiveContext | None,
        *,
        allow_inactive: bool = False,
    ) -> bool:
        if (
            not allow_inactive
            and entity_type == "service"
            and item.archived_at is not None
        ):
            return False
        if not allow_inactive and entity_type == "business_function" and not item.active:
            return False
        if not self.principal.can(
            NODE_PERMISSIONS[entity_type], item.customer_id, item.site_id
        ):
            return False
        if context is None:
            return True
        if context.customer_id is not None and item.customer_id != context.customer_id:
            return False
        if (
            context.site_id is not None
            and item.site_id is not None
            and item.site_id != context.site_id
        ):
            return False
        return True

    def _edge_is_viewable(
        self,
        family: EdgeFamily,
        row,
        source,
        target,
    ) -> bool:
        if family == "asset_relationship":
            return self.principal.can(
                "relationships.view", source.customer_id, source.site_id
            ) and self.principal.can(
                "relationships.view", target.customer_id, target.site_id
            )
        permission = (
            "business_functions.view"
            if family == "service_business_function"
            else "service_dependencies.view"
        )
        return self.principal.can(permission, row.customer_id, row.site_id)

    def _load_edge_candidates(
        self,
        frontier: list[tuple[EntityType, uuid.UUID]],
        families: frozenset[str],
        direction: Direction,
        generated_at: datetime,
    ) -> list[tuple[EdgeFamily, object]]:
        ids: dict[EntityType, list[uuid.UUID]] = defaultdict(list)
        for entity_type, entity_id in frontier:
            ids[entity_type].append(entity_id)
        candidates: dict[str, tuple[EdgeFamily, object]] = {}

        def add(family: EdgeFamily, rows) -> None:
            for row in rows:
                if not self._row_touches_frontier(family, row, ids, direction):
                    continue
                if family != "asset_relationship" and not (
                    row.valid_from <= generated_at
                    and (row.valid_to is None or row.valid_to > generated_at)
                ):
                    continue
                candidates[graph_edge_key(family, row.id)] = (family, row)

        if "asset_relationship" in families and ids["asset"]:
            predicates = self._direction_predicates(
                AssetRelationship.source_asset_id,
                AssetRelationship.target_asset_id,
                ids["asset"],
                ids["asset"],
                direction,
            )
            if predicates:
                add(
                    "asset_relationship",
                    self.db.scalars(select(AssetRelationship).where(or_(*predicates))),
                )

        if "service_asset" in families:
            predicates = self._direction_predicates(
                ServiceAssetDependency.service_id,
                ServiceAssetDependency.asset_id,
                ids["service"],
                ids["asset"],
                direction,
            )
            if predicates:
                add(
                    "service_asset",
                    self.db.scalars(
                        select(ServiceAssetDependency).where(
                            or_(*predicates),
                            ServiceAssetDependency.valid_from <= generated_at,
                            or_(
                                ServiceAssetDependency.valid_to.is_(None),
                                ServiceAssetDependency.valid_to > generated_at,
                            ),
                        )
                    ),
                )

        if "service_service" in families and ids["service"]:
            predicates = self._direction_predicates(
                ServiceDependency.source_service_id,
                ServiceDependency.target_service_id,
                ids["service"],
                ids["service"],
                direction,
            )
            if predicates:
                add(
                    "service_service",
                    self.db.scalars(
                        select(ServiceDependency).where(
                            or_(*predicates),
                            ServiceDependency.valid_from <= generated_at,
                            or_(
                                ServiceDependency.valid_to.is_(None),
                                ServiceDependency.valid_to > generated_at,
                            ),
                        )
                    ),
                )

        if "service_business_function" in families:
            predicates = self._direction_predicates(
                ServiceBusinessFunction.service_id,
                ServiceBusinessFunction.business_function_id,
                ids["service"],
                ids["business_function"],
                direction,
            )
            if predicates:
                add(
                    "service_business_function",
                    self.db.scalars(
                        select(ServiceBusinessFunction).where(
                            or_(*predicates),
                            ServiceBusinessFunction.valid_from <= generated_at,
                            or_(
                                ServiceBusinessFunction.valid_to.is_(None),
                                ServiceBusinessFunction.valid_to > generated_at,
                            ),
                        )
                    ),
                )
        return [candidates[key] for key in sorted(candidates)]

    @staticmethod
    def _row_touches_frontier(
        family: EdgeFamily,
        row,
        ids: dict[EntityType, list[uuid.UUID]],
        direction: Direction,
    ) -> bool:
        if family == "asset_relationship":
            source_type, source_id = "asset", row.source_asset_id
            target_type, target_id = "asset", row.target_asset_id
        elif family == "service_asset":
            source_type, source_id = "service", row.service_id
            target_type, target_id = "asset", row.asset_id
        elif family == "service_service":
            source_type, source_id = "service", row.source_service_id
            target_type, target_id = "service", row.target_service_id
        else:
            source_type, source_id = "service", row.service_id
            target_type, target_id = "business_function", row.business_function_id
        return (
            direction in {"both", "outgoing"} and source_id in ids[source_type]
        ) or (
            direction in {"both", "incoming"} and target_id in ids[target_type]
        )

    @staticmethod
    def _direction_predicates(
        source_column,
        target_column,
        source_frontier_ids: list[uuid.UUID],
        target_frontier_ids: list[uuid.UUID],
        direction: Direction,
    ) -> list:
        predicates = []
        if direction in {"both", "outgoing"} and source_frontier_ids:
            predicates.append(source_column.in_(source_frontier_ids))
        if direction in {"both", "incoming"} and target_frontier_ids:
            predicates.append(target_column.in_(target_frontier_ids))
        return predicates

    @staticmethod
    def _edge_endpoints(
        row,
    ) -> tuple[tuple[EntityType, uuid.UUID], tuple[EntityType, uuid.UUID]]:
        if isinstance(row, AssetRelationship):
            return ("asset", row.source_asset_id), ("asset", row.target_asset_id)
        if isinstance(row, ServiceAssetDependency):
            return ("service", row.service_id), ("asset", row.asset_id)
        if isinstance(row, ServiceDependency):
            return (
                ("service", row.source_service_id),
                ("service", row.target_service_id),
            )
        if isinstance(row, ServiceBusinessFunction):
            return (
                ("service", row.service_id),
                ("business_function", row.business_function_id),
            )
        raise TypeError(f"Unsupported operational graph edge: {type(row).__name__}")

    def _batch_load_objects(
        self,
        refs: set[tuple[EntityType, uuid.UUID]],
        objects: dict[str, object],
        object_types: dict[str, EntityType],
    ) -> None:
        by_type: dict[EntityType, list[uuid.UUID]] = defaultdict(list)
        for entity_type, entity_id in refs:
            if graph_node_key(entity_type, entity_id) not in objects:
                by_type[entity_type].append(entity_id)
        for entity_type, entity_ids in by_type.items():
            model = MODEL_BY_ENTITY_TYPE[entity_type]
            for item in self.db.scalars(select(model).where(model.id.in_(entity_ids))):
                key = graph_node_key(entity_type, item.id)
                objects[key] = item
                object_types[key] = entity_type

    def _edge_schema(
        self,
        family: EdgeFamily,
        row,
        relationship_types_by_id: dict[uuid.UUID, RelationshipType],
        relationship_types_by_key: dict[str, RelationshipType],
        dependency_group: DependencyGroup | None,
    ) -> OperationalGraphEdge:
        source_ref, target_ref = self._edge_endpoints(row)
        if family == "asset_relationship":
            relationship = relationship_types_by_key.get(row.relationship_type)
            relationship_key = row.relationship_type
            fallback_label = row.relationship_type.replace("_", " ").capitalize()
        else:
            relationship_id = getattr(row, "relationship_type_id", None)
            relationship = relationship_types_by_id.get(relationship_id)
            relationship_key = relationship.key if relationship else None
            fallback_label = (
                "Supports"
                if family == "service_business_function"
                else "Depends on"
            )
        is_dependency = family in {"service_asset", "service_service"}
        required_for_operation = getattr(row, "required_for_operation", None)
        return OperationalGraphEdge(
            key=graph_edge_key(family, row.id),
            edge_family=family,
            edge_id=row.id,
            source_key=graph_node_key(*source_ref),
            target_key=graph_node_key(*target_ref),
            relationship_type_key=relationship_key,
            relationship_type_name=relationship.name if relationship else None,
            label=relationship.source_label if relationship else fallback_label,
            required_for_operation=required_for_operation,
            dependency_group_id=dependency_group.id if dependency_group else None,
            dependency_group_name=dependency_group.name if dependency_group else None,
            dependency_strategy=dependency_group.strategy if dependency_group else None,
            dependency_requirement=(
                dependency_group.requirement
                if dependency_group
                else ("required" if required_for_operation else "optional")
                if is_dependency
                else None
            ),
            failure_effect=(
                dependency_group.failure_effect
                if dependency_group
                else "unknown" if is_dependency else None
            ),
            valid_from=getattr(row, "valid_from", None),
            valid_to=getattr(row, "valid_to", None),
            source=getattr(row, "source", None),
        )

    def _load_dependency_groups(
        self,
        candidates: list[tuple[EdgeFamily, object]],
        generated_at: datetime,
    ) -> dict[tuple[EdgeFamily, uuid.UUID], DependencyGroup]:
        asset_ids = [row.id for family, row in candidates if family == "service_asset"]
        service_ids = [row.id for family, row in candidates if family == "service_service"]
        predicates = []
        if asset_ids:
            predicates.append(DependencyGroupMembership.service_asset_dependency_id.in_(asset_ids))
        if service_ids:
            predicates.append(DependencyGroupMembership.service_dependency_id.in_(service_ids))
        if not predicates:
            return {}
        memberships = [
            row
            for row in self.db.scalars(select(DependencyGroupMembership).where(
                or_(*predicates),
                DependencyGroupMembership.valid_from <= generated_at,
                or_(
                    DependencyGroupMembership.valid_to.is_(None),
                    DependencyGroupMembership.valid_to > generated_at,
                ),
            ))
            if row.valid_from <= generated_at
            and (row.valid_to is None or row.valid_to > generated_at)
        ]
        group_ids = {row.dependency_group_id for row in memberships}
        if not group_ids:
            return {}
        groups = {
            row.id: row
            for row in self.db.scalars(select(DependencyGroup).where(
                DependencyGroup.id.in_(group_ids),
                DependencyGroup.valid_from <= generated_at,
                or_(DependencyGroup.valid_to.is_(None), DependencyGroup.valid_to > generated_at),
            ))
            if row.valid_from <= generated_at
            and (row.valid_to is None or row.valid_to > generated_at)
        }
        rows_by_key = {(family, row.id): row for family, row in candidates}
        result: dict[tuple[EdgeFamily, uuid.UUID], DependencyGroup] = {}
        for membership in memberships:
            if membership.service_asset_dependency_id is not None:
                key: tuple[EdgeFamily, uuid.UUID] = (
                    "service_asset",
                    membership.service_asset_dependency_id,
                )
            else:
                key = ("service_service", membership.service_dependency_id)
            group = groups.get(membership.dependency_group_id)
            dependency = rows_by_key.get(key)
            if group is None or dependency is None:
                continue
            subject_id = (
                dependency.service_id
                if key[0] == "service_asset"
                else dependency.source_service_id
            )
            if (
                group.service_id == subject_id
                and group.customer_id == dependency.customer_id
                and group.site_id == dependency.site_id
                and self.principal.can(
                    "service_dependencies.view", group.customer_id, group.site_id
                )
            ):
                result[key] = group
        return result

    def _node_schemas(
        self,
        objects: dict[str, object],
        object_types: dict[str, EntityType],
    ) -> list[OperationalGraphNode]:
        asset_type_keys = {
            item.asset_type
            for key, item in objects.items()
            if object_types[key] == "asset"
        }
        service_type_ids = {
            item.service_type_id
            for key, item in objects.items()
            if object_types[key] == "service"
        }
        criticality_ids = {
            item.criticality_level_id
            for key, item in objects.items()
            if object_types[key] in {"service", "business_function"}
            and item.criticality_level_id is not None
        }
        asset_types = {
            item.key: item
            for item in self.db.scalars(
                select(AssetType).where(AssetType.key.in_(asset_type_keys))
            )
        } if asset_type_keys else {}
        service_types = {
            item.id: item
            for item in self.db.scalars(
                select(ServiceType).where(ServiceType.id.in_(service_type_ids))
            )
        } if service_type_ids else {}
        criticalities = {
            item.id: item
            for item in self.db.scalars(
                select(CriticalityLevel).where(CriticalityLevel.id.in_(criticality_ids))
            )
        } if criticality_ids else {}

        supported_ids: dict[str, set[uuid.UUID]] = defaultdict(set)
        for key, item in objects.items():
            entity_type = object_types[key]
            if entity_type in {"asset", "service"}:
                supported_ids[entity_type].add(item.id)
        completeness_conditions = [
            (KnowledgeCompletenessSummary.entity_type == entity_type)
            & (KnowledgeCompletenessSummary.entity_id.in_(entity_ids))
            for entity_type, entity_ids in supported_ids.items()
            if entity_ids
        ]
        summaries = {}
        gaps: dict[tuple[str, uuid.UUID], int] = defaultdict(int)
        if completeness_conditions:
            summaries = {
                (item.entity_type, item.entity_id): item
                for item in self.db.scalars(
                    select(KnowledgeCompletenessSummary).where(
                        or_(*completeness_conditions)
                    )
                )
            }
            for gap in self.db.scalars(
                select(KnowledgeGap).where(
                    or_(*[
                        (KnowledgeGap.entity_type == entity_type)
                        & (KnowledgeGap.entity_id.in_(entity_ids))
                        for entity_type, entity_ids in supported_ids.items()
                        if entity_ids
                    ]),
                    KnowledgeGap.status.in_(ACTIVE_GAP_STATUSES),
                )
            ):
                gaps[(gap.entity_type, gap.entity_id)] += 1

        nodes = []
        for key, item in objects.items():
            entity_type = object_types[key]
            summary = summaries.get((entity_type, item.id))
            if entity_type == "asset":
                asset_type = asset_types.get(item.asset_type)
                nodes.append(
                    OperationalGraphNode(
                        key=key,
                        entity_type=entity_type,
                        entity_id=item.id,
                        customer_id=item.customer_id,
                        site_id=item.site_id,
                        name=item.name,
                        subtitle=asset_type.name if asset_type else item.asset_type,
                        href=f"/assets/{item.id}",
                        lifecycle_state=item.status,
                        completeness_status=(
                            summary.completeness_status
                            if summary
                            else "not_evaluated"
                        ),
                        open_gap_count=gaps[(entity_type, item.id)],
                        source=item.source,
                        updated_at=item.updated_at,
                    )
                )
            elif entity_type == "service":
                service_type = service_types.get(item.service_type_id)
                criticality = criticalities.get(item.criticality_level_id)
                nodes.append(
                    OperationalGraphNode(
                        key=key,
                        entity_type=entity_type,
                        entity_id=item.id,
                        customer_id=item.customer_id,
                        site_id=item.site_id,
                        name=item.name,
                        subtitle=service_type.name if service_type else "Service",
                        href=f"/services/{item.id}",
                        lifecycle_state=item.lifecycle_status,
                        operational_state=item.operational_status,
                        criticality_key=criticality.key if criticality else None,
                        criticality_name=criticality.name if criticality else None,
                        completeness_status=(
                            summary.completeness_status
                            if summary
                            else "not_evaluated"
                        ),
                        open_gap_count=gaps[(entity_type, item.id)],
                        source=item.source,
                        updated_at=item.updated_at,
                    )
                )
            else:
                criticality = criticalities.get(item.criticality_level_id)
                nodes.append(
                    OperationalGraphNode(
                        key=key,
                        entity_type=entity_type,
                        entity_id=item.id,
                        customer_id=item.customer_id,
                        site_id=item.site_id,
                        name=item.name,
                        subtitle="Business Function",
                        href=f"/business-functions/{item.id}",
                        lifecycle_state="active" if item.active else "inactive",
                        criticality_key=criticality.key if criticality else None,
                        criticality_name=criticality.name if criticality else None,
                        completeness_status=None,
                        open_gap_count=None,
                        source=None,
                        updated_at=item.updated_at,
                    )
                )
        return nodes


def operational_graph_to_service_graph(
    graph: OperationalGraphResponse,
) -> ServiceGraphResponse:
    """Adapt namespaced C2.1 output to the existing C1 response contract."""

    edge_type = {
        "asset_relationship": "asset_asset",
        "service_asset": "service_asset",
        "service_service": "service_service",
        "service_business_function": "service_business_function",
    }
    nodes_by_key = {node.key: node for node in graph.nodes}
    return ServiceGraphResponse(
        nodes=[
            {
                "id": node.entity_id,
                "entity_type": node.entity_type,
                "name": node.name,
                "subtitle": node.subtitle,
                "href": node.href,
            }
            for node in graph.nodes
        ],
        edges=[
            {
                "id": edge.edge_id,
                "source_id": nodes_by_key[edge.source_key].entity_id,
                "target_id": nodes_by_key[edge.target_key].entity_id,
                "label": edge.label,
                "edge_type": edge_type[edge.edge_family],
            }
            for edge in graph.edges
        ],
    )
