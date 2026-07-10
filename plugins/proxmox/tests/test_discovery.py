import asyncio
import uuid

import httpx
import pytest

from atlas_plugin_sdk import ConnectionConfig, DiscoveryError, DiscoveryPlugin
from atlas_proxmox import ProxmoxPlugin

TOKEN_SECRET = "00000000-1111-2222-3333-444444444444"


def config() -> ConnectionConfig:
    return ConnectionConfig(
        integration_id=uuid.uuid4(),
        base_url="https://pve.example.test:8006",
        credentials={
            "token_id": "atlas@pve!discovery",
            "token_secret": TOKEN_SECRET,
        },
    )


RESPONSES = {
    "/api2/json/nodes": [
        {"node": "pve-01", "status": "online", "maxcpu": 16},
        {"node": "pve-02", "status": "online", "maxcpu": 8},
    ],
    "/api2/json/nodes/pve-01/qemu": [
        {"vmid": 100, "name": "dc-01", "status": "running", "maxmem": 4096},
    ],
    "/api2/json/nodes/pve-01/lxc": [
        {"vmid": 200, "name": "proxy-01", "status": "running"},
    ],
    "/api2/json/nodes/pve-01/storage": [
        {"storage": "shared-zfs", "type": "zfspool", "total": 1000, "used": 400},
    ],
    "/api2/json/nodes/pve-01/network": [
        {"iface": "vmbr0", "type": "bridge", "bridge_ports": "eno1", "active": 1},
        {"iface": "eno1", "type": "eth", "active": 1},
    ],
    "/api2/json/nodes/pve-02/qemu": [],
    "/api2/json/nodes/pve-02/lxc": [],
    "/api2/json/nodes/pve-02/storage": [
        {"storage": "shared-zfs", "type": "zfspool", "total": 1000, "used": 400},
    ],
    "/api2/json/nodes/pve-02/network": [
        {"iface": "vmbr0", "type": "bridge", "bridge_ports": "eno1", "active": 1},
    ],
}


def handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"].endswith(TOKEN_SECRET)
    return httpx.Response(200, json={"data": RESPONSES[request.url.path]})


def test_plugin_implements_full_discovery_contract() -> None:
    assert isinstance(ProxmoxPlugin(), DiscoveryPlugin)


def test_discovers_raw_resources_and_normalizes_assets() -> None:
    plugin = ProxmoxPlugin(transport=httpx.MockTransport(handler))
    discovery = asyncio.run(plugin.discover(config()))

    assert len(discovery.items) == 8
    assert discovery.metadata == {
        "plugin_id": "proxmox",
        "node_count": 2,
        "item_count": 8,
    }
    assert discovery.raw_payload == {
        "nodes": RESPONSES["/api2/json/nodes"],
        "resources_by_node": {
            "pve-01": {
                "qemu": RESPONSES["/api2/json/nodes/pve-01/qemu"],
                "lxc": RESPONSES["/api2/json/nodes/pve-01/lxc"],
                "storage": RESPONSES["/api2/json/nodes/pve-01/storage"],
                "network": RESPONSES["/api2/json/nodes/pve-01/network"],
            },
            "pve-02": {
                "qemu": [],
                "lxc": [],
                "storage": RESPONSES["/api2/json/nodes/pve-02/storage"],
                "network": RESPONSES["/api2/json/nodes/pve-02/network"],
            },
        },
    }
    assert not any(item.external_id.endswith("eno1") for item in discovery.items)

    normalized = plugin.normalize(discovery)
    assets = {asset.external_id: asset for asset in normalized.assets}
    assert set(assets) == {
        "node/pve-01",
        "node/pve-02",
        "qemu/100",
        "lxc/200",
        "storage/shared-zfs",
        "bridge/pve-01/vmbr0",
        "bridge/pve-02/vmbr0",
    }
    assert assets["qemu/100"].asset_type == "virtual_machine"
    assert assets["lxc/200"].asset_type == "container"
    assert assets["storage/shared-zfs"].metadata["nodes"] == ["pve-01", "pve-02"]
    assert len(normalized.relationships) == 6
    relationships = {
        (item.source_external_id, item.target_external_id, item.relationship_type)
        for item in normalized.relationships
    }
    assert ("qemu/100", "node/pve-01", "runs_on") in relationships
    assert ("node/pve-02", "storage/shared-zfs", "uses_storage") in relationships
    assert ("bridge/pve-01/vmbr0", "node/pve-01", "connected_to") in relationships


def test_http_errors_are_sanitized_as_discovery_errors() -> None:
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": TOKEN_SECRET})

    plugin = ProxmoxPlugin(transport=httpx.MockTransport(failing_handler))
    with pytest.raises(DiscoveryError) as exc_info:
        asyncio.run(plugin.discover(config()))
    assert "HTTP 403" in str(exc_info.value)
    assert TOKEN_SECRET not in str(exc_info.value)


def test_missing_required_vendor_identity_fails_normalization() -> None:
    broken = dict(RESPONSES)
    broken["/api2/json/nodes"] = [{"status": "online"}]

    def broken_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": broken[request.url.path]})

    plugin = ProxmoxPlugin(transport=httpx.MockTransport(broken_handler))
    with pytest.raises(DiscoveryError):
        asyncio.run(plugin.discover(config()))
