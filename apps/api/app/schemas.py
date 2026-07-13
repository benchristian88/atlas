import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class TopologyResponse(BaseModel):
    customers: list[CustomerResponse]
    sites: list[SiteResponse]
    assets: list[ManualAssetResponse]
    relationships: list[AssetRelationshipResponse]
