"""Response-shaping helpers shared by authentication and administration routes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authorization import Principal, role_names
from app.models import Asset, AssetType, KnowledgeCompletenessSummary
from app.services.custom_fields import custom_field_values
from app.services.asset_icons import icon_fields


def user_response_data(principal: Principal, *, administrative: bool = False) -> dict:
    user = principal.user
    data = {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "accent_colour": user.accent_colour,
        "theme_mode": user.theme_mode or "system",
        "is_active": user.is_active,
        "force_password_change": user.force_password_change,
        "last_login_at": user.last_login_at,
        "roles": role_names(principal),
        "permissions": sorted(principal.permissions),
        "assignments": [
            {
                "id": grant.assignment_id,
                "role_id": grant.role_id,
                "role_name": grant.role_name,
                "scope_type": grant.scope_type,
                "customer_id": grant.customer_id,
                "site_id": grant.site_id,
                "permissions": sorted(grant.permissions),
            }
            for grant in principal.grants
        ],
    }
    if administrative:
        data.update(
            failed_login_count=user.failed_login_count,
            locked_until=user.locked_until,
            auth_provider=user.auth_provider,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    return data


def asset_response_data(db: Session, asset: Asset) -> dict:
    asset_type = db.scalar(select(AssetType).where(AssetType.key == asset.asset_type))
    completeness = db.scalar(
        select(KnowledgeCompletenessSummary).where(
            KnowledgeCompletenessSummary.entity_type == "asset",
            KnowledgeCompletenessSummary.entity_id == asset.id,
        )
    )
    if not isinstance(completeness, KnowledgeCompletenessSummary):
        completeness = None
    return {
        "id": asset.id,
        "workspace_id": asset.workspace_id,
        "customer_id": asset.customer_id,
        "site_id": asset.site_id,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "icon_url": asset.icon_url,
        **icon_fields(asset, asset_type),
        "vendor": asset.vendor,
        "model": asset.model,
        "hostname": asset.hostname,
        "ip_address": asset.ip_address,
        "status": asset.status,
        "description": asset.description,
        "source": asset.source,
        "metadata_": asset.metadata_,
        "custom_fields": custom_field_values(db, asset),
        "completeness_status": completeness.completeness_status if completeness else "not_evaluated",
        "open_knowledge_gap_count": completeness.open_gap_count if completeness else 0,
        "critical_knowledge_gap_count": completeness.critical_gap_count if completeness else 0,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }
