from __future__ import annotations

import ipaddress
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.taxonomy import NETWORK_TYPES


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


def _validate_icon_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Icon URL must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("Icon URL must not contain credentials")
    if parsed.path.lower().endswith(".svg"):
        raise ValueError("Remote SVG icons are not supported")
    return value


def _trim_nonempty(value: str | None) -> str:
    if value is None:
        raise ValueError("Value must not be null")
    value = value.strip()
    if not value:
        raise ValueError("Value must not be blank")
    return value


def _normalize_accent_colour(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("Accent colour must be a six-digit hexadecimal colour")
    return value.upper()


def _validate_optional_http_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("URL must not contain credentials")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class AccessAssignmentInput(BaseModel):
    role_id: uuid.UUID
    scope_type: Literal["global", "customer", "site"]
    customer_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def valid_scope(self):
        if self.scope_type == "global" and (
            self.customer_id is not None or self.site_id is not None
        ):
            raise ValueError("Global assignments cannot specify a customer or site")
        if self.scope_type == "customer" and (
            self.customer_id is None or self.site_id is not None
        ):
            raise ValueError("Customer assignments require a customer and no site")
        if self.scope_type == "site" and (
            self.customer_id is None or self.site_id is None
        ):
            raise ValueError("Site assignments require both customer and site")
        return self


class AccessAssignmentResponse(ORMResponse):
    id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    scope_type: str
    customer_id: uuid.UUID | None
    site_id: uuid.UUID | None
    permissions: list[str] = Field(default_factory=list)


class UserResponse(ORMResponse):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    accent_colour: str | None
    is_active: bool
    force_password_change: bool
    last_login_at: datetime | None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    assignments: list[AccessAssignmentResponse] = Field(default_factory=list)


class UserAdminResponse(UserResponse):
    failed_login_count: int
    locked_until: datetime | None
    auth_provider: str
    mfa_enabled: bool
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    user: UserResponse


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=255)
    accent_colour: str | None = None

    _display_name = field_validator("display_name")(_trim_nonempty)
    _accent_colour = field_validator("accent_colour")(_normalize_accent_colour)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)
    new_password_confirmation: str = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.new_password_confirmation:
            raise ValueError("New password confirmation does not match")
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current password")
        return self


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    temporary_password: str = Field(min_length=12, max_length=1024)
    force_password_change: bool = True
    assignments: list[AccessAssignmentInput] = Field(min_length=1)

    _display_name = field_validator("display_name")(_trim_nonempty)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    force_password_change: bool | None = None
    assignments: list[AccessAssignmentInput] | None = None

    _display_name = field_validator("display_name")(_trim_nonempty)


class AdminPasswordResetRequest(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=1024)
    force_password_change: bool = True


class PermissionResponse(ORMResponse):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    category: str | None = None
    system_defined: bool


class RoleResponse(ORMResponse):
    id: uuid.UUID
    name: str
    description: str | None
    system_defined: bool
    active: bool
    sort_order: int
    permissions: list[PermissionResponse] = Field(default_factory=list)


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    permission_keys: list[str] = Field(default_factory=list)
    active: bool = True
    sort_order: int = Field(default=100, ge=0)

    _name = field_validator("name")(_trim_nonempty)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    permission_keys: list[str] | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)

    _name = field_validator("name")(_trim_nonempty)


class CustomerCreate(BaseModel):
    workspace_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    status: Literal["active", "inactive"] = "active"

    _name = field_validator("name")(_trim_nonempty)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    status: Literal["active", "inactive"] | None = None

    _name = field_validator("name")(_trim_nonempty)


class CustomerResponse(ORMResponse):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class SiteCreate(BaseModel):
    customer_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=10000)
    status: Literal["active", "inactive"] = "active"

    _name = field_validator("name")(_trim_nonempty)


class SiteUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=10000)
    status: Literal["active", "inactive"] | None = None

    _name = field_validator("name")(_trim_nonempty)


class SiteResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    address: str | None
    notes: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ManualAssetCreate(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    asset_type: str = Field(min_length=1, max_length=100)
    icon_url: str | None = Field(default=None, max_length=2048)
    vendor: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    status: str = Field(default="active", min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    _icon = field_validator("icon_url")(_validate_icon_url)
    _name = field_validator("name")(_trim_nonempty)


class ManualAssetUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_type: str | None = Field(default=None, min_length=1, max_length=100)
    icon_url: str | None = Field(default=None, max_length=2048)
    vendor: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=10000)
    metadata: dict[str, Any] | None = None
    custom_fields: dict[str, Any] | None = None

    _icon = field_validator("icon_url")(_validate_icon_url)
    _name = field_validator("name")(_trim_nonempty)


class ManualAssetResponse(ORMResponse):
    id: uuid.UUID
    workspace_id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID
    name: str
    asset_type: str
    icon_url: str | None
    resolved_icon_url: str | None = None
    vendor: str | None
    model: str | None
    hostname: str | None
    ip_address: str | None
    status: str
    description: str | None
    source: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    completeness_status: str = "not_evaluated"
    open_knowledge_gap_count: int = 0
    critical_knowledge_gap_count: int = 0
    created_at: datetime
    updated_at: datetime


class AssetTypeCountResponse(BaseModel):
    asset_type_id: uuid.UUID
    asset_type_name: str
    count: int


class AssetSummaryResponse(BaseModel):
    total: int
    by_asset_type: list[AssetTypeCountResponse]


class AssetRelationshipCreate(BaseModel):
    source_asset_id: uuid.UUID
    target_asset_id: uuid.UUID
    relationship_type: str = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=10000)


class AssetRelationshipUpdate(BaseModel):
    relationship_type: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=10000)


class AssetRelationshipResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID
    source_asset_id: uuid.UUID
    target_asset_id: uuid.UUID
    relationship_type: str
    legacy_cross_context: bool
    notes: str | None
    source_asset_name: str | None = None
    target_asset_name: str | None = None
    created_at: datetime
    updated_at: datetime


class NetworkCreate(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    network_type: str = Field(min_length=1, max_length=50)
    vlan_id: int | None = Field(default=None, ge=0, le=4094)
    cidr: str | None = Field(default=None, max_length=49)
    gateway: str | None = Field(default=None, max_length=45)
    purpose: str | None = Field(default=None, max_length=255)
    zone: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=10000)

    _name = field_validator("name")(_trim_nonempty)

    @field_validator("network_type")
    @classmethod
    def validate_network_type(cls, value: str | None) -> str | None:
        if value is not None and value not in NETWORK_TYPES:
            raise ValueError("network_type must be a supported Atlas network type")
        return value

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str | None) -> str | None:
        return str(ipaddress.ip_network(value, strict=False)) if value else None

    @field_validator("gateway")
    @classmethod
    def validate_gateway(cls, value: str | None) -> str | None:
        return str(ipaddress.ip_address(value)) if value else None


class NetworkUpdate(NetworkCreate):
    customer_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    network_type: str | None = None


class NetworkResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    name: str
    network_type: str
    vlan_id: int | None
    cidr: str | None
    gateway: str | None
    purpose: str | None
    zone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AssetInterfaceCreate(BaseModel):
    asset_id: uuid.UUID
    network_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)
    mac_address: str | None = Field(default=None, max_length=17)
    is_primary: bool = False
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        return str(ipaddress.ip_address(value)) if value else None


class AssetInterfaceUpdate(BaseModel):
    network_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)
    mac_address: str | None = Field(default=None, max_length=17)
    is_primary: bool | None = None
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        return str(ipaddress.ip_address(value)) if value else None


class AssetInterfaceResponse(ORMResponse):
    id: uuid.UUID
    asset_id: uuid.UUID
    network_id: uuid.UUID | None
    name: str
    ip_address: str | None
    mac_address: str | None
    is_primary: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AssetTypeCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    default_icon_url: str | None = Field(default=None, max_length=2048)
    active: bool = True
    sort_order: int = Field(default=100, ge=0)

    _icon = field_validator("default_icon_url")(_validate_icon_url)
    _name = field_validator("name")(_trim_nonempty)


class AssetTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    default_icon_url: str | None = Field(default=None, max_length=2048)
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)

    _icon = field_validator("default_icon_url")(_validate_icon_url)
    _name = field_validator("name")(_trim_nonempty)


class AssetTypeResponse(ORMResponse):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    category: str | None
    default_icon_url: str | None
    system_defined: bool
    active: bool
    sort_order: int
    in_use_count: int = 0
    created_at: datetime
    updated_at: datetime


class RelationshipTypeApplicabilityInput(BaseModel):
    source_entity_type: Literal["asset", "service", "business_function"]
    target_entity_type: Literal["asset", "service", "business_function"]
    active: bool = True


class RelationshipTypeApplicabilityResponse(ORMResponse):
    id: uuid.UUID
    relationship_type_id: uuid.UUID
    source_entity_type: str
    target_entity_type: str
    active: bool
    created_at: datetime
    updated_at: datetime


class RelationshipTypeCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    source_label: str = Field(min_length=1, max_length=100)
    target_label: str = Field(min_length=1, max_length=100)
    inverse_label: str | None = Field(default=None, max_length=100)
    directional: bool = True
    active: bool = True
    sort_order: int = Field(default=100, ge=0)
    allowed_source_asset_type_keys: list[str] = Field(default_factory=list)
    allowed_target_asset_type_keys: list[str] = Field(default_factory=list)
    applicability: list[RelationshipTypeApplicabilityInput] = Field(default_factory=list)

    _name = field_validator("name")(_trim_nonempty)
    _labels = field_validator("source_label", "target_label")(_trim_nonempty)


class RelationshipTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    source_label: str | None = Field(default=None, min_length=1, max_length=100)
    target_label: str | None = Field(default=None, min_length=1, max_length=100)
    inverse_label: str | None = Field(default=None, max_length=100)
    directional: bool | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    allowed_source_asset_type_keys: list[str] | None = None
    allowed_target_asset_type_keys: list[str] | None = None
    applicability: list[RelationshipTypeApplicabilityInput] | None = None

    _name = field_validator("name")(_trim_nonempty)
    _labels = field_validator("source_label", "target_label")(_trim_nonempty)


class RelationshipTypeResponse(ORMResponse):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    source_label: str
    target_label: str
    inverse_label: str | None
    directional: bool
    system_defined: bool
    active: bool
    sort_order: int
    allowed_source_asset_type_keys: list[str]
    allowed_target_asset_type_keys: list[str]
    applicability: list[RelationshipTypeApplicabilityResponse] = Field(default_factory=list)
    in_use_count: int = 0
    created_at: datetime
    updated_at: datetime


FieldDataType = Literal[
    "text", "multiline_text", "number", "date", "boolean", "url", "dropdown"
]


class CustomFieldOptionInput(BaseModel):
    value: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=255)
    active: bool = True
    sort_order: int = Field(default=100, ge=0)

    _value_and_label = field_validator("value", "label")(_trim_nonempty)


class CustomFieldOptionResponse(ORMResponse):
    id: uuid.UUID
    field_definition_id: uuid.UUID
    value: str
    label: str
    active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class CustomFieldDefinitionCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    help_text: str | None = Field(default=None, max_length=2000)
    data_type: FieldDataType
    required: bool = False
    active: bool = True
    sort_order: int = Field(default=100, ge=0)
    applies_to_all_asset_types: bool = True
    asset_type_keys: list[str] = Field(default_factory=list)
    options: list[CustomFieldOptionInput] = Field(default_factory=list)

    _name = field_validator("name")(_trim_nonempty)


class CustomFieldDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    help_text: str | None = Field(default=None, max_length=2000)
    data_type: FieldDataType | None = None
    required: bool | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    applies_to_all_asset_types: bool | None = None
    asset_type_keys: list[str] | None = None
    options: list[CustomFieldOptionInput] | None = None

    _name = field_validator("name")(_trim_nonempty)


class CustomFieldDefinitionResponse(ORMResponse):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    help_text: str | None
    data_type: str
    required: bool
    active: bool
    sort_order: int
    applies_to_all_asset_types: bool
    asset_type_keys: list[str] = Field(default_factory=list)
    options: list[CustomFieldOptionResponse] = Field(default_factory=list)
    in_use_count: int = 0
    created_at: datetime
    updated_at: datetime


class AssetCustomFieldsUpdate(BaseModel):
    values: dict[str, Any]


class AssetCustomFieldValueResponse(BaseModel):
    definition_id: uuid.UUID
    key: str
    name: str
    data_type: str
    active: bool
    value: str | Decimal | date | bool | None


class ContextCustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str


class ContextSiteResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    status: str


class ContextResponse(BaseModel):
    customers: list[ContextCustomerResponse]
    sites: list[ContextSiteResponse]
    global_access: bool


class DashboardSummaryResponse(BaseModel):
    customers: int
    sites: int
    assets: int
    networks: int
    relationships: int
    reconciliation: int
    open_reconciliation_count: int
    newly_discovered_count: int
    changed_count: int
    no_longer_observed_count: int
    contradiction_count: int
    possible_duplicate_count: int
    oldest_open_item_at: datetime | None
    knowledge_changes_last_7_days: int
    open_knowledge_gap_count: int
    critical_knowledge_gap_count: int
    high_knowledge_gap_count: int
    assets_with_critical_gaps: int
    assets_not_evaluated: int
    assets_operationally_complete: int
    expired_exception_count: int
    services: int = 0
    business_functions: int = 0
    services_with_critical_gaps: int = 0
    critical_services: int = 0
    services_with_required_gaps: int = 0
    services_missing_recovery_targets: int = 0
    services_missing_dependencies: int = 0


class AuditEventResponse(ORMResponse):
    id: uuid.UUID
    workspace_id: uuid.UUID | None
    user_id: uuid.UUID | None
    actor_snapshot: str | None
    event_type: str
    target_type: str
    target_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    site_id: uuid.UUID | None
    success: bool
    change_summary: str | None
    source_ip: str | None
    request_id: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    created_at: datetime


class SystemSettingResponse(ORMResponse):
    id: uuid.UUID
    key: str
    value: Any = Field(validation_alias="value_")
    description: str | None
    sensitive: bool
    updated_at: datetime


class SystemSettingUpdate(BaseModel):
    value: Any


DataSourceType = Literal[
    "manual",
    "simulated_discovery",
    "proxmox",
    "pbs",
    "docker",
    "unifi",
    "netbox",
    "imported_file",
    "generated_inference",
]
DiscoveryRunStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
TruthClassification = Literal["observed", "declared", "intended", "inferred"]
ConfirmationStatus = Literal[
    "unreviewed", "confirmed", "rejected", "superseded", "conflicted"
]
ReconciliationCategory = Literal[
    "newly_discovered",
    "changed",
    "no_longer_observed",
    "contradiction",
    "possible_duplicate",
    "missing_classification",
    "inferred_relationship",
    "stale_human_knowledge",
]
ReconciliationStatus = Literal["open", "accepted", "rejected", "deferred", "exception"]
ResolutionStatus = Literal[
    "resolved_existing",
    "resolved_link",
    "resolved_same_run",
    "pending_asset_acceptance",
    "possible_duplicate",
    "unresolved",
]


class DataSourceCreate(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    source_type: DataSourceType
    status: str = Field(default="active", min_length=1, max_length=50)
    trust_level: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=10000)

    _name = field_validator("name")(_trim_nonempty)


class DataSourceResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    name: str
    source_type: str
    status: str
    trust_level: str | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DiscoveryRunResponse(ORMResponse):
    id: uuid.UUID
    integration_id: uuid.UUID | None
    data_source_id: uuid.UUID | None
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    summary: dict[str, Any] | None
    error_message: str | None
    created_by_user_id: uuid.UUID | None
    archived_at: datetime | None
    archived_by_user_id: uuid.UUID | None
    archive_reason: str | None
    coverage_key: str | None
    is_complete_snapshot: bool
    completeness_status: str
    source_name: str | None = None
    deletion_safety: "DeletionSafetyResponse | None" = None
    created_at: datetime
    updated_at: datetime


class LifecycleReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=10000)

    _reason = field_validator("reason")(_trim_nonempty)


class AssertionRetractionRequest(LifecycleReasonRequest):
    confirm_provenance_gap: bool = False


class DeletionSafetyResponse(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    identifiers: dict[str, str | None] = Field(default_factory=dict)
    recommended_alternative: str | None = None


class SimulationInterface(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)
    mac_address: str | None = Field(default=None, max_length=17)
    network_name: str | None = Field(default=None, max_length=255)
    is_primary: bool = False

    _name = field_validator("name")(_trim_nonempty)

    @field_validator("ip_address")
    @classmethod
    def valid_ip(cls, value: str | None) -> str | None:
        return str(ipaddress.ip_address(value)) if value else None


class SimulationRelationship(BaseModel):
    relationship_type: str = Field(min_length=1, max_length=100)
    target_external_id: str = Field(min_length=1, max_length=1024)

    _relationship_type = field_validator("relationship_type")(_trim_nonempty)
    _target = field_validator("target_external_id")(_trim_nonempty)


class SimulationObservation(BaseModel):
    external_id: str | None = Field(default=None, max_length=1024)
    entity_kind: Literal[
        "asset", "asset_interface", "network", "relationship", "backup", "service"
    ] = "asset"
    asset_type: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    facts: dict[str, Any] = Field(default_factory=dict)
    interfaces: list[SimulationInterface] = Field(default_factory=list)
    relationships: list[SimulationRelationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def asset_identity(self):
        if self.entity_kind == "asset" and (not self.asset_type or not self.name):
            raise ValueError("Asset observations require asset_type and name")
        return self


class SimulatedDiscoveryRequest(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = None
    data_source_id: uuid.UUID | None = None
    coverage_key: str | None = Field(default=None, max_length=1024)
    is_complete_snapshot: bool = False
    observations: list[SimulationObservation] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_observed_identities(self):
        identities = [
            (item.entity_kind, item.external_id or f"simulated:{item.asset_type}:{item.name}")
            for item in self.observations
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("A discovery snapshot cannot contain duplicate external identities")
        return self


class KnowledgeAssertionResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    subject_type: str
    subject_id: uuid.UUID | None
    subject_external_id: str | None
    predicate: str
    value_json: Any | None
    object_type: str | None
    object_id: uuid.UUID | None
    object_external_id: str | None
    truth_classification: str
    confirmation_status: str
    data_source_id: uuid.UUID | None
    discovery_run_id: uuid.UUID | None
    evidence_record_id: uuid.UUID | None
    confidence: float
    first_observed_at: datetime
    last_observed_at: datetime
    valid_from: datetime | None
    valid_to: datetime | None
    superseded_by_id: uuid.UUID | None
    is_current: bool
    is_source_current: bool
    is_accepted: bool
    accepted_at: datetime | None
    accepted_by_user_id: uuid.UUID | None
    retracted_at: datetime | None
    retracted_by_user_id: uuid.UUID | None
    retraction_reason: str | None
    source_name: str | None = None
    deletion_safety: DeletionSafetyResponse | None = None
    provenance_gap_warning: bool = False
    created_at: datetime
    updated_at: datetime


class ReconciliationItemResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    category: str
    status: str
    entity_type: str
    entity_id: uuid.UUID | None
    candidate_external_id: str | None
    assertion_id: uuid.UUID
    current_value_json: Any | None
    observed_value_json: Any | None
    recommended_action: str | None
    decision_reason: str | None
    decided_by_user_id: uuid.UUID | None
    decided_at: datetime | None
    source_name: str | None = None
    source_external_id: str | None = None
    target_external_id: str | None = None
    resolved_source_asset_id: uuid.UUID | None = None
    resolved_target_asset_id: uuid.UUID | None = None
    resolved_source_name: str | None = None
    resolved_target_name: str | None = None
    source_resolution_status: ResolutionStatus | None = None
    target_resolution_status: ResolutionStatus | None = None
    blocked_reason: str | None = None
    current_relationship_id: uuid.UUID | None = None
    discovery_run_id: uuid.UUID | None = None
    discovery_run_status: str | None = None
    entity_name: str | None = None
    last_observed_at: datetime | None = None
    missing_since_run_id: uuid.UUID | None = None
    missing_since_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReconciliationDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=10000)
    disposition: Literal[
        "mark_missing",
        "mark_inactive",
        "mark_retired",
        "retire",
        "keep_active",
        "exception",
    ] | None = None
    exception_review_at: datetime | None = None


class ReconciliationSummaryResponse(BaseModel):
    by_status: dict[str, int]
    by_category: dict[str, int]
    actionable: int


class ReconciliationLinkAssetRequest(BaseModel):
    asset_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=10000)


class SimulatedDiscoveryResponse(BaseModel):
    run: DiscoveryRunResponse
    evidence_records_created: int
    assertions_created: int
    reconciliation_items_created: int
    reconciliation_items: list[ReconciliationItemResponse]
    baseline_run_id: uuid.UUID | None = None
    observed_count: int = 0
    new_count: int = 0
    changed_count: int = 0
    no_longer_observed_count: int = 0
    reobserved_count: int = 0


class KnowledgeChangeResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    change_type: str
    entity_type: str
    entity_id: uuid.UUID | None
    entity_name_snapshot: str
    entity_name: str = ""
    predicate: str | None
    previous_value_json: Any | None
    new_value_json: Any | None
    previous_value: Any | None = None
    new_value: Any | None = None
    truth_classification: str | None
    data_source_id: uuid.UUID | None
    discovery_run_id: uuid.UUID | None
    assertion_id: uuid.UUID | None
    reconciliation_item_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    summary: str
    occurred_at: datetime
    metadata_json: dict[str, Any] | None
    source_name: str | None = None
    discovery_run_status: str | None = None
    reconciliation_status: str | None = None
    actor_display_name: str | None = None
    attention_required: bool = False
    links: dict[str, str] = Field(default_factory=dict)
    created_at: datetime


class KnowledgeChangeListResponse(BaseModel):
    items: list[KnowledgeChangeResponse]
    total: int
    limit: int
    offset: int


class KnowledgeChangeSummaryResponse(BaseModel):
    total: int
    by_type: dict[str, int]
    last_24_hours: int
    last_7_days: int
    unresolved_attention_count: int


class AssetFactHistoryItem(BaseModel):
    predicate: str
    value: Any | None
    truth_classification: str | None
    source_name: str | None
    discovery_run_id: uuid.UUID | None
    assertion_id: uuid.UUID | None
    confirmation_status: str | None
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    is_current: bool
    is_source_current: bool
    is_accepted: bool
    retracted_at: datetime | None


class AssetFactHistoryResponse(BaseModel):
    asset_id: uuid.UUID
    facts: dict[str, list[AssetFactHistoryItem]]


class KnowledgeSummaryValue(BaseModel):
    assertion_id: uuid.UUID
    value: Any | None
    truth_classification: str
    confirmation_status: str
    source_id: uuid.UUID | None
    source_name: str | None
    first_observed_at: datetime
    last_observed_at: datetime
    accepted_at: datetime | None = None
    confirmed_at: datetime | None = None
    accepted_by_user_id: uuid.UUID | None = None
    accepted_by_name: str | None = None
    actor_name: str | None = None
    is_source_current: bool
    is_accepted: bool
    conflicts_with_accepted: bool = False


class KnowledgePredicateSummary(BaseModel):
    predicate: str
    label: str
    cardinality: Literal["single", "multi"]
    accepted: KnowledgeSummaryValue | None = None
    accepted_values: list[KnowledgeSummaryValue] = Field(default_factory=list)
    latest_observations: list[KnowledgeSummaryValue] = Field(default_factory=list)
    active_source_count: int
    source_count: int
    distinct_active_value_count: int
    assertion_count: int
    historical_count: int
    conflict: bool
    unresolved: bool
    last_observed_at: datetime | None
    freshness: Literal["current", "historical", "unknown"]


class AssetKnowledgeSummaryResponse(BaseModel):
    asset_id: uuid.UUID
    groups: list[KnowledgePredicateSummary]
    conflict_count: int
    unresolved_count: int


RequirementLevel = Literal["required", "conditional", "recommended"]
GapSeverity = Literal["critical", "high", "medium", "low"]
GapStatus = Literal["open", "deferred", "exception", "resolved", "superseded"]


class KnowledgeRequirementBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    entity_type: Literal["asset", "service"] = "asset"
    asset_type_id: uuid.UUID | None = None
    service_type_id: uuid.UUID | None = None
    requirement_level: RequirementLevel
    severity: GapSeverity
    rule_type: str = Field(min_length=1, max_length=80)
    rule_config_json: dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    sort_order: int = Field(default=100, ge=0)
    remediation_hint: str | None = Field(default=None, max_length=10000)

    _name = field_validator("name")(_trim_nonempty)


class KnowledgeRequirementCreate(KnowledgeRequirementBase):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,149}$")


class KnowledgeRequirementUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    requirement_level: RequirementLevel | None = None
    severity: GapSeverity | None = None
    rule_type: str | None = Field(default=None, min_length=1, max_length=80)
    rule_config_json: dict[str, Any] | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    remediation_hint: str | None = Field(default=None, max_length=10000)

    _name = field_validator("name")(_trim_nonempty)


class KnowledgeRequirementResponse(ORMResponse):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    entity_type: str
    asset_type_id: uuid.UUID | None
    asset_type_name: str | None = None
    service_type_id: uuid.UUID | None = None
    service_type_name: str | None = None
    requirement_level: str
    severity: str
    rule_type: str
    rule_config_json: dict[str, Any]
    rule_summary: str = ""
    active: bool
    system_defined: bool
    sort_order: int
    remediation_hint: str | None
    configuration_valid: bool
    configuration_error: str | None
    created_by_user_id: uuid.UUID | None
    updated_by_user_id: uuid.UUID | None
    affected_asset_count: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeRequirementValidationRequest(BaseModel):
    rule_type: str = Field(min_length=1, max_length=80)
    rule_config_json: dict[str, Any] = Field(default_factory=dict)


class KnowledgeRequirementValidationResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    interpretation: str


class KnowledgeGapResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    requirement_definition_id: uuid.UUID
    requirement_name: str | None = None
    remediation_hint: str | None = None
    entity_type: str
    entity_id: uuid.UUID
    entity_name: str | None = None
    asset_type_id_snapshot: uuid.UUID | None
    asset_type_name: str | None = None
    status: str
    severity: str
    requirement_level: str
    summary: str
    details_json: dict[str, Any] | None
    first_detected_at: datetime
    last_evaluated_at: datetime
    last_state_changed_at: datetime
    resolved_at: datetime | None
    resolved_by_user_id: uuid.UUID | None
    resolution_reason: str | None
    exception_reason: str | None
    exception_created_at: datetime | None
    exception_created_by_user_id: uuid.UUID | None
    exception_expires_at: datetime | None
    deferred_until: datetime | None
    deferred_by_user_id: uuid.UUID | None
    assigned_to_user_id: uuid.UUID | None
    assigned_to_name: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeCompletenessSummaryResponse(ORMResponse):
    entity_type: str
    entity_id: uuid.UUID
    required_total: int
    required_satisfied: int
    recommended_total: int
    recommended_satisfied: int
    critical_gap_count: int
    high_gap_count: int
    open_gap_count: int
    exception_count: int
    completeness_status: str
    last_evaluated_at: datetime | None


# C1 first-class Service contracts -------------------------------------------------

class ServiceTypeCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    icon_key: str | None = Field(default=None, max_length=100)
    active: bool = True
    sort_order: int = Field(default=100, ge=0)
    requires_asset_dependency: bool = True
    _name = field_validator("name")(_trim_nonempty)


class ServiceTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    icon_key: str | None = Field(default=None, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)
    requires_asset_dependency: bool | None = None
    active: bool | None = None
    _name = field_validator("name")(_trim_nonempty)


class ServiceTypeResponse(ORMResponse):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    icon_key: str | None
    active: bool
    system_defined: bool
    sort_order: int
    requires_asset_dependency: bool
    in_use_count: int = 0
    created_at: datetime
    updated_at: datetime


class CriticalityLevelCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    rank: int = Field(ge=0)
    default_rto_minutes: int | None = Field(default=None, ge=0)
    default_rpo_minutes: int | None = Field(default=None, ge=0)
    active: bool = True
    sort_order: int = Field(default=100, ge=0)
    _name = field_validator("name")(_trim_nonempty)


class CriticalityLevelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    rank: int | None = Field(default=None, ge=0)
    default_rto_minutes: int | None = Field(default=None, ge=0)
    default_rpo_minutes: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    active: bool | None = None
    _name = field_validator("name")(_trim_nonempty)


class CriticalityLevelResponse(ORMResponse):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    rank: int
    default_rto_minutes: int | None
    default_rpo_minutes: int | None
    active: bool
    system_defined: bool
    sort_order: int
    in_use_count: int = 0
    created_at: datetime
    updated_at: datetime


class ServiceBase(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    purpose: str | None = Field(default=None, max_length=20000)
    service_type_id: uuid.UUID
    criticality_level_id: uuid.UUID
    lifecycle_status: str = Field(default="active", min_length=1, max_length=50)
    operational_status: str = Field(default="unknown", min_length=1, max_length=50)
    owner_name: str | None = Field(default=None, max_length=255)
    technical_contact: str | None = Field(default=None, max_length=255)
    support_group: str | None = Field(default=None, max_length=255)
    documentation_url: str | None = Field(default=None, max_length=2048)
    runbook_url: str | None = Field(default=None, max_length=2048)
    rto_minutes: int | None = Field(default=None, ge=0)
    rpo_minutes: int | None = Field(default=None, ge=0)
    backup_notes: str | None = Field(default=None, max_length=20000)
    recovery_notes: str | None = Field(default=None, max_length=20000)
    notes: str | None = Field(default=None, max_length=20000)
    _name = field_validator("name")(_trim_nonempty)
    _urls = field_validator("documentation_url", "runbook_url")(_validate_optional_http_url)


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    site_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    purpose: str | None = Field(default=None, max_length=20000)
    service_type_id: uuid.UUID | None = None
    criticality_level_id: uuid.UUID | None = None
    lifecycle_status: str | None = Field(default=None, min_length=1, max_length=50)
    operational_status: str | None = Field(default=None, min_length=1, max_length=50)
    owner_name: str | None = Field(default=None, max_length=255)
    technical_contact: str | None = Field(default=None, max_length=255)
    support_group: str | None = Field(default=None, max_length=255)
    documentation_url: str | None = Field(default=None, max_length=2048)
    runbook_url: str | None = Field(default=None, max_length=2048)
    rto_minutes: int | None = Field(default=None, ge=0)
    rpo_minutes: int | None = Field(default=None, ge=0)
    backup_notes: str | None = Field(default=None, max_length=20000)
    recovery_notes: str | None = Field(default=None, max_length=20000)
    notes: str | None = Field(default=None, max_length=20000)
    _name = field_validator("name")(_trim_nonempty)
    _urls = field_validator("documentation_url", "runbook_url")(_validate_optional_http_url)


class ServiceResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    purpose: str | None
    service_type_id: uuid.UUID
    service_type_key: str | None = None
    service_type_name: str | None = None
    criticality_level_id: uuid.UUID
    criticality_key: str | None = None
    criticality_name: str | None = None
    criticality_rank: int | None = None
    suggested_rto_minutes: int | None = None
    suggested_rpo_minutes: int | None = None
    lifecycle_status: str
    operational_status: str
    owner_name: str | None
    technical_contact: str | None
    support_group: str | None
    documentation_url: str | None
    runbook_url: str | None
    rto_minutes: int | None
    rpo_minutes: int | None
    backup_notes: str | None
    recovery_notes: str | None
    notes: str | None
    source: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    asset_dependency_count: int = 0
    service_dependency_count: int = 0
    business_function_count: int = 0
    completeness_status: str = "not_evaluated"
    open_gap_count: int = 0
    required_gap_count: int = 0
    recommended_gap_count: int = 0


class ServiceSummaryResponse(BaseModel):
    total: int
    active: int
    archived: int
    critical: int
    high: int
    incomplete: int
    with_required_gaps: int
    missing_owner: int
    missing_dependencies: int
    missing_recovery_targets: int


class ServiceArchiveRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=10000)


class ServiceAssetDependencyCreate(BaseModel):
    asset_id: uuid.UUID
    relationship_type_id: uuid.UUID
    required_for_operation: bool = True
    description: str | None = Field(default=None, max_length=10000)


class ServiceAssetDependencyUpdate(BaseModel):
    relationship_type_id: uuid.UUID | None = None
    required_for_operation: bool | None = None
    description: str | None = Field(default=None, max_length=10000)


class ServiceAssetDependencyResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    service_id: uuid.UUID
    service_name: str | None = None
    asset_id: uuid.UUID
    asset_name: str | None = None
    asset_type: str | None = None
    relationship_type_id: uuid.UUID
    relationship_type_name: str | None = None
    source_label: str | None = None
    target_label: str | None = None
    required_for_operation: bool
    dependency_group_id: uuid.UUID | None = None
    dependency_group_name: str | None = None
    dependency_strategy: Literal["all", "any"] | None = None
    dependency_requirement: Literal["required", "optional"] = "required"
    failure_effect: Literal["unavailable", "degraded", "unknown"] = "unknown"
    description: str | None
    source: str
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime
    updated_at: datetime


class ServiceDependencyCreate(BaseModel):
    target_service_id: uuid.UUID
    relationship_type_id: uuid.UUID
    required_for_operation: bool = True
    description: str | None = Field(default=None, max_length=10000)


class ServiceDependencyUpdate(BaseModel):
    relationship_type_id: uuid.UUID | None = None
    required_for_operation: bool | None = None
    description: str | None = Field(default=None, max_length=10000)


class ServiceDependencyResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    source_service_id: uuid.UUID
    source_service_name: str | None = None
    target_service_id: uuid.UUID
    target_service_name: str | None = None
    relationship_type_id: uuid.UUID
    relationship_type_name: str | None = None
    source_label: str | None = None
    target_label: str | None = None
    required_for_operation: bool
    dependency_group_id: uuid.UUID | None = None
    dependency_group_name: str | None = None
    dependency_strategy: Literal["all", "any"] | None = None
    dependency_requirement: Literal["required", "optional"] = "required"
    failure_effect: Literal["unavailable", "degraded", "unknown"] = "unknown"
    description: str | None
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime
    updated_at: datetime


class DependencyGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    strategy: Literal["all", "any"] = "all"
    requirement: Literal["required", "optional"] = "required"
    failure_effect: Literal["unavailable", "degraded", "unknown"] = "unknown"
    asset_dependency_ids: list[uuid.UUID] = Field(default_factory=list)
    service_dependency_ids: list[uuid.UUID] = Field(default_factory=list)
    _name = field_validator("name")(_trim_nonempty)

    @model_validator(mode="after")
    def validate_members(self):
        if not self.asset_dependency_ids and not self.service_dependency_ids:
            raise ValueError("A dependency group must contain at least one dependency")
        if len(set(self.asset_dependency_ids)) != len(self.asset_dependency_ids):
            raise ValueError("Asset dependency membership cannot be duplicated")
        if len(set(self.service_dependency_ids)) != len(self.service_dependency_ids):
            raise ValueError("Service dependency membership cannot be duplicated")
        return self


class DependencyGroupCreate(DependencyGroupBase):
    pass


class DependencyGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    strategy: Literal["all", "any"] | None = None
    requirement: Literal["required", "optional"] | None = None
    failure_effect: Literal["unavailable", "degraded", "unknown"] | None = None
    asset_dependency_ids: list[uuid.UUID] | None = None
    service_dependency_ids: list[uuid.UUID] | None = None
    _name = field_validator("name")(_trim_nonempty)

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        if not self.model_fields_set:
            raise ValueError("At least one dependency group field must be changed")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class DependencyGroupResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    service_id: uuid.UUID
    supersedes_group_id: uuid.UUID | None
    name: str
    strategy: Literal["all", "any"]
    requirement: Literal["required", "optional"]
    failure_effect: Literal["unavailable", "degraded", "unknown"]
    asset_dependency_ids: list[uuid.UUID] = Field(default_factory=list)
    service_dependency_ids: list[uuid.UUID] = Field(default_factory=list)
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime
    updated_at: datetime


class BusinessFunctionCreate(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    owner_name: str | None = Field(default=None, max_length=255)
    criticality_level_id: uuid.UUID | None = None
    active: bool = True
    _name = field_validator("name")(_trim_nonempty)


class BusinessFunctionUpdate(BaseModel):
    site_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    owner_name: str | None = Field(default=None, max_length=255)
    criticality_level_id: uuid.UUID | None = None
    active: bool | None = None
    _name = field_validator("name")(_trim_nonempty)


class BusinessFunctionResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    name: str
    description: str | None
    owner_name: str | None
    criticality_level_id: uuid.UUID | None
    criticality_name: str | None = None
    active: bool
    service_count: int = 0
    open_gap_count: int = 0
    created_at: datetime
    updated_at: datetime


class ServiceBusinessFunctionCreate(BaseModel):
    business_function_id: uuid.UUID
    relationship_type_id: uuid.UUID | None = None
    is_primary: bool = False
    importance: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=10000)


class ServiceBusinessFunctionUpdate(BaseModel):
    relationship_type_id: uuid.UUID | None = None
    is_primary: bool | None = None
    importance: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=10000)


class ServiceBusinessFunctionResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    service_id: uuid.UUID
    service_name: str | None = None
    business_function_id: uuid.UUID
    business_function_name: str | None = None
    relationship_type_id: uuid.UUID | None
    relationship_type_name: str | None = None
    relationship_label: str = "Supports"
    is_primary: bool
    importance: str | None
    description: str | None
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime
    updated_at: datetime


class ServiceCompletenessResponse(BaseModel):
    service_id: uuid.UUID
    summary: KnowledgeCompletenessSummaryResponse
    active_gaps: list[KnowledgeGapResponse]
    resolved_gaps: list[KnowledgeGapResponse]


class ServiceGraphNode(BaseModel):
    id: uuid.UUID
    entity_type: Literal["service", "asset", "business_function"]
    name: str
    subtitle: str | None = None
    href: str


class ServiceGraphEdge(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    label: str
    edge_type: Literal["service_asset", "service_service", "service_business_function", "asset_asset"]


class ServiceGraphResponse(BaseModel):
    nodes: list[ServiceGraphNode]
    edges: list[ServiceGraphEdge]


class OperationalGraphNode(BaseModel):
    key: str
    entity_type: Literal["asset", "service", "business_function"]
    entity_id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    name: str
    subtitle: str | None = None
    href: str
    lifecycle_state: str | None = None
    operational_state: str | None = None
    criticality_key: str | None = None
    criticality_name: str | None = None
    completeness_status: str | None = None
    open_gap_count: int | None = None
    source: str | None = None
    updated_at: datetime | None = None
    site_name: str | None = None
    criticality_rank: int | None = None
    required_total: int | None = None
    required_satisfied: int | None = None
    contextual_ip: str | None = None
    contextual_vlan: int | None = None


class OperationalGraphEdge(BaseModel):
    key: str
    edge_family: Literal[
        "asset_relationship",
        "service_asset",
        "service_service",
        "service_business_function",
    ]
    edge_id: uuid.UUID
    source_key: str
    target_key: str
    relationship_type_key: str | None = None
    relationship_type_name: str | None = None
    label: str
    required_for_operation: bool | None = None
    dependency_group_id: uuid.UUID | None = None
    dependency_group_name: str | None = None
    dependency_strategy: Literal["all", "any"] | None = None
    dependency_requirement: Literal["required", "optional"] | None = None
    failure_effect: Literal["unavailable", "degraded", "unknown"] | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source: str | None = None
    knowledge_state: Literal["accepted"] = "accepted"


class OperationalGraphResponse(BaseModel):
    focus_key: str
    generated_at: datetime
    requested_depth: int
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    nodes: list[OperationalGraphNode] = Field(default_factory=list)
    edges: list[OperationalGraphEdge] = Field(default_factory=list)


class AssetCompletenessResponse(BaseModel):
    asset_id: uuid.UUID
    summary: KnowledgeCompletenessSummaryResponse
    active_gaps: list[KnowledgeGapResponse]
    resolved_gaps: list[KnowledgeGapResponse]


class GapSummaryResponse(BaseModel):
    open_knowledge_gap_count: int
    critical_knowledge_gap_count: int
    high_knowledge_gap_count: int
    assets_with_critical_gaps: int
    assets_not_evaluated: int
    assets_operationally_complete: int
    expired_exception_count: int


class GapDeferRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=10000)
    deferred_until: datetime

    _reason = field_validator("reason")(_trim_nonempty)


class GapExceptionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=10000)
    expires_at: datetime | None = None

    _reason = field_validator("reason")(_trim_nonempty)


class GapReopenRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=10000)


class GapAssignRequest(BaseModel):
    user_id: uuid.UUID | None


class CompletenessBatchRequest(BaseModel):
    asset_type_id: uuid.UUID | None = None
    limit: int = Field(default=100, ge=1, le=500)


class TopologyResponse(BaseModel):
    customers: list[CustomerResponse]
    sites: list[SiteResponse]
    assets: list[ManualAssetResponse]
    relationships: list[AssetRelationshipResponse]
    networks: list[NetworkResponse]
    asset_interfaces: list[AssetInterfaceResponse]
