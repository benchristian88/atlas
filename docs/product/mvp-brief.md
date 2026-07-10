# Atlas MVP Brief

## Purpose

Atlas is an infrastructure knowledge and documentation platform for MSPs and internal IT teams.

The MVP proves that Atlas can connect to a Proxmox environment, discover infrastructure, normalize the discovered data into a vendor-neutral asset model, and generate useful documentation views.

## MVP Goal

Build a working prototype that allows a user to:

1. Log in.
2. Create a workspace.
3. Create a customer.
4. Create a site.
5. Add a Proxmox integration.
6. Run a discovery job.
7. Import Proxmox nodes, VMs, LXCs, storage, and network bridges.
8. View discovered assets.
9. View relationships between assets.
10. Generate a basic documentation page for each asset.
11. See discovery history and errors.

## Non-Goals for MVP

The MVP will not include:

- Billing.
- Multi-MSP commercial tenancy.
- Fortinet, Check Point, Meraki, UniFi, Microsoft 365, or other plugins.
- Complex RBAC.
- AI-generated remediation.
- Full topology mapping.
- External customer portal.
- Production hardening beyond basic security hygiene.

## First Discovery Plugin

The first plugin is Proxmox.

It should use Proxmox API token authentication and support read-only discovery.

The plugin should discover:

- Proxmox nodes.
- QEMU virtual machines.
- LXC containers.
- Storage pools.
- Network bridges where available.
- Basic VM/container metadata.

## MVP Success Criteria

The MVP is successful when:

- Atlas can be deployed using Docker Compose.
- A user can log in.
- A Proxmox connection can be added.
- A discovery run can be triggered.
- Discovered systems appear in the asset inventory.
- Running discovery twice does not duplicate assets.
- Assets have a last-seen timestamp.
- Raw discovery data is retained for debugging.
- A readable documentation page is generated for each asset.