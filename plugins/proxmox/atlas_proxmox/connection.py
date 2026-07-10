import httpx

from atlas_plugin_sdk import ConnectionConfig, ConnectionValidation

from .client import ProxmoxApiClient, ProxmoxConfigurationError


class ProxmoxConnectionValidator:
    """Perform a read-only API-token connection and permission check."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    async def validate_connection(
        self, config: ConnectionConfig
    ) -> ConnectionValidation:
        try:
            nodes = await ProxmoxApiClient(
                config,
                transport=self._transport,
                timeout_seconds=self._timeout_seconds,
            ).list_nodes()
        except ProxmoxConfigurationError as exc:
            return ConnectionValidation(valid=False, message=str(exc))
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                message = "API token was rejected or lacks permission to list nodes"
            elif status_code == 404:
                message = "Proxmox API nodes endpoint was not found"
            else:
                message = "Proxmox API returned an unexpected HTTP status"
            return ConnectionValidation(
                valid=False,
                message=message,
                details={"status_code": status_code},
            )
        except httpx.TimeoutException:
            return ConnectionValidation(
                valid=False, message="Connection to Proxmox timed out"
            )
        except httpx.RequestError:
            return ConnectionValidation(
                valid=False, message="Could not connect to the Proxmox API"
            )
        except (ValueError, TypeError):
            return ConnectionValidation(
                valid=False, message="Proxmox returned an unexpected response"
            )

        return ConnectionValidation(
            valid=True,
            message="Connection successful",
            details={"node_count": len(nodes)},
        )


async def validate_connection(config: ConnectionConfig) -> ConnectionValidation:
    """Validate a Proxmox connection using the default HTTP transport."""

    return await ProxmoxConnectionValidator().validate_connection(config)
