from typing import Protocol, runtime_checkable

from .models import (
    ConnectionConfig,
    ConnectionValidation,
    DiscoveryResult,
    NormalizationResult,
    SyncContext,
    SyncResult,
)


@runtime_checkable
class ConnectionValidator(Protocol):
    async def validate_connection(
        self, config: ConnectionConfig
    ) -> ConnectionValidation:
        """Confirm that configuration and credentials can reach the source."""
        ...


@runtime_checkable
class Discoverer(Protocol):
    async def discover(self, config: ConnectionConfig) -> DiscoveryResult:
        """Fetch raw vendor data without writing Atlas state."""
        ...


@runtime_checkable
class Normalizer(Protocol):
    def normalize(self, discovery: DiscoveryResult) -> NormalizationResult:
        """Convert raw data into vendor-neutral assets and relationships."""
        ...


@runtime_checkable
class DiscoveryPlugin(ConnectionValidator, Discoverer, Normalizer, Protocol):
    """Contract implemented by every Atlas discovery plugin."""

    plugin_id: str


@runtime_checkable
class SyncBackend(Protocol):
    async def sync(
        self, context: SyncContext, normalized: NormalizationResult
    ) -> SyncResult:
        """Idempotently upsert normalized data into Atlas-owned storage."""
        ...
