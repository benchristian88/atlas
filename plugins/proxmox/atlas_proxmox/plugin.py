import httpx

from atlas_plugin_sdk import (
    ConnectionConfig,
    ConnectionValidation,
    DiscoveryResult,
    NormalizationResult,
)

from .connection import ProxmoxConnectionValidator
from .discovery import ProxmoxDiscoverer
from .normalization import ProxmoxNormalizer


class ProxmoxPlugin:
    plugin_id = "proxmox"

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._validator = ProxmoxConnectionValidator(
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        self._discoverer = ProxmoxDiscoverer(
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
        self._normalizer = ProxmoxNormalizer()

    async def validate_connection(
        self, config: ConnectionConfig
    ) -> ConnectionValidation:
        return await self._validator.validate_connection(config)

    async def discover(self, config: ConnectionConfig) -> DiscoveryResult:
        return await self._discoverer.discover(config)

    def normalize(self, discovery: DiscoveryResult) -> NormalizationResult:
        return self._normalizer.normalize(discovery)
