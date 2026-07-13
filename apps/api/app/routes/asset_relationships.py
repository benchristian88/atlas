import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import Asset, AssetRelationship
from app.routes.crud_helpers import commit, not_found
from app.schemas import AssetRelationshipCreate, AssetRelationshipResponse

router = APIRouter(prefix="/asset-relationships", tags=["asset relationships"])


@router.get("", response_model=list[AssetRelationshipResponse])
def list_asset_relationships(
    _: CurrentUser,
    asset_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(AssetRelationship).order_by(AssetRelationship.created_at).limit(limit).offset(offset)
    if asset_id is not None:
        query = query.where(
            or_(
                AssetRelationship.source_asset_id == asset_id,
                AssetRelationship.target_asset_id == asset_id,
            )
        )
    return list(db.scalars(query))


@router.post("", response_model=AssetRelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_asset_relationship(
    payload: AssetRelationshipCreate,
    _: CurrentUser,
    db: Session = Depends(get_db),
):
    if payload.source_asset_id == payload.target_asset_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Source and target assets must be different")
    if db.get(Asset, payload.source_asset_id) is None:
        raise not_found("Source asset")
    if db.get(Asset, payload.target_asset_id) is None:
        raise not_found("Target asset")
    relationship = AssetRelationship(**payload.model_dump(), metadata_={})
    db.add(relationship)
    commit(db, "Asset relationship")
    db.refresh(relationship)
    return relationship


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset_relationship(
    relationship_id: uuid.UUID,
    _: CurrentUser,
    db: Session = Depends(get_db),
) -> Response:
    relationship = db.get(AssetRelationship, relationship_id)
    if relationship is None:
        raise not_found("Asset relationship")
    db.delete(relationship)
    commit(db, "Asset relationship")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
