"""Site-local workflow decisions over canonical Atlas context."""
from fastapi import HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, forbidden, refresh_principal, require_scope
from app.models import (
    Asset, BusinessFunction, Customer, InstallationState, Integration, Network,
    OnboardingInvitationDismissal, Service, Site, SiteOnboarding,
)
from app.routes.crud_helpers import commit

MANAGE = "sites.manage"
CONFLICT = "Setup progress changed. Reload progress before trying again."


def require_site_access(principal, customer_id, site_id, *, manage):
    if principal.user.force_password_change:
        raise forbidden("You must change your password before continuing")
    require_scope(principal, "customers.view", customer_id, hide_existence=True)
    require_scope(principal, "sites.view", customer_id, site_id, hide_existence=True)
    if manage:
        require_scope(principal, MANAGE, customer_id, site_id, hide_existence=True)


def refreshed_access(db, principal, site, *, manage):
    principal = refresh_principal(principal, db)
    require_site_access(principal, site.customer_id, site.id, manage=manage)
    return principal


def scoped_site(db, principal, customer_id, site_id, *, lock=False, manage=False):
    # A Site grant may read its parent Customer. Mutations remain Site-scoped.
    require_site_access(principal, customer_id, site_id, manage=manage)
    query = (
        select(Site, Customer)
        .join(Customer, Customer.id == Site.customer_id)
        .where(Site.customer_id == customer_id, Site.id == site_id)
    )
    if lock:
        # Allow concurrent starts while preventing a context move or deletion.
        query = query.with_for_update(read=True, key_share=True, of=Site)
    row = db.execute(query).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    if lock:
        principal = refreshed_access(db, principal, row.Site, manage=manage)
    return row.Site, row.Customer, principal


def progress(db: Session, site: Site, *, lock=False):
    query = select(SiteOnboarding).where(
        SiteOnboarding.site_id == site.id, SiteOnboarding.customer_id == site.customer_id,
    )
    return db.scalar(query.with_for_update() if lock else query)


def bootstrap_context(db: Session, site: Site):
    return db.scalar(select(InstallationState.id).where(
        InstallationState.id == 1,
        InstallationState.onboarding_customer_id == site.customer_id,
        InstallationState.onboarding_site_id == site.id,
    )) is not None


def invitation(db: Session, principal: Principal, site: Site, state: SiteOnboarding | None):
    dismissed = db.get(OnboardingInvitationDismissal, principal.user.id) is not None
    if dismissed or state is not None or not bootstrap_context(db, site):
        return {"offered": False, "dismissed": dismissed}

    # Only use records whose existence the operator is permitted to know.
    # Require visibility at every queried scope before assessing emptiness.
    sources = (
        (Asset, "assets.view", False),
        (Integration, "integrations.view", False),
        (Network, "networks.view", True),
        (Service, "services.view", True),
        (BusinessFunction, "business_functions.view", True),
    )
    for _, permission, customer_wide in sources:
        if not principal.can(permission, site.customer_id, site.id):
            return {"offered": False, "dismissed": False}
        if customer_wide and not principal.can(permission, site.customer_id):
            return {"offered": False, "dismissed": False}
    for model, _, customer_wide in sources:
        site_match = model.site_id == site.id
        if customer_wide:
            site_match = or_(site_match, model.site_id.is_(None))
        # A top-level ORM select uses the canonical live-record policy.
        if db.scalar(select(model.id).where(model.customer_id == site.customer_id, site_match).limit(1)) is not None:
            return {"offered": False, "dismissed": False}
    return {"offered": True, "dismissed": False}


def audit(db, customer, site, principal, request: Request, action, *, version=None):
    add_audit_event(
        db, action=f"onboarding.{action}", target_type="site_onboarding",
        target_id=site.id, actor=principal.user, workspace_id=customer.workspace_id,
        customer_id=customer.id, site_id=site.id, request=request,
        summary=f"Guided onboarding {action.replace('_', ' ')}",
        metadata={"version": version} if version is not None else {},
    )


def dismiss(db, customer, site, principal, request):
    if not bootstrap_context(db, site):
        raise HTTPException(status_code=404, detail="Record not found")
    inserted = db.scalar(insert(OnboardingInvitationDismissal).values(
        user_id=principal.user.id,
    ).on_conflict_do_nothing().returning(OnboardingInvitationDismissal.user_id))
    principal = refreshed_access(db, principal, site, manage=False)
    if inserted is not None:
        audit(db, customer, site, principal, request, "invitation_dismissed")
        commit(db, "Onboarding invitation")


def start(db, customer, site, principal, request):
    inserted = db.scalar(insert(SiteOnboarding).values(
        customer_id=customer.id, site_id=site.id, last_actor_id=principal.user.id,
    ).on_conflict_do_nothing(index_elements=[SiteOnboarding.site_id]).returning(SiteOnboarding.site_id))
    principal = refreshed_access(db, principal, site, manage=True)
    state = progress(db, site)
    if inserted is not None:
        audit(db, customer, site, principal, request, "started", version=state.version)
        commit(db, "Onboarding progress")
    return state


def save_first_draft(db, customer, site, principal, request, profile):
    state = db.scalar(insert(SiteOnboarding).values(
        customer_id=customer.id, site_id=site.id, last_actor_id=principal.user.id,
        draft_only=True, draft_profile=profile, status="saved",
    ).on_conflict_do_nothing(index_elements=[SiteOnboarding.site_id]).returning(SiteOnboarding))
    principal = refreshed_access(db, principal, site, manage=True)
    if state is None:
        raise HTTPException(status_code=409, detail=CONFLICT)
    audit(db, customer, site, principal, request, "saved", version=state.version)
    commit(db, "Onboarding progress")
    return state


def update(db, customer, site, principal, request, *, version, action, profile=None):
    state = progress(db, site, lock=True)
    if state is None:
        raise HTTPException(status_code=404, detail="Record not found")
    # A second administrator may have lost access while waiting for the row.
    principal = refreshed_access(db, principal, site, manage=True)

    if action == "resumed" and state.status == "in_progress":
        return state
    if version != state.version:
        raise HTTPException(status_code=409, detail=CONFLICT)
    if state.status == "completed":
        raise HTTPException(status_code=409, detail="This setup is already complete.")

    if action == "environment_confirmed":
        if state.status != "in_progress" or state.current_stage != "environment":
            raise HTTPException(status_code=409, detail=CONFLICT)
        state.environment_profile = profile
        state.draft_profile = None
        state.draft_only = False
        state.stage_decisions = {**state.stage_decisions, "environment": "completed"}
        state.current_stage = "capabilities"
    elif action == "saved":
        if profile is not None and (state.current_stage != "environment" or state.environment_profile is not None):
            raise HTTPException(status_code=409, detail=CONFLICT)
        if state.status == "saved":
            if profile is not None and profile != state.draft_profile:
                raise HTTPException(status_code=409, detail=CONFLICT)
            return state
        if profile is not None:
            state.draft_profile = profile
        state.status = "saved"
    elif action == "resumed":
        state.status = "in_progress"
    else:
        raise ValueError("Unsupported onboarding action")

    record_progress(db, customer, site, principal, request, state, action)
    commit(db, "Onboarding progress")
    return state


def record_progress(db, customer, site, principal, request, state, action):
    state.last_actor_id = principal.user.id
    state.updated_at = db.scalar(select(func.clock_timestamp()))
    state.version += 1
    audit(db, customer, site, principal, request, action, version=state.version)
