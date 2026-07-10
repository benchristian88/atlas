import asyncio

import httpx

from atlas_plugin_sdk import (
    ConnectionConfig,
    DiscoveryError,
    DiscoveryResult,
    RawDiscoveryItem,
)

from .client import ProxmoxApiClient, ProxmoxConfigurationError

RESOURCE_COLLECTIONS = ("qemu", "lxc", "storage", "network")


def _required_text(payload: dict, field: str, resource: str) -> str:
    value = payload.get(field)
    if value is None or not str(value).strip():
        raise DiscoveryError(f"Proxmox {resource} response is missing {field}")
    return str(value)


class ProxmoxDiscoverer:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    async def discover(self, config: ConnectionConfig) -> DiscoveryResult:
        try:
            client = ProxmoxApiClient(
                config,
                transport=self._transport,
                timeout_seconds=self._timeout_seconds,
            )
            nodes = await client.list_nodes()
            node_names = [
                _required_text(node, "node", "node") for node in nodes
            ]
            requests = [
                client.list_node_resource(node_name, collection)
                for node_name in node_names
                for collection in RESOURCE_COLLECTIONS
            ]
            responses = await asyncio.gather(*requests)
        except DiscoveryError:
            raise
        except ProxmoxConfigurationError as exc:
            raise DiscoveryError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise DiscoveryError(
                f"Proxmox discovery endpoint returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise DiscoveryError("Proxmox discovery timed out") from exc
        except httpx.RequestError as exc:
            raise DiscoveryError("Could not connect to Proxmox during discovery") from exc
        except (TypeError, ValueError) as exc:
            raise DiscoveryError("Proxmox returned an unexpected discovery response") from exc

        by_node: dict[str, dict[str, list[dict]]] = {}
        response_index = 0
        for node_name in node_names:
            by_node[node_name] = {}
            for collection in RESOURCE_COLLECTIONS:
                by_node[node_name][collection] = responses[response_index]
                response_index += 1

        items: list[RawDiscoveryItem] = []
        for node in nodes:
            node_name = str(node["node"])
            items.append(RawDiscoveryItem(f"node/{node_name}", "node", node))
            for vm in by_node[node_name]["qemu"]:
                vmid = _required_text(vm, "vmid", "QEMU VM")
                items.append(
                    RawDiscoveryItem(
                        f"qemu/{vmid}",
                        "qemu",
                        {**vm, "node": node_name},
                    )
                )
            for container in by_node[node_name]["lxc"]:
                vmid = _required_text(container, "vmid", "LXC container")
                items.append(
                    RawDiscoveryItem(
                        f"lxc/{vmid}",
                        "lxc",
                        {**container, "node": node_name},
                    )
                )
            for storage in by_node[node_name]["storage"]:
                storage_id = _required_text(storage, "storage", "storage")
                items.append(
                    RawDiscoveryItem(
                        f"storage/{node_name}/{storage_id}",
                        "storage",
                        {**storage, "node": node_name},
                    )
                )
            for network in by_node[node_name]["network"]:
                if network.get("type") != "bridge":
                    continue
                interface = _required_text(network, "iface", "network bridge")
                items.append(
                    RawDiscoveryItem(
                        f"bridge/{node_name}/{interface}",
                        "bridge",
                        {**network, "node": node_name},
                    )
                )

        raw_payload = {
            "nodes": nodes,
            "resources_by_node": by_node,
        }
        return DiscoveryResult(
            items=tuple(items),
            raw_payload=raw_payload,
            metadata={
                "plugin_id": "proxmox",
                "node_count": len(nodes),
                "item_count": len(items),
            },
        )
