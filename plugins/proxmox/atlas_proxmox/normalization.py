from collections.abc import Iterable, Mapping

from atlas_plugin_sdk import (
    DiscoveryResult,
    NormalizationError,
    NormalizationResult,
    NormalizedAsset,
    NormalizedFact,
    NormalizedRelationship,
    RawDiscoveryItem,
)

FACT_SOURCE = "proxmox"


def _text(payload: Mapping, key: str, fallback: str | None = None) -> str | None:
    value = payload.get(key, fallback)
    return str(value) if value is not None and str(value).strip() else fallback


def _metadata(payload: Mapping, keys: Iterable[str]) -> dict:
    return {key: payload[key] for key in keys if payload.get(key) is not None}


def _facts(payload: Mapping, keys: Iterable[str]) -> tuple[NormalizedFact, ...]:
    return tuple(
        NormalizedFact(key=key, value=payload[key], source=FACT_SOURCE)
        for key in keys
        if payload.get(key) is not None
    )


def _node_asset(item: RawDiscoveryItem) -> NormalizedAsset:
    payload = item.payload
    name = _text(payload, "node")
    if name is None:
        raise NormalizationError("Proxmox node is missing its name")
    return NormalizedAsset(
        external_id=item.external_id,
        name=name,
        asset_type="hypervisor_node",
        vendor="Proxmox",
        metadata=_metadata(payload, ("status", "level", "ssl_fingerprint")),
        facts=_facts(payload, ("status", "cpu", "maxcpu", "mem", "maxmem", "uptime")),
    )


def _guest_asset(item: RawDiscoveryItem, asset_type: str) -> NormalizedAsset:
    payload = item.payload
    vmid = _text(payload, "vmid")
    node = _text(payload, "node")
    if vmid is None or node is None:
        raise NormalizationError("Proxmox guest is missing vmid or node")
    return NormalizedAsset(
        external_id=item.external_id,
        name=_text(payload, "name", f"{asset_type}-{vmid}"),
        asset_type=asset_type,
        vendor="Proxmox",
        description=_text(payload, "description"),
        metadata=_metadata(payload, ("node", "vmid", "template", "tags", "pool", "status")),
        facts=_facts(
            payload,
            ("status", "cpu", "cpus", "maxcpu", "mem", "maxmem", "disk", "maxdisk", "uptime"),
        ),
    )


def normalize(discovery: DiscoveryResult) -> NormalizationResult:
    assets: dict[str, NormalizedAsset] = {}
    relationships: dict[tuple[str, str, str], NormalizedRelationship] = {}
    storage_nodes: dict[str, set[str]] = {}
    storage_payloads: dict[str, Mapping] = {}

    for item in discovery.items:
        payload = item.payload
        if item.resource_type == "node":
            asset = _node_asset(item)
        elif item.resource_type in {"qemu", "lxc"}:
            asset = _guest_asset(
                item,
                "virtual_machine" if item.resource_type == "qemu" else "container",
            )
            node_id = f"node/{payload['node']}"
            relationship = NormalizedRelationship(
                source_external_id=asset.external_id,
                target_external_id=node_id,
                relationship_type="runs_on",
            )
            relationships[(asset.external_id, node_id, "runs_on")] = relationship
        elif item.resource_type == "storage":
            storage_id = _text(payload, "storage")
            node = _text(payload, "node")
            if storage_id is None or node is None:
                raise NormalizationError("Proxmox storage is missing storage or node")
            external_id = f"storage/{storage_id}"
            storage_nodes.setdefault(external_id, set()).add(node)
            storage_payloads.setdefault(external_id, payload)
            node_id = f"node/{node}"
            relationship = NormalizedRelationship(
                source_external_id=node_id,
                target_external_id=external_id,
                relationship_type="uses_storage",
            )
            relationships[(node_id, external_id, "uses_storage")] = relationship
            continue
        elif item.resource_type == "bridge":
            interface = _text(payload, "iface")
            node = _text(payload, "node")
            if interface is None or node is None:
                raise NormalizationError("Proxmox bridge is missing iface or node")
            asset = NormalizedAsset(
                external_id=item.external_id,
                name=interface,
                asset_type="network_bridge",
                vendor="Proxmox",
                metadata=_metadata(
                    payload,
                    ("node", "iface", "active", "autostart", "bridge_ports", "address", "cidr", "gateway"),
                ),
                facts=_facts(payload, ("active", "autostart", "method", "method6")),
            )
            node_id = f"node/{node}"
            relationship = NormalizedRelationship(
                source_external_id=asset.external_id,
                target_external_id=node_id,
                relationship_type="connected_to",
            )
            relationships[(asset.external_id, node_id, "connected_to")] = relationship
        else:
            continue
        if asset.external_id in assets:
            raise NormalizationError(
                f"Duplicate normalized asset identity: {asset.external_id}"
            )
        assets[asset.external_id] = asset

    for external_id, nodes in storage_nodes.items():
        payload = storage_payloads[external_id]
        storage_id = external_id.removeprefix("storage/")
        assets[external_id] = NormalizedAsset(
            external_id=external_id,
            name=storage_id,
            asset_type="storage_pool",
            vendor="Proxmox",
            metadata={
                **_metadata(payload, ("storage", "type", "content", "shared", "active", "enabled")),
                "nodes": sorted(nodes),
            },
            facts=_facts(payload, ("total", "used", "avail")),
        )

    missing_targets = {
        endpoint
        for relationship in relationships.values()
        for endpoint in (
            relationship.source_external_id,
            relationship.target_external_id,
        )
        if endpoint not in assets
    }
    if missing_targets:
        raise NormalizationError(
            "Relationships reference missing assets: " + ", ".join(sorted(missing_targets))
        )

    return NormalizationResult(
        assets=tuple(assets.values()),
        relationships=tuple(relationships.values()),
    )


class ProxmoxNormalizer:
    def normalize(self, discovery: DiscoveryResult) -> NormalizationResult:
        return normalize(discovery)
