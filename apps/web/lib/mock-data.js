export const customers = [
  { id: "customer-1", name: "Harbour Legal", description: "Regional legal practice", sites: 2, assets: 18 },
  { id: "customer-2", name: "Northstar Manufacturing", description: "Industrial components", sites: 3, assets: 42 },
  { id: "customer-3", name: "Kauri Health", description: "Community healthcare provider", sites: 1, assets: 11 },
];

export const sites = [
  { id: "site-1", name: "Auckland Office", customer: "Harbour Legal", location: "Auckland", assets: 12 },
  { id: "site-2", name: "Hamilton Office", customer: "Harbour Legal", location: "Hamilton", assets: 6 },
  { id: "site-3", name: "Main Plant", customer: "Northstar Manufacturing", location: "Tauranga", assets: 31 },
  { id: "site-4", name: "Distribution Centre", customer: "Northstar Manufacturing", location: "Rotorua", assets: 11 },
  { id: "site-5", name: "Central Clinic", customer: "Kauri Health", location: "Wellington", assets: 11 },
];

export const assets = [
  { id: "asset-1", name: "pve-auckland-01", type: "Proxmox node", customer: "Harbour Legal", site: "Auckland Office", vendor: "Proxmox", status: "active", lastSeen: "10 Jul 2026, 16:14" },
  { id: "asset-2", name: "hl-dc-01", type: "Virtual machine", customer: "Harbour Legal", site: "Auckland Office", vendor: "Microsoft", status: "active", lastSeen: "10 Jul 2026, 16:14" },
  { id: "asset-3", name: "nsm-erp-01", type: "LXC container", customer: "Northstar Manufacturing", site: "Main Plant", vendor: "Proxmox", status: "active", lastSeen: "10 Jul 2026, 15:42" },
  { id: "asset-4", name: "local-zfs", type: "Storage pool", customer: "Northstar Manufacturing", site: "Main Plant", vendor: "ZFS", status: "active", lastSeen: "10 Jul 2026, 15:42" },
  { id: "asset-5", name: "pve-clinic-01", type: "Proxmox node", customer: "Kauri Health", site: "Central Clinic", vendor: "Proxmox", status: "stale", lastSeen: "8 Jul 2026, 09:20" },
];

export const integrations = [
  { id: "integration-1", name: "Auckland Proxmox", plugin: "Proxmox", customer: "Harbour Legal", site: "Auckland Office", endpoint: "https://pve-auckland.example.test:8006", status: "connected" },
  { id: "integration-2", name: "Plant Proxmox", plugin: "Proxmox", customer: "Northstar Manufacturing", site: "Main Plant", endpoint: "https://pve-plant.example.test:8006", status: "connected" },
  { id: "integration-3", name: "Clinic Proxmox", plugin: "Proxmox", customer: "Kauri Health", site: "Central Clinic", endpoint: "https://pve-clinic.example.test:8006", status: "warning" },
];

export const discoveryRuns = [
  { id: "run-1042", integration: "Auckland Proxmox", customer: "Harbour Legal", status: "completed", started: "10 Jul 2026, 16:14", duration: "18s", summary: "18 assets seen" },
  { id: "run-1041", integration: "Plant Proxmox", customer: "Northstar Manufacturing", status: "completed", started: "10 Jul 2026, 15:42", duration: "31s", summary: "42 assets seen" },
  { id: "run-1040", integration: "Clinic Proxmox", customer: "Kauri Health", status: "failed", started: "10 Jul 2026, 14:05", duration: "5s", summary: "Connection timed out" },
  { id: "run-1039", integration: "Auckland Proxmox", customer: "Harbour Legal", status: "completed", started: "9 Jul 2026, 16:10", duration: "20s", summary: "18 assets seen" },
];
