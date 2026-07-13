import uuid
from datetime import datetime
from typing import Any

import ipaddress

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.taxonomy import NETWORK_TYPES


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerCreate(BaseModel):
    workspace_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    status: str = Field(default="active", min_length=1, max_length=50)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    status: str | None = Field(default=None, min_length=1, max_length=50)


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
    status: str = Field(default="active", min_length=1, max_length=50)


class SiteUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=10000)
    status: str | None = Field(default=None, min_length=1, max_length=50)


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
    site_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    asset_type: str = Field(min_length=1, max_length=100)
    vendor: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    status: str = Field(default="active", min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManualAssetUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_type: str | None = Field(default=None, min_length=1, max_length=100)
    vendor: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=10000)
    metadata: dict[str, Any] | None = None


class ManualAssetResponse(ORMResponse):
    id: uuid.UUID
    workspace_id: uuid.UUID
    customer_id: uuid.UUID
    site_id: uuid.UUID | None
    name: str
    asset_type: str
    vendor: str | None
    model: str | None
    hostname: str | None
    ip_address: str | None
    status: str
    description: str | None
    source: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime


class AssetRelationshipCreate(BaseModel):
    source_asset_id: uuid.UUID
    target_asset_id: uuid.UUID
    relationship_type: str = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=10000)


class AssetRelationshipResponse(ORMResponse):
    id: uuid.UUID
    source_asset_id: uuid.UUID
    target_asset_id: uuid.UUID
    relationship_type: str
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

    @field_validator("network_type")
    @classmethod
    def validate_network_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in NETWORK_TYPES:
            raise ValueError("network_type must be a supported Atlas network type")
        return value

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str | None) -> str | None:
        if not value:
            return None
        return str(ipaddress.ip_network(value, strict=False))

    @field_validator("gateway")
    @classmethod
    def validate_gateway(cls, value: str | None) -> str | None:
        if not value:
            return None
        return str(ipaddress.ip_address(value))


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
        if not value:
            return None
        return str(ipaddress.ip_address(value))


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
        if not value:
            return None
        return str(ipaddress.ip_address(value))


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


class TopologyResponse(BaseModel):
    customers: list[CustomerResponse]
    sites: list[SiteResponse]
    assets: list[ManualAssetResponse]
    relationships: list[AssetRelationshipResponse]
    networks: list[NetworkResponse]
    asset_interfaces: list[AssetInterfaceResponse]
