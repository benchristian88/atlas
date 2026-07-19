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
    created_at: datetime
    updated_at: datetime


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
    source_name: str | None = None
    created_at: datetime
    updated_at: datetime


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
    observations: list[SimulationObservation] = Field(min_length=1, max_length=500)


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
    source_name: str | None = None
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
    created_at: datetime
    updated_at: datetime


class ReconciliationDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=10000)


class ReconciliationLinkAssetRequest(BaseModel):
    asset_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=10000)


class SimulatedDiscoveryResponse(BaseModel):
    run: DiscoveryRunResponse
    evidence_records_created: int
    assertions_created: int
    reconciliation_items_created: int
    reconciliation_items: list[ReconciliationItemResponse]


class TopologyResponse(BaseModel):
    customers: list[CustomerResponse]
    sites: list[SiteResponse]
    assets: list[ManualAssetResponse]
    relationships: list[AssetRelationshipResponse]
    networks: list[NetworkResponse]
    asset_interfaces: list[AssetInterfaceResponse]
