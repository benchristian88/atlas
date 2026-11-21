from collections.abc import Generator

from sqlalchemy import create_engine, event, or_, select
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from app.models import Asset, BusinessFunction, KnowledgeAssertion, KnowledgeCompletenessSummary, KnowledgeGap, Service
from app.config import database_url

DATABASE_URL = database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a transaction-capable database session to API dependencies."""
    with SessionLocal() as session:
        yield session


# One read policy covers lists, counts, search, pickers and graph loaders,
# including scalar column queries. Audit and Changes retain their snapshots.
# Internal lifecycle inspection can explicitly opt into retained records.
def _not_deleted_reference(kind, entity_id):
    return (
        or_(kind != "service", entity_id.is_(None), ~entity_id.in_(
            select(Service.__table__.c.id).where(Service.__table__.c.deleted_at.is_not(None))
        ))
        & or_(kind != "business_function", entity_id.is_(None), ~entity_id.in_(
            select(BusinessFunction.__table__.c.id).where(BusinessFunction.__table__.c.deleted_at.is_not(None))
        ))
    )


def _matches_live_completeness_scope(row):
    assets = Asset.__table__
    services = Service.__table__
    return or_(
        (row.entity_type == "asset") & select(assets.c.id).where(
            assets.c.id == row.entity_id,
            assets.c.customer_id == row.customer_id,
            assets.c.site_id.is_not_distinct_from(row.site_id),
        ).correlate_except(assets).exists(),
        (row.entity_type == "service") & select(services.c.id).where(
            services.c.id == row.entity_id,
            services.c.deleted_at.is_(None),
            services.c.customer_id == row.customer_id,
            services.c.site_id.is_not_distinct_from(row.site_id),
        ).correlate_except(services).exists(),
    )


def _matches_live_summary_scope(row):
    # Older transfers could update the summary scope while still counting gaps
    # from the previous scope. Treat that summary as unevaluated until repaired.
    gaps = KnowledgeGap.__table__
    stale_gap = select(gaps.c.id).where(
        gaps.c.entity_type == row.entity_type,
        gaps.c.entity_id == row.entity_id,
        gaps.c.status.in_(("open", "deferred", "exception")),
        or_(gaps.c.customer_id != row.customer_id, gaps.c.site_id.is_distinct_from(row.site_id)),
    ).correlate_except(gaps).exists()
    return _matches_live_completeness_scope(row) & ~stale_gap


@event.listens_for(Session, "do_orm_execute")
def exclude_entity_tombstones(execute_state):
    if not execute_state.is_select or execute_state.execution_options.get("include_deleted"):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(Service, Service.deleted_at.is_(None), include_aliases=True),
        with_loader_criteria(BusinessFunction, BusinessFunction.deleted_at.is_(None), include_aliases=True),
        with_loader_criteria(KnowledgeAssertion, _not_deleted_reference(KnowledgeAssertion.subject_type, KnowledgeAssertion.subject_id) & or_(KnowledgeAssertion.object_type.is_(None), _not_deleted_reference(KnowledgeAssertion.object_type, KnowledgeAssertion.object_id)), include_aliases=True),
    )
    if not execute_state.execution_options.get("include_unmatched_completeness"):
        # Scope filters on persisted completeness rows are safe only while the
        # row still belongs to the live entity's customer and site.
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(KnowledgeGap, _matches_live_completeness_scope, include_aliases=True),
            with_loader_criteria(KnowledgeCompletenessSummary, _matches_live_summary_scope, include_aliases=True),
        )
