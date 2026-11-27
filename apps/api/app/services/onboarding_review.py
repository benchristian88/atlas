"""Live, read-only projections for the confirmed Site's advisory review."""

from fastapi import HTTPException
from sqlalchemy import func

from app.authorization import ActiveContext
from app.models import BusinessFunction, KnowledgeGap
from app.routes.business_functions import scoped_business_functions
from app.routes.integrations import read_configured_integrations
from app.services import onboarding, onboarding_link_services as links
from app.services.discovery_review import DiscoveryReview
from app.services.knowledge_completeness import OPEN_GAP_STATUSES, REQUIRED_GAP_LEVELS, scoped_completeness_query

INTEGRATION_LIMIT = 500


def integration_summary(db, context, principal):
    rows = read_configured_integrations(
        db, context, principal, active_only=True, include_discovery=True, include_continuation=False,
        limit=INTEGRATION_LIMIT + 1,
    )
    return {
        "items": [{
            "id": row["id"],
            "name": row["name"],
            "status": row["status"],
            "discovery_status": row["run"]["status"] if row["run"] else None,
            "discovery_configured": row["discovery_configured"] if row.get("discovery_capable") else None,
        } for row in rows[:INTEGRATION_LIMIT]],
        "has_more": len(rows) > INTEGRATION_LIMIT,
    }


def review(db, site, customer, principal):
    state = onboarding.progress(db, site)
    if state is None or not state.environment_profile or not (
        state.current_stage == "review_ready" or "review_ready" in state.stage_decisions
    ):
        raise HTTPException(404, "Record not found")

    context = ActiveContext(customer.id, site.id)

    def can(permission):
        return principal.can(permission, customer.id, site.id)

    functions = None
    if can("business_functions.view"):
        query = scoped_business_functions(context, principal, active_only=True)
        functions = db.scalar(query.with_only_columns(func.count(BusinessFunction.id)))
    # Every active scoped Service falls into exactly one bucket, including
    # Services whose relationships the operator cannot see.
    mappings = links.summary(db, principal, site)
    services = None if mappings is None else mappings["linked"] + mappings["unlinked"] + mappings["unavailable"]

    required_gaps = None
    if can("knowledge_gaps.view"):
        query = scoped_completeness_query(KnowledgeGap, context, principal, include_customer_wide=True)
        required_gaps = db.scalar(query.with_only_columns(func.count(KnowledgeGap.id)).where(
            KnowledgeGap.status.in_(OPEN_GAP_STATUSES),
            KnowledgeGap.requirement_level.in_(REQUIRED_GAP_LEVELS),
        ))

    return {
        "customer": customer,
        "site": site,
        "profile": state.environment_profile,
        "business_functions": functions,
        "services": services,
        "integrations": integration_summary(db, context, principal) if can("integrations.view") else None,
        "discovery": DiscoveryReview(db, context, principal).attention_counts(),
        "link_services": mappings if can("assets.view") and can(links.VIEW) else None,
        "required_gaps": required_gaps,
    }
