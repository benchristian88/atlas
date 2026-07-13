import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import Customer, Workspace
from app.routes.crud_helpers import apply_changes, commit, not_found
from app.schemas import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    _: CurrentUser,
    workspace_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Customer).order_by(Customer.name).limit(limit).offset(offset)
    if workspace_id is not None:
        query = query.where(Customer.workspace_id == workspace_id)
    return list(db.scalars(query))


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, _: CurrentUser, db: Session = Depends(get_db)):
    workspace = db.get(Workspace, payload.workspace_id) if payload.workspace_id else None
    if payload.workspace_id and workspace is None:
        raise not_found("Workspace")
    if workspace is None:
        workspace = db.scalar(select(Workspace).order_by(Workspace.created_at))
    if workspace is None:
        workspace = Workspace(name="Atlas Workspace", slug="atlas")
        db.add(workspace)
        commit(db, "Workspace")
        db.refresh(workspace)
    values = payload.model_dump(exclude={"workspace_id"})
    customer = Customer(**values, workspace_id=workspace.id)
    db.add(customer)
    commit(db, "Customer")
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    _: CurrentUser,
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    apply_changes(customer, payload.model_dump(exclude_unset=True))
    commit(db, "Customer")
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)
) -> Response:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    db.delete(customer)
    commit(db, "Customer")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
