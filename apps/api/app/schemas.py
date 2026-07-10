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
    user: UserResponse


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)


class CustomerResponse(ORMResponse):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class SiteCreate(BaseModel):
    customer_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=10000)


class SiteUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=10000)


class SiteResponse(ORMResponse):
    id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    address: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ManualAssetCreate(BaseModel):
    customer_id: uuid.UUID
    site_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    asset_type: str = Field(min_length=1, max_length=100)
    vendor: str | None = Field(default=None, max_length=100)
    status: str = Field(default="active", min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManualAssetUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_type: str | None = Field(default=None, min_length=1, max_length=100)
    vendor: str | None = Field(default=None, max_length=100)
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
    status: str
    description: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime
