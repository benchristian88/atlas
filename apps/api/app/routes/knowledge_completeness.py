"""Knowledge profiles, completeness evaluation, and gap lifecycle APIs."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_global, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import Asset, AssetType, KnowledgeCompletenessSummary, KnowledgeGap, KnowledgeRequirementDefinition, User
from app.routes.crud_helpers import commit, flush, not_found
from app.schemas import (
    AssetCompletenessResponse, CompletenessBatchRequest, GapAssignRequest,
    GapDeferRequest, GapExceptionRequest, GapReopenRequest, GapSummaryResponse,
    KnowledgeCompletenessSummaryResponse, KnowledgeGapResponse,
    KnowledgeRequirementCreate, KnowledgeRequirementResponse,
    KnowledgeRequirementUpdate, KnowledgeRequirementValidationRequest,
    KnowledgeRequirementValidationResponse,
)
from app.services.knowledge_completeness import ACTIVE_GAP_STATUSES, evaluate_asset, evaluate_assets_for_asset_type
from app.services.knowledge_changes import record_change
from app.services.knowledge_requirement_references import interpret_rule, validate_rule_config
from app.utils.json_values import to_json_value

router = APIRouter(tags=["knowledge completeness"])


def _requirement_response(db: Session, item: KnowledgeRequirementDefinition) -> dict:
    asset_type = db.get(AssetType, item.asset_type_id) if item.asset_type_id else None
    asset_count = int(db.scalar(select(func.count()).select_from(Asset).where(Asset.asset_type == asset_type.key)) or 0) if asset_type else int(db.scalar(select(func.count()).select_from(Asset)) or 0)
    result = KnowledgeRequirementResponse.model_validate(item).model_dump()
    result.update(asset_type_name=asset_type.name if asset_type else None, rule_summary=interpret_rule(db, item.rule_type, item.rule_config_json or {}), affected_asset_count=asset_count)
    return to_json_value(result)


def _gap_response(db: Session, gap: KnowledgeGap) -> dict:
    requirement = db.get(KnowledgeRequirementDefinition, gap.requirement_definition_id)
    asset = db.get(Asset, gap.entity_id) if gap.entity_type == "asset" else None
    asset_type = db.get(AssetType, gap.asset_type_id_snapshot) if gap.asset_type_id_snapshot else None
    assigned = db.get(User, gap.assigned_to_user_id) if gap.assigned_to_user_id else None
    result = KnowledgeGapResponse.model_validate(gap).model_dump()
    result.update(
        requirement_name=requirement.name if requirement else None,
        remediation_hint=requirement.remediation_hint if requirement else None,
        entity_name=asset.name if asset else None,
        asset_type_name=asset_type.name if asset_type else None,
        assigned_to_name=(assigned.display_name or assigned.email) if assigned else None,
        details_json=to_json_value(gap.details_json),
    )
    return to_json_value(result)


def _asset(db: Session, principal: Principal, asset_id: uuid.UUID, permission: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(principal, permission, asset.customer_id, asset.site_id, hide_existence=True)
    return asset


@router.get("/asset-types/{asset_type_id}/knowledge-requirements", response_model=list[KnowledgeRequirementResponse])
def list_profile_requirements(asset_type_id: uuid.UUID, principal: Principal = Depends(require_permission("knowledge_requirements.view")), db: Session = Depends(get_db)):
    require_global(principal, "knowledge_requirements.view")
    if db.get(AssetType, asset_type_id) is None:
        raise not_found("Asset type")
    rows = db.scalars(select(KnowledgeRequirementDefinition).where(or_(KnowledgeRequirementDefinition.asset_type_id == asset_type_id, KnowledgeRequirementDefinition.asset_type_id.is_(None))).order_by(KnowledgeRequirementDefinition.sort_order, KnowledgeRequirementDefinition.name))
    return [_requirement_response(db, item) for item in rows]


@router.post("/asset-types/{asset_type_id}/knowledge-requirements", response_model=KnowledgeRequirementResponse, status_code=status.HTTP_201_CREATED)
def create_profile_requirement(asset_type_id: uuid.UUID, payload: KnowledgeRequirementCreate, request: Request, principal: Principal = Depends(require_permission("knowledge_requirements.manage")), db: Session = Depends(get_db)):
    require_global(principal, "knowledge_requirements.manage")
    asset_type = db.get(AssetType, asset_type_id)
    if asset_type is None:
        raise not_found("Asset type")
    valid, errors, _ = validate_rule_config(db, payload.rule_type, payload.rule_config_json)
    if not valid:
        raise HTTPException(status_code=422, detail={"message": "Invalid requirement configuration", "errors": errors})
    values = payload.model_dump(exclude={"asset_type_id", "rule_config_json"})
    item = KnowledgeRequirementDefinition(**values, rule_config_json=to_json_value(payload.rule_config_json), asset_type_id=asset_type.id, system_defined=False, configuration_valid=True, created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item)
    flush(db, "Knowledge requirement")
    count = evaluate_assets_for_asset_type(db, asset_type.id, actor_user_id=principal.user.id)
    add_audit_event(db, action="knowledge_requirement.created", target_type="knowledge_requirement", target_id=item.id, actor=principal.user, summary="Knowledge requirement created", metadata={"key": item.key, "affected_assets": count}, request=request)
    commit(db, "Knowledge requirement")
    db.refresh(item)
    return _requirement_response(db, item)


@router.post("/knowledge-requirements/validate", response_model=KnowledgeRequirementValidationResponse)
def validate_requirement(payload: KnowledgeRequirementValidationRequest, principal: Principal = Depends(require_permission("knowledge_requirements.view")), db: Session = Depends(get_db)):
    require_global(principal, "knowledge_requirements.view")
    valid, errors, interpretation = validate_rule_config(db, payload.rule_type, payload.rule_config_json)
    return {"valid": valid, "errors": errors, "interpretation": interpretation}


@router.post("/knowledge-requirements", response_model=KnowledgeRequirementResponse, status_code=status.HTTP_201_CREATED)
def create_global_requirement(payload: KnowledgeRequirementCreate, request: Request, principal: Principal = Depends(require_permission("knowledge_requirements.manage")), db: Session = Depends(get_db)):
    """Create a global requirement. Type-specific definitions use the profile route."""
    require_global(principal, "knowledge_requirements.manage")
    valid, errors, _ = validate_rule_config(db, payload.rule_type, payload.rule_config_json)
    if not valid:
        raise HTTPException(status_code=422, detail={"message": "Invalid requirement configuration", "errors": errors})
    values = payload.model_dump(exclude={"asset_type_id", "rule_config_json"})
    item = KnowledgeRequirementDefinition(**values, rule_config_json=to_json_value(payload.rule_config_json), asset_type_id=None, system_defined=False, configuration_valid=True, created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item)
    flush(db, "Knowledge requirement")
    count = evaluate_assets_for_asset_type(db, None, actor_user_id=principal.user.id)
    add_audit_event(db, action="knowledge_requirement.created", target_type="knowledge_requirement", target_id=item.id, actor=principal.user, summary="Global knowledge requirement created", metadata={"key": item.key, "affected_assets": count}, request=request)
    commit(db, "Knowledge requirement")
    db.refresh(item)
    return _requirement_response(db, item)


def _requirement(db: Session, requirement_id: uuid.UUID) -> KnowledgeRequirementDefinition:
    item = db.get(KnowledgeRequirementDefinition, requirement_id)
    if item is None:
        raise not_found("Knowledge requirement")
    return item


@router.patch("/knowledge-requirements/{requirement_id}", response_model=KnowledgeRequirementResponse)
def update_requirement(requirement_id: uuid.UUID, payload: KnowledgeRequirementUpdate, request: Request, principal: Principal = Depends(require_permission("knowledge_requirements.manage")), db: Session = Depends(get_db)):
    require_global(principal, "knowledge_requirements.manage")
    item = _requirement(db, requirement_id)
    changes = payload.model_dump(exclude_unset=True)
    if "rule_config_json" in changes:
        changes["rule_config_json"] = to_json_value(changes["rule_config_json"])
    rule_type = changes.get("rule_type", item.rule_type)
    config = changes.get("rule_config_json", item.rule_config_json)
    valid, errors, _ = validate_rule_config(db, rule_type, config)
    if not valid:
        raise HTTPException(status_code=422, detail={"message": "Invalid requirement configuration", "errors": errors})
    for key, value in changes.items():
        setattr(item, key, value)
    item.configuration_valid = True
    item.configuration_error = None
    item.updated_by_user_id = principal.user.id
    count = evaluate_assets_for_asset_type(db, item.asset_type_id, actor_user_id=principal.user.id)
    add_audit_event(db, action="knowledge_requirement.updated", target_type="knowledge_requirement", target_id=item.id, actor=principal.user, summary="Knowledge requirement updated", metadata={"changed_fields": sorted(changes), "affected_assets": count}, request=request)
    commit(db, "Knowledge requirement")
    db.refresh(item)
    return _requirement_response(db, item)


@router.delete("/knowledge-requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(requirement_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("knowledge_requirements.manage")), db: Session = Depends(get_db)) -> Response:
    require_global(principal, "knowledge_requirements.manage")
    item = _requirement(db, requirement_id)
    gap_count = int(db.scalar(select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.requirement_definition_id == item.id)) or 0)
    if item.system_defined or gap_count:
        raise HTTPException(status_code=409, detail="Requirement has history and must be deactivated instead of deleted")
    add_audit_event(db, action="knowledge_requirement.deleted", target_type="knowledge_requirement", target_id=item.id, actor=principal.user, summary="Knowledge requirement deleted", metadata={"key": item.key}, request=request)
    db.delete(item)
    commit(db, "Knowledge requirement")
    return Response(status_code=204)


@router.post("/knowledge-requirements/{requirement_id}/activate", response_model=KnowledgeRequirementResponse)
def activate_requirement(requirement_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("knowledge_requirements.manage")), db: Session = Depends(get_db)):
    item = _requirement(db, requirement_id)
    require_global(principal, "knowledge_requirements.manage")
    valid, errors, _ = validate_rule_config(db, item.rule_type, item.rule_config_json)
    if not valid:
        raise HTTPException(status_code=422, detail={"message": "Requirement references are invalid", "errors": errors})
    item.active = True
    item.configuration_valid = True
    item.configuration_error = None
    count = evaluate_assets_for_asset_type(db, item.asset_type_id, actor_user_id=principal.user.id)
    add_audit_event(db, action="knowledge_requirement.activated", target_type="knowledge_requirement", target_id=item.id, actor=principal.user, summary="Knowledge requirement activated", metadata={"affected_assets": count}, request=request)
    commit(db, "Knowledge requirement activation")
    return _requirement_response(db, item)


@router.post("/knowledge-requirements/{requirement_id}/deactivate", response_model=KnowledgeRequirementResponse)
def deactivate_requirement(requirement_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("knowledge_requirements.manage")), db: Session = Depends(get_db)):
    item = _requirement(db, requirement_id)
    require_global(principal, "knowledge_requirements.manage")
    item.active = False
    count = evaluate_assets_for_asset_type(db, item.asset_type_id, actor_user_id=principal.user.id)
    add_audit_event(db, action="knowledge_requirement.deactivated", target_type="knowledge_requirement", target_id=item.id, actor=principal.user, summary="Knowledge requirement deactivated", metadata={"affected_assets": count}, request=request)
    commit(db, "Knowledge requirement deactivation")
    return _requirement_response(db, item)


@router.post("/assets/{asset_id}/evaluate-completeness", response_model=KnowledgeCompletenessSummaryResponse)
def evaluate_asset_endpoint(asset_id: uuid.UUID, principal: Principal = Depends(require_permission("knowledge_completeness.evaluate")), db: Session = Depends(get_db)):
    asset = _asset(db, principal, asset_id, "knowledge_completeness.evaluate")
    summary = evaluate_asset(db, asset, trigger_context="manual_reevaluation", actor_user_id=principal.user.id)
    commit(db, "Knowledge completeness")
    db.refresh(summary)
    return summary


@router.post("/knowledge-completeness/evaluate-batch")
def evaluate_batch(payload: CompletenessBatchRequest, principal: Principal = Depends(require_permission("knowledge_completeness.evaluate")), db: Session = Depends(get_db)):
    require_global(principal, "knowledge_completeness.evaluate")
    count = evaluate_assets_for_asset_type(db, payload.asset_type_id, limit=payload.limit, actor_user_id=principal.user.id)
    commit(db, "Knowledge completeness batch")
    return {"evaluated_assets": count, "bounded_limit": payload.limit}


@router.get("/assets/{asset_id}/completeness", response_model=AssetCompletenessResponse)
def asset_completeness(asset_id: uuid.UUID, principal: Principal = Depends(require_permission("knowledge_gaps.view")), db: Session = Depends(get_db)):
    asset = _asset(db, principal, asset_id, "knowledge_gaps.view")
    summary = db.scalar(select(KnowledgeCompletenessSummary).where(KnowledgeCompletenessSummary.entity_type == "asset", KnowledgeCompletenessSummary.entity_id == asset.id))
    if summary is None:
        summary = KnowledgeCompletenessSummary(
            entity_type="asset", entity_id=asset.id,
            customer_id=asset.customer_id, site_id=asset.site_id,
            required_total=0, required_satisfied=0,
            recommended_total=0, recommended_satisfied=0,
            critical_gap_count=0, high_gap_count=0, open_gap_count=0,
            exception_count=0, completeness_status="not_evaluated",
            last_evaluated_at=None,
        )
    gaps = list(db.scalars(select(KnowledgeGap).where(KnowledgeGap.entity_type == "asset", KnowledgeGap.entity_id == asset.id).order_by(KnowledgeGap.created_at.desc()).limit(500)))
    return {"asset_id": asset.id, "summary": summary, "active_gaps": [_gap_response(db, item) for item in gaps if item.status in ACTIVE_GAP_STATUSES], "resolved_gaps": [_gap_response(db, item) for item in gaps if item.status not in ACTIVE_GAP_STATUSES]}


def _gap_query(context: RequestContext, principal: Principal):
    query = select(KnowledgeGap).where(scope_condition(principal, "knowledge_gaps.view", KnowledgeGap.customer_id, KnowledgeGap.site_id))
    if context.customer_id:
        query = query.where(KnowledgeGap.customer_id == context.customer_id)
    if context.site_id:
        query = query.where(KnowledgeGap.site_id == context.site_id)
    return query


@router.get("/knowledge-gaps", response_model=list[KnowledgeGapResponse])
def list_gaps(context: RequestContext, principal: Principal = Depends(require_permission("knowledge_gaps.view")), asset_type_id: uuid.UUID | None = None, requirement_id: uuid.UUID | None = None, severity: str | None = None, requirement_level: str | None = None, gap_status: str | None = Query(default=None, alias="status"), assigned_user_id: uuid.UUID | None = None, minimum_age_days: int | None = Query(default=None, ge=0), limit: int = Query(default=200, ge=1, le=500), db: Session = Depends(get_db)):
    query = _gap_query(context, principal)
    if asset_type_id: query = query.where(KnowledgeGap.asset_type_id_snapshot == asset_type_id)
    if requirement_id: query = query.where(KnowledgeGap.requirement_definition_id == requirement_id)
    if severity: query = query.where(KnowledgeGap.severity == severity)
    if requirement_level: query = query.where(KnowledgeGap.requirement_level == requirement_level)
    if gap_status: query = query.where(KnowledgeGap.status == gap_status)
    else: query = query.where(KnowledgeGap.status.in_(ACTIVE_GAP_STATUSES))
    if assigned_user_id: query = query.where(KnowledgeGap.assigned_to_user_id == assigned_user_id)
    if minimum_age_days is not None: query = query.where(KnowledgeGap.first_detected_at <= datetime.now(timezone.utc) - timedelta(days=minimum_age_days))
    return [_gap_response(db, item) for item in db.scalars(query.order_by(KnowledgeGap.severity, KnowledgeGap.first_detected_at).limit(limit))]


@router.get("/knowledge-gaps/summary", response_model=GapSummaryResponse)
def gap_summary(context: RequestContext, principal: Principal = Depends(require_permission("knowledge_gaps.view")), db: Session = Depends(get_db)):
    gaps = list(db.scalars(_gap_query(context, principal)))
    active_open = [item for item in gaps if item.status in {"open", "deferred"}]
    summaries = list(db.scalars(select(KnowledgeCompletenessSummary).where(scope_condition(principal, "knowledge_gaps.view", KnowledgeCompletenessSummary.customer_id, KnowledgeCompletenessSummary.site_id))))
    if context.customer_id: summaries = [item for item in summaries if item.customer_id == context.customer_id]
    if context.site_id: summaries = [item for item in summaries if item.site_id == context.site_id]
    asset_count_query = select(func.count()).select_from(Asset).where(
        scope_condition(principal, "knowledge_gaps.view", Asset.customer_id, Asset.site_id)
    )
    if context.customer_id: asset_count_query = asset_count_query.where(Asset.customer_id == context.customer_id)
    if context.site_id: asset_count_query = asset_count_query.where(Asset.site_id == context.site_id)
    asset_count = int(db.scalar(asset_count_query) or 0)
    now = datetime.now(timezone.utc)
    return {"open_knowledge_gap_count": sum(item.requirement_level in {"required", "conditional"} for item in active_open), "critical_knowledge_gap_count": sum(item.severity == "critical" for item in active_open), "high_knowledge_gap_count": sum(item.severity == "high" for item in active_open), "assets_with_critical_gaps": len({item.entity_id for item in active_open if item.severity == "critical"}), "assets_not_evaluated": max(0, asset_count - sum(item.completeness_status != "not_evaluated" for item in summaries)), "assets_operationally_complete": sum(item.completeness_status in {"complete", "operationally_complete", "exception_accepted"} for item in summaries), "expired_exception_count": sum(item.status == "exception" and item.exception_expires_at and item.exception_expires_at <= now for item in gaps)}


def _scoped_gap(db: Session, principal: Principal, gap_id: uuid.UUID, permission: str) -> tuple[KnowledgeGap, Asset]:
    gap = db.get(KnowledgeGap, gap_id)
    if gap is None: raise not_found("Knowledge gap")
    require_scope(principal, permission, gap.customer_id, gap.site_id, hide_existence=True)
    asset = db.get(Asset, gap.entity_id)
    if asset is None: raise HTTPException(status_code=409, detail="Gap entity is unavailable")
    return gap, asset


def _audit_gap_action(db: Session, request: Request, principal: Principal, gap: KnowledgeGap, asset: Asset, action: str, metadata: dict | None = None) -> None:
    add_audit_event(
        db, action=f"knowledge_gap.{action}", target_type="knowledge_gap",
        target_id=gap.id, actor=principal.user, workspace_id=asset.workspace_id,
        customer_id=gap.customer_id, site_id=gap.site_id,
        summary=f"Knowledge gap {action.replace('_', ' ')}",
        metadata={"asset_id": asset.id, "requirement_definition_id": gap.requirement_definition_id, **(metadata or {})},
        request=request,
    )


@router.post("/knowledge-gaps/{gap_id}/defer", response_model=KnowledgeGapResponse)
def defer_gap(gap_id: uuid.UUID, payload: GapDeferRequest, request: Request, principal: Principal = Depends(require_permission("knowledge_gaps.defer")), db: Session = Depends(get_db)):
    gap, asset = _scoped_gap(db, principal, gap_id, "knowledge_gaps.defer")
    if gap.status not in {"open", "deferred"}:
        raise HTTPException(status_code=409, detail="Only an open or deferred gap can be deferred")
    gap.status = "deferred"; gap.deferred_until = payload.deferred_until; gap.deferred_by_user_id = principal.user.id; gap.resolution_reason = payload.reason; gap.last_state_changed_at = datetime.now(timezone.utc)
    record_change(db, customer_id=gap.customer_id, site_id=gap.site_id, change_type="knowledge_gap_deferred", entity_type="asset", entity_id=asset.id, entity_name=asset.name, summary=f"Deferred {gap.summary}", actor_user_id=principal.user.id, metadata={"gap_id": gap.id, "reason": payload.reason, "deferred_until": payload.deferred_until})
    _audit_gap_action(db, request, principal, gap, asset, "deferred", {"reason": payload.reason, "deferred_until": payload.deferred_until})
    evaluate_asset(db, asset, trigger_context="gap_deferred", actor_user_id=principal.user.id); commit(db, "Knowledge gap deferral")
    return _gap_response(db, gap)


@router.post("/knowledge-gaps/{gap_id}/exception", response_model=KnowledgeGapResponse)
def except_gap(gap_id: uuid.UUID, payload: GapExceptionRequest, request: Request, principal: Principal = Depends(require_permission("knowledge_gaps.exception")), db: Session = Depends(get_db)):
    gap, asset = _scoped_gap(db, principal, gap_id, "knowledge_gaps.exception")
    if gap.status not in {"open", "deferred", "exception"}:
        raise HTTPException(status_code=409, detail="Only an active gap can receive an exception")
    now = datetime.now(timezone.utc); gap.status = "exception"; gap.exception_reason = payload.reason; gap.exception_created_at = now; gap.exception_created_by_user_id = principal.user.id; gap.exception_expires_at = payload.expires_at; gap.last_state_changed_at = now
    record_change(db, customer_id=gap.customer_id, site_id=gap.site_id, change_type="knowledge_gap_exception_created", entity_type="asset", entity_id=asset.id, entity_name=asset.name, summary=f"Excepted {gap.summary}: {payload.reason}", actor_user_id=principal.user.id, metadata={"gap_id": gap.id, "expires_at": payload.expires_at})
    _audit_gap_action(db, request, principal, gap, asset, "exception_created", {"reason": payload.reason, "expires_at": payload.expires_at})
    evaluate_asset(db, asset, trigger_context="gap_exception", actor_user_id=principal.user.id); commit(db, "Knowledge gap exception")
    return _gap_response(db, gap)


@router.post("/knowledge-gaps/{gap_id}/reopen", response_model=KnowledgeGapResponse)
def reopen_gap(gap_id: uuid.UUID, payload: GapReopenRequest, request: Request, principal: Principal = Depends(require_permission("knowledge_gaps.exception")), db: Session = Depends(get_db)):
    gap, asset = _scoped_gap(db, principal, gap_id, "knowledge_gaps.exception")
    if gap.status not in {"deferred", "exception"}:
        raise HTTPException(status_code=409, detail="Only a deferred or excepted gap can be reopened")
    gap.status = "open"; gap.deferred_until = None; gap.last_state_changed_at = datetime.now(timezone.utc); gap.resolution_reason = payload.reason
    _audit_gap_action(db, request, principal, gap, asset, "reopened", {"reason": payload.reason})
    evaluate_asset(db, asset, trigger_context="gap_reopened", actor_user_id=principal.user.id); commit(db, "Knowledge gap reopen")
    return _gap_response(db, gap)


@router.post("/knowledge-gaps/{gap_id}/assign", response_model=KnowledgeGapResponse)
def assign_gap(gap_id: uuid.UUID, payload: GapAssignRequest, request: Request, principal: Principal = Depends(require_permission("knowledge_gaps.assign")), db: Session = Depends(get_db)):
    gap, asset = _scoped_gap(db, principal, gap_id, "knowledge_gaps.assign")
    if gap.status not in ACTIVE_GAP_STATUSES:
        raise HTTPException(status_code=409, detail="Only an active gap can be assigned")
    if payload.user_id and db.get(User, payload.user_id) is None: raise not_found("User")
    gap.assigned_to_user_id = payload.user_id
    _audit_gap_action(db, request, principal, gap, asset, "assigned", {"assigned_to_user_id": payload.user_id})
    commit(db, "Knowledge gap assignment")
    return _gap_response(db, gap)


@router.post("/knowledge-gaps/{gap_id}/resolve", response_model=KnowledgeGapResponse)
def resolve_gap(gap_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("knowledge_completeness.evaluate")), db: Session = Depends(get_db)):
    gap, asset = _scoped_gap(db, principal, gap_id, "knowledge_completeness.evaluate")
    evaluate_asset(db, asset, trigger_context="manual_resolution_check", actor_user_id=principal.user.id)
    if gap.status in ACTIVE_GAP_STATUSES:
        db.rollback()
        raise HTTPException(status_code=409, detail="Provide the missing knowledge or record an exception; the requirement is not satisfied")
    _audit_gap_action(db, request, principal, gap, asset, "resolution_confirmed")
    commit(db, "Knowledge gap resolution")
    return _gap_response(db, gap)
