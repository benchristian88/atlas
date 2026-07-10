"""Public contracts for Atlas discovery plugins and synchronization backends."""

from .exceptions import (
    ConnectionValidationError,
    DiscoveryError,
    NormalizationError,
    PluginError,
    SyncError,
)
from .interfaces import (
    ConnectionValidator,
    Discoverer,
    DiscoveryPlugin,
    Normalizer,
    SyncBackend,
)
from .models import (
    ConnectionConfig,
    ConnectionValidation,
    DiscoveryResult,
    NormalizationResult,
    NormalizedAsset,
    NormalizedFact,
    NormalizedRelationship,
    RawDiscoveryItem,
    SyncContext,
    SyncResult,
)
from .types import JsonObject, JsonScalar, JsonValue

__all__ = [
    "ConnectionConfig",
    "ConnectionValidation",
    "ConnectionValidationError",
    "ConnectionValidator",
    "Discoverer",
    "DiscoveryError",
    "DiscoveryPlugin",
    "DiscoveryResult",
    "JsonObject",
    "JsonScalar",
    "JsonValue",
    "NormalizationError",
    "NormalizationResult",
    "NormalizedAsset",
    "NormalizedFact",
    "NormalizedRelationship",
    "Normalizer",
    "PluginError",
    "RawDiscoveryItem",
    "SyncBackend",
    "SyncContext",
    "SyncError",
    "SyncResult",
]
