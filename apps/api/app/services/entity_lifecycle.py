"""Delete mistakes; archive history. Callers own authorization and transaction.

No retained evidence is removed. Blockers deliberately disclose no related
names, categories or counts: some references can be outside the caller's scope.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.audit import add_audit_event
from app.authorization import require_scope
from app.models import (
    AuditEvent, Base, BusinessFunction, KnowledgeAssertion, KnowledgeChange,
    KnowledgeGap, ReconciliationItem, RunObservedEntity, Service,
)
from app.routes.crud_helpers import commit, not_found
from app.services.knowledge_changes import record_change
from app.services.manual_knowledge import MANUAL_SERVICE_KNOWLEDGE_FIELDS
from app.utils.json_values import to_json_value

MESSAGE = "This {label} cannot be deleted because it has participated in the operational model. Archive it instead."


def _rows(db, model, condition):
    return list(db.scalars(select(model).where(condition).execution_options(include_deleted=True)))


def deletion_eligible(db, item) -> bool:
    kind = "service" if isinstance(item, Service) else "business_function"
    if item.deleted_at is not None or (isinstance(item, Service) and item.archived_at is not None) or (isinstance(item, BusinessFunction) and not item.active):
        return False
    if item.updated_at != item.created_at:
        return False
    # Inspect every actual FK, including ended relationships. New FK references
    # fail closed automatically; memberships cannot exist without a blocking parent.
    for table in Base.metadata.sorted_tables:
        columns = [column for column in table.c if any(fk.target_fullname == f"{item.__tablename__}.id" for fk in column.foreign_keys)]
        if columns and db.scalar(select(table.c.id).where(or_(*(column == item.id for column in columns))).limit(1)):
            return False
    audits = _rows(db, AuditEvent, (AuditEvent.target_type == kind) & (AuditEvent.target_id == item.id))
    if any(row.event_type != f"{kind}.created" for row in audits):
        return False
    changes = _rows(db, KnowledgeChange, (KnowledgeChange.entity_type == kind) & (KnowledgeChange.entity_id == item.id))
    automatic_changes = {f"{kind}_created", "service_completeness_changed", "knowledge_gap_opened", "knowledge_gap_resolved", "knowledge_requirement_changed"}
    if any(row.change_type not in automatic_changes or row.discovery_run_id is not None or row.reconciliation_item_id is not None or row.assertion_id is not None for row in changes):
        return False
    for model in (ReconciliationItem, RunObservedEntity):
        if _rows(db, model, (model.entity_type == kind) & (model.entity_id == item.id)):
            return False
    assertions = _rows(db, KnowledgeAssertion, or_(
        (KnowledgeAssertion.subject_type == kind) & (KnowledgeAssertion.subject_id == item.id),
        (KnowledgeAssertion.object_type == kind) & (KnowledgeAssertion.object_id == item.id),
    ))
    # New creation events explicitly identify initial declarations. For older
    # records, PostgreSQL transaction timestamps and the creation change establish
    # the original batch; do not exempt assertions merely because they are manual.
    initial_ids = {str(value) for row in audits for value in (row.metadata_ or {}).get("initial_assertion_ids", [])}
    creation = next((row for row in changes if row.change_type == "service_created"), None)
    seen = set()
    field_by_predicate = {predicate: field for field, predicate in MANUAL_SERVICE_KNOWLEDGE_FIELDS.items()}
    for row in assertions:
        initial = str(row.id) in initial_ids or (
            creation is not None and row.created_at == item.created_at
            and row.first_observed_at <= creation.occurred_at
        )
        field = field_by_predicate.get(row.predicate)
        if not (
            kind == "service" and initial and field and row.predicate not in seen
            and row.subject_type == kind and row.subject_id == item.id
            and row.object_id is None and row.object_external_id is None
            and row.discovery_run_id is None and row.evidence_record_id is None
            and row.truth_classification == "declared" and row.is_accepted
            and row.confirmation_status == "confirmed" and row.retracted_at is None
            and row.superseded_by_id is None and row.valid_to is None
            and row.first_observed_at == row.last_observed_at == row.accepted_at
            and row.value_json == to_json_value(getattr(item, field))
        ):
            return False
        seen.add(row.predicate)
    gaps = _rows(db, KnowledgeGap, (KnowledgeGap.entity_type == kind) & (KnowledgeGap.entity_id == item.id))
    gap_ids = [gap.id for gap in gaps]
    if gap_ids and _rows(db, AuditEvent, (AuditEvent.target_type == "knowledge_gap") & AuditEvent.target_id.in_(gap_ids)):
        return False
    if any(any(getattr(gap, field) is not None for field in (
        "resolved_by_user_id", "resolution_reason", "exception_reason",
        "exception_created_at", "exception_created_by_user_id", "deferred_until",
        "deferred_by_user_id", "assigned_to_user_id",
    )) for gap in gaps):
        return False
    return True


def delete_mistake(db, item, principal, request):
    # Refresh after waiting: another writer may have added history or archived it.
    locked = db.scalar(select(type(item)).where(type(item).id == item.id).with_for_update().execution_options(populate_existing=True))
    if locked is None or locked.deleted_at is not None:
        raise not_found("Service" if isinstance(item, Service) else "Business Function")
    require_scope(principal, "services.archive" if isinstance(locked, Service) else "business_functions.manage", locked.customer_id, locked.site_id, hide_existence=True)
    if not deletion_eligible(db, locked):
        raise HTTPException(status_code=409, detail=MESSAGE.format(label="Service" if isinstance(item, Service) else "Business Function"))
    kind = "service" if isinstance(item, Service) else "business_function"
    locked.deleted_at = datetime.now(timezone.utc)
    record_change(db, customer_id=item.customer_id, site_id=item.site_id,
                  change_type=f"{kind}_deleted", entity_type=kind, entity_id=item.id,
                  entity_name=item.name, summary=f"Deleted mistaken {'Service' if kind == 'service' else 'Business Function'} {item.name}",
                  actor_user_id=principal.user.id)
    add_audit_event(db, action=f"{kind}.deleted", target_type=kind, target_id=item.id,
                    actor=principal.user, customer_id=item.customer_id, site_id=item.site_id,
                    summary="Mistaken record deleted; history retained", request=request)
    commit(db, "Entity deletion")
