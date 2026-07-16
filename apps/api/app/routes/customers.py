import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, require_global, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import AccessAssignment, Asset, Customer, Integration, Network, Site, Workspace
from app.routes.crud_helpers import apply_changes, commit, flush, not_found
from app.schemas import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    principal: Principal = Depends(require_permission("customers.view")),
    workspace_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = (
        select(Customer)
        .where(scope_condition(principal, "customers.view", Customer.id))
        .order_by(Customer.name)
        .limit(limit)
        .offset(offset)
    )
    if workspace_id is not None:
        query = query.where(Customer.workspace_id == workspace_id)
    return list(db.scalars(query))


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    request: Request,
    principal: Principal = Depends(require_permission("customers.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "customers.manage")
    workspace = db.get(Workspace, payload.workspace_id) if payload.workspace_id else None
    if payload.workspace_id and workspace is None:
        raise not_found("Workspace")
    if workspace is None:
        workspace = db.scalar(select(Workspace).order_by(Workspace.created_at))
    if workspace is None:
        workspace = Workspace(name="Atlas Workspace", slug="atlas")
        db.add(workspace)
        flush(db, "Workspace")
    values = payload.model_dump(exclude={"workspace_id"})
    customer = Customer(**values, workspace_id=workspace.id)
    db.add(customer)
    flush(db, "Customer")
    add_audit_event(
        db,
        action="customer.created",
        target_type="customer",
        target_id=customer.id,
        actor=principal.user,
        workspace_id=workspace.id,
        customer_id=customer.id,
        summary="Customer created",
        metadata={"name": customer.name},
        request=request,
    )
    commit(db, "Customer")
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: uuid.UUID,
    principal: Principal = Depends(require_permission("customers.view")),
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    require_scope(principal, "customers.view", customer.id, hide_existence=True)
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("customers.manage")),
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    require_scope(principal, "customers.manage", customer.id, hide_existence=True)
    changes = payload.model_dump(exclude_unset=True)
    apply_changes(customer, changes)
    add_audit_event(
        db,
        action="customer.updated",
        target_type="customer",
        target_id=customer.id,
        actor=principal.user,
        workspace_id=customer.workspace_id,
        customer_id=customer.id,
        summary="Customer updated",
        metadata={"changed_fields": sorted(changes)},
        request=request,
    )
    commit(db, "Customer")
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("customers.manage")),
    db: Session = Depends(get_db),
) -> Response:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    require_scope(principal, "customers.manage", customer.id, hide_existence=True)
    dependencies = {
        "sites": (Site, Site.customer_id),
        "assets": (Asset, Asset.customer_id),
        "networks": (Network, Network.customer_id),
        "integrations": (Integration, Integration.customer_id),
        "access assignments": (AccessAssignment, AccessAssignment.customer_id),
    }
    used_by = [
        label
        for label, (model, column) in dependencies.items()
        if db.scalar(select(func.count()).select_from(model).where(column == customer.id))
    ]
    if used_by:
        raise HTTPException(
            status_code=409,
            detail=(
                "Customer is in use by " + ", ".join(used_by) + ". Deactivate it instead."
            ),
        )
    add_audit_event(
        db,
        action="customer.deleted",
        target_type="customer",
        target_id=customer.id,
        actor=principal.user,
        workspace_id=customer.workspace_id,
        summary="Unused customer deleted",
        metadata={"name": customer.name},
        request=request,
    )
    db.delete(customer)
    commit(db, "Customer")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
