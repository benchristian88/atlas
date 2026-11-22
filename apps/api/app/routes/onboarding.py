"""Authenticated preview of the Guided Onboarding foundation."""
from datetime import datetime
import os
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authorization import CurrentPrincipal, Principal, forbidden, scope_condition
from app.database import get_db
from app.models import Customer, Site, SiteOnboarding
from app.services import onboarding

router = APIRouter(prefix="/onboarding", tags=["guided onboarding"])
PAIR = "/{customer_id}/{site_id}"


def preview_principal(
    response: Response,
    principal: CurrentPrincipal,
) -> Principal:
    if os.getenv("ATLAS_ONBOARDING_PREVIEW", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Record not found")
    if principal.user.force_password_change:
        raise forbidden("You must change your password before continuing")
    if not all(principal.can_anywhere(permission) for permission in ("customers.view", "sites.view")):
        raise forbidden()
    response.headers["Cache-Control"] = "no-store"
    return principal


PreviewPrincipal = Annotated[Principal, Depends(preview_principal)]
Database = Annotated[Session, Depends(get_db)]


class ContextName(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str


class OnboardingSite(ContextName):
    customer_id: UUID


class OnboardingCustomer(ContextName):
    can_add_site: bool


WorkflowStatus = Literal["not_started", "in_progress", "saved", "completed"]


class OnboardingSiteOption(OnboardingSite):
    status: WorkflowStatus


class ContextOptions(BaseModel):
    customers: list[OnboardingCustomer]
    sites: list[OnboardingSiteOption]
    can_add_customer: bool


class Progress(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    customer_id: UUID
    site_id: UUID
    environment_profile: str | None
    draft_profile: str | None
    current_stage: str
    stage_decisions: dict[str, Literal["completed", "skipped", "attention"]]
    status: Literal["in_progress", "saved", "completed"]
    version: int
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class Invitation(BaseModel):
    offered: bool
    dismissed: bool


class SiteStatus(BaseModel):
    customer: ContextName
    site: OnboardingSite
    status: WorkflowStatus
    progress: Progress | None
    invitation: Invitation
    can_manage: bool


class VersionedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(strict=True, ge=1, le=2147483647)


class ConfirmEnvironment(VersionedRequest):
    environment_profile: Literal["homelab", "blank"]


class SaveProgress(VersionedRequest):
    version: int = Field(strict=True, ge=0, le=2147483647)
    draft_profile: Literal["homelab", "blank"] | None = None


@router.get("/contexts", response_model=ContextOptions)
def contexts(principal: PreviewPrincipal, db: Database):
    visible = scope_condition(principal, "customers.view", Customer.id)
    rows = db.execute(
        select(Site, SiteOnboarding.status)
        .join(Customer, Customer.id == Site.customer_id)
        .outerjoin(SiteOnboarding, SiteOnboarding.site_id == Site.id)
        .where(
            visible,
            scope_condition(principal, "sites.view", Site.customer_id, Site.id),
            scope_condition(principal, onboarding.MANAGE, Site.customer_id, Site.id),
        ).order_by(Site.name, Site.id)
    )
    sites = [
        OnboardingSiteOption(id=site.id, name=site.name, customer_id=site.customer_id, status=status or "not_started")
        for site, status in rows
    ]
    site_customers = {site.customer_id for site in sites}
    customers = []
    for customer in db.scalars(select(Customer).where(visible).order_by(Customer.name, Customer.id)):
        can_add = principal.can(onboarding.MANAGE, customer.id) and principal.can("sites.view", customer.id)
        if can_add or customer.id in site_customers:
            customers.append(OnboardingCustomer(id=customer.id, name=customer.name, can_add_site=can_add))
    return {
        "customers": customers, "sites": sites,
        "can_add_customer": all(principal.can(permission) for permission in (
            "customers.manage", "customers.view", "sites.manage", "sites.view",
        )),
    }


@router.get(PAIR, response_model=SiteStatus)
def site_status(customer_id: UUID, site_id: UUID, principal: PreviewPrincipal, db: Database):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id)
    state = onboarding.progress(db, site)
    return {
        "customer": customer, "site": site, "progress": state,
        "status": state.status if state else "not_started",
        "invitation": onboarding.invitation(db, principal, site, state),
        "can_manage": principal.can(onboarding.MANAGE, customer.id, site.id),
    }


@router.post(PAIR + "/start", response_model=Progress)
def start(customer_id: UUID, site_id: UUID, request: Request, principal: PreviewPrincipal, db: Database):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return onboarding.start(db, customer, site, principal, request)


@router.patch(PAIR + "/environment", response_model=Progress)
def confirm(
    customer_id: UUID, site_id: UUID, payload: ConfirmEnvironment,
    request: Request, principal: PreviewPrincipal, db: Database,
):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return onboarding.update(
        db, customer, site, principal, request, version=payload.version,
        action="environment_confirmed", profile=payload.environment_profile,
    )


@router.post(PAIR + "/save", response_model=Progress)
def save(
    customer_id: UUID, site_id: UUID, payload: SaveProgress,
    request: Request, principal: PreviewPrincipal, db: Database,
):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    if payload.version == 0:
        if payload.draft_profile is None:
            raise HTTPException(status_code=422, detail="Select an Environment profile to save.")
        return onboarding.save_first_draft(db, customer, site, principal, request, payload.draft_profile)
    return onboarding.update(
        db, customer, site, principal, request, version=payload.version,
        action="saved", profile=payload.draft_profile,
    )


@router.post(PAIR + "/resume", response_model=Progress)
def resume(
    customer_id: UUID, site_id: UUID, payload: VersionedRequest,
    request: Request, principal: PreviewPrincipal, db: Database,
):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return onboarding.update(db, customer, site, principal, request, version=payload.version, action="resumed")


@router.post(PAIR + "/invitation/dismiss", status_code=204)
def dismiss(customer_id: UUID, site_id: UUID, request: Request, principal: PreviewPrincipal, db: Database):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True)
    onboarding.dismiss(db, customer, site, principal, request)
