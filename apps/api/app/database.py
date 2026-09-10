import os
from collections.abc import Generator

from sqlalchemy import create_engine, event, or_, select
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from app.models import BusinessFunction, KnowledgeAssertion, KnowledgeCompletenessSummary, KnowledgeGap, Service

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://atlas:atlas_dev@localhost:5432/atlas",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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


@event.listens_for(Session, "do_orm_execute")
def exclude_entity_tombstones(execute_state):
    if not execute_state.is_select or execute_state.execution_options.get("include_deleted"):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(Service, Service.deleted_at.is_(None), include_aliases=True),
        with_loader_criteria(BusinessFunction, BusinessFunction.deleted_at.is_(None), include_aliases=True),
        with_loader_criteria(KnowledgeGap, _not_deleted_reference(KnowledgeGap.entity_type, KnowledgeGap.entity_id), include_aliases=True),
        with_loader_criteria(KnowledgeCompletenessSummary, _not_deleted_reference(KnowledgeCompletenessSummary.entity_type, KnowledgeCompletenessSummary.entity_id), include_aliases=True),
        with_loader_criteria(KnowledgeAssertion, _not_deleted_reference(KnowledgeAssertion.subject_type, KnowledgeAssertion.subject_id) & or_(KnowledgeAssertion.object_type.is_(None), _not_deleted_reference(KnowledgeAssertion.object_type, KnowledgeAssertion.object_id)), include_aliases=True),
    )
