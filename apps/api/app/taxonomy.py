"""Suggested Atlas taxonomy values.

The database intentionally keeps these fields as strings so existing discovery
plugins and legacy rows remain compatible. API clients should prefer these
values while still being able to represent vendor-specific infrastructure.
"""

ASSET_TYPES = (
    "firewall", "router", "switch", "access_point", "network", "vlan",
    "proxmox_cluster", "proxmox_host", "virtual_machine", "lxc_container",
    "docker_host", "docker_container", "application", "database",
    "storage_pool", "nas", "backup_target", "backup_job", "service",
)

RELATIONSHIP_TYPES = (
    "contains", "hosts", "runs_on", "runs", "connects_to", "routes",
    "protects", "depends_on", "uses_storage", "backs_up_to", "monitors",
    "proxies", "authenticates", "exposes", "belongs_to_network",
)

NETWORK_TYPES = (
    "lan", "vlan", "wan", "vpn", "docker_bridge", "overlay", "storage",
    "management", "guest", "iot", "dmz",
)
