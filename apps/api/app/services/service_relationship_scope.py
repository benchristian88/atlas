"""Live ownership rules shared by Service relationship writes and reads."""

from sqlalchemy import and_, literal, or_, select
from sqlalchemy.orm import aliased

from app.authorization import scope_condition
from app.models import Asset, BusinessFunction, KnowledgeAssertion, Service, ServiceAssetDependency, ServiceBusinessFunction, ServiceDependency


RELATIONSHIPS = {
    ServiceAssetDependency: ("service_id", "asset_id", Asset, "assets.view"),
    ServiceDependency: ("source_service_id", "target_service_id", Service, "services.view"),
    ServiceBusinessFunction: ("service_id", "business_function_id", BusinessFunction, "business_functions.view"),
}


def compatible_target_scope(source, target) -> bool:
    # Asset.site_id is required, so the nullable-target rule also works for Assets.
    return source.customer_id == target.customer_id and (
        source.site_id is None or target.site_id in {None, source.site_id}
    )


def matches_service_scope(row, service) -> bool:
    return row.customer_id == service.customer_id and row.site_id == service.site_id


def valid_relationship_scope(row, source, target) -> bool:
    return matches_service_scope(row, source) and compatible_target_scope(source, target)


def _compatible_target_scope(source_customer, source_site, target_customer, target_site):
    return and_(
        source_customer == target_customer,
        or_(source_site.is_(None), target_site.is_(None), source_site == target_site),
    )


def _endpoint_scope(model, source, target, principal, *, include_history=False):
    _, _, target_model, target_permission = RELATIONSHIPS[model]
    conditions = [source.deleted_at.is_(None)]
    if target_model is not Asset:
        conditions.append(target.deleted_at.is_(None))
    current_scope = and_(
        model.customer_id == source.customer_id,
        model.site_id.is_not_distinct_from(source.site_id),
        _compatible_target_scope(source.customer_id, source.site_id, target.customer_id, target.site_id),
    )
    if include_history:
        # Ended rows keep their original scope. Both live endpoints must remain
        # readable and within the historical customer to show their live names.
        conditions.append(or_(
            and_(model.valid_to.is_(None), current_scope),
            and_(model.valid_to.is_not(None), model.customer_id == source.customer_id,
                 model.customer_id == target.customer_id),
        ))
    else:
        conditions.extend((model.valid_to.is_(None), current_scope))
    if principal is not None:
        link_permission = "business_functions.view" if model is ServiceBusinessFunction else "service_dependencies.view"
        conditions.extend((
            scope_condition(principal, link_permission, model.customer_id, model.site_id),
            scope_condition(principal, "services.view", source.customer_id, source.site_id),
            scope_condition(principal, target_permission, target.customer_id, target.site_id),
        ))
    return conditions


def current_relationship(model, principal=None):
    """Predicate for counts, filters and evaluations over a relationship table."""
    source_id, target_id, target_model, _ = RELATIONSHIPS[model]
    source, target = Service.__table__.alias(), target_model.__table__.alias()
    return select(1).select_from(source.join(target, source.c.customer_id == target.c.customer_id)).where(
        source.c.id == getattr(model, source_id),
        target.c.id == getattr(model, target_id),
        *_endpoint_scope(model, source.c, target.c, principal),
    ).correlate(model).exists()


def visible_relationships(model, principal, *, include_history=False):
    """Read authorized endpoints and the edge in the same statement."""
    source_id, target_id, target_model, _ = RELATIONSHIPS[model]
    row, source, target = model.__table__, Service.__table__.alias(), target_model.__table__.alias()
    joins = row.join(source, row.c[source_id] == source.c.id).join(target, row.c[target_id] == target.c.id)
    return select(aliased(Service, source), aliased(target_model, target), model).select_from(joins).where(
        *_endpoint_scope(model, source.c, target.c, principal, include_history=include_history),
    ).execution_options(populate_existing=True)


def visible_service_relationship_assertion(principal):
    """Apply endpoint visibility to typed Service claims in provenance reads."""
    row = KnowledgeAssertion
    source = Service.__table__.alias()
    current = and_(row.is_source_current.is_(True), row.valid_to.is_(None), row.retracted_at.is_(None))
    visible_types = []
    for kind, model in (("asset", ServiceAssetDependency), ("service", ServiceDependency),
                        ("business_function", ServiceBusinessFunction)):
        _, _, target_model, permission = RELATIONSHIPS[model]
        target = target_model.__table__.alias()
        endpoints = select(1).select_from(source.join(target, source.c.customer_id == target.c.customer_id)).where(
            source.c.id == row.subject_id,
            target.c.id == row.object_id,
            source.c.customer_id == row.customer_id,
            source.c.deleted_at.is_(None),
            scope_condition(principal, "services.view", source.c.customer_id, source.c.site_id),
            scope_condition(principal, permission, target.c.customer_id, target.c.site_id),
            or_(~current, and_(
                row.site_id.is_not_distinct_from(source.c.site_id),
                _compatible_target_scope(source.c.customer_id, source.c.site_id, target.c.customer_id, target.c.site_id),
            )),
        )
        if target_model is not Asset:
            endpoints = endpoints.where(target.c.deleted_at.is_(None))
        visible_types.append(and_(row.object_type == kind, endpoints.correlate(row).exists()))
    return or_(
        row.subject_type != "service",
        row.object_type.is_(None),
        row.object_type.not_in(("asset", "service", "business_function")),
        *visible_types,
    )


def incompatible_incoming_move(db, model, target_id, customer_id, site_id) -> bool:
    # The caller holds the target lock. Every relationship writer needs that
    # lock, and a Service with an outgoing edge cannot change its scope.
    source_id, target_column, _, _ = RELATIONSHIPS[model]
    return db.scalar(select(model.id).join(Service, Service.id == getattr(model, source_id)).where(
        getattr(model, target_column) == target_id,
        model.valid_to.is_(None),
        or_(
            Service.deleted_at.is_not(None),
            model.customer_id != Service.customer_id,
            model.site_id.is_distinct_from(Service.site_id),
            ~_compatible_target_scope(
                Service.customer_id, Service.site_id, customer_id,
                literal(site_id, type_=Service.site_id.type),
            ),
        ),
    ).execution_options(include_deleted=True).limit(1)) is not None
