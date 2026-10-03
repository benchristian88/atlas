"""Improve built-in Service requirement descriptions without replacing custom copy.

Revision ID: 20260910_0017
Revises: 20260910_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0017"
down_revision = "20260910_0016"
branch_labels = None
depends_on = None

# Immutable built-in keys and exact historical descriptions, never display-name matching.
DESCRIPTIONS = (
    ('service_name', 'Default C1 Service knowledge requirement: Name.', 'Every Service must have a meaningful name.'),
    ('service_type', 'Default C1 Service knowledge requirement: Service type.', 'Classifies the operational capability.'),
    ('service_purpose', 'Default C1 Service knowledge requirement: Purpose.', 'Explains what this Service provides and why it exists.'),
    ('service_criticality', 'Default C1 Service knowledge requirement: Criticality.', 'Identifies the importance of this Service.'),
    ('service_asset_dependency', 'Default C1 Service knowledge requirement: Asset dependency.', 'Ensures managed Services are linked to the infrastructure that provides them.'),
    ('service_owner', 'Default C1 Service knowledge requirement: Owner.', 'Identifies who is accountable for this Service.'),
    ('service_contact', 'Default C1 Service knowledge requirement: Technical contact or support group.', 'Identifies who can support or restore this Service.'),
    ('service_rto', 'Default C1 Service knowledge requirement: Recovery time objective.', 'Defines the target time to restore this Service after disruption.'),
    ('service_rpo', 'Default C1 Service knowledge requirement: Recovery point objective.', 'Defines the acceptable amount of data loss after disruption.'),
    ('service_recovery_guidance', 'Default C1 Service knowledge requirement: Recovery guidance.', 'Provides enough information to guide recovery.'),
    ('service_business_function', 'Default C1 Service knowledge requirement: Business function.', 'Links the Service to the outcome it supports.'),
    ('critical_service_rto', 'Default C1 Service knowledge requirement: Critical-service RTO.', 'Ensures higher-criticality Services have an explicit recovery time objective.'),
    ('critical_service_rpo', 'Default C1 Service knowledge requirement: Critical-service RPO.', 'Ensures higher-criticality Services have an explicit recovery point objective.'),
    ('critical_service_owner', 'Default C1 Service knowledge requirement: Critical-service owner.', 'Identifies who is accountable for higher-criticality Services.'),
    ('critical_service_contact', 'Default C1 Service knowledge requirement: Critical-service contact.', 'Identifies who can support or restore higher-criticality Services.'),
    ('critical_service_recovery', 'Default C1 Service knowledge requirement: Critical-service recovery guidance.', 'Ensures higher-criticality Services have guidance for recovery.'),
)


def upgrade() -> None:
    requirements = sa.table(
        "knowledge_requirement_definitions",
        sa.column("key", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("entity_type", sa.String()),
        sa.column("system_defined", sa.Boolean()),
        sa.column("asset_type_id", sa.Uuid()),
        sa.column("service_type_id", sa.Uuid()),
    )
    for key, original, description in DESCRIPTIONS:
        op.execute(requirements.update().where(
            requirements.c.key == key,
            requirements.c.entity_type == "service",
            requirements.c.system_defined.is_(True),
            requirements.c.asset_type_id.is_(None),
            requirements.c.service_type_id.is_(None),
            requirements.c.description == original,
        ).values(description=description))


def downgrade() -> None:
    # Copy-only repair: retain improved text. Reversing could overwrite later
    # administrator choices, and no schema or rule semantics need reverting.
    pass
