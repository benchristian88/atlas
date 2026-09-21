"""Global taxonomy uses the existing Asset Type reference-data permissions."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, require_global, require_permission
from app.database import get_db
from app.models import AssetCategory, AssetType
from app.routes.crud_helpers import commit, flush
from app.schemas import AssetCategoryCreate, AssetCategoryResponse, AssetCategoryUpdate

router = APIRouter(prefix="/asset-categories", tags=["asset categories"])


def category_response(db, item):
    result = AssetCategoryResponse.model_validate(item)
    result.asset_types_count = db.scalar(select(func.count()).select_from(AssetType).where(AssetType.category_id == item.id)) or 0
    return result


@router.get("", response_model=list[AssetCategoryResponse])
def list_categories(
    principal: Principal = Depends(require_permission("asset_types.view")),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = select(AssetCategory).order_by(AssetCategory.sort_order, AssetCategory.name, AssetCategory.id)
    if active_only:
        query = query.where(AssetCategory.active.is_(True))
    return [category_response(db, item) for item in db.scalars(query)]


def audit(db, principal, request, item, action):
    add_audit_event(db, action=f"asset_category.{action}", target_type="asset_category", target_id=item.id,
                   actor=principal.user, summary=f"Asset category {action}", metadata={"key": item.key, "name": item.name}, request=request)


@router.post("", response_model=AssetCategoryResponse, status_code=201)
def create_category(payload: AssetCategoryCreate, request: Request,
                    principal: Principal = Depends(require_permission("asset_types.manage")), db: Session = Depends(get_db)):
    require_global(principal, "asset_types.manage")
    if payload.key == "uncategorized":
        raise HTTPException(409, "Uncategorized is a protected built-in category")
    item = AssetCategory(**payload.model_dump())
    db.add(item)
    flush(db, "Asset category")
    audit(db, principal, request, item, "created")
    commit(db, "Asset category")
    db.refresh(item)
    return category_response(db, item)


@router.patch("/{category_id}", response_model=AssetCategoryResponse)
def update_category(category_id: uuid.UUID, payload: AssetCategoryUpdate, request: Request,
                    principal: Principal = Depends(require_permission("asset_types.manage")), db: Session = Depends(get_db)):
    require_global(principal, "asset_types.manage")
    item = db.get(AssetCategory, category_id)
    if item is None:
        raise HTTPException(404, "Asset category not found")
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None and key != "description" for key, value in changes.items()):
        raise HTTPException(422, "Category fields must not be null")
    if item.key == "uncategorized" and (changes.get("active") is False or changes.get("name", item.name) != "Uncategorized"):
        raise HTTPException(409, "Uncategorized must remain active and retain its name")
    for key, value in changes.items():
        setattr(item, key, value)
    audit(db, principal, request, item, "updated")
    commit(db, "Asset category")
    db.refresh(item)
    return category_response(db, item)


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, request: Request,
                    principal: Principal = Depends(require_permission("asset_types.manage")), db: Session = Depends(get_db)):
    require_global(principal, "asset_types.manage")
    item = db.get(AssetCategory, category_id)
    if item is None:
        raise HTTPException(404, "Asset category not found")
    if item.key == "uncategorized":
        raise HTTPException(409, "Uncategorized cannot be deleted")
    if db.scalar(select(func.count()).select_from(AssetType).where(AssetType.category_id == item.id)):
        raise HTTPException(409, "Reassign this category's Asset Types before deleting it")
    audit(db, principal, request, item, "deleted")
    db.delete(item)
    commit(db, "Asset category")
    return Response(status_code=204)
