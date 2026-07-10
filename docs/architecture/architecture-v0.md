# Atlas Architecture v0

## Overview

Atlas is composed of:

- Web UI
- API server
- Worker process
- PostgreSQL database
- Redis queue
- Plugin system
- Proxmox plugin

## Runtime Architecture

Browser
  -> Next.js Web UI
  -> FastAPI Backend
  -> PostgreSQL

FastAPI Backend
  -> Redis Queue
  -> Worker
  -> Plugin SDK
  -> Proxmox Plugin
  -> Proxmox API

## Main Components

### Web UI

The web UI allows users to:

- Log in.
- Manage customers.
- Manage sites.
- Add integrations.
- Trigger discovery runs.
- View assets.
- View documentation pages.

### API

The API owns:

- Authentication.
- Workspace/customer/site management.
- Asset management.
- Integration configuration.
- Discovery run creation.
- Documentation endpoints.

### Worker

The worker executes background jobs, including discovery runs.

Discovery should not run inside the web request lifecycle.

### Database

PostgreSQL stores:

- Users.
- Workspaces.
- Customers.
- Sites.
- Integrations.
- Discovery runs.
- Assets.
- Asset relationships.
- Asset facts.
- Documents.
- Audit events.

### Plugin System

Plugins are responsible for:

- Validating connections.
- Discovering raw vendor/system data.
- Normalizing data into Atlas assets.
- Returning relationships between assets.

### Proxmox Plugin

The Proxmox plugin is the first plugin.

It connects using API token authentication and discovers nodes, VMs, LXCs, storage, and network data.