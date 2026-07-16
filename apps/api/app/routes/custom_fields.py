from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import (
    Principal,
    require_global,
    require_permission,
    require_scope,
    scope_condition,
)
from app.database import get_db
from app.models import (
    Asset,
    AssetCustomFieldValue,
    AssetType,
    CustomFieldAssetType,
    CustomFieldDefinition,
    CustomFieldOption,
)
from app.schemas import (
    AssetCustomFieldsUpdate,
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionResponse,
    CustomFieldDefinitionUpdate,
)
from app.routes.crud_helpers import commit, flush
from app.services.custom_fields import (
    applicable_definitions,
    custom_field_values,
    ensure_field_limit,
    lock_field_limit,
    set_asset_custom_fields,
)

router = APIRouter(prefix="/custom-fields", tags=["custom fields"])
asset_values_router = APIRouter(prefix="/assets", tags=["asset custom fields"])


def _definition_response(
    db: Session, definition: CustomFieldDefinition, principal: Principal
) -> CustomFieldDefinitionResponse:
    asset_type_keys = list(
        db.scalars(
            select(CustomFieldAssetType.asset_type_key)
            .where(CustomFieldAssetType.field_definition_id == definition.id)
            .order_by(CustomFieldAssetType.asset_type_key)
        )
    )
    options = list(
        db.scalars(
            select(CustomFieldOption)
            .where(CustomFieldOption.field_definition_id == definition.id)
            .order_by(CustomFieldOption.sort_order, CustomFieldOption.label)
        )
    )
    count = int(
        db.scalar(
            select(func.count())
            .select_from(AssetCustomFieldValue)
            .join(Asset, Asset.id == AssetCustomFieldValue.asset_id)
            .where(AssetCustomFieldValue.field_definition_id == definition.id)
            .where(
                scope_condition(
                    principal,
                    "assets.view",
                    Asset.customer_id,
                    Asset.site_id,
                )
            )
        )
        or 0
    )
    return CustomFieldDefinitionResponse.model_validate(
        {
            "id": definition.id,
            "key": definition.key,
            "name": definition.name,
            "description": definition.description,
            "help_text": definition.help_text,
            "data_type": definition.data_type,
            "required": definition.required,
            "active": definition.active,
            "sort_order": definition.sort_order,
            "applies_to_all_asset_types": definition.applies_to_all_asset_types,
            "asset_type_keys": asset_type_keys,
            "options": options,
            "in_use_count": count,
            "created_at": definition.created_at,
            "updated_at": definition.updated_at,
        }
    )


def _validate_applicability(
    db: Session, applies_to_all: bool, keys: list[str]
) -> list[str]:
    keys = sorted(set(keys))
    if applies_to_all and keys:
        raise HTTPException(
            status_code=422,
            detail="A global field cannot also list individual asset types",
        )
    if not applies_to_all and not keys:
        raise HTTPException(
            status_code=422,
            detail="Select at least one asset type or make the field global",
        )
    existing = set(db.scalars(select(AssetType.key).where(AssetType.key.in_(keys))))
    missing = sorted(set(keys) - existing)
    if missing:
        raise HTTPException(
            status_code=422,
            detail="Unknown asset types: " + ", ".join(missing),
        )
    return keys


def _set_applicability(
    db: Session, definition: CustomFieldDefinition, keys: list[str]
) -> None:
    db.execute(
        delete(CustomFieldAssetType).where(
            CustomFieldAssetType.field_definition_id == definition.id
        )
    )
    for key in keys:
        db.add(
            CustomFieldAssetType(
                field_definition_id=definition.id,
                asset_type_key=key,
            )
        )


def _set_options(db: Session, definition: CustomFieldDefinition, supplied) -> None:
    existing = {
        item.value: item
        for item in db.scalars(
            select(CustomFieldOption).where(
                CustomFieldOption.field_definition_id == definition.id
            )
        )
    }
    supplied_values = {item.value for item in supplied}
    for item in supplied:
        option = existing.get(item.value)
        if option is None:
            db.add(
                CustomFieldOption(
                    field_definition_id=definition.id,
                    **item.model_dump(),
                )
            )
        else:
            option.label = item.label
            option.active = item.active
            option.sort_order = item.sort_order
    for value, option in existing.items():
        if value in supplied_values:
            continue
        used = db.scalar(
            select(func.count())
            .select_from(AssetCustomFieldValue)
            .where(AssetCustomFieldValue.value_option_id == option.id)
        )
        if used:
            option.active = False
        else:
            db.delete(option)


def _validate_options(data_type: str, active: bool, supplied) -> None:
    if data_type != "dropdown":
        if supplied:
            raise HTTPException(
                status_code=422, detail="Only dropdown fields accept options"
            )
        return
    if not supplied:
        raise HTTPException(status_code=422, detail="Dropdown fields require options")
    values = [item.value for item in supplied]
    if len(values) != len(set(values)):
        raise HTTPException(
            status_code=422, detail="Dropdown option values must be unique"
        )
    if active and not any(item.active for item in supplied):
        raise HTTPException(
            status_code=422,
            detail="An active dropdown field requires an active option",
        )


@router.get("", response_model=list[CustomFieldDefinitionResponse])
def list_custom_fields(
    principal: Principal = Depends(require_permission("custom_fields.view")),
    active_only: bool = Query(default=False),
    asset_type: str | None = None,
    db: Session = Depends(get_db),
):
    if asset_type:
        definitions = applicable_definitions(db, asset_type, active_only=active_only)
    else:
        query = select(CustomFieldDefinition).order_by(
            CustomFieldDefinition.sort_order, CustomFieldDefinition.name
        )
        if active_only:
            query = query.where(CustomFieldDefinition.active.is_(True))
        definitions = list(db.scalars(query))
    return [_definition_response(db, item, principal) for item in definitions]


@router.post(
    "", response_model=CustomFieldDefinitionResponse, status_code=status.HTTP_201_CREATED
)
def create_custom_field(
    payload: CustomFieldDefinitionCreate,
    request: Request,
    principal: Principal = Depends(require_permission("custom_fields.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "custom_fields.manage")
    lock_field_limit(db)
    _validate_options(payload.data_type, payload.active, payload.options)
    keys = _validate_applicability(
        db, payload.applies_to_all_asset_types, payload.asset_type_keys
    )
    definition = CustomFieldDefinition(
        **payload.model_dump(exclude={"asset_type_keys", "options"})
    )
    db.add(definition)
    flush(db, "Custom field")
    _set_applicability(db, definition, keys)
    _set_options(db, definition, payload.options)
    flush(db, "Custom field")
    try:
        ensure_field_limit(db)
    except HTTPException:
        db.rollback()
        raise
    add_audit_event(
        db,
        action="custom_field.created",
        target_type="custom_field_definition",
        target_id=definition.id,
        actor=principal.user,
        summary="Custom-field definition created",
        metadata={"key": definition.key, "data_type": definition.data_type},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Custom-field key must be unique") from exc
    db.refresh(definition)
    return _definition_response(db, definition, principal)


@router.patch("/{field_id}", response_model=CustomFieldDefinitionResponse)
def update_custom_field(
    field_id: uuid.UUID,
    payload: CustomFieldDefinitionUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("custom_fields.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "custom_fields.manage")
    lock_field_limit(db)
    definition = db.get(CustomFieldDefinition, field_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Custom field not found")
    used_count = int(
        db.scalar(
            select(func.count())
            .select_from(AssetCustomFieldValue)
            .where(AssetCustomFieldValue.field_definition_id == definition.id)
        )
        or 0
    )
    if payload.data_type is not None and payload.data_type != definition.data_type and used_count:
        raise HTTPException(
            status_code=409,
            detail="A field's data type cannot change after values have been stored",
        )
    changes = payload.model_dump(
        exclude_unset=True, exclude={"asset_type_keys", "options"}
    )
    for key, value in changes.items():
        setattr(definition, key, value)
    applies_to_all = definition.applies_to_all_asset_types
    if payload.asset_type_keys is not None or payload.applies_to_all_asset_types is not None:
        current_keys = list(
            db.scalars(
                select(CustomFieldAssetType.asset_type_key).where(
                    CustomFieldAssetType.field_definition_id == definition.id
                )
            )
        )
        keys = _validate_applicability(
            db,
            applies_to_all,
            payload.asset_type_keys if payload.asset_type_keys is not None else current_keys,
        )
        _set_applicability(db, definition, keys)
    final_type = definition.data_type
    final_active = definition.active
    if final_type == "dropdown" and payload.options is None:
        option_count = int(
            db.scalar(
                select(func.count())
                .select_from(CustomFieldOption)
                .where(
                    CustomFieldOption.field_definition_id == definition.id,
                    CustomFieldOption.active.is_(True),
                )
            )
            or 0
        )
        if final_active and option_count == 0:
            raise HTTPException(status_code=422, detail="Dropdown fields require options")
    if payload.options is not None:
        _validate_options(final_type, final_active, payload.options)
        _set_options(db, definition, payload.options)
    elif final_type != "dropdown" and payload.data_type is not None:
        _set_options(db, definition, [])
    flush(db, "Custom field")
    try:
        ensure_field_limit(db)
    except HTTPException:
        db.rollback()
        raise
    add_audit_event(
        db,
        action="custom_field.updated",
        target_type="custom_field_definition",
        target_id=definition.id,
        actor=principal.user,
        summary="Custom-field definition updated",
        metadata={"key": definition.key, "changed_fields": sorted(payload.model_fields_set)},
        request=request,
    )
    db.commit()
    db.refresh(definition)
    return _definition_response(db, definition, principal)


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_field(
    field_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("custom_fields.manage")),
    db: Session = Depends(get_db),
) -> Response:
    require_global(principal, "custom_fields.manage")
    definition = db.get(CustomFieldDefinition, field_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Custom field not found")
    used = db.scalar(
        select(func.count())
        .select_from(AssetCustomFieldValue)
        .where(AssetCustomFieldValue.field_definition_id == definition.id)
    )
    if used:
        raise HTTPException(
            status_code=409,
            detail="Custom field has values. Deactivate it instead of deleting it.",
        )
    add_audit_event(
        db,
        action="custom_field.deleted",
        target_type="custom_field_definition",
        target_id=definition.id,
        actor=principal.user,
        summary="Unused custom-field definition deleted",
        metadata={"key": definition.key},
        request=request,
    )
    db.execute(
        delete(CustomFieldOption).where(
            CustomFieldOption.field_definition_id == definition.id
        )
    )
    db.delete(definition)
    commit(db, "Custom field")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@asset_values_router.get("/{asset_id}/custom-fields", response_model=dict[str, object])
def get_asset_custom_fields(
    asset_id: uuid.UUID,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_scope(
        principal, "assets.view", asset.customer_id, asset.site_id, hide_existence=True
    )
    return custom_field_values(db, asset)


@asset_values_router.put("/{asset_id}/custom-fields", response_model=dict[str, object])
def update_asset_custom_fields(
    asset_id: uuid.UUID,
    payload: AssetCustomFieldsUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("assets.edit")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_scope(
        principal, "assets.edit", asset.customer_id, asset.site_id, hide_existence=True
    )
    set_asset_custom_fields(db, asset, payload.values, replace_active=True)
    add_audit_event(
        db,
        action="asset.custom_fields_updated",
        target_type="asset",
        target_id=asset.id,
        actor=principal.user,
        workspace_id=asset.workspace_id,
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        summary="Asset custom-field values updated",
        metadata={"field_keys": sorted(payload.values)},
        request=request,
    )
    commit(db, "Asset custom fields")
    return custom_field_values(db, asset)
