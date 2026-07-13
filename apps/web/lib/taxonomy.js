export const ASSET_TYPES = [
  "firewall", "router", "switch", "access_point", "network", "vlan",
  "proxmox_cluster", "proxmox_host", "virtual_machine", "lxc_container",
  "docker_host", "docker_container", "application", "database",
  "storage_pool", "nas", "backup_target", "backup_job", "service",
  "physical_server", "proxy",
];

export const RELATIONSHIP_TYPES = [
  "contains", "hosts", "runs_on", "runs", "connects_to", "routes",
  "protects", "depends_on", "uses_storage", "backs_up_to", "monitors",
  "proxies", "authenticates", "exposes", "belongs_to_network", "uplinks_to",
  "member_of", "connected_via", "served_by", "protected_by",
  "replicates_to", "syncs_to",
];

export const NETWORK_TYPES = [
  "lan", "vlan", "wan", "vpn", "docker_bridge", "overlay", "storage",
  "management", "guest", "iot", "dmz",
];

export function taxonomyLabel(value) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
