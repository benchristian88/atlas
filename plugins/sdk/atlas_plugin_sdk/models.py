import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .types import JsonObject, JsonValue


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Vendor-neutral integration settings passed to a plugin.

    Credentials are excluded from repr so routine logs cannot expose them.
    Plugins must not place secrets in ``settings`` or result details.
    """

    integration_id: uuid.UUID
    base_url: str
    credentials: Mapping[str, str] = field(repr=False)
    verify_tls: bool = True
    settings: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConnectionValidation:
    valid: bool
    message: str | None = None
    details: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawDiscoveryItem:
    """One vendor object exactly as observed by a plugin."""

    external_id: str
    resource_type: str
    payload: JsonObject


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Raw discovery output retained separately from normalized assets."""

    items: tuple[RawDiscoveryItem, ...]
    raw_payload: JsonValue | None = None
    observed_at: datetime = field(default_factory=utc_now)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedFact:
    key: str
    value: JsonValue
    source: str


@dataclass(frozen=True, slots=True)
class NormalizedAsset:
    external_id: str
    name: str
    asset_type: str
    vendor: str
    status: str = "active"
    description: str | None = None
    metadata: JsonObject = field(default_factory=dict)
    facts: tuple[NormalizedFact, ...] = ()


@dataclass(frozen=True, slots=True)
class NormalizedRelationship:
    source_external_id: str
    target_external_id: str
    relationship_type: str
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    assets: tuple[NormalizedAsset, ...]
    relationships: tuple[NormalizedRelationship, ...] = ()


@dataclass(frozen=True, slots=True)
class SyncContext:
    workspace_id: uuid.UUID
    customer_id: uuid.UUID
    integration_id: uuid.UUID
    discovery_run_id: uuid.UUID
    site_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SyncResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    relationships_upserted: int = 0
    facts_upserted: int = 0
    stale_marked: int = 0

    @property
    def assets_seen(self) -> int:
        return self.created + self.updated + self.unchanged
