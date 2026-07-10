from collections.abc import Mapping
from urllib.parse import quote

import httpx

from atlas_plugin_sdk import ConnectionConfig

NODES_PATH = "/api2/json/nodes"
DEFAULT_TIMEOUT_SECONDS = 10.0


class ProxmoxConfigurationError(ValueError):
    """Raised when connection settings are incomplete or unsafe."""


def api_token_header(credentials: Mapping[str, str]) -> str:
    """Build the Proxmox API-token Authorization header.

    The token identifier must use Proxmox's ``user@realm!token-name`` format.
    The returned value must never be logged.
    """

    token_id = credentials.get("token_id", "").strip()
    token_secret = credentials.get("token_secret", "").strip()
    if not token_id or not token_secret:
        raise ProxmoxConfigurationError(
            "API token ID and secret are required"
        )
    user_and_realm, separator, token_name = token_id.partition("!")
    user, realm_separator, realm = user_and_realm.partition("@")
    if (
        separator != "!"
        or realm_separator != "@"
        or not user
        or not realm
        or not token_name
        or any(character.isspace() for character in token_id)
        or "=" in token_id
    ):
        raise ProxmoxConfigurationError(
            "API token ID must use user@realm!token-name format"
        )
    return f"PVEAPIToken={token_id}={token_secret}"


def validated_base_url(value: str) -> str:
    try:
        url = httpx.URL(value.strip())
    except httpx.InvalidURL as exc:
        raise ProxmoxConfigurationError("Proxmox base URL is invalid") from exc
    if url.scheme != "https":
        raise ProxmoxConfigurationError("Proxmox base URL must use HTTPS")
    if not url.host:
        raise ProxmoxConfigurationError("Proxmox base URL must include a host")
    if url.path not in {"", "/"}:
        raise ProxmoxConfigurationError("Proxmox base URL cannot include a path")
    if url.userinfo or url.query or url.fragment:
        raise ProxmoxConfigurationError(
            "Proxmox base URL cannot include credentials, a query, or a fragment"
        )
    return str(url.copy_with(path="", query=None, fragment=None)).rstrip("/")


class ProxmoxApiClient:
    def __init__(
        self,
        config: ConnectionConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = validated_base_url(config.base_url)
        self._authorization = api_token_header(config.credentials)
        self._verify_tls = config.verify_tls
        self._transport = transport
        self._timeout = httpx.Timeout(timeout_seconds)

    async def get_collection(self, path: str) -> list[dict]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": self._authorization,
                "Accept": "application/json",
            },
            timeout=self._timeout,
            verify=self._verify_tls,
            transport=self._transport,
        ) as client:
            response = await client.get(path)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Proxmox returned an unexpected collection response")
        if not all(isinstance(node, dict) for node in payload["data"]):
            raise ValueError("Proxmox returned an unexpected collection entry")
        return payload["data"]

    async def list_nodes(self) -> list[dict]:
        return await self.get_collection(NODES_PATH)

    async def list_node_resource(self, node: str, resource: str) -> list[dict]:
        if resource not in {"qemu", "lxc", "storage", "network"}:
            raise ProxmoxConfigurationError("Unsupported Proxmox resource collection")
        encoded_node = quote(node, safe="")
        return await self.get_collection(
            f"/api2/json/nodes/{encoded_node}/{resource}"
        )
