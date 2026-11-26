"""Validate the bundled starter definitions independently of Atlas release metadata."""
from functools import lru_cache
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.entity_names import service_slug, trim_nonempty


FIXTURE = Path(__file__).resolve().parents[1] / "onboarding_data" / "homelab-v1.json"
SERVICE_TYPE_KEYS = {
    "Application": "application_service",
    "External": "external_service",
    "Infrastructure": "infrastructure_service",
    "Integration": "integration_service",
    "Platform": "platform_service",
    "Shared": "shared_service",
}
DEFAULT_CRITICALITY_KEY = "medium"
FUNCTION_COUNT = 8
SERVICE_COUNT = 42
STANDARD_COUNT = 24

FunctionID = Annotated[str, Field(max_length=80, pattern=r"^bf\.[a-z0-9]+(?:-[a-z0-9]+)*$")]
ServiceID = Annotated[str, Field(max_length=80, pattern=r"^svc\.[a-z0-9]+(?:-[a-z0-9]+)*$")]
AssociationID = Annotated[str, Field(max_length=160, pattern=r"^assoc\.[a-z0-9-]+\.[a-z0-9-]+$")]
CatalogueID = Literal["atlas.homelab.capabilities"]
ContentVersion = Annotated[str, Field(max_length=32, pattern=r"^\d+\.\d+\.\d+$")]


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=20000)
    preselected: bool
    sort_order: int = Field(ge=1)
    _name = field_validator("name")(trim_nonempty)


class ServiceDefinition(Definition):
    id: ServiceID
    selection_tier: Literal["standard", "extended"]
    service_type_name: str
    criticality_name: Literal["Medium"]
    business_function_id: FunctionID

    @model_validator(mode="after")
    def check_defaults(self):
        if self.preselected != (self.selection_tier == "standard"):
            raise ValueError("Only Standard Services are preselected")
        if self.service_type_name not in SERVICE_TYPE_KEYS:
            raise ValueError("Unknown starter Service Type")
        return self


class FunctionDefinition(Definition):
    id: FunctionID
    services: tuple[ServiceDefinition, ...] = Field(min_length=1, max_length=SERVICE_COUNT)

    @field_validator("name")
    @classmethod
    def ascii_name(cls, value: str) -> str:
        if not value.isascii():
            raise ValueError("Bundled Business Function names must contain only ASCII characters")
        return value


class Association(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    id: AssociationID
    business_function_id: FunctionID
    service_id: ServiceID


class Catalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1]
    catalogue_id: CatalogueID
    content_version: ContentVersion
    status: Literal["approved-content--proposed-wire-schema"]
    profile: Literal["homelab"]
    description: str
    functions: tuple[FunctionDefinition, ...] = Field(min_length=FUNCTION_COUNT, max_length=FUNCTION_COUNT)
    associations: tuple[Association, ...] = Field(min_length=SERVICE_COUNT, max_length=SERVICE_COUNT)

    @model_validator(mode="after")
    def check_catalogue(self):
        if len({function.id for function in self.functions}) != FUNCTION_COUNT:
            raise ValueError("Business Function IDs must be unique")
        if len({service.id for function in self.functions for service in function.services}) != SERVICE_COUNT:
            raise ValueError("Expected 42 distinct Service IDs")

        expected_links = []
        standard_count = 0
        functions_by_name = {}
        services_by_slug = {}
        for order, function in enumerate(self.functions, 1):
            if function.sort_order != order or function.preselected != any(s.preselected for s in function.services):
                raise ValueError("Business Function order or default is invalid")
            # Names have been trimmed and constrained to ASCII for offline comparison.
            name_key = function.name.lower()
            if name_key in functions_by_name:
                raise ValueError(f"Duplicate Business Function name for {functions_by_name[name_key]} and {function.id}")
            functions_by_name[name_key] = function.id
            for service_order, service in enumerate(function.services, 1):
                if service.business_function_id != function.id or service.sort_order != service_order:
                    raise ValueError("Service order or Business Function endpoint is invalid")
                slug = service_slug(service.name)
                if slug in services_by_slug:
                    raise ValueError(f"Duplicate generated Service slug for {services_by_slug[slug]} and {service.id}")
                services_by_slug[slug] = service.id
                link_id = f"assoc.{function.id.removeprefix('bf.')}.{service.id.removeprefix('svc.')}"
                expected_links.append((link_id, function.id, service.id))
                standard_count += service.preselected
        if standard_count != STANDARD_COUNT:
            raise ValueError("Expected 24 Standard Services")
        actual_links = [(link.id, link.business_function_id, link.service_id) for link in self.associations]
        if actual_links != expected_links:
            raise ValueError("Starter associations must use the approved endpoints, identity and order")
        return self

    @property
    def versions(self) -> dict:
        return {
            "catalogue_id": self.catalogue_id,
            "schema_version": self.schema_version,
            "content_version": self.content_version,
        }


def validate_catalogue(raw: bytes) -> Catalogue:
    def unique_pairs(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate field in starter catalogue")
        return result

    # JSON-mode validation retains strict types while decoding arrays as tuples.
    json.loads(raw, object_pairs_hook=unique_pairs)
    return Catalogue.model_validate_json(raw)


@lru_cache(maxsize=1)
def load_catalogue() -> Catalogue:
    return validate_catalogue(FIXTURE.read_bytes())
