# Homelab Service MVP test plan

## Prerequisites

Run the current migration, sign in as a scoped Administrator, and select the
homelab customer/site. Confirm the Viewer role has read permissions but no C1
mutation permissions.

## Identity and Access example

1. Create Business Function **Identity and Access**.
2. Create Service **Authentik**, type **Application Service**, Criticality
   **High**, with purpose, owner/contact/support labels, RTO **4 hours**, RPO
   **24 hours**, and recovery notes.
3. Link Authentik to the Business Function.
4. Link the Authentik LXC Asset using **Runs on**. Add AdGuard, Nginx Proxy
   Manager, and PBS Asset dependencies with appropriate applicable types.
5. Create a **DNS** Infrastructure Service and link its AdGuard LXC Asset.
6. Add `Authentik depends on DNS`. If Atlas and Paperless Services exist, add
   their dependencies on Authentik.
7. Verify Authentik detail shows purpose, ownership, RTO/RPO, recovery notes,
   Assets, upstream/downstream Services, and Business Function.
8. Evaluate completeness. Fill a required field and verify its gap resolves;
   remove the supporting Asset dependency and verify the gap reopens.
9. Confirm assertions contain declared Service fields and relationships, and
   Changes contains meaningful create/edit/add/remove events.
10. Open both graph views. Confirm Function → Service → Asset context is
    navigable and the focused Service shows connected Services in direction.

## External Service example

1. Create **Cloudflare DNS** as an External Service with a purpose and owner.
2. Confirm the seeded profile does not require a local Asset dependency when
   the Service Type rule or a documented exception applies.
3. Confirm recommended documentation/recovery gaps remain visible without
   incorrectly marking the Service incomplete.

## API, scope, and lifecycle checks

1. Create/read/update/archive/restore a Service through `/api/services`.
2. Verify negative recovery durations and non-HTTP(S) URLs return validation
   errors.
3. Repeat a no-op patch and confirm it creates no duplicate history.
4. Reject self-dependency and endpoint-inapplicable Relationship Types; allow a
   legitimate two-Service cycle.
5. Remove Asset, Service, and Business Function links. Confirm active lists no
   longer contain them and `include_history=true` does.
6. Sign in as Viewer and confirm all mutation endpoints return `403` while list,
   detail, and graph remain readable in scope.
7. Use a user assigned to another customer and confirm direct IDs, graph,
   dependency targets, summaries, and gap filters do not disclose the homelab.
8. Leave Services and Business Functions pages idle and confirm the browser does
   not continuously poll.

## Regression and release validation

Run:

```bash
cd apps/api
pytest
alembic current
alembic heads

cd ../web
npm test
npm run build
```

Finally verify existing Assets, Asset relationships, Knowledge Graph lenses,
Discovery, Reconciliation, Changes, and Knowledge Gaps still load. The existing
Asset Type named Service must remain and no Asset may be converted into a
first-class Service automatically.
