"""Authenticated preview of the Guided Onboarding foundation."""
from datetime import datetime
import os
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authorization import CurrentPrincipal, Principal, forbidden, scope_condition
from app.database import get_db
from app.models import Customer, Site, SiteOnboarding
from app.services import onboarding, onboarding_capabilities as starter
from app.services import onboarding_link_services as links
from app.services import onboarding_review, onboarding_showcase
from app.services.homelab_catalogue import Catalogue
from app.services.knowledge_locks import concurrent_decision

router = APIRouter(prefix="/onboarding", tags=["guided onboarding"])
PAIR = "/{customer_id}/{site_id}"


def require_preview_enabled():
    if os.getenv("ATLAS_ONBOARDING_PREVIEW", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Record not found")


def preview_principal(
    response: Response,
    principal: CurrentPrincipal,
) -> Principal:
    require_preview_enabled()
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


class DecideIntegrations(VersionedRequest):
    decision: Literal["completed", "skipped"]
    discovery_run_id: UUID | None = None


class DecideDiscoveryReview(VersionedRequest):
    decision: Literal["completed", "attention", "skipped"]
    review_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


LINK_SERVICES = PAIR + "/link-services"
LINK_SERVICE = LINK_SERVICES + "/services/{service_id}"


class DecideLinkServices(VersionedRequest):
    action: Literal["continue", "skip"]
    acknowledge_attention: bool = Field(default=False, strict=True)


class LinkSummary(BaseModel):
    linked: int
    unlinked: int
    mappings: int
    unavailable: int


class ReviewIntegration(ContextName):
    status: str
    discovery_status: str | None
    discovery_configured: bool | None


class ReviewIntegrations(BaseModel):
    items: list[ReviewIntegration]
    has_more: bool


class ReviewDiscoveryDecisions(BaseModel):
    eligible: int
    conflicts: int
    exceptions: int


class ReviewDiscovery(BaseModel):
    decisions: ReviewDiscoveryDecisions | None
    active_runs: int | None


class ReviewReady(BaseModel):
    customer: ContextName
    site: OnboardingSite
    profile: Literal["homelab", "blank"]
    business_functions: int | None
    services: int | None
    integrations: ReviewIntegrations | None
    discovery: ReviewDiscovery
    link_services: LinkSummary | None
    required_gaps: int | None


class ShowcaseServiceExamples(BaseModel):
    total: int
    examples: list[ContextName]


class ShowcaseFunction(ContextName):
    services: ShowcaseServiceExamples | None


class ShowcaseCapabilities(BaseModel):
    total: int
    items: list[ShowcaseFunction]


class ShowcaseAssetType(ContextName):
    count: int


class ShowcaseAssets(BaseModel):
    total: int
    by_type: list[ShowcaseAssetType]
    other_assets: int


class ShowcaseIntegrations(BaseModel):
    total: int
    enabled: int
    disabled: int
    active_runs: int


class Showcase(BaseModel):
    business_functions: ShowcaseCapabilities | None
    services: int | None
    services_without_functions: int | None
    assets: ShowcaseAssets | None
    networks: int | None
    integrations: ShowcaseIntegrations | None
    mappings: LinkSummary | None
    asset_relationships: int | None
    network_memberships: int | None
    required_gaps: int | None
    analysis_focus: str | None


@router.get(PAIR + "/showcase", response_model=Showcase)
def showcase(customer_id: UUID, site_id: UUID, principal: PreviewPrincipal, db: Database):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id)
    return onboarding_showcase.showcase(db, site, customer, principal)


@router.post(PAIR + "/complete", response_model=Progress)
@concurrent_decision
def complete(customer_id: UUID, site_id: UUID, payload: VersionedRequest,
             request: Request, principal: PreviewPrincipal, db: Database):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return onboarding.update(db, customer, site, principal, request, version=payload.version, action="completed")


@router.get(PAIR + "/review-ready", response_model=ReviewReady)
def review_ready(customer_id: UUID, site_id: UUID, principal: PreviewPrincipal, db: Database):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id)
    return onboarding_review.review(db, site, customer, principal)


@router.post(PAIR + "/review-ready/decision", response_model=Progress)
@concurrent_decision
def decide_review_ready(
    customer_id: UUID, site_id: UUID, payload: VersionedRequest, request: Request,
    principal: PreviewPrincipal, db: Database,
):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return onboarding.update(
        db, customer, site, principal, request, version=payload.version, action="review_ready_completed",
    )


class LinkService(ContextName):
    site_id: UUID | None
    service_type_id: UUID
    service_type_icon_key: str | None
    service_type_accent_key: str | None
    mapping_count: int | None


class LinkServicePage(BaseModel):
    summary: LinkSummary | None
    services: list[LinkService]
    has_more: bool


class LinkAsset(ContextName):
    status: str
    asset_type: str
    type_name: str
    hostname: str | None
    cached_icon_url: str | None
    default_icon_url: str | None
    resolved_icon_url: str | None


class SiteMapping(BaseModel):
    id: UUID
    asset: LinkAsset
    site_name: str
    relationship_name: str
    removal_version: str | None


class ConfirmMappingRemoval(BaseModel):
    removal_version: str = Field(pattern=r"^[a-f0-9]{64}$")


class LinkAssetType(BaseModel):
    key: str
    name: str


class LinkMappingPage(BaseModel):
    service_name: str
    can_manage: bool
    site_mappings: list[SiteMapping] | None
    other_mappings: list[SiteMapping] | None
    available: list[LinkAsset] | None
    asset_types: list[LinkAssetType]
    has_eligible_assets: bool
    has_unlinked_assets: bool
    has_more: bool


class AddMappingOutcome(BaseModel):
    outcome: Literal["added", "already_exists"]


@router.get(LINK_SERVICES, response_model=LinkServicePage)
def link_service_page(
    customer_id: UUID, site_id: UUID, principal: PreviewPrincipal, db: Database,
    search: str = Query(default="", max_length=300), mapping: Literal["all", "unlinked", "linked"] = "all",
    offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100),
):
    site, _, principal = links.context(db, principal, customer_id, site_id)
    return links.service_page(db, principal, site, search=search, mapping=mapping, offset=offset, limit=limit)


@router.get(LINK_SERVICE, response_model=LinkMappingPage)
def link_mapping_page(
    customer_id: UUID, site_id: UUID, service_id: UUID, principal: PreviewPrincipal, db: Database,
    search: str = Query(default="", max_length=300), asset_type: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100),
):
    site, _, principal = links.context(db, principal, customer_id, site_id)
    return links.mapping_page(db, principal, site, service_id, search=search, asset_type=asset_type, offset=offset, limit=limit)


@router.post(LINK_SERVICE + "/assets/{asset_id}", response_model=AddMappingOutcome)
@concurrent_decision
def add_link_mapping(
    customer_id: UUID, site_id: UUID, service_id: UUID, asset_id: UUID, request: Request,
    principal: PreviewPrincipal, db: Database,
):
    site, _, principal = links.context(db, principal, customer_id, site_id, write=True)
    return links.add_mapping(db, principal, site, service_id, asset_id, request)


@router.delete(LINK_SERVICE + "/mappings/{dependency_id}", status_code=204)
@concurrent_decision
def remove_link_mapping(
    customer_id: UUID, site_id: UUID, service_id: UUID, dependency_id: UUID,
    payload: ConfirmMappingRemoval, request: Request,
    principal: PreviewPrincipal, db: Database,
):
    site, _, principal = links.context(db, principal, customer_id, site_id, write=True)
    links.remove_mapping(db, principal, site, service_id, dependency_id, payload.removal_version, request)


@router.post(LINK_SERVICES + "/decision", response_model=Progress)
@concurrent_decision
def decide_link_services(
    customer_id: UUID, site_id: UUID, payload: DecideLinkServices, request: Request,
    principal: PreviewPrincipal, db: Database,
):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return links.decide(db, customer, site, principal, request, version=payload.version,
                        action=payload.action, acknowledge_attention=payload.acknowledge_attention)


@router.post(PAIR + "/discovery-review/decision", response_model=Progress)
@concurrent_decision
def decide_discovery_review(
    customer_id: UUID, site_id: UUID, payload: DecideDiscoveryReview, request: Request,
    principal: PreviewPrincipal, db: Database,
):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return onboarding.decide_discovery_review(
        db, customer, site, principal, request, version=payload.version,
        decision=payload.decision, review_version=payload.review_version,
    )


@router.post(PAIR + "/integrations/decision", response_model=Progress)
@concurrent_decision
def decide_integrations(
    customer_id: UUID, site_id: UUID, payload: DecideIntegrations, request: Request,
    principal: PreviewPrincipal, db: Database,
):
    site, customer, principal = onboarding.scoped_site(db, principal, customer_id, site_id, lock=True, manage=True)
    return onboarding.decide_integrations(
        db, customer, site, principal, request, version=payload.version,
        decision=payload.decision, discovery_run_id=payload.discovery_run_id,
    )


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


class CapabilitiesRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded_body(request: Request):
            require_preview_enabled()
            size = 0

            async def receive():
                nonlocal size
                message = await request.receive()
                size += len(message.get("body", b""))
                # Accommodate every allowed text field even with JSON-escaped
                # supplementary Unicode characters.
                if size > 12 * 1024 * 1024:
                    raise HTTPException(413, "Capabilities request is too large.")
                return message

            return await handler(Request(request.scope, receive))

        return bounded_body


capabilities_router = APIRouter(route_class=CapabilitiesRoute)
CAPABILITIES = PAIR + "/capabilities"


class CapabilityPermissions(BaseModel):
    can_manage: bool
    can_view_service_types: bool
    can_view_criticality_levels: bool
    can_create_functions: bool
    can_create_services: bool
    can_create_associations: bool


class CapabilitiesStatus(BaseModel):
    version: int
    profile: Literal["homelab", "blank"]
    permissions: CapabilityPermissions
    catalogue: Catalogue | None
    defaults: starter.Selection | None
    draft: dict | None
    draft_stale: bool
    default_service_type_keys: dict[str, str]
    default_criticality_key: str | None


class PreviewSelection(VersionedRequest):
    selection: starter.Selection


class SaveSelection(PreviewSelection):
    save_and_exit: bool = Field(default=False, strict=True)
    replace_stale_draft: bool = Field(default=False, strict=True)


class ApplySelection(VersionedRequest):
    submission_id: UUID


class SelectionPreview(BaseModel):
    warnings: list[starter.NameWarning]


def capability_context(db, principal, customer_id, site_id, *, write=False, homelab=False):
    site, customer, principal = onboarding.scoped_site(
        db, principal, customer_id, site_id, lock=write, manage=write,
    )
    state = onboarding.progress(db, site, lock=write)
    if write:
        principal = onboarding.refreshed_access(db, principal, site, manage=True)
    starter.require_confirmed(state, homelab=homelab)
    return site, customer, principal, state


@capabilities_router.get(CAPABILITIES, response_model=CapabilitiesStatus, response_model_exclude_unset=True)
def get_capabilities(customer_id: UUID, site_id: UUID, principal: PreviewPrincipal, db: Database):
    site, _, principal, state = capability_context(db, principal, customer_id, site_id)
    return starter.read(state, principal, site)


@capabilities_router.post(CAPABILITIES + "/preview", response_model=SelectionPreview)
def preview_capabilities(
    customer_id: UUID, site_id: UUID, payload: PreviewSelection, principal: PreviewPrincipal, db: Database,
):
    _, customer, principal, state = capability_context(db, principal, customer_id, site_id, homelab=True)
    starter.require_version(state, payload.version)
    functions, services, _ = starter.prepare_selection(db, payload.selection, customer.id, principal)
    return {"warnings": starter.name_warnings(db, principal, customer.id, functions, services)}


@capabilities_router.put(CAPABILITIES + "/draft", response_model=Progress)
@concurrent_decision
def save_capabilities_draft(
    customer_id: UUID, site_id: UUID, payload: SaveSelection, request: Request, principal: PreviewPrincipal, db: Database,
):
    site, customer, principal, state = capability_context(
        db, principal, customer_id, site_id, write=True, homelab=True,
    )
    starter.save_draft(db, customer, site, principal, request, state, payload)
    return state


@capabilities_router.post(CAPABILITIES + "/apply", response_model=starter.ApplyOutcome)
@concurrent_decision
def apply_capabilities(
    customer_id: UUID, site_id: UUID, payload: ApplySelection, request: Request, principal: PreviewPrincipal, db: Database,
):
    site, customer, principal, state = capability_context(
        db, principal, customer_id, site_id, write=True, homelab=True,
    )
    return starter.apply(db, customer, site, principal, request, state, payload)


@capabilities_router.post(CAPABILITIES + "/skip", response_model=Progress)
@concurrent_decision
def skip_capabilities(
    customer_id: UUID, site_id: UUID, payload: VersionedRequest, request: Request, principal: PreviewPrincipal, db: Database,
):
    site, customer, principal, state = capability_context(db, principal, customer_id, site_id, write=True)
    starter.skip(db, customer, site, principal, request, state, payload.version)
    return state


router.include_router(capabilities_router)
