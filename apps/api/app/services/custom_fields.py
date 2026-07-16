from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetCustomFieldValue,
    CustomFieldAssetType,
    CustomFieldDefinition,
    CustomFieldOption,
)


# Keep these bounds aligned with AssetCustomFieldValue.value_number Numeric(24, 8).
NUMBER_INTEGER_DIGITS = 16
NUMBER_DECIMAL_DIGITS = 8
NUMBER_ABSOLUTE_LIMIT = Decimal(10) ** NUMBER_INTEGER_DIGITS


def _validated_number(field_name: str, raw_value) -> Decimal:
    if isinstance(raw_value, bool):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a number")
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a number")
    if not value.is_finite():
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be a finite number",
        )
    if value.copy_abs() >= NUMBER_ABSOLUTE_LIMIT:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{field_name} must have at most {NUMBER_INTEGER_DIGITS} digits "
                "before the decimal point"
            ),
        )
    if value:
        sign, digits, exponent = value.as_tuple()
        if exponent < -NUMBER_DECIMAL_DIGITS:
            extra_digits = -NUMBER_DECIMAL_DIGITS - exponent
            if extra_digits > len(digits) or any(digits[-extra_digits:]):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{field_name} must have at most {NUMBER_DECIMAL_DIGITS} "
                        "digits after the decimal point"
                    ),
                )
        while len(digits) > 1 and digits[-1] == 0:
            digits = digits[:-1]
            exponent += 1
        return Decimal((sign, digits, exponent))
    return Decimal(0)


def applicable_definitions(
    db: Session,
    asset_type_key: str,
    *,
    active_only: bool = True,
) -> list[CustomFieldDefinition]:
    query = (
        select(CustomFieldDefinition)
        .outerjoin(
            CustomFieldAssetType,
            CustomFieldAssetType.field_definition_id == CustomFieldDefinition.id,
        )
        .where(
            or_(
                CustomFieldDefinition.applies_to_all_asset_types.is_(True),
                CustomFieldAssetType.asset_type_key == asset_type_key,
            )
        )
        .distinct()
        .order_by(CustomFieldDefinition.sort_order, CustomFieldDefinition.name)
    )
    if active_only:
        query = query.where(CustomFieldDefinition.active.is_(True))
    return list(db.scalars(query))


def active_field_count(db: Session, asset_type_key: str) -> int:
    return len(applicable_definitions(db, asset_type_key, active_only=True))


def ensure_field_limit(db: Session, asset_type_keys: list[str] | None = None) -> None:
    from app.models import AssetType

    keys = asset_type_keys or list(db.scalars(select(AssetType.key)))
    exceeded = [key for key in keys if active_field_count(db, key) > 10]
    if exceeded:
        raise HTTPException(
            status_code=422,
            detail=(
                "At most 10 active custom fields may apply to an asset type. "
                "Limit exceeded for: " + ", ".join(sorted(exceeded))
            ),
        )


def lock_field_limit(db: Session) -> None:
    """Serialize definition mutations that affect the per-type ten-field cap."""

    db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtext('atlas_custom_field_definition_limit'))"
        )
    )


def _option_for_value(
    db: Session, definition: CustomFieldDefinition, raw_value
) -> CustomFieldOption:
    try:
        option_id = uuid.UUID(str(raw_value))
    except (TypeError, ValueError):
        option_id = None
    query = select(CustomFieldOption).where(
        CustomFieldOption.field_definition_id == definition.id,
        CustomFieldOption.active.is_(True),
    )
    if option_id is not None:
        query = query.where(CustomFieldOption.id == option_id)
    else:
        query = query.where(CustomFieldOption.value == str(raw_value))
    option = db.scalar(query)
    if option is None:
        raise HTTPException(
            status_code=422,
            detail=f"{definition.name} must use an active dropdown option",
        )
    return option


def _typed_columns(
    db: Session, definition: CustomFieldDefinition, raw_value
) -> dict:
    empty = {
        "value_text": None,
        "value_number": None,
        "value_date": None,
        "value_bool": None,
        "value_option_id": None,
    }
    data_type = definition.data_type
    if data_type in {"text", "multiline_text", "url"}:
        if not isinstance(raw_value, str):
            raise HTTPException(status_code=422, detail=f"{definition.name} must be text")
        value = raw_value.strip() if data_type != "multiline_text" else raw_value
        if not value:
            raise HTTPException(status_code=422, detail=f"{definition.name} cannot be empty")
        if len(value) > 10000:
            raise HTTPException(status_code=422, detail=f"{definition.name} is too long")
        if data_type == "url":
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise HTTPException(
                    status_code=422,
                    detail=f"{definition.name} must be an absolute HTTP or HTTPS URL",
                )
        empty["value_text"] = value
    elif data_type == "number":
        empty["value_number"] = _validated_number(definition.name, raw_value)
    elif data_type == "date":
        try:
            empty["value_date"] = (
                raw_value if isinstance(raw_value, date) else date.fromisoformat(str(raw_value))
            )
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"{definition.name} must be an ISO date (YYYY-MM-DD)",
            )
    elif data_type == "boolean":
        if not isinstance(raw_value, bool):
            raise HTTPException(status_code=422, detail=f"{definition.name} must be true or false")
        empty["value_bool"] = raw_value
    elif data_type == "dropdown":
        empty["value_option_id"] = _option_for_value(db, definition, raw_value).id
    else:
        raise HTTPException(status_code=422, detail="Unsupported custom-field type")
    return empty


def set_asset_custom_fields(
    db: Session,
    asset: Asset,
    supplied_values: dict,
    *,
    replace_active: bool,
) -> None:
    definitions = applicable_definitions(db, asset.asset_type, active_only=True)
    definitions_by_key = {item.key: item for item in definitions}
    unknown = sorted(set(supplied_values) - set(definitions_by_key))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail="Unknown or inapplicable custom fields: " + ", ".join(unknown),
        )
    missing_required = [
        item.name
        for item in definitions
        if item.required
        and (
            item.key not in supplied_values
            or supplied_values[item.key] is None
            or supplied_values[item.key] == ""
        )
    ]
    if missing_required:
        raise HTTPException(
            status_code=422,
            detail="Required custom fields are missing: " + ", ".join(missing_required),
        )
    existing = {
        item.field_definition_id: item
        for item in db.scalars(
            select(AssetCustomFieldValue).where(AssetCustomFieldValue.asset_id == asset.id)
        )
    }
    if replace_active:
        active_by_id = {item.id: item for item in definitions}
        for field_id, value in list(existing.items()):
            definition = active_by_id.get(field_id)
            if definition is not None and definition.key not in supplied_values:
                db.delete(value)
                existing.pop(field_id, None)
    for key, raw_value in supplied_values.items():
        definition = definitions_by_key[key]
        current = existing.get(definition.id)
        if raw_value is None or raw_value == "":
            if definition.required:
                raise HTTPException(status_code=422, detail=f"{definition.name} is required")
            if current is not None:
                db.delete(current)
            continue
        columns = _typed_columns(db, definition, raw_value)
        if current is None:
            current = AssetCustomFieldValue(
                asset_id=asset.id,
                field_definition_id=definition.id,
                **columns,
            )
            db.add(current)
        else:
            for column, value in columns.items():
                setattr(current, column, value)


def custom_field_values(db: Session, asset: Asset) -> dict[str, object]:
    rows = db.execute(
        select(AssetCustomFieldValue, CustomFieldDefinition, CustomFieldOption)
        .join(
            CustomFieldDefinition,
            CustomFieldDefinition.id == AssetCustomFieldValue.field_definition_id,
        )
        .outerjoin(CustomFieldOption, CustomFieldOption.id == AssetCustomFieldValue.value_option_id)
        .where(AssetCustomFieldValue.asset_id == asset.id)
        .order_by(CustomFieldDefinition.sort_order, CustomFieldDefinition.name)
    ).all()
    values: dict[str, object] = {}
    for stored, definition, option in rows:
        if stored.value_text is not None:
            value = stored.value_text
        elif stored.value_number is not None:
            value = stored.value_number
        elif stored.value_date is not None:
            value = stored.value_date
        elif stored.value_bool is not None:
            value = stored.value_bool
        else:
            value = option.value if option is not None else None
        values[definition.key] = value
    return values
