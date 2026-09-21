import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("theme_mode IN ('light', 'dark', 'system')", name="theme_mode"),
        UniqueConstraint(
            "auth_provider",
            "external_subject",
            name="uq_users_auth_provider_external_subject",
        ),
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    accent_colour: Mapped[str | None] = mapped_column(String(7))
    theme_mode: Mapped[str | None] = mapped_column(String(6))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    force_password_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    auth_provider: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="local", index=True
    )
    external_subject: Mapped[str | None] = mapped_column(String(255))
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    system_defined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    system_defined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AccessAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "access_assignments"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'global' AND customer_id IS NULL AND site_id IS NULL) OR "
            "(scope_type = 'customer' AND customer_id IS NOT NULL AND site_id IS NULL) OR "
            "(scope_type = 'site' AND customer_id IS NOT NULL AND site_id IS NOT NULL)",
            name="valid_scope",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_access_assignments_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_access_assignments_global",
            "user_id",
            "role_id",
            unique=True,
            postgresql_where=text("scope_type = 'global'"),
        ),
        Index(
            "uq_access_assignments_customer",
            "user_id",
            "role_id",
            "customer_id",
            unique=True,
            postgresql_where=text("scope_type = 'customer'"),
        ),
        Index(
            "uq_access_assignments_site",
            "user_id",
            "role_id",
            "site_id",
            unique=True,
            postgresql_where=text("scope_type = 'site'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)


UNCATEGORIZED_ID = uuid.UUID("cbb23449-f856-5a92-a031-02c83946b579")


class AssetCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_categories"
    __table_args__ = (
        CheckConstraint("key <> 'uncategorized' OR active", name="uncategorized_active"),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    # Exact names preserve distinct legacy values, including case differences.
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100", index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    show_in_topology: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class AssetType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_types"
    __table_args__ = (
        Index("uq_asset_types_name_lower", text("lower(name)"), unique=True),
    )

    key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Frozen upgrade snapshot; never read or edited as managed taxonomy.
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset_categories.id", ondelete="RESTRICT"), nullable=False,
        index=True, server_default=str(UNCATEGORIZED_ID),
    )
    category_record: Mapped["AssetCategory"] = relationship(lazy="joined")
    default_icon_url: Mapped[str | None] = mapped_column(String(2048))
    system_defined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", index=True
    )


class RelationshipType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "relationship_types"
    __table_args__ = (
        Index(
            "uq_relationship_types_name_lower",
            text("lower(name)"),
            unique=True,
        ),
    )

    key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)
    inverse_label: Mapped[str | None] = mapped_column(String(255))
    directional: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    system_defined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", index=True
    )
    allowed_source_asset_type_keys: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    allowed_target_asset_type_keys: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )


class RelationshipTypeApplicability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Allowed endpoint-kind pair for a relationship type.

    Asset-only relationship types created before C1 remain valid for the legacy
    asset-to-asset path. New service dependency paths require an explicit row.
    """

    __tablename__ = "relationship_type_applicabilities"
    __table_args__ = (
        UniqueConstraint(
            "relationship_type_id",
            "source_entity_type",
            "target_entity_type",
            name="uq_relationship_type_applicability_endpoints",
        ),
        CheckConstraint(
            "source_entity_type IN ('asset', 'service', 'business_function')",
            name="valid_source_entity_type",
        ),
        CheckConstraint(
            "target_entity_type IN ('asset', 'service', 'business_function')",
            name="valid_target_entity_type",
        ),
    )

    relationship_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_customers_workspace_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="active", index=True
    )


class Site(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (
        UniqueConstraint("customer_id", "name", name="uq_sites_customer_name"),
        UniqueConstraint("customer_id", "id", name="uq_sites_customer_id_id"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="active", index=True
    )


class ServiceType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_types"
    __table_args__ = (
        Index("uq_service_types_name_lower", text("lower(name)"), unique=True),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon_key: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    system_defined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100", index=True
    )
    requires_asset_dependency: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class CriticalityLevel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "criticality_levels"
    __table_args__ = (
        Index("uq_criticality_levels_name_lower", text("lower(name)"), unique=True),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    default_rto_minutes: Mapped[int | None] = mapped_column(Integer)
    default_rpo_minutes: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    system_defined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100", index=True
    )


class Service(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_services_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_services_customer_name_without_site",
            "customer_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("site_id IS NULL AND archived_at IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_services_customer_site_name",
            "customer_id",
            "site_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("site_id IS NOT NULL AND archived_at IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_services_customer_slug_without_site",
            "customer_id",
            "slug",
            unique=True,
            postgresql_where=text("site_id IS NULL AND archived_at IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_services_customer_site_slug",
            "customer_id",
            "site_id",
            "slug",
            unique=True,
            postgresql_where=text("site_id IS NOT NULL AND archived_at IS NULL AND deleted_at IS NULL"),
        ),
        CheckConstraint("rto_minutes IS NULL OR rto_minutes >= 0", name="valid_rto_minutes"),
        CheckConstraint("rpo_minutes IS NULL OR rpo_minutes >= 0", name="valid_rpo_minutes"),
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    service_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    criticality_level_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("criticality_levels.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="active", index=True
    )
    operational_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="unknown", index=True
    )
    owner_name: Mapped[str | None] = mapped_column(String(255))
    technical_contact: Mapped[str | None] = mapped_column(String(255))
    support_group: Mapped[str | None] = mapped_column(String(255))
    documentation_url: Mapped[str | None] = mapped_column(String(2048))
    runbook_url: Mapped[str | None] = mapped_column(String(2048))
    rto_minutes: Mapped[int | None] = mapped_column(Integer)
    rpo_minutes: Mapped[int | None] = mapped_column(Integer)
    backup_notes: Mapped[str | None] = mapped_column(Text)
    recovery_notes: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="manual", index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    archive_reason: Mapped[str | None] = mapped_column(Text)


class ServiceAssetDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_asset_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_service_asset_dependencies_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_service_asset_dependencies_active_edge",
            "service_id", "asset_id", "relationship_type_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    relationship_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    required_for_operation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False, server_default="manual")
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class ServiceDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_service_dependencies_customer_site_sites",
            ondelete="RESTRICT",
        ),
        CheckConstraint("source_service_id <> target_service_id", name="not_self_referential"),
        Index(
            "uq_service_dependencies_active_edge",
            "source_service_id", "target_service_id", "relationship_type_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    source_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    relationship_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    required_for_operation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    description: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class DependencyGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A temporal semantic set over existing Service dependency rows."""

    __tablename__ = "dependency_groups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_dependency_groups_customer_site_sites",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "strategy IN ('all', 'any')", name="valid_strategy"
        ),
        CheckConstraint(
            "requirement IN ('required', 'optional')", name="valid_requirement"
        ),
        CheckConstraint(
            "failure_effect IN ('unavailable', 'degraded', 'unknown')",
            name="valid_failure_effect",
        ),
        Index(
            "uq_dependency_groups_active_name",
            "service_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supersedes_group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dependency_groups.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    requirement: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_effect: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unknown"
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class DependencyGroupMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Temporal membership linking a semantic group to one dependency kind."""

    __tablename__ = "dependency_group_memberships"
    __table_args__ = (
        CheckConstraint(
            "(service_asset_dependency_id IS NOT NULL) <> "
            "(service_dependency_id IS NOT NULL)",
            name="exactly_one_dependency",
        ),
        Index(
            "uq_dependency_group_memberships_active_asset_dependency",
            "service_asset_dependency_id",
            unique=True,
            postgresql_where=text(
                "valid_to IS NULL AND service_asset_dependency_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_dependency_group_memberships_active_service_dependency",
            "service_dependency_id",
            unique=True,
            postgresql_where=text(
                "valid_to IS NULL AND service_dependency_id IS NOT NULL"
            ),
        ),
    )

    dependency_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dependency_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    service_asset_dependency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_asset_dependencies.id", ondelete="RESTRICT"), index=True
    )
    service_dependency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_dependencies.id", ondelete="RESTRICT"), index=True
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class BusinessFunction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "business_functions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_business_functions_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index("uq_business_functions_customer_name_without_site", "customer_id", text("lower(name)"), unique=True, postgresql_where=text("site_id IS NULL AND deleted_at IS NULL")),
        Index("uq_business_functions_customer_site_name", "customer_id", "site_id", text("lower(name)"), unique=True, postgresql_where=text("site_id IS NOT NULL AND deleted_at IS NULL")),
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_name: Mapped[str | None] = mapped_column(String(255))
    criticality_level_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("criticality_levels.id", ondelete="RESTRICT"), index=True
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class ServiceBusinessFunction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_business_functions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_service_business_functions_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_service_business_functions_active_link",
            "service_id", "business_function_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_function_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business_functions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    relationship_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("relationship_types.id", ondelete="RESTRICT"), index=True
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    importance: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class Integration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integrations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_integrations_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    username_or_token_id: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    verify_tls: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending", index=True
    )


class DataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('manual', 'simulated_discovery', 'proxmox', 'pbs', "
            "'docker', 'unifi', 'netbox', 'imported_file', 'generated_inference')",
            name="valid_source_type",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_data_sources_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="active", index=True
    )
    trust_level: Mapped[str | None] = mapped_column(String(50))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class EntitySourceLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entity_source_links"
    __table_args__ = (
        CheckConstraint("entity_type IN ('asset')", name="valid_entity_type"),
        UniqueConstraint(
            "data_source_id",
            "entity_type",
            "external_id",
            name="uq_entity_source_links_source_type_external",
        ),
        ForeignKeyConstraint(
            ["entity_id", "customer_id", "site_id"],
            ["assets.id", "assets.customer_id", "assets.site_id"],
            name="fk_entity_source_links_asset_context",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_entity_source_links_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    external_type: Mapped[str | None] = mapped_column(String(100), index=True)
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class DiscoveryRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discovery_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="valid_status",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial', 'failed', 'unknown')",
            name="valid_completeness_status",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_discovery_runs_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integrations.id", ondelete="RESTRICT"), index=True
    )
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending", index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Retained for compatibility with the existing plugin synchronization path.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    archive_reason: Mapped[str | None] = mapped_column(Text)
    coverage_key: Mapped[str | None] = mapped_column(String(1024), index=True)
    is_complete_snapshot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    completeness_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="unknown", index=True
    )


class RunObservedEntity(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "run_observed_entities"
    __table_args__ = (
        UniqueConstraint(
            "discovery_run_id",
            "entity_type",
            "external_id",
            name="uq_run_observed_entities_run_type_external",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_run_observed_entities_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    discovery_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    coverage_key: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="SET NULL"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_evidence_records_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    discovery_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    external_id: Mapped[str | None] = mapped_column(String(1024), index=True)
    entity_kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeAssertion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_assertions"
    __table_args__ = (
        CheckConstraint(
            "truth_classification IN ('observed', 'declared', 'intended', 'inferred')",
            name="valid_truth_classification",
        ),
        CheckConstraint(
            "confirmation_status IN ('unreviewed', 'confirmed', 'rejected', "
            "'superseded', 'conflicted')",
            name="valid_confirmation_status",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="valid_confidence"),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_knowledge_assertions_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_knowledge_assertions_single_accepted",
            "subject_type",
            "subject_id",
            "predicate",
            unique=True,
            postgresql_where=text(
                "is_accepted = true AND retracted_at IS NULL "
                "AND subject_id IS NOT NULL AND predicate IN "
                "('name', 'hostname', 'asset_type', 'status', "
                "'operational_state', 'observation_state', 'platform', "
                "'lifecycle_state')"
            ),
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    subject_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    subject_external_id: Mapped[str | None] = mapped_column(String(1024), index=True)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value_json: Mapped[Any | None] = mapped_column(JSONB)
    object_type: Mapped[str | None] = mapped_column(String(100), index=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    object_external_id: Mapped[str | None] = mapped_column(String(1024), index=True)
    truth_classification: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )
    confirmation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="unreviewed", index=True
    )
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), index=True
    )
    discovery_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="SET NULL"), index=True
    )
    evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="SET NULL"), index=True
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, server_default="1.0"
    )
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_assertions.id", ondelete="SET NULL"), index=True
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    # ``is_current`` remains a compatibility mirror of ``is_source_current``.
    # It never means that Atlas has accepted this assertion as canonical truth.
    is_source_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    is_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    retracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    retracted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    retraction_reason: Mapped[str | None] = mapped_column(Text)


class ReconciliationItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_items"
    __table_args__ = (
        CheckConstraint(
            "category IN ('newly_discovered', 'changed', 'no_longer_observed', "
            "'contradiction', 'possible_duplicate', 'missing_classification', "
            "'inferred_relationship', 'stale_human_knowledge')",
            name="valid_category",
        ),
        CheckConstraint(
            "status IN ('open', 'accepted', 'rejected', 'deferred', 'exception')",
            name="valid_status",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_reconciliation_items_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="open", index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    candidate_external_id: Mapped[str | None] = mapped_column(String(1024), index=True)
    assertion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_assertions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    current_value_json: Mapped[Any | None] = mapped_column(JSONB)
    observed_value_json: Mapped[Any | None] = mapped_column(JSONB)
    recommended_action: Mapped[str | None] = mapped_column(String(255))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeChange(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_changes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_knowledge_changes_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_knowledge_changes_customer_site_occurred",
            "customer_id",
            "site_id",
            "occurred_at",
        ),
        Index(
            "ix_knowledge_changes_entity_occurred",
            "entity_type",
            "entity_id",
            "occurred_at",
        ),
        Index(
            "ix_knowledge_changes_type_occurred",
            "change_type",
            "occurred_at",
        ),
        Index(
            "ix_knowledge_changes_source_run",
            "data_source_id",
            "discovery_run_id",
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    entity_name_snapshot: Mapped[str] = mapped_column(String(1024), nullable=False)
    predicate: Mapped[str | None] = mapped_column(String(255), index=True)
    previous_value_json: Mapped[Any | None] = mapped_column(JSONB)
    new_value_json: Mapped[Any | None] = mapped_column(JSONB)
    truth_classification: Mapped[str | None] = mapped_column(String(30), index=True)
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), index=True
    )
    discovery_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="SET NULL"), index=True
    )
    assertion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_assertions.id", ondelete="SET NULL"), index=True
    )
    reconciliation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reconciliation_items.id", ondelete="SET NULL"), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeRequirementDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_requirement_definitions"
    __table_args__ = (
        CheckConstraint("entity_type IN ('asset', 'service')", name="supported_entity_type"),
        CheckConstraint(
            "requirement_level IN ('required', 'conditional', 'recommended')",
            name="valid_requirement_level",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name="valid_severity",
        ),
    )

    key: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="asset", index=True
    )
    asset_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("asset_types.id", ondelete="RESTRICT"), index=True
    )
    service_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_types.id", ondelete="RESTRICT"), index=True
    )
    requirement_level: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    rule_config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    system_defined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100"
    )
    remediation_hint: Mapped[str | None] = mapped_column(Text)
    configuration_valid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    configuration_error: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class KnowledgeGap(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_gaps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'deferred', 'exception', 'resolved', 'superseded')",
            name="valid_status",
        ),
        CheckConstraint(
            "requirement_level IN ('required', 'conditional', 'recommended')",
            name="valid_requirement_level",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name="valid_severity",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_knowledge_gaps_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_knowledge_gaps_active_requirement_entity",
            "requirement_definition_id",
            "entity_type",
            "entity_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'deferred', 'exception')"),
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    requirement_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_requirement_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    asset_type_id_snapshot: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("asset_types.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="open", index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    requirement_level: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    resolution_reason: Mapped[str | None] = mapped_column(Text)
    exception_reason: Mapped[str | None] = mapped_column(Text)
    exception_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exception_created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    exception_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deferred_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deferred_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class KnowledgeCompletenessSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_completeness_summaries"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_completeness_entity"),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_completeness_summaries_customer_site_sites",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "completeness_status IN ('not_evaluated', 'complete', "
            "'operationally_complete', 'incomplete', 'critical_gaps', "
            "'exception_accepted')",
            name="valid_completeness_status",
        ),
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    required_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    required_satisfied: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    recommended_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    recommended_satisfied: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    critical_gap_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    high_gap_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    open_gap_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    exception_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completeness_status: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="not_evaluated", index=True
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "source_integration_id",
            "external_id",
            name="uq_assets_source_external_id",
        ),
        UniqueConstraint(
            "id", "customer_id", "site_id", name="uq_assets_id_customer_site"
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_assets_customer_site_sites",
            ondelete="RESTRICT",
        ),
        Index("ix_assets_customer_type", "customer_id", "asset_type"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    source_integration_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integrations.id", ondelete="SET NULL"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(1024))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("asset_types.key", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    icon_url: Mapped[str | None] = mapped_column(String(2048))
    vendor: Mapped[str | None] = mapped_column(String(100), index=True)
    model: Mapped[str | None] = mapped_column(String(255))
    hostname: Mapped[str | None] = mapped_column(String(255), index=True)
    # Deprecated compatibility storage; current IPs belong to AssetInterface.
    ip_address: Mapped[str | None] = mapped_column(String(45), index=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="active", index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="manual", index=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )


class AssetIconCache(Base):
    """Disposable bounded image bytes; never part of accepted Asset knowledge."""
    __tablename__ = "asset_icon_cache"
    __table_args__ = (
        CheckConstraint("octet_length(data) <= 524288", name="bounded_icon_data"),
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[bytes | None] = mapped_column(LargeBinary)
    attempted_source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retry_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AssetRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "relationship_type",
            name="uq_asset_relationships_edge_type",
        ),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_asset_relationships_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("relationship_types.key", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    legacy_cross_context: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class Network(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "networks"
    __table_args__ = (
        UniqueConstraint("customer_id", "site_id", "name", name="uq_networks_customer_site_name"),
        ForeignKeyConstraint(
            ["customer_id", "site_id"],
            ["sites.customer_id", "sites.id"],
            name="fk_networks_customer_site_sites",
            ondelete="RESTRICT",
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    network_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vlan_id: Mapped[int | None] = mapped_column(Integer)
    cidr: Mapped[str | None] = mapped_column(String(49), index=True)
    gateway: Mapped[str | None] = mapped_column(String(45))
    purpose: Mapped[str | None] = mapped_column(String(255))
    zone: Mapped[str | None] = mapped_column(String(100), index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class AssetInterface(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_interfaces"
    __table_args__ = (
        UniqueConstraint("asset_id", "name", name="uq_asset_interfaces_asset_name"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    network_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("networks.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), index=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), index=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)


class AssetFact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_facts"
    __table_args__ = (
        UniqueConstraint("asset_id", "key", "source", name="uq_asset_facts_key_source"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)


class CustomFieldDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (
        CheckConstraint(
            "data_type IN ('text', 'multiline_text', 'number', 'date', "
            "'boolean', 'url', 'dropdown')",
            name="valid_data_type",
        ),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    help_text: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", index=True
    )
    applies_to_all_asset_types: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )


class CustomFieldAssetType(Base):
    __tablename__ = "custom_field_asset_types"

    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_type_key: Mapped[str] = mapped_column(
        ForeignKey("asset_types.key", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CustomFieldOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "custom_field_options"
    __table_args__ = (
        UniqueConstraint(
            "field_definition_id", "value", name="uq_custom_field_options_value"
        ),
        UniqueConstraint(
            "field_definition_id",
            "id",
            name="uq_custom_field_options_definition_id_id",
        ),
    )

    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )


class AssetCustomFieldValue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_custom_field_values"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "field_definition_id",
            name="uq_asset_custom_field_values_asset_definition",
        ),
        CheckConstraint(
            "num_nonnulls(value_text, value_number, value_date, value_bool, "
            "value_option_id) = 1",
            name="exactly_one_typed_value",
        ),
        ForeignKeyConstraint(
            ["field_definition_id", "value_option_id"],
            ["custom_field_options.field_definition_id", "custom_field_options.id"],
            name="fk_asset_custom_field_values_definition_option",
            ondelete="RESTRICT",
        ),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    value_date: Mapped[date | None] = mapped_column(Date)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    value_option_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    generated_from_discovery_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="SET NULL"), index=True
    )


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), index=True)
    actor_display_name: Mapped[str | None] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), index=True
    )
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    summary: Mapped[str | None] = mapped_column(Text)
    source_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    @property
    def actor_snapshot(self) -> str | None:
        if self.actor_display_name and self.actor_email:
            return f"{self.actor_display_name} <{self.actor_email}>"
        return self.actor_display_name or self.actor_email

    @property
    def change_summary(self) -> str | None:
        return self.summary


class SystemSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    value_: Mapped[Any] = mapped_column("value", JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sensitive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
