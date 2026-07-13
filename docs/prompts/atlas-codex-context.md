# Atlas Codex Context

Atlas is an infrastructure knowledge and documentation platform for MSPs and internal IT teams.

The current goal is to complete the v0.1 MVP foundation.

## Current status

The repo has been scaffolded with:

- FastAPI API
- Next.js web app
- Python worker
- PostgreSQL
- Redis
- Docker Compose
- Proxmox plugin placeholder
- Basic demo site/scaffold
- GitHub repository
- Docker build workflow on a Proxmox Docker host

The intended workflow is:

1. Edit code locally on Mac using VS Code.
2. Commit and push to GitHub.
3. Pull on the Proxmox Docker host.
4. Build and run with Docker Compose.

## MVP target

The next milestone is the Atlas v0.1 Core Loop:

1. User can open web app.
2. User can log in.
3. User lands on protected dashboard.
4. User can create a workspace.
5. User can create a customer.
6. User can create a site.
7. User can create a manual asset.
8. Data persists in PostgreSQL.

Do not proceed to Proxmox discovery until this core loop works.

## Immediate priority

Authentication is expected but may not be fully implemented.

Audit and complete:

- backend user model
- password hashing
- login endpoint
- /auth/me endpoint
- seed admin command
- frontend login page
- frontend dashboard
- logout
- protected route behaviour
- README instructions

## Required auth behaviour

A fresh deployment should support this flow:

1. Admin user is created from environment variables:
   - ATLAS_ADMIN_EMAIL
   - ATLAS_ADMIN_PASSWORD
   - ATLAS_ADMIN_DISPLAY_NAME

2. Admin user can log in from the web UI.

3. Login returns a bearer token.

4. Frontend stores token for MVP use.

5. Dashboard calls /auth/me.

6. Visiting /dashboard while logged out redirects to /login.

7. Logout clears token and redirects to /login.

## Security constraints

- Never log passwords.
- Never return password hashes to frontend.
- Hash passwords securely.
- Do not commit .env.
- Do not display saved secrets.
- Keep .env.example complete but non-secret.

## Docker/deployment constraints

The repo should be runnable by a fresh clone:

```bash
git clone https://github.com/benchristian88/atlas.git
cd atlas
cp .env.example .env
nano .env
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d --build