from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import Asset, AssetRelationship, Customer, Site
from app.routes.asset_relationships import relationship_response
from app.schemas import TopologyResponse

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("", response_model=TopologyResponse)
def get_topology(_: CurrentUser, db: Session = Depends(get_db)):
    customers = list(db.scalars(select(Customer).order_by(Customer.name)))
    sites = list(db.scalars(select(Site).order_by(Site.name)))
    assets = list(db.scalars(select(Asset).order_by(Asset.name)))
    relationships = [
        relationship_response(db, item)
        for item in db.scalars(select(AssetRelationship).order_by(AssetRelationship.created_at))
    ]
    return {
        "customers": customers,
        "sites": sites,
        "assets": assets,
        "relationships": relationships,
    }
